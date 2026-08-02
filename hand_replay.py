"""Shared hand-state reconstruction for ClubWPT Gold hands.

Both output formats — PokerStars text (`converter.py`) and Open Hand History
JSON (`ohh_converter.py`) — need the same reconstruction of a hand: starting
stacks, forced bets, the real chip amount behind every action, the uncalled
bet, the rake and the winners. All of the API quirks documented in CLAUDE.md
are handled here exactly once, so the two renderers can never drift apart.

Everything in this module works in chips (cents), matching the API.
"""

from dataclasses import dataclass, field

DEFAULT_HERO_UID = "235160"


def _detect_hero_uid(hand: dict) -> str | None:
    """The hero's UID is embedded in table.session_id as '{table_id}|{seat}|{uid}|{date}'."""
    parts = hand.get('table', {}).get('session_id', '').split('|')
    return parts[2] if len(parts) >= 3 and parts[2] else None


def parse_cards(card_str: str) -> list[str]:
    """Parse a card string like '5c5s' into ['5c', '5s']."""
    if not card_str:
        return []
    cards = []
    i = 0
    while i < len(card_str):
        if i + 1 < len(card_str):
            cards.append(card_str[i:i+2])
            i += 2
        else:
            break
    return cards


def format_cards(cards: list[str]) -> str:
    """Format cards for display: ['5c', '5s'] -> '5c 5s'."""
    return ' '.join(cards)


# ClubWPT Gold rake structure for NLHE ring games.
# Source: https://support.clubwptgold.com/portal/en/kb/articles/rake
# Keyed by (small_blind, big_blind) in chips (cents, matching the API's
# table.small_blind / table.big_blind). Each entry is
# (rake_fraction, (cap_2p, cap_3_4p, cap_5plus)) with caps in chips.
RAKE_TABLE = {
    (1, 2):       (0.05, (10, 20, 40)),
    (5, 10):      (0.05, (30, 30, 60)),
    (10, 20):     (0.05, (60, 60, 120)),
    (20, 50):     (0.05, (100, 100, 200)),
    (50, 100):    (0.05, (200, 200, 400)),
    (100, 200):   (0.04, (300, 400, 600)),
    (200, 400):   (0.04, (300, 400, 700)),
    (500, 1000):  (0.04, (300, 600, 1000)),
    (2500, 5000): (0.04, (300, 600, 1500)),
}


def compute_rake(sb: int, bb: int, num_players: int, pot: int,
                 flop_dealt: bool) -> int:
    """Compute the rake (in chips) for a hand per the ClubWPT Gold structure.

    Rake is a percentage of the contested pot, capped by stake and by the
    number of players dealt into the hand. Two standard poker conventions
    not spelled out on the rake page are applied here:

    - "No flop, no rake": hands that end before a flop is dealt are not raked.
    - The rake is rounded to the nearest chip (cent), half rounding up.

    Returns 0 for stakes that are not in the published rake table.
    """
    if not flop_dealt or pot <= 0:
        return 0
    entry = RAKE_TABLE.get((sb, bb))
    if entry is None:
        return 0
    pct, caps = entry
    if num_players <= 2:
        cap = caps[0]
    elif num_players <= 4:
        cap = caps[1]
    else:
        cap = caps[2]
    rake = int(pot * pct + 0.5)  # round half up to nearest chip
    return min(rake, cap)


def _find_player_by_position(players: list[dict], position: str) -> dict | None:
    for p in players:
        if p['position'] == position:
            return p
    return None


def _find_straddle_player(players: list[dict]) -> dict | None:
    """Find the UTG player who posts the straddle."""
    return _find_player_by_position(players, 'UTG')


def _get_seat_no_map(players: list[dict]) -> dict[int, dict]:
    """Map seat_no -> player dict."""
    return {p['seat_no']: p for p in players}


def _player_folded_on_street(hand: dict, seat_no: int) -> str | None:
    """Return the street name where a player folded, or None if they didn't fold."""
    for street in hand.get('hand_history', []):
        for action in street.get('actions', []):
            if action['seatNo'] == seat_no and action['action'] == 'fold':
                return street['type']
    return None


@dataclass
class Action:
    """A single voluntary action, with the chip amounts already resolved.

    `amount` is the additional chips this action puts in the pot (already
    capped at the player's remaining stack); `street_total` is the player's
    running total for the street afterwards. `raise_by` is only meaningful
    for `kind == 'raise'`.
    """
    seat_no: int
    kind: str            # 'fold' | 'check' | 'call' | 'bet' | 'raise'
    amount: int = 0
    street_total: int = 0
    raise_by: int = 0
    is_allin: bool = False


