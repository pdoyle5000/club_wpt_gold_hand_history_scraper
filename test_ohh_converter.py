"""Tests for the Open Hand History (OHH) converter."""

import copy
import json

import pytest

from hand_replay import replay_hand
from ohh_converter import (
    SPEC_VERSION, convert_hand_to_ohh, convert_hand_to_ohh_json,
    convert_hands_to_ohh_file, to_amount,
)
from test_converter import (
    HAND_10000302080, SAMPLE_HAND_1, SAMPLE_HAND_2,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def chips(amount: float) -> int:
    """Inverse of to_amount: 2.5 -> 250."""
    return int(round(amount * 100))


def ohh(hand: dict, **kwargs) -> dict:
    return convert_hand_to_ohh(copy.deepcopy(hand), **kwargs)['ohh']


def round_for(doc: dict, street: str) -> dict | None:
    return next((r for r in doc['rounds'] if r['street'] == street), None)


def actions_of(doc: dict, street: str, action: str) -> list[dict]:
    rnd = round_for(doc, street)
    return [a for a in (rnd['actions'] if rnd else []) if a['action'] == action]


def player_named(doc: dict, name: str) -> dict:
    return next(p for p in doc['players'] if p['name'] == name)


def contributions(doc: dict) -> dict[int, int]:
    """Total chips each player_id put in, across every round."""
    totals = {p['id']: 0 for p in doc['players']}
    for rnd in doc['rounds']:
        for a in rnd['actions']:
            totals[a['player_id']] += chips(a['amount'])
    return totals


# ---------------------------------------------------------------------------
# Document shape
# ---------------------------------------------------------------------------

class TestDocumentShape:
    def test_top_level_key_is_ohh(self):
        assert list(convert_hand_to_ohh(SAMPLE_HAND_1).keys()) == ['ohh']

    def test_required_fields_present(self):
        doc = ohh(SAMPLE_HAND_1)
        for field in ('spec_version', 'site_name', 'network_name', 'internal_version',
                      'tournament', 'game_number', 'start_date_utc', 'table_name',
                      'game_type', 'bet_limit', 'table_size', 'currency', 'dealer_seat',
                      'small_blind_amount', 'big_blind_amount', 'ante_amount',
                      'hero_player_id', 'flags', 'players', 'rounds', 'pots'):
            assert field in doc, f"missing required field {field}"

    def test_spec_version(self):
        doc = ohh(SAMPLE_HAND_1)
        assert doc['spec_version'] == SPEC_VERSION
        assert doc['internal_version'] == SPEC_VERSION

    def test_cash_game_not_tournament(self):
        assert ohh(SAMPLE_HAND_1)['tournament'] is False

    def test_game_number_keeps_full_api_id(self):
        """Unlike the PokerStars renderer, OHH has no 12-digit limit to work around."""
        assert ohh(SAMPLE_HAND_1)['game_number'] == "1297910741818527744"

    def test_start_date_is_utc_with_z_suffix(self):
        # 1784248922000 ms == 2026-07-17T00:42:02Z
        assert ohh(SAMPLE_HAND_1)['start_date_utc'] == "2026-07-17T00:42:02Z"

    def test_bet_limit_is_no_limit(self):
        assert ohh(SAMPLE_HAND_1)['bet_limit'] == {"bet_type": "NL", "bet_cap": 0.0}

    def test_blinds_and_ante_in_currency_units(self):
        doc = ohh(SAMPLE_HAND_1)
        assert doc['small_blind_amount'] == 0.20
        assert doc['big_blind_amount'] == 0.50
        assert doc['ante_amount'] == 0.20

    def test_table_size_and_dealer_seat(self):
        doc = ohh(SAMPLE_HAND_1)
        assert doc['table_size'] == 7
        # Ptaters is the BTN in seat_no 3, which is displayed seat 4
        assert doc['dealer_seat'] == 4

    def test_json_serializable(self):
        text = convert_hand_to_ohh_json(SAMPLE_HAND_1)
        assert json.loads(text)['ohh']['game_number'] == "1297910741818527744"


class TestPlayers:
    def test_ids_are_sequential_in_seat_order(self):
        doc = ohh(SAMPLE_HAND_1)
        assert [p['id'] for p in doc['players']] == list(range(len(doc['players'])))
        assert doc['players'] == sorted(doc['players'], key=lambda p: p['seat'])

    def test_seats_are_one_based(self):
        """seat_no 0 in the API is seat 1 at the table."""
        doc = ohh(SAMPLE_HAND_1)
        assert player_named(doc, 'Krabman1234')['seat'] == 1

    def test_starting_stacks_not_ending_stacks(self):
        """The API 'stack' is the ending stack; starting = stack - win_bet."""
        doc = ohh(SAMPLE_HAND_1)
        # Ptaters: ending 17528, win_bet 670 -> starting 16858
        assert player_named(doc, 'Ptaters')['starting_stack'] == 168.58

    def test_hero_player_id_points_at_hero(self):
        doc = ohh(SAMPLE_HAND_1)
        assert doc['hero_player_id'] == player_named(doc, 'Ptaters')['id']

    def test_hero_uid_override(self):
        doc = ohh(SAMPLE_HAND_1, hero_uid="302271")
        assert doc['hero_player_id'] == player_named(doc, 'Shmoosie')['id']


# ---------------------------------------------------------------------------
# Rounds and actions
# ---------------------------------------------------------------------------

class TestRounds:
    def test_streets_present_and_ordered(self):
        doc = ohh(SAMPLE_HAND_1)
        assert [r['street'] for r in doc['rounds']] == [
            'Preflop', 'Flop', 'Turn', 'River', 'Showdown']
        assert [r['id'] for r in doc['rounds']] == [0, 1, 2, 3, 4]

    def test_board_cards_split_across_rounds(self):
        doc = ohh(SAMPLE_HAND_1)
        assert round_for(doc, 'Preflop')['cards'] == []
        assert round_for(doc, 'Flop')['cards'] == ['Ks', 'Tc', '7h']
        assert round_for(doc, 'Turn')['cards'] == ['7d']
        assert round_for(doc, 'River')['cards'] == ['Ah']

    def test_action_numbers_restart_each_round(self):
        doc = ohh(SAMPLE_HAND_1)
        for rnd in doc['rounds']:
            numbers = [a['action_number'] for a in rnd['actions']]
            assert numbers == list(range(1, len(numbers) + 1))

    def test_no_showdown_round_when_nobody_shows(self):
        hand = copy.deepcopy(SAMPLE_HAND_1)
        for p in hand['players']:
            p['is_showdown'] = False
        assert round_for(ohh(hand), 'Showdown') is None

    def test_showdown_round_shows_cards(self):
        shows = actions_of(ohh(SAMPLE_HAND_1), 'Showdown', 'Shows Cards')
        assert {tuple(a['cards']) for a in shows} == {
            ('5c', '5s'), ('5h', '3h'), ('4s', '6d')}

    def test_hero_gets_dealt_cards_action(self):
        doc = ohh(SAMPLE_HAND_1)
        dealt = actions_of(doc, 'Preflop', 'Dealt Cards')
        assert len(dealt) == 1
        assert dealt[0]['cards'] == ['5c', '5s']
        assert dealt[0]['player_id'] == doc['hero_player_id']


class TestForcedBets:
    def test_antes_posted_individually(self):
        doc = ohh(SAMPLE_HAND_1)
        antes = actions_of(doc, 'Preflop', 'Post Ante')
        assert len(antes) == len(doc['players'])
        assert all(a['amount'] == 0.20 for a in antes)

    def test_blinds_posted(self):
        doc = ohh(SAMPLE_HAND_1)
        sb = actions_of(doc, 'Preflop', 'Post SB')
        bb = actions_of(doc, 'Preflop', 'Post BB')
        assert [a['amount'] for a in sb] == [0.20]
        assert [a['amount'] for a in bb] == [0.50]
        assert sb[0]['player_id'] == player_named(doc, 'Shmoosie')['id']
        assert bb[0]['player_id'] == player_named(doc, 'Gandalf92')['id']

    def test_straddle_is_a_straddle_not_a_raise(self):
        """The whole point of OHH here: no synthetic raise workaround."""
        doc = ohh(SAMPLE_HAND_1)
        straddles = actions_of(doc, 'Preflop', 'Straddle')
        assert len(straddles) == 1
        assert straddles[0]['amount'] == 1.00  # 2x the 0.50 big blind
        assert straddles[0]['player_id'] == player_named(doc, 'YNH9362')['id']

    def test_no_straddle_action_without_a_straddle(self):
        hand = copy.deepcopy(SAMPLE_HAND_1)
        hand['table']['has_straddle'] = False
        assert actions_of(ohh(hand), 'Preflop', 'Straddle') == []

    def test_forced_bets_precede_voluntary_action(self):
        rnd = round_for(ohh(SAMPLE_HAND_1), 'Preflop')
        forced = {'Post Ante', 'Post SB', 'Post BB', 'Post Extra Blind', 'Straddle'}
        last_forced = max(i for i, a in enumerate(rnd['actions']) if a['action'] in forced)
        first_voluntary = min(i for i, a in enumerate(rnd['actions'])
                              if a['action'] in {'Fold', 'Check', 'Call', 'Bet', 'Raise'})
        assert last_forced < first_voluntary


class TestActionAmounts:
    """OHH records the chips a player puts in *during that action* (spec:
    a re-raise to 20 after betting 2 has amount 18)."""

    def test_raise_amount_is_incremental(self):
        doc = ohh(SAMPLE_HAND_2)
        # SB re-raises to a street total of 1000 having already posted 20
        raises = actions_of(doc, 'Preflop', 'Raise')
        sb_raise = next(a for a in raises
                        if a['player_id'] == player_named(doc, 'TrashTripp')['id'])
        assert sb_raise['amount'] == 9.80

    def test_call_amount_is_incremental(self):
        doc = ohh(SAMPLE_HAND_2)
        # BTN raised to 250, faces 1000, so calls the 750 difference
        calls = actions_of(doc, 'Preflop', 'Call')
        btn_call = next(a for a in calls
                        if a['player_id'] == player_named(doc, 'Ptaters')['id'])
        assert btn_call['amount'] == 7.50

    def test_bet_amount(self):
        doc = ohh(SAMPLE_HAND_2)
        bets = actions_of(doc, 'River', 'Bet')
        assert [a['amount'] for a in bets] == [18.32]

    def test_folds_and_checks_have_zero_amount(self):
        doc = ohh(SAMPLE_HAND_1)
        for rnd in doc['rounds']:
            for a in rnd['actions']:
                if a['action'] in ('Fold', 'Check'):
                    assert a['amount'] == 0.0

    def test_preflop_check_below_the_bet_becomes_a_call(self):
        """The API reports limps and straddle-calls as 'check' with amount 0."""
        doc = ohh(HAND_10000302080)
        hj = player_named(doc, 'TheRealDealPhil')['id']
        preflop = round_for(doc, 'Preflop')['actions']
        voluntary = {'Fold', 'Check', 'Call', 'Bet', 'Raise'}
        hj_actions = [a for a in preflop
                      if a['player_id'] == hj and a['action'] in voluntary]
        assert [(a['action'], a['amount']) for a in hj_actions] == [('Call', 4.00)]

    def test_contributions_never_exceed_starting_stack(self):
        for hand in (SAMPLE_HAND_1, SAMPLE_HAND_2, HAND_10000302080):
            doc = ohh(hand)
            totals = contributions(doc)
            for p in doc['players']:
                assert totals[p['id']] <= chips(p['starting_stack'])

    def test_all_in_flag_set_only_when_stack_is_emptied(self):
        for hand in (SAMPLE_HAND_1, SAMPLE_HAND_2, HAND_10000302080):
            doc = ohh(hand)
            totals = contributions(doc)
            flagged = {a['player_id'] for rnd in doc['rounds'] for a in rnd['actions']
                       if a['is_allin']}
            for p in doc['players']:
                assert (p['id'] in flagged) == (totals[p['id']] == chips(p['starting_stack']))


# ---------------------------------------------------------------------------
# Pots
# ---------------------------------------------------------------------------

class TestPots:
    def test_pot_amount_is_gross_and_wins_are_net_of_rake(self):
        pot = ohh(SAMPLE_HAND_2)['pots'][0]
        won = sum(chips(w['win_amount']) for w in pot['player_wins'])
        assert won == chips(pot['amount']) - chips(pot['rake'])

    def test_contributed_rake_sums_to_rake(self):
        pot = ohh(SAMPLE_HAND_2)['pots'][0]
        assert sum(chips(w['contributed_rake']) for w in pot['player_wins']) == chips(pot['rake'])

    def test_pot_equals_contributions_less_the_uncalled_bet(self):
        for hand in (SAMPLE_HAND_1, SAMPLE_HAND_2, HAND_10000302080):
            doc = ohh(hand)
            r = replay_hand(copy.deepcopy(hand))
            assert (sum(contributions(doc).values()) - r.uncalled_amount
                    == chips(doc['pots'][0]['amount']))

    def test_each_players_net_matches_the_api(self):
        """win - contributed + uncalled returned == the API's reported net,
        less that player's share of the rake we re-apply."""
        for hand in (SAMPLE_HAND_1, SAMPLE_HAND_2, HAND_10000302080):
            doc = ohh(hand)
            r = replay_hand(copy.deepcopy(hand))
            totals = contributions(doc)
            wins = {w['player_id']: chips(w['win_amount']) for w in doc['pots'][0]['player_wins']}
            rakes = {w['player_id']: chips(w['contributed_rake'])
                     for w in doc['pots'][0]['player_wins']}
            by_seat = {p['seat'] - 1: p['id'] for p in doc['players']}
            for p in r.players:
                pid = by_seat[p['seat_no']]
                returned = r.uncalled_amount if p['seat_no'] == r.uncalled_seat else 0
                net = wins.get(pid, 0) - totals[pid] + returned
                assert net == p['win_bet'] - rakes.get(pid, 0)

    def test_winner_identified(self):
        doc = ohh(SAMPLE_HAND_2)
        wins = doc['pots'][0]['player_wins']
        assert [w['player_id'] for w in wins] == [player_named(doc, 'Ptaters')['id']]


# ---------------------------------------------------------------------------
# Forced-bet model: verified against the API's own hand_history[0].pot_size
# ---------------------------------------------------------------------------

class TestForcedBetModel:
    def _forced_total(self, hand):
        doc = ohh(hand)
        forced = {'Post Ante', 'Post SB', 'Post BB', 'Post Extra Blind', 'Straddle'}
        return sum(chips(a['amount']) for a in round_for(doc, 'Preflop')['actions']
                   if a['action'] in forced)

    def test_forced_money_matches_api_pot_size(self):
        for hand in (SAMPLE_HAND_1, SAMPLE_HAND_2, HAND_10000302080):
            assert self._forced_total(hand) == hand['hand_history'][0]['pot_size']

    def test_ante_charged_when_only_two_players_are_dealt_in(self):
        """The PokerStars renderer skips antes heads-up; that loses real money,
        so OHH charges them (the API's pot_size confirms they are paid)."""
        hand = copy.deepcopy(SAMPLE_HAND_1)
        hand['table']['max_players'] = 2
        hand['players'] = [p for p in hand['players'] if p['position'] in ('BTN', 'BB')]
        hand['hand_history'] = [{'type': 'preflop', 'pot_size': 0, 'actions': []}]
        doc = ohh(hand)
        assert len(actions_of(doc, 'Preflop', 'Post Ante')) == 2

    def test_button_posts_small_blind_when_no_seat_has_it(self):
        hand = copy.deepcopy(SAMPLE_HAND_1)
        hand['players'] = [p for p in hand['players'] if p['position'] in ('BTN', 'BB')]
        hand['hand_history'] = [{'type': 'preflop', 'pot_size': 0, 'actions': []}]
        doc = ohh(hand)
        sb = actions_of(doc, 'Preflop', 'Post SB')
        assert [a['player_id'] for a in sb] == [player_named(doc, 'Ptaters')['id']]

    def test_post_to_enter_matches_the_straddle(self):
        """A post-to-enter matches the opening bet, so in a straddle game it is
        the straddle. The PokerStars renderer has to understate it as a BB."""
        hand = copy.deepcopy(SAMPLE_HAND_1)
        hand['post_seats'] = [0]  # Krabman1234, position MP
        doc = ohh(hand)
        posts = actions_of(doc, 'Preflop', 'Post Extra Blind')
        assert [a['amount'] for a in posts] == [1.00]  # straddle, not the 0.50 BB

    def test_post_to_enter_is_a_big_blind_without_a_straddle(self):
        hand = copy.deepcopy(SAMPLE_HAND_1)
        hand['table']['has_straddle'] = False
        hand['post_seats'] = [0]
        doc = ohh(hand)
        posts = actions_of(doc, 'Preflop', 'Post Extra Blind')
        assert [a['amount'] for a in posts] == [0.50]


class TestUndeclaredPosts:
    """The API sometimes charges a post without listing the seat in
    `post_seats`; the shortfall against the player's reported net gives it away."""

    def _hand_with_hidden_post(self):
        # Krabman1234 (MP) folds preflop having paid ante + an unannounced post
        hand = copy.deepcopy(SAMPLE_HAND_1)
        hand['post_seats'] = []
        krab = next(p for p in hand['players'] if p['name'] == 'Krabman1234')
        krab['win_bet'] = -(20 + 100)  # ante + straddle-sized post
        krab['net'] = krab['win_bet']
        return hand

    def test_hidden_post_is_recovered(self):
        doc = ohh(self._hand_with_hidden_post())
        posts = actions_of(doc, 'Preflop', 'Post Extra Blind')
        assert [(a['player_id'], a['amount'])
                for a in posts] == [(player_named(doc, 'Krabman1234')['id'], 1.00)]

    def test_hidden_post_reconciles_the_players_net(self):
        hand = self._hand_with_hidden_post()
        doc = ohh(hand)
        pid = player_named(doc, 'Krabman1234')['id']
        assert contributions(doc)[pid] == 120

    def test_unexplained_shortfall_is_left_alone(self):
        """Only a shortfall of exactly one post is treated as a post."""
        hand = copy.deepcopy(SAMPLE_HAND_1)
        hand['post_seats'] = []
        krab = next(p for p in hand['players'] if p['name'] == 'Krabman1234')
        krab['win_bet'] = -(20 + 37)
        krab['net'] = krab['win_bet']
        assert actions_of(ohh(hand), 'Preflop', 'Post Extra Blind') == []


# ---------------------------------------------------------------------------
# File output
# ---------------------------------------------------------------------------

class TestFileOutput:
    def test_hands_separated_by_one_blank_line(self):
        text = convert_hands_to_ohh_file([SAMPLE_HAND_1, SAMPLE_HAND_2])
        parts = text.strip().split('\n\n')
        assert len(parts) == 2
        assert [json.loads(p)['ohh']['game_number'] for p in parts] == [
            "1297910741818527744", "1297910515140395008"]

    def test_file_ends_with_newline(self):
        assert convert_hands_to_ohh_file([SAMPLE_HAND_1]).endswith('\n')

    def test_bad_hand_is_skipped_not_fatal(self, capsys):
        text = convert_hands_to_ohh_file([{"id": "boom"}, SAMPLE_HAND_1])
        assert len(text.strip().split('\n\n')) == 1
        assert "Error converting hand boom" in capsys.readouterr().out


class TestToAmount:
    @pytest.mark.parametrize("chips_in,expected", [
        (0, 0.0), (1, 0.01), (20, 0.2), (250, 2.5), (100, 1.0), (9764, 97.64),
    ])
    def test_conversion(self, chips_in, expected):
        assert to_amount(chips_in) == expected
