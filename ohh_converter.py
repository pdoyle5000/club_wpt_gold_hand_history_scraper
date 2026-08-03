"""Convert ClubWPT Gold JSON hand data to Open Hand History (OHH) format.

OHH is the open JSON hand-history standard used by PokerTracker 4 and Holdem
Manager 3 (https://hh-specs.handhistory.org). Unlike the PokerStars text
format it models antes and straddles natively, so ClubWPT Gold hands convert
without the synthetic-raise workaround that the PokerStars renderer needs
(see CLAUDE.md quirks 1 and 2). A post-to-enter still has to be understated
as a big blind, though — PT4 mis-reads a larger one in either format
(quirk 6).

The hand itself is reconstructed by `hand_replay.replay_hand`; this module is
only responsible for rendering that reconstruction as OHH JSON.
"""

import json
from datetime import datetime, timezone

from hand_replay import parse_cards, replay_hand, winner_share

SPEC_VERSION = "1.4.9"
SITE_NAME = "ClubWPT Gold"
NETWORK_NAME = "ClubWPT Gold"
CURRENCY = "USD"
GAME_TYPE = "Holdem"
BET_TYPE = "NL"

STREET_NAMES = {'preflop': 'Preflop', 'flop': 'Flop', 'turn': 'Turn', 'river': 'River'}
ACTION_NAMES = {'fold': 'Fold', 'check': 'Check', 'call': 'Call',
                'bet': 'Bet', 'raise': 'Raise'}


def to_amount(chips: int) -> float:
    """Convert API chips (cents) to the currency amount OHH expects: 250 -> 2.5."""
    return round(chips / 100.0, 2)


def _gross_collected(r) -> list[tuple[dict, int]] | None:
    """Who pulled chips out of the pot before rake, in seat order.

    The analysis data is rake-free and zero-sum, so what a player took from
    the pot is their reported net plus everything they put in, less any
    uncalled bet handed back to them. Deriving it that way stays exact when
    an all-in creates side pots — a side-pot winner can still finish the hand
    down money, so the reported net alone would miss them.

    Returns None if the takes fail to reconcile with the pot, so the caller
    can fall back rather than emit a pot that doesn't add up.
    """
    contributions = r.contributions()
    takes = []
    for p in sorted(r.players, key=lambda x: x['seat_no']):
        seat = p['seat_no']
        returned = r.uncalled_amount if seat == r.uncalled_seat else 0
        gross = p.get('win_bet', 0) + contributions[seat] - returned
        if gross > 0:
            takes.append((p, gross))
    if not takes or sum(g for _, g in takes) != r.effective_pot:
        return None
    return takes