@dataclass
class Street:
    type: str            # 'preflop' | 'flop' | 'turn' | 'river'
    actions: list[Action] = field(default_factory=list)


@dataclass
class ForcedBets:
    """The forced money in front of players before voluntary action starts."""
    ante: int = 0
    ante_seats: list[int] = field(default_factory=list)
    sb_seat: int | None = None
    sb_amount: int = 0
    bb_seat: int | None = None
    bb_amount: int = 0
    posts: list[tuple[int, int]] = field(default_factory=list)  # (seat_no, amount)
    straddle_seat: int | None = None
    straddle_amount: int = 0


@dataclass
class HandReplay:
    """A fully resolved hand, ready to be rendered into any output format."""
    hand: dict
    table: dict
    players: list[dict]
    seat_map: dict[int, dict]
    hero: dict | None
    hero_uid: str
    sb: int
    bb: int
    ante: int
    max_players: int
    has_straddle: bool
    is_heads_up: bool
    btn_seat: int                     # 1-based, as displayed
    sb_player: dict | None
    bb_player: dict | None
    straddle_player: dict | None
    timestamp_ms: int
    community: list[str]
    forced: ForcedBets
    streets: list[Street]
    total_pot: int
    uncalled_amount: int
    uncalled_seat: int | None
    effective_pot: int
    rake: int
    raked_pot: int
    winners: list[dict]
    showdown_players: list[dict]
    winner_seats: set[int]

    @property
    def flop_cards(self) -> list[str]:
        return self.community[:3] if len(self.community) >= 3 else []

    @property
    def turn_card(self) -> str | None:
        return self.community[3] if len(self.community) >= 4 else None

    @property
    def river_card(self) -> str | None:
        return self.community[4] if len(self.community) >= 5 else None

    def winner_share(self, winner: dict) -> int:
        """This winner's share of the pot, net of rake."""
        return winner_share(winner, self.winners, self.raked_pot)

    def contributions(self) -> dict[int, int]:
        """Total chips each seat put in the pot, forced bets included."""
        totals = {p['seat_no']: 0 for p in self.players}
        f = self.forced
        for seat_no in f.ante_seats:
            totals[seat_no] += f.ante
        if f.sb_seat is not None:
            totals[f.sb_seat] += f.sb_amount
        if f.bb_seat is not None:
            totals[f.bb_seat] += f.bb_amount
        for seat_no, amount in f.posts:
            totals[seat_no] += amount
        if f.straddle_seat is not None:
            totals[f.straddle_seat] += f.straddle_amount
        for street in self.streets:
            for action in street.actions:
                totals[action.seat_no] += action.amount
        return totals


