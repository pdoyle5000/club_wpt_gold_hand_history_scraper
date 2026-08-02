"""Convert ClubWPT Gold JSON hand data to PokerStars hand history format.

The hand itself is reconstructed by `hand_replay.replay_hand`; this module is
only responsible for rendering that reconstruction as PokerStars text.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from collections import defaultdict
from itertools import combinations

from hand_replay import (
    _player_folded_on_street,
    format_cards,
    parse_cards,
    replay_hand,
)
# Re-exported for callers that predate the hand_replay split.
from hand_replay import DEFAULT_HERO_UID, RAKE_TABLE, compute_rake  # noqa: F401

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


def convert_hand(hand: dict, hero_uid: str | None = None) -> str:
    """Convert a single hand JSON object to PokerStars hand history format.

    hero_uid: explicit override; if None, auto-detected from table.session_id
    (falls back to DEFAULT_HERO_UID when session_id isn't present, e.g. in tests).
    """
    r = replay_hand(hand, hero_uid=hero_uid, pokerstars_compat=True)
    lines = []
    seat_map = r.seat_map
    forced = r.forced

    # Timestamp (PT4 expects ET)
    dt = datetime.fromtimestamp(r.timestamp_ms / 1000.0, tz=ZoneInfo('America/New_York'))
    date_str = dt.strftime('%Y/%m/%d %H:%M:%S ET')

    # Header — truncate 19-digit ID to 12 digits for PT4 compatibility
    hand_id = str(int(hand['id']) % 1_000_000_000_000)
    lines.append(
        f"PokerStars Hand #{hand_id}: Hold'em No Limit ({fmt_amount(r.sb)}/{fmt_amount(r.bb)} USD) - {date_str}"
    )

    # Table line — readable name instead of raw numeric ID
    table_name = f"ClubWPT #{int(r.table['table_id']) % 100000}"
    lines.append(f"Table '{table_name}' {r.max_players}-max Seat #{r.btn_seat} is the button")

    # FIX: Seat lines use STARTING stacks (not ending)
    for p in sorted(r.players, key=lambda x: x['seat_no']):
        seat = p['seat_no'] + 1
        lines.append(f"Seat {seat}: {p['name']} ({fmt_amount(p['starting_stack'])} in chips)")

    # Antes — individual per player (skipped in heads-up where ante == SB)
    for seat_no in forced.ante_seats:
        lines.append(f"{seat_map[seat_no]['name']}: posts the ante {fmt_amount(forced.ante)}")

    # Blinds
    if forced.sb_seat is not None:
        lines.append(f"{seat_map[forced.sb_seat]['name']}: posts small blind {fmt_amount(forced.sb_amount)}")
    if forced.bb_seat is not None:
        lines.append(f"{seat_map[forced.bb_seat]['name']}: posts big blind {fmt_amount(forced.bb_amount)}")

    # NOTE: Straddle is handled as a synthetic preflop raise (not a blind line)
    # because PT4 doesn't support "posts the straddle" in PokerStars format.

    # Post seats (players who posted to enter) — always the BB amount, see
    # hand_replay for why the straddle amount must not be used here.
    for ps, amt in forced.posts:
        lines.append(f"{seat_map[ps]['name']}: posts big blind {fmt_amount(amt)}")

    # Hole cards
    lines.append("*** HOLE CARDS ***")
    if r.hero and r.hero.get('hand_cards'):
        hero_cards = parse_cards(r.hero['hand_cards'])
        lines.append(f"Dealt to {r.hero['name']} [{format_cards(hero_cards)}]")

    flop_cards = r.flop_cards
    turn_card = r.turn_card
    river_card = r.river_card

    straddle_rendered = False
    for street in r.streets:
        if street.type == 'flop' and flop_cards:
            lines.append(f"*** FLOP *** [{format_cards(flop_cards)}]")
        elif street.type == 'turn' and turn_card:
            lines.append(f"*** TURN *** [{format_cards(flop_cards)}] [{turn_card}]")
        elif street.type == 'river' and river_card:
            flop_turn = flop_cards + ([turn_card] if turn_card else [])
            lines.append(f"*** RIVER *** [{format_cards(flop_turn)}] [{river_card}]")

        if not street.actions:
            continue

        # Synthetic straddle as a preflop raise (PT4 can't parse "posts the straddle")
        if street.type == 'preflop' and forced.straddle_seat is not None and not straddle_rendered:
            straddle_rendered = True
            s_name = seat_map[forced.straddle_seat]['name']
            s_raise_by = forced.straddle_amount - r.bb
            lines.append(
                f"{s_name}: raises {fmt_amount(s_raise_by)} to {fmt_amount(forced.straddle_amount)}"
            )

        for action in street.actions:
            name = seat_map[action.seat_no]['name']
            if action.kind == 'fold':
                lines.append(f"{name}: folds")
            elif action.kind == 'check':
                lines.append(f"{name}: checks")
            else:
                if action.kind == 'call':
                    line = f"{name}: calls {fmt_amount(action.amount)}"
                elif action.kind == 'bet':
                    line = f"{name}: bets {fmt_amount(action.street_total)}"
                else:
                    line = (f"{name}: raises {fmt_amount(action.raise_by)} "
                            f"to {fmt_amount(action.street_total)}")
                if action.is_allin:
                    line += " and is all-in"
                lines.append(line)

    if r.uncalled_amount > 0 and r.uncalled_seat in seat_map:
        lines.append(
            f"Uncalled bet ({fmt_amount(r.uncalled_amount)}) returned to "
            f"{seat_map[r.uncalled_seat]['name']}"
        )

    # The "Total pot" line reports the gross pot while winners collect the pot
    # net of rake, matching PokerStars' format.
    community = r.community
    showdown_players = r.showdown_players
    winner_seats = r.winner_seats

    if showdown_players:
        lines.append("*** SHOW DOWN ***")
        for p in sorted(showdown_players, key=lambda x: x['seat_no']):
            cards = parse_cards(p['hand_cards'])
            _, hand_desc = evaluate_hand(cards, community)
            if not hand_desc:
                hand_desc = "a hand"
            if p['seat_no'] in winner_seats:
                collected = r.winner_share(p)
                lines.append(f"{p['name']}: shows [{format_cards(cards)}] ({hand_desc})")
                lines.append(f"{p['name']} collected {fmt_amount(collected)} from pot")
            else:
                lines.append(f"{p['name']}: shows [{format_cards(cards)}] ({hand_desc})")
    else:
        for w in r.winners:
            collected = r.winner_share(w)
            lines.append(f"{w['name']} collected {fmt_amount(collected)} from pot")
            if w.get('hand_cards') and not w.get('is_showdown'):
                lines.append(f"{w['name']}: doesn't show hand")

    # Summary
    lines.append("*** SUMMARY ***")
    lines.append(f"Total pot {fmt_amount(r.effective_pot)} | Rake {fmt_amount(r.rake)}")

    if community:
        lines.append(f"Board [{format_cards(community)}]")

    # Seat results
    for p in sorted(r.players, key=lambda x: x['seat_no']):
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
            won_amount = r.winner_share(p)
            lines.append(
                f"Seat {seat}: {name}{pos_str} showed [{format_cards(cards)}] "
                f"and won ({fmt_amount(won_amount)}) with {hand_desc}"
            )
        elif p['seat_no'] in winner_seats:
            won_amount = r.winner_share(p)
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
                                          r.sb_player, r.bb_player, r.straddle_player,
                                          r.has_straddle)
            lines.append(f"Seat {seat}: {name}{pos_str} {fold_desc}")
        else:
            lines.append(f"Seat {seat}: {name}{pos_str} mucked")

    return '\n'.join(lines)


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


def convert_hands_to_file(hands: list[dict], hero_uid: str | None = None) -> str:
    """Convert a list of hand objects to a single PokerStars HH file string."""
    converted = []
    for hand in hands:
        try:
            converted.append(convert_hand(hand, hero_uid=hero_uid))
        except Exception as e:
            print(f"Error converting hand {hand.get('id', 'unknown')}: {e}")
    return '\n\n\n'.join(converted) + '\n'