def _apportion(total: int, weights: list[int]) -> list[int]:
    """Split `total` chips across `weights`, remainder to the earliest seat(s)."""
    if not weights:
        return []
    weight_sum = sum(weights)
    if weight_sum <= 0:
        parts = [total // len(weights)] * len(weights)
    else:
        parts = [total * w // weight_sum for w in weights]
    for i in range(total - sum(parts)):
        parts[i] += 1
    return parts


def convert_hand_to_ohh(hand: dict, hero_uid: str | None = None) -> dict:
    """Convert a single hand JSON object to an OHH document (the outer dict
    with the single "ohh" key).

    hero_uid: explicit override; if None, auto-detected from table.session_id.
    """
    r = replay_hand(hand, hero_uid=hero_uid, post_as_big_blind=True)
    forced = r.forced

    seated = sorted(r.players, key=lambda p: p['seat_no'])
    pid = {p['seat_no']: i for i, p in enumerate(seated)}

    dt = datetime.fromtimestamp(r.timestamp_ms / 1000.0, tz=timezone.utc)

    # Track stacks through the forced bets so a blind/ante that puts a short
    # stack all-in is flagged; voluntary actions carry is_allin from the replay.
    stacks = {p['seat_no']: p['starting_stack'] for p in r.players}
    preflop_actions: list[dict] = []

    def add_action(seat_no: int, action: str, amount: int = 0,
                   is_allin: bool = False, cards: list[str] | None = None,
                   into: list[dict] | None = None) -> None:
        target = preflop_actions if into is None else into
        entry = {
            "action_number": len(target) + 1,
            "player_id": pid[seat_no],
            "action": action,
        }
        if cards is not None:
            entry["cards"] = cards
        entry["amount"] = to_amount(amount)
        entry["is_allin"] = is_allin
        target.append(entry)

    def add_forced(seat_no: int, action: str, amount: int) -> None:
        stacks[seat_no] -= amount
        add_action(seat_no, action, amount, is_allin=stacks[seat_no] <= 0)

    for seat_no in forced.ante_seats:
        add_forced(seat_no, "Post Ante", forced.ante)
    if forced.sb_seat is not None:
        add_forced(forced.sb_seat, "Post SB", forced.sb_amount)
    if forced.bb_seat is not None:
        add_forced(forced.bb_seat, "Post BB", forced.bb_amount)
    # Post-to-enter: a live blind that isn't the table's SB/BB. OHH has an
    # action for it, but PT4 treats any post above the big blind as part dead,
    # so it is charged as a big blind here too (quirk 6).
    for seat_no, amount in forced.posts:
        add_forced(seat_no, "Post Extra Blind", amount)
    # The straddle is a first-class OHH action — no synthetic raise needed.
    if forced.straddle_seat is not None:
        add_forced(forced.straddle_seat, "Straddle", forced.straddle_amount)

    if r.hero is not None and r.hero.get('hand_cards'):
        add_action(r.hero['seat_no'], "Dealt Cards",
                   cards=parse_cards(r.hero['hand_cards']))

    community = r.community
    street_cards = {
        'preflop': [],
        'flop': community[:3] if len(community) >= 3 else [],
        'turn': [community[3]] if len(community) >= 4 else [],
        'river': [community[4]] if len(community) >= 5 else [],
    }

    rounds: list[dict] = []
    for street in r.streets:
        # Preflop continues the list the forced bets were written into.
        actions = preflop_actions if street.type == 'preflop' else []
        for action in street.actions:
            add_action(action.seat_no, ACTION_NAMES[action.kind],
                       amount=action.amount, is_allin=action.is_allin,
                       into=actions)
        rounds.append({
            "id": len(rounds),
            "street": STREET_NAMES.get(street.type, street.type.title()),
            "cards": street_cards.get(street.type, []),
            "actions": actions,
        })

    # A hand whose API payload has no preflop street still needs its forced
    # bets recorded.
    if not any(rnd["street"] == "Preflop" for rnd in rounds):
        rounds.insert(0, {"id": 0, "street": "Preflop", "cards": [],
                          "actions": preflop_actions})
        for i, rnd in enumerate(rounds):
            rnd["id"] = i

    if r.showdown_players:
        showdown_actions: list[dict] = []
        for p in sorted(r.showdown_players, key=lambda x: x['seat_no']):
            add_action(p['seat_no'], "Shows Cards",
                       cards=parse_cards(p['hand_cards']), into=showdown_actions)
        rounds.append({
            "id": len(rounds),
            "street": "Showdown",
            "cards": [],
            "actions": showdown_actions,
        })

    # A single pot: the API never exposes side-pot structure, so even a
    # multi-way all-in is reported as one pot — but each winner's share is
    # still their exact take, so the amounts won are right regardless.
    # `amount` is the contested pot (uncalled bets are excluded, as in the OHH
    # reference examples) and includes the rake; win_amount is net of it.
    takes = _gross_collected(r)
    if takes is None:
        # Fall back to splitting the pot in proportion to the reported nets.
        # Each winner's rake share is then the gap between their slice of the
        # gross pot and what they collect, so the two still reconcile exactly.
        sorted_winners = sorted(r.winners, key=lambda w: w['seat_no'])
        takes = [(w, winner_share(w, r.winners, r.effective_pot)) for w in sorted_winners]
        shares = [r.winner_share(w) for w in sorted_winners]
        rake_parts = [gross - share for (_, gross), share in zip(takes, shares)]
    else:
        rake_parts = _apportion(r.rake, [gross for _, gross in takes])
        shares = [gross - rake_part for (_, gross), rake_part in zip(takes, rake_parts)]

    pot = {
        "number": 0,
        "amount": to_amount(r.effective_pot),
        "rake": to_amount(r.rake),
        "player_wins": [
            {
                "player_id": pid[w['seat_no']],
                "win_amount": to_amount(share),
                "contributed_rake": to_amount(rake_part),
            }
            for (w, _gross), share, rake_part in zip(takes, shares, rake_parts)
        ],
    }

    table_name = r.table.get('table_name') or f"ClubWPT #{int(r.table['table_id']) % 100000}"

    return {
        "ohh": {
            "spec_version": SPEC_VERSION,
            "internal_version": SPEC_VERSION,
            "network_name": NETWORK_NAME,
            "site_name": SITE_NAME,
            "game_type": GAME_TYPE,
            "tournament": False,
            "game_number": str(hand['id']),
            "start_date_utc": dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "table_name": table_name,
            "table_size": r.max_players,
            "currency": CURRENCY,
            "dealer_seat": r.btn_seat,
            "small_blind_amount": to_amount(r.sb),
            "big_blind_amount": to_amount(r.bb),
            # 0 in heads-up, where the API's "ante" is really the small blind.
            "ante_amount": to_amount(forced.ante),
            "bet_limit": {"bet_type": BET_TYPE, "bet_cap": 0.0},
            "hero_player_id": pid[r.hero['seat_no']] if r.hero is not None else None,
            "flags": [],
            "players": [
                {
                    "id": pid[p['seat_no']],
                    "seat": p['seat_no'] + 1,
                    "name": p['name'],
                    "starting_stack": to_amount(p['starting_stack']),
                }
                for p in seated
            ],
            "rounds": rounds,
            "pots": [pot],
        }
    }


def convert_hand_to_ohh_json(hand: dict, hero_uid: str | None = None,
                             indent: int | None = None) -> str:
    """Convert a single hand to its OHH JSON text."""
    return json.dumps(convert_hand_to_ohh(hand, hero_uid=hero_uid), indent=indent)


def convert_hands_to_ohh_file(hands: list[dict], hero_uid: str | None = None,
                              indent: int | None = None) -> str:
    """Convert hands to the contents of a single .ohh file.

    Per the OHH storage format, a file holds a sequence of JSON objects
    separated by one blank line rather than one enclosing JSON array.
    """
    documents = []
    for hand in hands:
        try:
            documents.append(convert_hand_to_ohh_json(hand, hero_uid=hero_uid, indent=indent))
        except Exception as e:
            print(f"Error converting hand {hand.get('id', 'unknown')}: {e}")
    return '\n\n'.join(documents) + '\n'
