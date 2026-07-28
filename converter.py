"""Convert ClubWPT Gold JSON hand data to PokerStars hand history format."""

from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict
from itertools import combinations

DEFAULT_HERO_UID = "235160"

# Card rank values for hand evaluation
RANK_VALUES = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
               '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14}
RANK_NAMES = {2: 'Deuce', 3: 'Three', 4: 'Four', 5: 'Five', 6: 'Six',
              7: 'Seven', 8: 'Eight', 9: 'Nine', 10: 'Ten', 11: 'Jack',
              12: 'Queen', 13: 'King', 14: 'Ace'}
RANK_NAMES_PLURAL = {2: 'Deuces', 3: 'Threes', 4: 'Fours', 5: 'Fives',
                     6: 'Sixes', 7: 'Sevens', 8: 'Eights', 9: 'Nines',
                     10: 'Tens', 11: 'Jacks', 12: 'Queens', 13: 'Kings',
                     14: 'Aces'}


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


def card_rank(card: str) -> int:
    return RANK_VALUES[card[0]]


def card_suit(card: str) -> str:
    return card[1]


def evaluate_hand(hole_cards: list[str], community_cards: list[str]) -> tuple[int, str]:
    """Evaluate the best 5-card poker hand and return (rank_score, description).

    rank_score: higher is better
    Returns the best hand from all 5-card combinations of 7 cards.
    """
    all_cards = hole_cards + community_cards
    if len(all_cards) < 5:
        return (0, "")

    best_score = -1
    best_desc = ""

    for combo in combinations(all_cards, 5):
        score, desc = _evaluate_five(list(combo))
        if score > best_score:
            best_score = score
            best_desc = desc

    return (best_score, best_desc)


def _evaluate_five(cards: list[str]) -> tuple[int, str]:
    """Evaluate exactly 5 cards. Returns (score, description)."""
    ranks = sorted([card_rank(c) for c in cards], reverse=True)
    suits = [card_suit(c) for c in cards]

    is_flush = len(set(suits)) == 1

    # Check for straight
    is_straight = False
    straight_high = 0
    unique_ranks = sorted(set(ranks), reverse=True)
    if len(unique_ranks) == 5:
        if unique_ranks[0] - unique_ranks[4] == 4:
            is_straight = True
            straight_high = unique_ranks[0]
        # Wheel (A-2-3-4-5)
        elif unique_ranks == [14, 5, 4, 3, 2]:
            is_straight = True
            straight_high = 5

    rank_counts = defaultdict(int)
    for r in ranks:
        rank_counts[r] += 1

    counts = sorted(rank_counts.values(), reverse=True)

    # Base scores per hand category (must be spaced far enough apart
    # that no sub-category score can overlap with the next category)
    BASE = 100_000_000_000  # 10^11

    if is_straight and is_flush:
        if straight_high == 14 and min(ranks) == 10:
            return (8 * BASE + straight_high, "a Royal Flush")
        return (8 * BASE + straight_high, f"a straight flush, {RANK_NAMES.get(straight_high, str(straight_high))} high")

    if counts == [4, 1]:
        quad_rank = [r for r, c in rank_counts.items() if c == 4][0]
        kicker = [r for r, c in rank_counts.items() if c == 1][0]
        return (7 * BASE + quad_rank * 100 + kicker,
                f"four of a kind, {RANK_NAMES_PLURAL.get(quad_rank, str(quad_rank))}")

    if counts == [3, 2]:
        trip_rank = [r for r, c in rank_counts.items() if c == 3][0]
        pair_rank = [r for r, c in rank_counts.items() if c == 2][0]
        return (6 * BASE + trip_rank * 100 + pair_rank,
                f"a full house, {RANK_NAMES_PLURAL.get(trip_rank, str(trip_rank))} full of {RANK_NAMES_PLURAL.get(pair_rank, str(pair_rank))}")

    if is_flush:
        score = 5 * BASE
        for i, r in enumerate(ranks):
            score += r * (100 ** (4 - i))
        return (score, f"a flush, {RANK_NAMES.get(ranks[0], str(ranks[0]))} high")

    if is_straight:
        return (4 * BASE + straight_high,
                f"a straight, {RANK_NAMES.get(straight_high, str(straight_high))} high")

    if counts == [3, 1, 1]:
        trip_rank = [r for r, c in rank_counts.items() if c == 3][0]
        kickers = sorted([r for r, c in rank_counts.items() if c == 1], reverse=True)
        return (3 * BASE + trip_rank * 10000 + kickers[0] * 100 + kickers[1],
                f"three of a kind, {RANK_NAMES_PLURAL.get(trip_rank, str(trip_rank))}")

    if counts == [2, 2, 1]:
        pairs = sorted([r for r, c in rank_counts.items() if c == 2], reverse=True)
        kicker = [r for r, c in rank_counts.items() if c == 1][0]
        return (2 * BASE + pairs[0] * 10000 + pairs[1] * 100 + kicker,
                f"two pair, {RANK_NAMES_PLURAL.get(pairs[0], str(pairs[0]))} and {RANK_NAMES_PLURAL.get(pairs[1], str(pairs[1]))}")

    if counts == [2, 1, 1, 1]:
        pair_rank = [r for r, c in rank_counts.items() if c == 2][0]
        kickers = sorted([r for r, c in rank_counts.items() if c == 1], reverse=True)
        return (1 * BASE + pair_rank * 1000000 + kickers[0] * 10000 + kickers[1] * 100 + kickers[2],
                f"a pair of {RANK_NAMES_PLURAL.get(pair_rank, str(pair_rank))}")

    # High card
    score = 0
    for i, r in enumerate(ranks):
        score += r * (100 ** (4 - i))
    return (score, f"high card, {RANK_NAMES.get(ranks[0], str(ranks[0]))}")