def winner_share(winner: dict, all_winners: list[dict], effective_pot: int) -> int:
    """Calculate a winner's share of the effective pot.

    Uses floor division with remainder chips distributed to the earliest
    seat(s), ensuring shares always sum to exactly effective_pot.
    """
    if len(all_winners) == 1:
        return effective_pot
    sorted_winners = sorted(all_winners, key=lambda w: w['seat_no'])
    n = len(sorted_winners)
    total_won = sum(w['win_bet'] for w in sorted_winners)

    if total_won <= 0:
        shares = [effective_pot // n] * n
    else:
        shares = [effective_pot * w['win_bet'] // total_won for w in sorted_winners]

    # Distribute remainder chips to earliest seat(s)
    remainder = effective_pot - sum(shares)
    for i in range(remainder):
        shares[i] += 1

    idx = next(i for i, w in enumerate(sorted_winners) if w['seat_no'] == winner['seat_no'])
    return shares[idx]


def _infer_undeclared_posts(r: HandReplay, true_post_amount: int,
                            charge_amount: int) -> list[tuple[int, int]]:
    """Find players who posted to enter without appearing in `post_seats`.

    The API's `post_seats` list is incomplete: in ~2% of hands a player in a
    late seat is charged a post that is never announced. Because the analysis
    data is rake-free and zero-sum, a player who does not win the hand
    contributed exactly `-win_bet` chips, so any shortfall against what the
    replay charged them is money they were forced to put up. Only a shortfall
    of exactly one post is treated as such; anything else is left alone rather
    than invented away.

    The post is recognised at its true size but charged at `charge_amount`,
    which is all the PokerStars format can express (see `replay_hand`).
    """
    if true_post_amount <= 0:
        return []
    charged = r.contributions()
    accounted = {r.forced.sb_seat, r.forced.bb_seat, r.forced.straddle_seat}
    accounted.update(seat for seat, _ in r.forced.posts)
    extra = []
    for p in r.players:
        seat = p['seat_no']
        if seat in accounted or seat in r.winner_seats or p.get('win_bet', 0) >= 0:
            continue
        if -p['win_bet'] - charged[seat] == true_post_amount:
            extra.append((seat, charge_amount))
    return extra


def replay_hand(hand: dict, hero_uid: str | None = None,
                pokerstars_compat: bool = False,
                _extra_posts: list[tuple[int, int]] | None = None) -> HandReplay:
    """Reconstruct a hand from the raw API JSON.

    hero_uid: explicit override; if None, auto-detected from table.session_id
    (falls back to DEFAULT_HERO_UID when session_id isn't present, e.g. in tests).

    pokerstars_compat: charge a post-to-enter as a big blind rather than at
    its real size, which is all PT4's text parser will accept (quirk 6). It is
    the only compromise the PokerStars format still needs; everything else
    here is the faithful reconstruction, checked against the API's own
    `hand_history[0].pot_size` (always `ante * players + SB + BB + straddle`).
    """
    if hero_uid is None:
        hero_uid = _detect_hero_uid(hand) or DEFAULT_HERO_UID

    table = hand['table']
    players = hand['players']
    seat_map = _get_seat_no_map(players)

    sb = table['small_blind']
    bb = table['big_blind']
    ante = table['ante']
    has_straddle = table.get('has_straddle', False)
    straddle_amount = bb * 2 if has_straddle else 0
    max_players = table['max_players']

    # FIX: API 'stack' is the ENDING stack, not starting.
    # starting = ending - net (where net == win_bet)
    for p in players:
        p['starting_stack'] = p['stack'] - p.get('win_bet', 0)

    btn_player = _find_player_by_position(players, 'BTN')
    btn_seat = (btn_player['seat_no'] + 1) if btn_player else 1

    sb_player = _find_player_by_position(players, 'SB')
    bb_player = _find_player_by_position(players, 'BB')
    straddle_player = _find_straddle_player(players) if has_straddle else None

    # When only two players are dealt in, the API marks the small blind's
    # position as "BTN" and no seat has position "SB" — the button posts it.
    # This happens on any table size, not just 2-max tables.
    is_heads_up = sb_player is None and btn_player is not None
    if is_heads_up:
        sb_player = btn_player

    hero = next((p for p in players if p['uid'] == hero_uid), None)

    community = parse_cards(hand.get('community_cards', ''))
    flop_cards = community[:3] if len(community) >= 3 else []

    # A post-to-enter matches the current opening bet, so in a straddle game
    # it is the straddle, not the big blind (confirmed against `win_bet` for
    # every player in the corpus who posted and then folded).
    # The PokerStars renderer must understate it as a big blind: PT4 reads
    # "posts big blind $X" where X > BB as having a dead component, which
    # breaks its street investment tracking and causes pot / stack errors.
    # It still has to recognise a post at its true size, though, or it can't
    # tell that an unannounced one happened at all.
    true_post_amount = straddle_amount if has_straddle else bb
    post_amount = bb if pokerstars_compat else true_post_amount
    post_seat_set = set(hand.get('post_seats', []))
    post_seats = [
        (ps, post_amount)
        for ps in sorted(post_seat_set)
        if ps in seat_map
        and seat_map[ps].get('position') not in ('SB', 'BB', 'UTG' if has_straddle else '')
    ]
    if _extra_posts:
        post_seats = sorted(post_seats + list(_extra_posts))

    forced = ForcedBets(
        ante=ante,
        ante_seats=([] if ante <= 0
                    else [p['seat_no'] for p in sorted(players, key=lambda x: x['seat_no'])]),
        sb_seat=sb_player['seat_no'] if sb_player else None,
        sb_amount=sb if sb_player else 0,
        bb_seat=bb_player['seat_no'] if bb_player else None,
        bb_amount=bb if bb_player else 0,
        posts=post_seats,
    )

    initial_invested = {p['seat_no']: 0 for p in players}
    if sb_player:
        initial_invested[sb_player['seat_no']] = sb
    if bb_player:
        initial_invested[bb_player['seat_no']] = bb
    for ps, amt in post_seats:
        initial_invested[ps] = amt

    # FIX: Remaining stacks use STARTING stacks (not ending)
    remaining_stack = {
        p['seat_no']: p['starting_stack'] - ante
        for p in players
    }
    if sb_player:
        remaining_stack[sb_player['seat_no']] -= sb
    if bb_player:
        remaining_stack[bb_player['seat_no']] -= bb
    for ps, amt in post_seats:
        remaining_stack[ps] -= amt

    # FIX: Track total_pot from forced bets + actions (not from win_bet)
    total_pot = ante * len(players)
    if sb_player:
        total_pot += sb
    if bb_player:
        total_pot += bb
    for _ps, amt in post_seats:
        total_pot += amt

    streets: list[Street] = []
    last_street_invested = None  # track final street_invested for uncalled calc

    for raw_street in hand.get('hand_history', []):
        street_type = raw_street['type']
        raw_actions = raw_street.get('actions', [])
        street = Street(type=street_type)
        streets.append(street)

        if not raw_actions:
            continue

        # Reset per-street tracking
        if street_type == 'preflop':
            street_invested = dict(initial_invested)
            current_bet = bb
        else:
            street_invested = {p['seat_no']: 0 for p in players}
            current_bet = 0

        # The straddle is a real forced bet, but the API doesn't report it as
        # an action, so it is reconstructed here as the opening wager.
        if street_type == 'preflop' and has_straddle and straddle_player:
            s_seat = straddle_player['seat_no']
            remaining_stack[s_seat] -= straddle_amount
            street_invested[s_seat] = straddle_amount
            current_bet = straddle_amount
            total_pot += straddle_amount
            forced.straddle_seat = s_seat
            forced.straddle_amount = straddle_amount

        for raw_action in raw_actions:
            seat = raw_action['seatNo']
            if seat not in seat_map:
                continue
            act = raw_action['action']
            amount = raw_action.get('amount', 0)

            # For raise/bet/allin: API 'amount' is player's TOTAL for the street
            # (includes their blind/straddle). For call: amount is ADDITIONAL only.
            if act == 'fold':
                street.actions.append(Action(seat_no=seat, kind='fold'))

            elif act == 'check':
                # The API reports preflop limps/straddle-calls as "check".
                # In straddle games, "checking" means calling the straddle.
                # In non-straddle games, a preflop "check" from a player who
                # hasn't matched the BB is actually a limp (call).
                if (street_type == 'preflop'
                        and street_invested.get(seat, 0) < current_bet):
                    call_amount = current_bet - street_invested.get(seat, 0)
                    avail = max(remaining_stack.get(seat, 0), 0)
                    if avail <= 0:
                        continue
                    call_amount = min(call_amount, avail)
                    remaining_stack[seat] -= call_amount
                    street_invested[seat] = street_invested.get(seat, 0) + call_amount
                    total_pot += call_amount
                    street.actions.append(Action(
                        seat_no=seat, kind='call', amount=call_amount,
                        street_total=street_invested[seat],
                        is_allin=remaining_stack[seat] <= 0,
                    ))
                else:
                    street.actions.append(Action(seat_no=seat, kind='check'))

            elif act == 'call':
                # amount = additional chips only
                # FIX: The API under-reports preflop call amounts for non-blind
                # players (by the big blind amount). Compute the correct amount
                # from our own current_bet tracking instead of trusting the API.
                if street_type == 'preflop':
                    amount = current_bet - street_invested.get(seat, 0)
                avail = max(remaining_stack.get(seat, 0), 0)
                if avail <= 0:
                    continue
                amount = min(amount, avail)
                remaining_stack[seat] -= amount
                street_invested[seat] = street_invested.get(seat, 0) + amount
                total_pot += amount
                street.actions.append(Action(
                    seat_no=seat, kind='call', amount=amount,
                    street_total=street_invested[seat],
                    is_allin=remaining_stack[seat] <= 0,
                ))

            elif act == 'bet':
                # amount = total for street (same as additional since no prior on post-flop)
                avail = max(remaining_stack.get(seat, 0), 0)
                if avail <= 0:
                    continue
                amount = min(amount, avail)
                remaining_stack[seat] -= amount
                street_invested[seat] = amount
                current_bet = amount
                total_pot += amount
                street.actions.append(Action(
                    seat_no=seat, kind='bet', amount=amount,
                    street_total=amount,
                    is_allin=remaining_stack[seat] <= 0,
                ))

            elif act == 'raise':
                # amount = player's TOTAL for the street (includes blind/straddle/prior)
                prev_invested = street_invested.get(seat, 0)
                additional = amount - prev_invested
                avail = max(remaining_stack.get(seat, 0), 0)
                if avail <= 0:
                    continue
                additional = min(additional, avail)
                new_total = prev_invested + additional
                remaining_stack[seat] -= additional
                street_invested[seat] = new_total
                raise_by = new_total - current_bet
                current_bet = new_total
                total_pot += additional
                street.actions.append(Action(
                    seat_no=seat, kind='raise', amount=additional,
                    street_total=new_total, raise_by=raise_by,
                    is_allin=remaining_stack[seat] <= 0,
                ))

            elif act == 'allin':
                # amount = player's TOTAL for the street
                prev_invested = street_invested.get(seat, 0)
                additional = amount - prev_invested
                avail = max(remaining_stack.get(seat, 0), 0)
                if avail <= 0:
                    continue
                additional = min(additional, avail)
                new_total = prev_invested + additional
                remaining_stack[seat] -= additional
                street_invested[seat] = new_total
                total_pot += additional
                if current_bet == 0:
                    kind, raise_by = 'bet', 0
                    current_bet = new_total
                elif new_total > current_bet:
                    kind, raise_by = 'raise', new_total - current_bet
                    current_bet = new_total
                else:
                    # All-in for less than current bet = call
                    kind, raise_by = 'call', 0
                street.actions.append(Action(
                    seat_no=seat, kind=kind, amount=additional,
                    street_total=new_total, raise_by=raise_by, is_allin=True,
                ))

        # Save this street's invested values for uncalled bet calculation
        last_street_invested = dict(street_invested)

    # Compute uncalled bet from actual street investments (max vs second-max).
    # This correctly handles all-in-for-less calls because street_invested
    # values are already capped at remaining stack during action processing.
    uncalled_amount = 0
    uncalled_seat = None
    if last_street_invested:
        invested_vals = sorted(last_street_invested.values(), reverse=True)
        if len(invested_vals) >= 2 and invested_vals[0] > invested_vals[1]:
            uncalled_amount = invested_vals[0] - invested_vals[1]
            uncalled_seat = max(last_street_invested, key=lambda s: last_street_invested[s])
    effective_pot = total_pot - uncalled_amount

    # Rake: a percentage of the contested pot, capped by stake and player
    # count (see RAKE_TABLE).
    rake = compute_rake(sb, bb, len(players), effective_pot, bool(flop_cards))
    raked_pot = effective_pot - rake

    showdown_players = [p for p in players if p.get('is_showdown') and p.get('hand_cards')]
    winners = [p for p in players if p.get('win_bet', 0) > 0]

    # FIX: When all showdown players have win_bet=0 (exact split, board plays),
    # treat them as winners splitting the pot equally.
    if not winners and showdown_players:
        winners = list(showdown_players)

    result = HandReplay(
        hand=hand,
        table=table,
        players=players,
        seat_map=seat_map,
        hero=hero,
        hero_uid=hero_uid,
        sb=sb,
        bb=bb,
        ante=ante,
        max_players=max_players,
        has_straddle=has_straddle,
        is_heads_up=is_heads_up,
        btn_seat=btn_seat,
        sb_player=sb_player,
        bb_player=bb_player,
        straddle_player=straddle_player,
        timestamp_ms=hand['timestamp'],
        community=community,
        forced=forced,
        streets=streets,
        total_pot=total_pot,
        uncalled_amount=uncalled_amount,
        uncalled_seat=uncalled_seat,
        effective_pot=effective_pot,
        rake=rake,
        raked_pot=raked_pot,
        winners=winners,
        showdown_players=showdown_players,
        winner_seats={w['seat_no'] for w in winners},
    )

    # A post the API failed to announce changes what its owner still owes, so
    # the hand has to be replayed once more with it in place.
    if _extra_posts is None:
        extra = _infer_undeclared_posts(result, true_post_amount, post_amount)
        if extra:
            return replay_hand(hand, hero_uid=hero_uid,
                               pokerstars_compat=pokerstars_compat, _extra_posts=extra)

    return result