def fmt_amount(chips: int | float) -> str:
    """Format chip amount as dollar string: 250 -> '$2.50'."""
    val = chips / 100.0
    if val == int(val):
        return f"${int(val):.2f}"
    return f"${val:.2f}"


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


def convert_hand(hand: dict, hero_uid: str = DEFAULT_HERO_UID) -> str:
    """Convert a single hand JSON object to PokerStars hand history format."""
    lines = []
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

    # Timestamp (PT4 expects ET)
    ts = hand['timestamp'] / 1000.0
    dt = datetime.fromtimestamp(ts, tz=ZoneInfo('America/New_York'))
    date_str = dt.strftime('%Y/%m/%d %H:%M:%S ET')

    # Find button
    btn_player = _find_player_by_position(players, 'BTN')
    btn_seat = (btn_player['seat_no'] + 1) if btn_player else 1

    # Find SB, BB, UTG (straddle)
    sb_player = _find_player_by_position(players, 'SB')
    bb_player = _find_player_by_position(players, 'BB')
    straddle_player = _find_straddle_player(players) if has_straddle else None

    # Heads-up (2-max): BTN is the SB but API marks position as "BTN".
    # In heads-up, ante == SB so we treat BTN as SB and skip antes entirely.
    is_heads_up = max_players == 2 and sb_player is None and btn_player is not None
    if is_heads_up:
        sb_player = btn_player

    # Header — truncate 19-digit ID to 12 digits for PT4 compatibility
    hand_id = str(int(hand['id']) % 1_000_000_000_000)
    lines.append(
        f"PokerStars Hand #{hand_id}: Hold'em No Limit ({fmt_amount(sb)}/{fmt_amount(bb)} USD) - {date_str}"
    )

    # Table line — readable name instead of raw numeric ID
    table_name = f"ClubWPT #{int(table['table_id']) % 100000}"
    lines.append(f"Table '{table_name}' {max_players}-max Seat #{btn_seat} is the button")

    # FIX: Seat lines use STARTING stacks (not ending)
    for p in sorted(players, key=lambda x: x['seat_no']):
        seat = p['seat_no'] + 1
        lines.append(f"Seat {seat}: {p['name']} ({fmt_amount(p['starting_stack'])} in chips)")

    # Antes — individual per player (skipped in heads-up where ante == SB)
    if ante > 0 and not is_heads_up:
        for p in sorted(players, key=lambda x: x['seat_no']):
            lines.append(f"{p['name']}: posts the ante {fmt_amount(ante)}")

    # Blinds
    if sb_player:
        lines.append(f"{sb_player['name']}: posts small blind {fmt_amount(sb)}")
    if bb_player:
        lines.append(f"{bb_player['name']}: posts big blind {fmt_amount(bb)}")

    # NOTE: Straddle is handled as a synthetic preflop raise (not a blind line)
    # because PT4 doesn't support "posts the straddle" in PokerStars format.

    # Post seats (players who posted to enter)
    # Post-to-enter is always the BB amount. In straddle games, the remaining
    # gap (straddle - BB) is covered by the check-to-call conversion or is
    # included in the player's raise/call action total from the API.
    # Using BB (not straddle) is critical because PT4 interprets "posts big
    # blind $X" where X > BB as having a dead component, which breaks its
    # street investment tracking and causes pot size / stack errors.
    post_amount = bb
    post_seat_set = set(hand.get('post_seats', []))
    for ps in sorted(post_seat_set):
        if ps in seat_map:
            pp = seat_map[ps]
            if pp.get('position') not in ('SB', 'BB', 'UTG' if has_straddle else ''):
                lines.append(f"{pp['name']}: posts big blind {fmt_amount(post_amount)}")

    # Hole cards
    lines.append("*** HOLE CARDS ***")
    hero = None
    for p in players:
        if p['uid'] == hero_uid:
            hero = p
            break
    if hero and hero.get('hand_cards'):
        hero_cards = parse_cards(hero['hand_cards'])
        lines.append(f"Dealt to {hero['name']} [{format_cards(hero_cards)}]")

    # Parse community cards
    community = parse_cards(hand.get('community_cards', ''))
    flop_cards = community[:3] if len(community) >= 3 else []
    turn_card = community[3] if len(community) >= 4 else None
    river_card = community[4] if len(community) >= 5 else None

    # Initial investments from forced bets (including straddle as blind)
    initial_invested = {}
    for p in players:
        initial_invested[p['seat_no']] = 0
    if sb_player:
        initial_invested[sb_player['seat_no']] = sb
    if bb_player:
        initial_invested[bb_player['seat_no']] = bb
    for ps in post_seat_set:
        if ps in seat_map:
            pp = seat_map[ps]
            if pp.get('position') not in ('SB', 'BB', 'UTG' if has_straddle else ''):
                initial_invested[ps] = post_amount

    # FIX: Remaining stacks use STARTING stacks (not ending)
    remaining_stack = {}
    for p in players:
        remaining_stack[p['seat_no']] = p['starting_stack'] - (0 if is_heads_up else ante)
    if sb_player:
        remaining_stack[sb_player['seat_no']] -= sb
    if bb_player:
        remaining_stack[bb_player['seat_no']] -= bb
    for ps in post_seat_set:
        if ps in seat_map:
            pp = seat_map[ps]
            if pp.get('position') not in ('SB', 'BB', 'UTG' if has_straddle else ''):
                remaining_stack[ps] -= post_amount

    # FIX: Track total_pot from forced bets + actions (not from win_bet)
    total_pot = 0 if is_heads_up else ante * len(players)
    if sb_player:
        total_pot += sb
    if bb_player:
        total_pot += bb
    for ps in post_seat_set:
        if ps in seat_map:
            pp = seat_map[ps]
            if pp.get('position') not in ('SB', 'BB', 'UTG' if has_straddle else ''):
                total_pot += post_amount

    last_street_invested = None  # track final street_invested for uncalled calc

    for street in hand.get('hand_history', []):
        street_type = street['type']
        actions = street.get('actions', [])

        if street_type == 'flop' and flop_cards:
            lines.append(f"*** FLOP *** [{format_cards(flop_cards)}]")
        elif street_type == 'turn' and turn_card:
            lines.append(f"*** TURN *** [{format_cards(flop_cards)}] [{turn_card}]")
        elif street_type == 'river' and river_card:
            flop_turn = flop_cards + ([turn_card] if turn_card else [])
            lines.append(f"*** RIVER *** [{format_cards(flop_turn)}] [{river_card}]")

        if not actions:
            continue

        # Reset per-street tracking
        if street_type == 'preflop':
            street_invested = dict(initial_invested)
            current_bet = bb
        else:
            street_invested = {p['seat_no']: 0 for p in players}
            current_bet = 0

        # Synthetic straddle as a preflop raise (PT4 can't parse "posts the straddle")
        if street_type == 'preflop' and has_straddle and straddle_player:
            s_seat = straddle_player['seat_no']
            s_name = straddle_player['name']
            s_additional = straddle_amount
            remaining_stack[s_seat] -= s_additional
            street_invested[s_seat] = straddle_amount
            s_raise_by = straddle_amount - current_bet
            current_bet = straddle_amount
            total_pot += s_additional
            lines.append(f"{s_name}: raises {fmt_amount(s_raise_by)} to {fmt_amount(straddle_amount)}")

        for action in actions:
            seat = action['seatNo']
            if seat not in seat_map:
                continue
            player = seat_map[seat]
            name = player['name']
            act = action['action']
            amount = action.get('amount', 0)

            # For raise/bet/allin: API 'amount' is player's TOTAL for the street
            # (includes their blind/straddle). For call: amount is ADDITIONAL only.
            if act == 'fold':
                lines.append(f"{name}: folds")

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
                    is_allin = remaining_stack[seat] <= 0
                    line = f"{name}: calls {fmt_amount(call_amount)}"
                    if is_allin:
                        line += " and is all-in"
                    lines.append(line)
                else:
                    lines.append(f"{name}: checks")

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
                is_allin = remaining_stack[seat] <= 0
                line = f"{name}: calls {fmt_amount(amount)}"
                if is_allin:
                    line += " and is all-in"
                lines.append(line)

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
                is_allin = remaining_stack[seat] <= 0
                line = f"{name}: bets {fmt_amount(amount)}"
                if is_allin:
                    line += " and is all-in"
                lines.append(line)

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
                is_allin = remaining_stack[seat] <= 0
                line = f"{name}: raises {fmt_amount(raise_by)} to {fmt_amount(new_total)}"
                if is_allin:
                    line += " and is all-in"
                lines.append(line)

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
                    line = f"{name}: bets {fmt_amount(new_total)} and is all-in"
                    current_bet = new_total
                elif new_total > current_bet:
                    raise_by = new_total - current_bet
                    line = f"{name}: raises {fmt_amount(raise_by)} to {fmt_amount(new_total)} and is all-in"
                    current_bet = new_total
                else:
                    # All-in for less than current bet = call
                    line = f"{name}: calls {fmt_amount(additional)} and is all-in"
                lines.append(line)

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
    if uncalled_amount > 0:
        if uncalled_seat is not None and uncalled_seat in seat_map:
            lines.append(f"Uncalled bet ({fmt_amount(uncalled_amount)}) returned to {seat_map[uncalled_seat]['name']}")
    effective_pot = total_pot - uncalled_amount

    # Rake: a percentage of the contested pot, capped by stake and player
    # count (see RAKE_TABLE). The "Total pot" line reports the gross pot while
    # winners collect the pot net of rake, matching PokerStars' format.
    rake = compute_rake(sb, bb, len(players), effective_pot, bool(flop_cards))
    raked_pot = effective_pot - rake

    # Showdown
    showdown_players = [p for p in players if p.get('is_showdown') and p.get('hand_cards')]
    winners = [p for p in players if p.get('win_bet', 0) > 0]

    # FIX: When all showdown players have win_bet=0 (exact split, board plays),
    # treat them as winners splitting the pot equally.
    if not winners and showdown_players:
        winners = list(showdown_players)

    winner_seats = {w['seat_no'] for w in winners}

    if showdown_players:
        lines.append("*** SHOW DOWN ***")
        for p in sorted(showdown_players, key=lambda x: x['seat_no']):
            cards = parse_cards(p['hand_cards'])
            _, hand_desc = evaluate_hand(cards, community)
            if not hand_desc:
                hand_desc = "a hand"
            if p['seat_no'] in winner_seats:
                collected = _winner_share(p, winners, raked_pot)
                lines.append(f"{p['name']}: shows [{format_cards(cards)}] ({hand_desc})")
                lines.append(f"{p['name']} collected {fmt_amount(collected)} from pot")
            else:
                lines.append(f"{p['name']}: shows [{format_cards(cards)}] ({hand_desc})")
    else:
        for w in winners:
            collected = _winner_share(w, winners, raked_pot)
            lines.append(f"{w['name']} collected {fmt_amount(collected)} from pot")
            if w.get('hand_cards') and not w.get('is_showdown'):
                lines.append(f"{w['name']}: doesn't show hand")

    # Summary
    lines.append("*** SUMMARY ***")
    lines.append(f"Total pot {fmt_amount(effective_pot)} | Rake {fmt_amount(rake)}")

    if community:
        lines.append(f"Board [{format_cards(community)}]")

    # Seat results
    for p in sorted(players, key=lambda x: x['seat_no']):
        seat = p['seat_no'] + 1
        pos = p['position']
        name = p['name']
        cards = parse_cards(p.get('hand_cards', ''))

        pos_label = {"BTN": "button", "SB": "small blind", "BB": "big blind"}.get(pos, "")
        pos_str = f" ({pos_label})" if pos_label else ""

        fold_street = _player_folded_on_street(hand, p['seat_no'])

        if p['seat_no'] in winner_seats and p.get('is_showdown') and cards:
            _, hand_desc = evaluate_hand(cards, community)
            if not hand_desc:
                hand_desc = "a hand"
            won_amount = _winner_share(p, winners, raked_pot)
            lines.append(
                f"Seat {seat}: {name}{pos_str} showed [{format_cards(cards)}] "
                f"and won ({fmt_amount(won_amount)}) with {hand_desc}"
            )
        elif p['seat_no'] in winner_seats:
            won_amount = _winner_share(p, winners, raked_pot)
            lines.append(f"Seat {seat}: {name}{pos_str} collected ({fmt_amount(won_amount)})")
        elif p.get('is_showdown') and cards:
            _, hand_desc = evaluate_hand(cards, community)
            if not hand_desc:
                hand_desc = "a hand"
            lines.append(
                f"Seat {seat}: {name}{pos_str} showed [{format_cards(cards)}] "
                f"and lost with {hand_desc}"
            )
        elif fold_street:
            fold_desc = _fold_description(fold_street, hand, p['seat_no'],
                                          sb_player, bb_player, straddle_player,
                                          has_straddle)
            lines.append(f"Seat {seat}: {name}{pos_str} {fold_desc}")
        else:
            lines.append(f"Seat {seat}: {name}{pos_str} mucked")

    return '\n'.join(lines)


def _winner_share(winner, all_winners, effective_pot):
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


def _fold_description(fold_street: str, hand: dict, seat_no: int,
                      sb_player, bb_player, straddle_player, has_straddle) -> str:
    """Generate fold description for summary line."""
    did_bet = False
    for street in hand.get('hand_history', []):
        if street['type'] != 'preflop':
            break
        for action in street.get('actions', []):
            if action['seatNo'] == seat_no and action['action'] in ('call', 'raise', 'bet', 'allin'):
                did_bet = True
                break

    if fold_street == 'preflop':
        if not did_bet:
            return "folded before Flop (didn't bet)"
        return "folded before Flop"
    elif fold_street == 'flop':
        return "folded on the Flop"
    elif fold_street == 'turn':
        return "folded on the Turn"
    elif fold_street == 'river':
        return "folded on the River"
    return "folded"


def convert_hands_to_file(hands: list[dict], hero_uid: str = DEFAULT_HERO_UID) -> str:
    """Convert a list of hand objects to a single PokerStars HH file string."""
    converted = []
    for hand in hands:
        try:
            converted.append(convert_hand(hand, hero_uid=hero_uid))
        except Exception as e:
            print(f"Error converting hand {hand.get('id', 'unknown')}: {e}")
    return '\n\n\n'.join(converted) + '\n'
