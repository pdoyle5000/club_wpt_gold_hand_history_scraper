"""Tests for ClubWPT Gold hand history converter."""

import re
import pytest
from converter import (
    parse_cards, format_cards, evaluate_hand, fmt_amount,
    convert_hand,
)


# ---------------------------------------------------------------------------
# Utility function tests
# ---------------------------------------------------------------------------

class TestParseCards:
    def test_two_cards(self):
        assert parse_cards("5c5s") == ["5c", "5s"]

    def test_five_cards(self):
        assert parse_cards("KsTc7h7dAh") == ["Ks", "Tc", "7h", "7d", "Ah"]

    def test_empty(self):
        assert parse_cards("") == []

    def test_ten(self):
        assert parse_cards("TsTh") == ["Ts", "Th"]


class TestFormatCards:
    def test_two_cards(self):
        assert format_cards(["5c", "5s"]) == "5c 5s"

    def test_five_cards(self):
        assert format_cards(["Ks", "Tc", "7h"]) == "Ks Tc 7h"


class TestFmtAmount:
    def test_integer_dollar(self):
        assert fmt_amount(100) == "$1.00"

    def test_half_dollar(self):
        assert fmt_amount(50) == "$0.50"

    def test_cents(self):
        assert fmt_amount(20) == "$0.20"

    def test_large(self):
        assert fmt_amount(51000) == "$510.00"

    def test_fractional(self):
        assert fmt_amount(9764) == "$97.64"


class TestEvaluateHand:
    def test_pair(self):
        score, desc = evaluate_hand(["5c", "5s"], ["Ks", "Tc", "7h", "7d", "Ah"])
        assert "two pair" in desc

    def test_flush(self):
        score, desc = evaluate_hand(["As", "Ks"], ["Qs", "Js", "2s", "3h", "4h"])
        assert "flush" in desc.lower()

    def test_straight(self):
        score, desc = evaluate_hand(["9h", "8d"], ["7c", "6s", "5h", "2d", "3c"])
        assert "straight" in desc.lower()

    def test_full_house(self):
        score, desc = evaluate_hand(["As", "Ad"], ["Ah", "Kc", "Kd", "2s", "3h"])
        assert "full house" in desc.lower()

    def test_high_card(self):
        score, desc = evaluate_hand(["2h", "7d"], ["Ks", "Tc", "4s", "3h", "9c"])
        assert "high card" in desc.lower()

    def test_royal_flush(self):
        score, desc = evaluate_hand(["As", "Ks"], ["Qs", "Js", "Ts", "2h", "3h"])
        assert "Royal Flush" in desc


# ---------------------------------------------------------------------------
# Helper to extract pot from converted hand text
# ---------------------------------------------------------------------------

def extract_pot(text: str) -> float:
    """Extract the 'Total pot $X.XX' value from a converted hand."""
    m = re.search(r"Total pot \$(\d+\.\d+)", text)
    assert m, f"Could not find 'Total pot' in output:\n{text[-300:]}"
    return float(m.group(1))


def extract_uncalled(text: str) -> float | None:
    """Extract the 'Uncalled bet ($X.XX)' value, or None if not present."""
    m = re.search(r"Uncalled bet \(\$(\d+\.\d+)\)", text)
    return float(m.group(1)) if m else None


def has_line_containing(text: str, substring: str) -> bool:
    """Check if any line in text contains the substring."""
    return any(substring in line for line in text.split("\n"))


# ---------------------------------------------------------------------------
# Sample hands (known-good from test_convert.py)
# ---------------------------------------------------------------------------

SAMPLE_HAND_1 = {
    "id": "1297910741818527744",
    "hole_cards": "5c5s",
    "community_cards": "KsTc7h7dAh",
    "hand_score": 10000,
    "timestamp": 1784248922000,
    "table": {
        "currency": "diamond",
        "table_id": "1297816455151448064",
        "session_id": "",
        "table_name": "",
        "small_blind": 20,
        "big_blind": 50,
        "ante": 20,
        "has_straddle": True,
        "game_type_code": "nlhe",
        "max_players": 7,
        "stack_depth": "medium",
        "ante_size": "small",
    },
    "player_position": "BTN",
    "players": [
        {"uid": "266497", "name": "Krabman1234", "stack": 2060, "seat_no": 0, "position": "MP", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "328519", "name": "LimpRaise2233", "stack": 7670, "seat_no": 1, "position": "HJ", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "206394", "name": "DAD", "stack": 9980, "seat_no": 2, "position": "CO", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "235160", "name": "Ptaters", "stack": 17528, "seat_no": 3, "position": "BTN", "win_bet": 670, "net": 670, "hand_cards": "5c5s", "is_showdown": True, "is_showcard": True},
        {"uid": "302271", "name": "Shmoosie", "stack": 15247, "seat_no": 4, "position": "SB", "win_bet": -270, "net": -270, "hand_cards": "5h3h", "is_showdown": True, "is_showcard": True},
        {"uid": "437267", "name": "Gandalf92", "stack": 8172, "seat_no": 6, "position": "BB", "win_bet": -70, "net": -70, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "686184", "name": "YNH9362", "stack": 9366, "seat_no": 7, "position": "UTG", "win_bet": -270, "net": -270, "hand_cards": "4s6d", "is_showdown": True, "is_showcard": True},
    ],
    "hand_history": [
        {
            "type": "preflop",
            "pot_size": 310,
            "actions": [
                {"role": "MP", "type": "action", "action": "fold", "seatNo": 0, "totalBet": 0, "amount": 0},
                {"role": "HJ", "type": "action", "action": "fold", "seatNo": 1, "totalBet": 0, "amount": 0},
                {"role": "CO", "type": "action", "action": "fold", "seatNo": 2, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "raise", "seatNo": 3, "totalBet": 250, "amount": 250},
                {"role": "SB", "type": "action", "action": "call", "seatNo": 4, "totalBet": 230, "amount": 230},
                {"role": "BB", "type": "action", "action": "fold", "seatNo": 6, "totalBet": 0, "amount": 0},
                {"role": "UTG", "type": "action", "action": "call", "seatNo": 7, "totalBet": 150, "amount": 150},
            ],
        },
        {
            "type": "flop",
            "pot_size": 940,
            "actions": [
                {"role": "SB", "type": "action", "action": "check", "seatNo": 4, "totalBet": 0, "amount": 0},
                {"role": "UTG", "type": "action", "action": "check", "seatNo": 7, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "check", "seatNo": 3, "totalBet": 0, "amount": 0},
            ],
        },
        {
            "type": "turn",
            "pot_size": 940,
            "actions": [
                {"role": "SB", "type": "action", "action": "check", "seatNo": 4, "totalBet": 0, "amount": 0},
                {"role": "UTG", "type": "action", "action": "check", "seatNo": 7, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "check", "seatNo": 3, "totalBet": 0, "amount": 0},
            ],
        },
        {
            "type": "river",
            "pot_size": 940,
            "actions": [
                {"role": "SB", "type": "action", "action": "check", "seatNo": 4, "totalBet": 0, "amount": 0},
                {"role": "UTG", "type": "action", "action": "check", "seatNo": 7, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "check", "seatNo": 3, "totalBet": 0, "amount": 0},
            ],
        },
    ],
    "attributes": {"analysis_mode": 1},
    "win_amount_bb": 13.4,
    "post_seats": [],
    "analysis": {"bestCount": 4, "inaccurateCount": 0, "blunderCount": 0},
}


SAMPLE_HAND_2 = {
    "id": "1297910515140395008",
    "hole_cards": "As3s",
    "community_cards": "AcQcQsQh7s",
    "hand_score": 1478,
    "timestamp": 1784248868000,
    "table": {
        "currency": "diamond",
        "table_id": "1297873833233141760",
        "session_id": "",
        "table_name": "",
        "small_blind": 20,
        "big_blind": 50,
        "ante": 20,
        "has_straddle": True,
        "game_type_code": "nlhe",
        "max_players": 7,
        "stack_depth": "medium",
        "ante_size": "small",
    },
    "player_position": "BTN",
    "players": [
        {"uid": "509451", "name": "ComeAlongThen", "stack": 9860, "seat_no": 2, "position": "MP", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "680102", "name": "Indycards48", "stack": 4640, "seat_no": 3, "position": "HJ", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "635355", "name": "The original doc", "stack": 2220, "seat_no": 4, "position": "CO", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "235160", "name": "Ptaters", "stack": 14454, "seat_no": 5, "position": "BTN", "win_bet": 3102, "net": 3102, "hand_cards": "As3s", "is_showdown": True, "is_showcard": True},
        {"uid": "527897", "name": "TrashTripp", "stack": 12502, "seat_no": 6, "position": "SB", "win_bet": -2852, "net": -2852, "hand_cards": "8d8c", "is_showdown": True, "is_showcard": True},
        {"uid": "561387", "name": "12Whiskey", "stack": 4670, "seat_no": 7, "position": "BB", "win_bet": -70, "net": -70, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "307100", "name": "FRANCISPURU", "stack": 3826, "seat_no": 1, "position": "UTG", "win_bet": -120, "net": -120, "hand_cards": "", "is_showdown": False, "is_showcard": False},
    ],
    "hand_history": [
        {
            "type": "preflop",
            "pot_size": 310,
            "actions": [
                {"role": "MP", "type": "action", "action": "fold", "seatNo": 2, "totalBet": 0, "amount": 0},
                {"role": "HJ", "type": "action", "action": "fold", "seatNo": 3, "totalBet": 0, "amount": 0},
                {"role": "CO", "type": "action", "action": "fold", "seatNo": 4, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "raise", "seatNo": 5, "totalBet": 250, "amount": 250},
                {"role": "SB", "type": "action", "action": "raise", "seatNo": 6, "totalBet": 1000, "amount": 1000},
                {"role": "BB", "type": "action", "action": "fold", "seatNo": 7, "totalBet": 0, "amount": 0},
                {"role": "UTG", "type": "action", "action": "fold", "seatNo": 1, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "call", "seatNo": 5, "totalBet": 750, "amount": 750},
            ],
        },
        {
            "type": "flop",
            "pot_size": 2290,
            "actions": [
                {"role": "SB", "type": "action", "action": "check", "seatNo": 6, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "check", "seatNo": 5, "totalBet": 0, "amount": 0},
            ],
        },
        {
            "type": "turn",
            "pot_size": 2290,
            "actions": [
                {"role": "SB", "type": "action", "action": "check", "seatNo": 6, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "check", "seatNo": 5, "totalBet": 0, "amount": 0},
            ],
        },
        {
            "type": "river",
            "pot_size": 2290,
            "actions": [
                {"role": "SB", "type": "action", "action": "check", "seatNo": 6, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "bet", "seatNo": 5, "totalBet": 1832, "amount": 1832},
                {"role": "SB", "type": "action", "action": "call", "seatNo": 6, "totalBet": 1832, "amount": 1832},
            ],
        },
    ],
    "attributes": {"analysis_mode": 1},
    "win_amount_bb": 62.04,
    "post_seats": [],
    "analysis": {"bestCount": 4, "inaccurateCount": 0, "blunderCount": 1},
}


# ---------------------------------------------------------------------------
# 5 Error hands from PT4
# ---------------------------------------------------------------------------

# Bug A: Preflop "check" is actually implicit straddle call
# PT4 error: (25.00 vs pot: 23.00) — correct pot is $29.00
HAND_10000302080 = {
    "id": "1183572010000302080",
    "hole_cards": "8cTh",
    "community_cards": "8hJh9sJdKd",
    "hand_score": 10000,
    "timestamp": 1756988444000,
    "table": {
        "currency": "diamond",
        "table_id": "1183247118699175936",
        "session_id": "",
        "table_name": "HL5809",
        "small_blind": 100,
        "big_blind": 200,
        "ante": 100,
        "has_straddle": True,
        "game_type_code": "nlhe",
        "max_players": 6,
        "stack_depth": "medium",
        "ante_size": "small",
    },
    "player_position": "CO",
    "players": [
        {"uid": "467190", "name": "TheRealDealPhil", "stack": 25800, "seat_no": 3, "position": "HJ", "win_bet": 1800, "net": 1800, "hand_cards": "6cAs", "is_showdown": True, "is_showcard": True},
        {"uid": "235160", "name": "Ptaters", "stack": 61156, "seat_no": 5, "position": "CO", "win_bet": -100, "net": -100, "hand_cards": "8cTh", "is_showdown": False, "is_showcard": False},
        {"uid": "214801", "name": "WinEmAllJamal", "stack": 118552, "seat_no": 6, "position": "BTN", "win_bet": -100, "net": -100, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "278122", "name": "DEMONBOI", "stack": 40772, "seat_no": 7, "position": "SB", "win_bet": -200, "net": -200, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "311891", "name": "SILENTHAMSTER", "stack": 19588, "seat_no": 0, "position": "BB", "win_bet": -300, "net": -300, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "460829", "name": "NPL4EV", "stack": 38400, "seat_no": 1, "position": "UTG", "win_bet": -1100, "net": -1100, "hand_cards": "4h3d", "is_showdown": True, "is_showcard": True},
    ],
    "hand_history": [
        {
            "type": "preflop",
            "pot_size": 1300,
            "actions": [
                {"role": "HJ", "type": "action", "action": "check", "seatNo": 3, "totalBet": 0, "amount": 0},
                {"role": "CO", "type": "action", "action": "fold", "seatNo": 5, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "fold", "seatNo": 6, "totalBet": 0, "amount": 0},
                {"role": "SB", "type": "action", "action": "fold", "seatNo": 7, "totalBet": 0, "amount": 0},
                {"role": "BB", "type": "action", "action": "fold", "seatNo": 0, "totalBet": 0, "amount": 0},
                {"role": "UTG", "type": "action", "action": "check", "seatNo": 1, "totalBet": 0, "amount": 0},
            ],
        },
        {
            "type": "flop",
            "pot_size": 1700,
            "actions": [
                {"role": "UTG", "type": "action", "action": "check", "seatNo": 1, "totalBet": 0, "amount": 0},
                {"role": "HJ", "type": "action", "action": "check", "seatNo": 3, "totalBet": 0, "amount": 0},
            ],
        },
        {
            "type": "turn",
            "pot_size": 1700,
            "actions": [
                {"role": "UTG", "type": "action", "action": "bet", "seatNo": 1, "totalBet": 600, "amount": 600},
                {"role": "HJ", "type": "action", "action": "call", "seatNo": 3, "totalBet": 600, "amount": 600},
            ],
        },
        {
            "type": "river",
            "pot_size": 2900,
            "actions": [
                {"role": "UTG", "type": "action", "action": "check", "seatNo": 1, "totalBet": 0, "amount": 0},
                {"role": "HJ", "type": "action", "action": "check", "seatNo": 3, "totalBet": 0, "amount": 0},
            ],
        },
    ],
    "attributes": {"analysis_mode": 0},
    "win_amount_bb": -0.5,
    "post_seats": [],
    "analysis": {"bestCount": 1, "inaccurateCount": 0, "blunderCount": 0},
}


# Bug A: Preflop "check" is actually implicit straddle call
# PT4 error: (125.00 vs pot: 115.00) — correct pot is $145.00
HAND_520341741568 = {
    "id": "1183594520341741568",
    "hole_cards": "2d4h",
    "community_cards": "3h4s8d5h",
    "hand_score": 10000,
    "timestamp": 1756993811000,
    "table": {
        "currency": "diamond",
        "table_id": "1183526081857314816",
        "session_id": "",
        "table_name": "HL6452",
        "small_blind": 500,
        "big_blind": 1000,
        "ante": 500,
        "has_straddle": True,
        "game_type_code": "nlhe",
        "max_players": 6,
        "stack_depth": "medium",
        "ante_size": "small",
    },
    "player_position": "CO",
    "players": [
        {"uid": "378338", "name": "Tbeast587", "stack": 44500, "seat_no": 4, "position": "HJ", "win_bet": -5500, "net": -5500, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "235160", "name": "Ptaters", "stack": 238750, "seat_no": 5, "position": "CO", "win_bet": -500, "net": -500, "hand_cards": "2d4h", "is_showdown": False, "is_showcard": False},
        {"uid": "314812", "name": "strictly business", "stack": 435317, "seat_no": 0, "position": "BTN", "win_bet": -500, "net": -500, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "329161", "name": "ChoochMcdoogle", "stack": 364848, "seat_no": 1, "position": "SB", "win_bet": -1000, "net": -1000, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "235318", "name": "Teraphobia", "stack": 210516, "seat_no": 2, "position": "BB", "win_bet": -1500, "net": -1500, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "322671", "name": "ghostclicker", "stack": 261920, "seat_no": 3, "position": "UTG", "win_bet": 9000, "net": 9000, "hand_cards": "", "is_showdown": False, "is_showcard": False},
    ],
    "hand_history": [
        {
            "type": "preflop",
            "pot_size": 6500,
            "actions": [
                {"role": "HJ", "type": "action", "action": "check", "seatNo": 4, "totalBet": 0, "amount": 0},
                {"role": "CO", "type": "action", "action": "fold", "seatNo": 5, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "fold", "seatNo": 0, "totalBet": 0, "amount": 0},
                {"role": "SB", "type": "action", "action": "fold", "seatNo": 1, "totalBet": 0, "amount": 0},
                {"role": "BB", "type": "action", "action": "fold", "seatNo": 2, "totalBet": 0, "amount": 0},
                {"role": "UTG", "type": "action", "action": "check", "seatNo": 3, "totalBet": 0, "amount": 0},
            ],
        },
        {
            "type": "flop",
            "pot_size": 8500,
            "actions": [
                {"role": "UTG", "type": "action", "action": "bet", "seatNo": 3, "totalBet": 3000, "amount": 3000},
                {"role": "HJ", "type": "action", "action": "call", "seatNo": 4, "totalBet": 3000, "amount": 3000},
            ],
        },
        {
            "type": "turn",
            "pot_size": 14500,
            "actions": [
                {"role": "UTG", "type": "action", "action": "bet", "seatNo": 3, "totalBet": 9700, "amount": 9700},
                {"role": "HJ", "type": "action", "action": "fold", "seatNo": 4, "totalBet": 0, "amount": 0},
            ],
        },
    ],
    "attributes": {"analysis_mode": 0},
    "win_amount_bb": -0.5,
    "post_seats": [],
    "analysis": {"bestCount": 1, "inaccurateCount": 0, "blunderCount": 0},
}


# Bug B: All-in-for-less not detected as uncalled
# PT4 error: (1156.00 vs pot: 992.00) — correct pot is $992.00
HAND_905042599936 = {
    "id": "1183595905042599936",
    "hole_cards": "8c2s",
    "community_cards": "Th9dAhAs7c",
    "hand_score": 10000,
    "timestamp": 1756994141000,
    "table": {
        "currency": "diamond",
        "table_id": "1183526081857314816",
        "session_id": "",
        "table_name": "HL6452",
        "small_blind": 500,
        "big_blind": 1000,
        "ante": 500,
        "has_straddle": True,
        "game_type_code": "nlhe",
        "max_players": 6,
        "stack_depth": "medium",
        "ante_size": "small",
    },
    "player_position": "CO",
    "players": [
        {"uid": "378338", "name": "Tbeast587", "stack": 0, "seat_no": 4, "position": "HJ", "win_bet": -43100, "net": -43100, "hand_cards": "JcTs", "is_showdown": True, "is_showcard": True},
        {"uid": "235160", "name": "Ptaters", "stack": 227250, "seat_no": 5, "position": "CO", "win_bet": -500, "net": -500, "hand_cards": "8c2s", "is_showdown": False, "is_showcard": False},
        {"uid": "314812", "name": "strictly business", "stack": 449789, "seat_no": 0, "position": "BTN", "win_bet": -8500, "net": -8500, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "329161", "name": "ChoochMcdoogle", "stack": 399848, "seat_no": 1, "position": "SB", "win_bet": 56100, "net": 56100, "hand_cards": "JsJh", "is_showdown": True, "is_showcard": True},
        {"uid": "235318", "name": "Teraphobia", "stack": 220356, "seat_no": 2, "position": "BB", "win_bet": -1500, "net": -1500, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "322671", "name": "ghostclicker", "stack": 254840, "seat_no": 3, "position": "UTG", "win_bet": -2500, "net": -2500, "hand_cards": "", "is_showdown": False, "is_showcard": False},
    ],
    "hand_history": [
        {
            "type": "preflop",
            "pot_size": 6500,
            "actions": [
                {"role": "HJ", "type": "action", "action": "call", "seatNo": 4, "totalBet": 2000, "amount": 2000},
                {"role": "CO", "type": "action", "action": "fold", "seatNo": 5, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "call", "seatNo": 0, "totalBet": 2000, "amount": 2000},
                {"role": "SB", "type": "action", "action": "raise", "seatNo": 1, "totalBet": 8000, "amount": 8000},
                {"role": "BB", "type": "action", "action": "fold", "seatNo": 2, "totalBet": 0, "amount": 0},
                {"role": "UTG", "type": "action", "action": "fold", "seatNo": 3, "totalBet": 0, "amount": 0},
                {"role": "HJ", "type": "action", "action": "call", "seatNo": 4, "totalBet": 6000, "amount": 6000},
                {"role": "BTN", "type": "action", "action": "call", "seatNo": 0, "totalBet": 6000, "amount": 6000},
            ],
        },
        {
            "type": "flop",
            "pot_size": 30000,
            "actions": [
                {"role": "SB", "type": "action", "action": "bet", "seatNo": 1, "totalBet": 17000, "amount": 17000},
                {"role": "HJ", "type": "action", "action": "raise", "seatNo": 4, "totalBet": 34000, "amount": 34000},
                {"role": "BTN", "type": "action", "action": "fold", "seatNo": 0, "totalBet": 0, "amount": 0},
                {"role": "SB", "type": "action", "action": "raise", "seatNo": 1, "totalBet": 51000, "amount": 51000},
                {"role": "HJ", "type": "action", "action": "allin", "seatNo": 4, "totalBet": 34600, "amount": 34600},
            ],
        },
        {"type": "turn", "pot_size": 99200, "actions": []},
        {"type": "river", "pot_size": 99200, "actions": []},
    ],
    "attributes": {"analysis_mode": 0},
    "win_amount_bb": -0.5,
    "post_seats": [],
    "analysis": {"bestCount": 1, "inaccurateCount": 0, "blunderCount": 0},
}


# Bug B: All-in-for-less not detected as uncalled
# PT4 error: (3602.40 vs pot: 2739.80) — correct pot is $2739.80
HAND_71578529792 = {
    "id": "1183589071578529792",
    "hole_cards": "8sJs",
    "community_cards": "4sTcQsAc4d",
    "hand_score": 8750,
    "timestamp": 1756992512000,
    "table": {
        "currency": "diamond",
        "table_id": "1183526081857314816",
        "session_id": "",
        "table_name": "HL6452",
        "small_blind": 500,
        "big_blind": 1000,
        "ante": 500,
        "has_straddle": True,
        "game_type_code": "nlhe",
        "max_players": 4,
        "stack_depth": "medium",
        "ante_size": "small",
    },
    "player_position": "BB",
    "players": [
        {"uid": "329161", "name": "ChoochMcdoogle", "stack": 273980, "seat_no": 1, "position": "BTN", "win_bet": 138740, "net": 138740, "hand_cards": "Qc2c", "is_showdown": True, "is_showcard": True},
        {"uid": "322671", "name": "ghostclicker", "stack": 350920, "seat_no": 3, "position": "SB", "win_bet": -1000, "net": -1000, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "235160", "name": "Ptaters", "stack": 86260, "seat_no": 5, "position": "BB", "win_bet": -135240, "net": -135240, "hand_cards": "8sJs", "is_showdown": True, "is_showcard": True},
        {"uid": "314812", "name": "strictly business", "stack": 499047, "seat_no": 0, "position": "UTG", "win_bet": -2500, "net": -2500, "hand_cards": "", "is_showdown": False, "is_showcard": False},
    ],
    "hand_history": [
        {
            "type": "preflop",
            "pot_size": 5500,
            "actions": [
                {"role": "BTN", "type": "action", "action": "raise", "seatNo": 1, "totalBet": 5000, "amount": 5000},
                {"role": "SB", "type": "action", "action": "fold", "seatNo": 3, "totalBet": 0, "amount": 0},
                {"role": "BB", "type": "action", "action": "call", "seatNo": 5, "totalBet": 4000, "amount": 4000},
                {"role": "UTG", "type": "action", "action": "fold", "seatNo": 0, "totalBet": 0, "amount": 0},
            ],
        },
        {
            "type": "flop",
            "pot_size": 14500,
            "actions": [
                {"role": "BB", "type": "action", "action": "check", "seatNo": 5, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "bet", "seatNo": 1, "totalBet": 9400, "amount": 9400},
                {"role": "BB", "type": "action", "action": "raise", "seatNo": 5, "totalBet": 30000, "amount": 30000},
                {"role": "BTN", "type": "action", "action": "raise", "seatNo": 1, "totalBet": 77500, "amount": 77500},
                {"role": "BB", "type": "action", "action": "allin", "seatNo": 5, "totalBet": 216000, "amount": 216000},
                {"role": "BTN", "type": "action", "action": "allin", "seatNo": 1, "totalBet": 129740, "amount": 129740},
            ],
        },
        {"type": "turn", "pot_size": 273980, "actions": []},
        {"type": "river", "pot_size": 273980, "actions": []},
    ],
    "attributes": {"analysis_mode": 0},
    "win_amount_bb": -135.24,
    "post_seats": [],
    "analysis": {"bestCount": 3, "inaccurateCount": 1, "blunderCount": 0},
}


# Bug B: All-in-for-less not detected as uncalled
# PT4 error: (252.64 vs pot: 210.28) — correct pot is $210.28
HAND_141179609088 = {
    "id": "1183576141179609088",
    "hole_cards": "QdAc",
    "community_cards": "8cTh7s6cTc",
    "hand_score": 10000,
    "timestamp": 1756989429000,
    "table": {
        "currency": "diamond",
        "table_id": "1183247118699175936",
        "session_id": "",
        "table_name": "HL5809",
        "small_blind": 100,
        "big_blind": 200,
        "ante": 100,
        "has_straddle": True,
        "game_type_code": "nlhe",
        "max_players": 8,
        "stack_depth": "deep",
        "ante_size": "small",
    },
    "player_position": "MP",
    "players": [
        {"uid": "326267", "name": "thetakeover", "stack": 38900, "seat_no": 4, "position": "UTG1", "win_bet": -100, "net": -100, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "235160", "name": "Ptaters", "stack": 76404, "seat_no": 5, "position": "MP", "win_bet": -9864, "net": -9864, "hand_cards": "QdAc", "is_showdown": True, "is_showcard": True},
        {"uid": "218599", "name": "Fullmetal44", "stack": 39800, "seat_no": 6, "position": "HJ", "win_bet": -100, "net": -100, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "252026", "name": "Qbanguy5450", "stack": 19500, "seat_no": 7, "position": "CO", "win_bet": -500, "net": -500, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "311891", "name": "SILENTHAMSTER", "stack": 21428, "seat_no": 0, "position": "BTN", "win_bet": 11564, "net": 11564, "hand_cards": "Kh9h", "is_showdown": True, "is_showcard": True},
        {"uid": "377143", "name": "PokerNinjaLar", "stack": 39800, "seat_no": 1, "position": "SB", "win_bet": -200, "net": -200, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "224235", "name": "Savage0212", "stack": 38700, "seat_no": 2, "position": "BB", "win_bet": -300, "net": -300, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "209559", "name": "Young", "stack": 28288, "seat_no": 3, "position": "UTG", "win_bet": -500, "net": -500, "hand_cards": "", "is_showdown": False, "is_showcard": False},
    ],
    "hand_history": [
        {
            "type": "preflop",
            "pot_size": 1500,
            "actions": [
                {"role": "UTG1", "type": "action", "action": "fold", "seatNo": 4, "totalBet": 0, "amount": 0},
                {"role": "MP", "type": "action", "action": "raise", "seatNo": 5, "totalBet": 1200, "amount": 1200},
                {"role": "HJ", "type": "action", "action": "fold", "seatNo": 6, "totalBet": 0, "amount": 0},
                {"role": "CO", "type": "action", "action": "fold", "seatNo": 7, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "raise", "seatNo": 0, "totalBet": 3600, "amount": 3600},
                {"role": "SB", "type": "action", "action": "fold", "seatNo": 1, "totalBet": 0, "amount": 0},
                {"role": "BB", "type": "action", "action": "fold", "seatNo": 2, "totalBet": 0, "amount": 0},
                {"role": "UTG", "type": "action", "action": "fold", "seatNo": 3, "totalBet": 0, "amount": 0},
                {"role": "MP", "type": "action", "action": "raise", "seatNo": 5, "totalBet": 14000, "amount": 14000},
                {"role": "BTN", "type": "action", "action": "allin", "seatNo": 0, "totalBet": 9764, "amount": 9764},
            ],
        },
        {"type": "flop", "pot_size": 21428, "actions": []},
        {"type": "turn", "pot_size": 21428, "actions": []},
        {"type": "river", "pot_size": 21428, "actions": []},
    ],
    "attributes": {"analysis_mode": 0},
    "win_amount_bb": -49.32,
    "post_seats": [],
    "analysis": {"bestCount": 2, "inaccurateCount": 0, "blunderCount": 0},
}


# ---------------------------------------------------------------------------
# Tests for known-good sample hands
# ---------------------------------------------------------------------------

class TestSampleHands:
    def test_hand1_converts(self):
        text = convert_hand(SAMPLE_HAND_1)
        assert "PokerStars Hand #" in text
        assert "Ptaters" in text
        assert "*** SHOW DOWN ***" in text

    def test_hand1_pot(self):
        """Hand 1: checked-down straddle pot.
        Antes: 7*20=140, SB:20, BB:50, straddle:100.
        BTN raise to 250 (additional=250), SB call 230, UTG call 150.
        Preflop total: 140+20+50+100+250+230+150 = 940.
        All streets checked down. No uncalled.
        Pot should be $9.40.
        """
        text = convert_hand(SAMPLE_HAND_1)
        assert extract_pot(text) == 9.40

    def test_hand2_converts(self):
        text = convert_hand(SAMPLE_HAND_2)
        assert "PokerStars Hand #" in text
        assert "Ptaters" in text

    def test_hand2_pot(self):
        """Hand 2: 3-bet pot, river bet+call.
        Antes: 7*20=140, SB:20, BB:50, straddle:100.
        BTN raise to 250, SB raise to 1000 (additional=980), UTG fold, BTN call 750.
        Preflop: 140+20+50+100+250+980+750 = 2290.
        Flop/Turn: checks.
        River: BTN bets 1832, SB calls 1832. +3664.
        Total: 2290+3664 = 5954. $59.54.
        """
        text = convert_hand(SAMPLE_HAND_2)
        assert extract_pot(text) == 59.54


# ---------------------------------------------------------------------------
# Tests for Bug A: Preflop check as implicit straddle call
# ---------------------------------------------------------------------------

class TestBugAStraddleCheck:
    def test_hand_10000302080_pot(self):
        """HJ 'checks' preflop in straddle game = call of straddle.
        Antes: 6*100=600, SB:100, BB:200, straddle:400, HJ call:400.
        After preflop: 1700. Turn: +600+600=1200. Total: 2900. $29.00.
        """
        text = convert_hand(HAND_10000302080)
        assert extract_pot(text) == 29.00

    def test_hand_10000302080_no_illegal_check(self):
        """HJ should NOT have a 'checks' line on preflop after straddle raise.
        (HJ may still legitimately check on later streets.)"""
        text = convert_hand(HAND_10000302080)
        # Extract the preflop section (before *** FLOP ***)
        preflop_section = text.split("*** FLOP ***")[0]
        assert not has_line_containing(preflop_section, "TheRealDealPhil: checks"), \
            "HJ should call the straddle preflop, not check"
        # HJ should call $4.00 (straddle amount)
        assert has_line_containing(preflop_section, "TheRealDealPhil: calls $4.00")

    def test_hand_10000302080_utg_still_checks(self):
        """UTG (straddle player) should still check their option."""
        text = convert_hand(HAND_10000302080)
        assert has_line_containing(text, "NPL4EV: checks")

    def test_hand_520341741568_pot(self):
        """HJ 'checks' preflop in straddle game = call of straddle.
        Antes: 6*500=3000, SB:500, BB:1000, straddle:2000, HJ call:2000.
        After preflop: 8500. Flop: +3000+3000=6000. Turn: +9700 uncalled.
        Total: 8500+6000+9700=24200. Uncalled: 9700. Effective: 14500. $145.00.
        """
        text = convert_hand(HAND_520341741568)
        assert extract_pot(text) == 145.00

    def test_hand_520341741568_hj_calls(self):
        """HJ should call $20.00 instead of checking."""
        text = convert_hand(HAND_520341741568)
        assert has_line_containing(text, "Tbeast587: calls $20.00")


# ---------------------------------------------------------------------------
# Tests for Bug B: All-in-for-less uncalled bet
# ---------------------------------------------------------------------------

class TestBugBAllinForLess:
    def test_hand_905042599936_pot(self):
        """SB raises to 51000, HJ allins 34600 (for less). Uncalled = 16400.
        Total from actions: 115600. Effective: 115600-16400=99200. $992.00.
        """
        text = convert_hand(HAND_905042599936)
        assert extract_pot(text) == 992.00

    def test_hand_905042599936_uncalled(self):
        """Uncalled bet should be $164.00 returned to ChoochMcdoogle (SB)."""
        text = convert_hand(HAND_905042599936)
        uncalled = extract_uncalled(text)
        assert uncalled == 164.00
        assert has_line_containing(text, "Uncalled bet ($164.00) returned to ChoochMcdoogle")

    def test_hand_71578529792_pot(self):
        """BB allins 216000, BTN allins 129740 (for less). Uncalled = 86260.
        Total from actions: 360240. Effective: 360240-86260=273980. $2739.80.
        """
        text = convert_hand(HAND_71578529792)
        assert extract_pot(text) == 2739.80

    def test_hand_71578529792_uncalled(self):
        """Uncalled bet should be $862.60 returned to Ptaters (BB)."""
        text = convert_hand(HAND_71578529792)
        uncalled = extract_uncalled(text)
        assert uncalled == 862.60
        assert has_line_containing(text, "Uncalled bet ($862.60) returned to Ptaters")

    def test_hand_141179609088_pot(self):
        """MP raises to 14000, BTN allins 9764 (for less). Uncalled = 4236.
        Total from actions: 25264. Effective: 25264-4236=21028. $210.28.
        """
        text = convert_hand(HAND_141179609088)
        assert extract_pot(text) == 210.28

    def test_hand_141179609088_uncalled(self):
        """Uncalled bet should be $42.36 returned to Ptaters (MP)."""
        text = convert_hand(HAND_141179609088)
        uncalled = extract_uncalled(text)
        assert uncalled == 42.36
        assert has_line_containing(text, "Uncalled bet ($42.36) returned to Ptaters")




# ---------------------------------------------------------------------------
# Error Set 2: Forced preflop bets causing phantom uncalled bets
# ---------------------------------------------------------------------------

# Hand #933391179776: HJ allins 5300, UTG (straddle) calls 4900.
# UTG's total = straddle(400) + call(4900) = 5300, matching HJ.
# Correct pot: $127.00 (no uncalled). PT4 error was (123.00 vs pot: 127.00).
HAND_933391179776 = {
    "id": "1190925933391179776",
    "hole_cards": "Qd5d",
    "community_cards": "7d7h6c6dJd",
    "hand_score": 10000,
    "timestamp": 1758741756000,
    "table": {
        "currency": "diamond",
        "table_id": "1190909860056436736",
        "session_id": "",
        "table_name": "HL2684",
        "small_blind": 100,
        "big_blind": 200,
        "ante": 100,
        "has_straddle": True,
        "game_type_code": "nlhe",
        "max_players": 8,
        "stack_depth": "medium",
        "ante_size": "small",
    },
    "player_position": "UTG1",
    "players": [
        {"uid": "235160", "name": "Ptaters", "stack": 43020, "seat_no": 5, "position": "UTG1", "win_bet": -100, "net": -100, "hand_cards": "Qd5d", "is_showdown": False, "is_showcard": False},
        {"uid": "225219", "name": "Layna", "stack": 39900, "seat_no": 6, "position": "MP", "win_bet": -1100, "net": -1100, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "370459", "name": "GabeRid", "stack": 0, "seat_no": 7, "position": "HJ", "win_bet": -5400, "net": -5400, "hand_cards": "TcTh", "is_showdown": True, "is_showcard": True},
        {"uid": "303250", "name": "OW", "stack": 41696, "seat_no": 0, "position": "CO", "win_bet": -100, "net": -100, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "298547", "name": "SketchyBonerPills", "stack": 52372, "seat_no": 1, "position": "BTN", "win_bet": -100, "net": -100, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "327452", "name": "RASKOL", "stack": 49300, "seat_no": 2, "position": "SB", "win_bet": -200, "net": -200, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "362373", "name": "Gtg1", "stack": 43464, "seat_no": 3, "position": "BB", "win_bet": -300, "net": -300, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "311174", "name": "Gameboy5050", "stack": 46800, "seat_no": 4, "position": "UTG", "win_bet": 7300, "net": 7300, "hand_cards": "KdKs", "is_showdown": True, "is_showcard": True},
    ],
    "hand_history": [
        {
            "type": "preflop",
            "pot_size": 1500,
            "actions": [
                {"role": "UTG1", "type": "action", "action": "fold", "seatNo": 5, "totalBet": 0, "amount": 0},
                {"role": "MP", "type": "action", "action": "raise", "seatNo": 6, "totalBet": 1000, "amount": 1000},
                {"role": "HJ", "type": "action", "action": "allin", "seatNo": 7, "totalBet": 5300, "amount": 5300},
                {"role": "CO", "type": "action", "action": "fold", "seatNo": 0, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "fold", "seatNo": 1, "totalBet": 0, "amount": 0},
                {"role": "SB", "type": "action", "action": "fold", "seatNo": 2, "totalBet": 0, "amount": 0},
                {"role": "BB", "type": "action", "action": "fold", "seatNo": 3, "totalBet": 0, "amount": 0},
                {"role": "UTG", "type": "action", "action": "call", "seatNo": 4, "totalBet": 4900, "amount": 4900},
                {"role": "MP", "type": "action", "action": "fold", "seatNo": 6, "totalBet": 0, "amount": 0},
            ],
        },
        {"type": "flop", "pot_size": 12700, "actions": []},
        {"type": "turn", "pot_size": 12700, "actions": []},
        {"type": "river", "pot_size": 12700, "actions": []},
    ],
    "attributes": {"analysis_mode": 0},
    "win_amount_bb": -0.5,
    "post_seats": [],
    "analysis": {"bestCount": 1, "inaccurateCount": 0, "blunderCount": 0},
}


# Hand #939622334464: MP allins 13860, BB calls 13660, UTG allins 17006, BB calls 3146.
# All allins were fully called. Correct pot: $487.72 (no uncalled).
# PT4 error was (485.72 vs pot: 487.72).
HAND_939622334464 = {
    "id": "1190637939622334464",
    "hole_cards": "7d6c",
    "community_cards": "3s7sKsAsKh",
    "hand_score": 10000,
    "timestamp": 1758673093000,
    "table": {
        "currency": "diamond",
        "table_id": "1190625486635790336",
        "session_id": "",
        "table_name": "HL5755",
        "small_blind": 100,
        "big_blind": 200,
        "ante": 100,
        "has_straddle": True,
        "game_type_code": "nlhe",
        "max_players": 8,
        "stack_depth": "medium",
        "ante_size": "small",
    },
    "player_position": "CO",
    "players": [
        {"uid": "455890", "name": "LightningSorcerer", "stack": 39300, "seat_no": 4, "position": "UTG1", "win_bet": -100, "net": -100, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "445429", "name": "ScoopsCallahan", "stack": 0, "seat_no": 5, "position": "MP", "win_bet": -13960, "net": -13960, "hand_cards": "4c5c", "is_showdown": True, "is_showcard": True},
        {"uid": "230489", "name": "FlopASet", "stack": 39900, "seat_no": 6, "position": "HJ", "win_bet": -100, "net": -100, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "235160", "name": "Ptaters", "stack": 43824, "seat_no": 7, "position": "CO", "win_bet": -100, "net": -100, "hand_cards": "7d6c", "is_showdown": False, "is_showcard": False},
        {"uid": "214540", "name": "LickMyTaint", "stack": 111312, "seat_no": 0, "position": "BTN", "win_bet": -100, "net": -100, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "222795", "name": "Sickmyduck", "stack": 9800, "seat_no": 1, "position": "SB", "win_bet": -200, "net": -200, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "284033", "name": "ILOVELIMP", "stack": 57214, "seat_no": 2, "position": "BB", "win_bet": -17106, "net": -17106, "hand_cards": "JhAc", "is_showdown": True, "is_showcard": True},
        {"uid": "201588", "name": "Quack", "stack": 48772, "seat_no": 3, "position": "UTG", "win_bet": 31666, "net": 31666, "hand_cards": "8c8s", "is_showdown": True, "is_showcard": True},
    ],
    "hand_history": [
        {
            "type": "preflop",
            "pot_size": 1500,
            "actions": [
                {"role": "UTG1", "type": "action", "action": "fold", "seatNo": 4, "totalBet": 0, "amount": 0},
                {"role": "MP", "type": "action", "action": "allin", "seatNo": 5, "totalBet": 13860, "amount": 13860},
                {"role": "HJ", "type": "action", "action": "fold", "seatNo": 6, "totalBet": 0, "amount": 0},
                {"role": "CO", "type": "action", "action": "fold", "seatNo": 7, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "fold", "seatNo": 0, "totalBet": 0, "amount": 0},
                {"role": "SB", "type": "action", "action": "fold", "seatNo": 1, "totalBet": 0, "amount": 0},
                {"role": "BB", "type": "action", "action": "call", "seatNo": 2, "totalBet": 13660, "amount": 13660},
                {"role": "UTG", "type": "action", "action": "allin", "seatNo": 3, "totalBet": 17006, "amount": 17006},
                {"role": "BB", "type": "action", "action": "call", "seatNo": 2, "totalBet": 3146, "amount": 3146},
            ],
        },
        {"type": "flop", "pot_size": 42480, "actions": []},
        {"type": "turn", "pot_size": 42480, "actions": []},
        {"type": "river", "pot_size": 42480, "actions": []},
    ],
    "attributes": {"analysis_mode": 0},
    "win_amount_bb": -0.5,
    "post_seats": [],
    "analysis": {"bestCount": 1, "inaccurateCount": 0, "blunderCount": 0},
}


# ---------------------------------------------------------------------------
# Integration tests for Error Set 2 hands
# ---------------------------------------------------------------------------

class TestErrorSet2ForcedBets:
    def test_hand_933391179776_pot(self):
        """HJ allins 5300, UTG calls 4900 (straddle+call=5300). No uncalled.
        Antes: 8*100=800, SB:100, BB:200, straddle:400, MP raise:1000,
        HJ allin:5300, UTG call:4900. Total: 12700. $127.00.
        """
        text = convert_hand(HAND_933391179776)
        assert extract_pot(text) == 127.00

    def test_hand_933391179776_no_uncalled(self):
        """UTG call fully matches HJ allin — no uncalled bet."""
        text = convert_hand(HAND_933391179776)
        assert extract_uncalled(text) is None

    def test_hand_939622334464_pot(self):
        """MP allins 13860, BB calls, UTG allins 17006, BB calls. No uncalled.
        Antes: 8*100=800, SB:100, BB:200, straddle:400,
        MP allin:13860, BB call:13660, UTG allin additional:16606, BB call:3146.
        Total: 48772. $487.72.
        """
        text = convert_hand(HAND_939622334464)
        assert extract_pot(text) == 487.72

    def test_hand_939622334464_no_uncalled(self):
        """BB call fully matches UTG allin — no uncalled bet."""
        text = convert_hand(HAND_939622334464)
        assert extract_uncalled(text) is None


# ---------------------------------------------------------------------------
# Error Set 3: Heads-up SB + All-in-for-less call
# ---------------------------------------------------------------------------

# Heads-up hand: 2-max, no straddle, SB=20, BB=50, ante=20.
# BTN is the SB in heads-up. PT4 expects no antes, just SB+BB.
# PT4 error was (1.20 vs pot: 1.00).
HAND_43959074816 = {
    "id": "1215183043959074816",
    "hole_cards": "Td7s",
    "community_cards": "Ah8c6h6sTh",
    "hand_score": 10000,
    "timestamp": 1764525102000,
    "table": {
        "currency": "diamond",
        "table_id": "1215177773043466240",
        "session_id": "",
        "table_name": "HL9237",
        "small_blind": 20,
        "big_blind": 50,
        "ante": 20,
        "has_straddle": False,
        "game_type_code": "nlhe",
        "max_players": 2,
        "stack_depth": "deep",
        "ante_size": "small",
    },
    "player_position": "BB",
    "players": [
        {"uid": "364987", "name": "Bvamerica97", "stack": 2300, "seat_no": 3, "position": "BTN", "win_bet": -70, "net": -70, "hand_cards": "2sJs", "is_showdown": True, "is_showcard": True},
        {"uid": "235160", "name": "Ptaters", "stack": 10929, "seat_no": 4, "position": "BB", "win_bet": 70, "net": 70, "hand_cards": "Td7s", "is_showdown": True, "is_showcard": True},
    ],
    "hand_history": [
        {
            "type": "preflop",
            "pot_size": 110,
            "actions": [
                {"role": "BTN", "type": "action", "action": "call", "seatNo": 3, "totalBet": 30, "amount": 30},
                {"role": "BB", "type": "action", "action": "check", "seatNo": 4, "totalBet": 0, "amount": 0},
            ],
        },
        {"type": "flop", "pot_size": 140, "actions": [
            {"role": "BB", "type": "action", "action": "check", "seatNo": 4, "totalBet": 0, "amount": 0},
            {"role": "BTN", "type": "action", "action": "check", "seatNo": 3, "totalBet": 0, "amount": 0},
        ]},
        {"type": "turn", "pot_size": 140, "actions": [
            {"role": "BB", "type": "action", "action": "check", "seatNo": 4, "totalBet": 0, "amount": 0},
            {"role": "BTN", "type": "action", "action": "check", "seatNo": 3, "totalBet": 0, "amount": 0},
        ]},
        {"type": "river", "pot_size": 140, "actions": [
            {"role": "BB", "type": "action", "action": "check", "seatNo": 4, "totalBet": 0, "amount": 0},
            {"role": "BTN", "type": "action", "action": "check", "seatNo": 3, "totalBet": 0, "amount": 0},
        ]},
    ],
    "attributes": {"analysis_mode": 0},
    "win_amount_bb": 1.4,
    "post_seats": [],
    "analysis": {"bestCount": 4, "inaccurateCount": 0, "blunderCount": 0},
}


# Heads-up hand with turn bet/fold: uncalled bet on turn.
# PT4 error was (15.00 vs pot: 14.80).
HAND_735670153216 = {
    "id": "1215200735670153216",
    "hole_cards": "QcKs",
    "community_cards": "Jh6sJcAh",
    "hand_score": 10000,
    "timestamp": 1764529320000,
    "table": {
        "currency": "diamond",
        "table_id": "1215166070925115392",
        "session_id": "",
        "table_name": "HL9205",
        "small_blind": 20,
        "big_blind": 50,
        "ante": 20,
        "has_straddle": False,
        "game_type_code": "nlhe",
        "max_players": 2,
        "stack_depth": "deep",
        "ante_size": "small",
    },
    "player_position": "BB",
    "players": [
        {"uid": "378882", "name": "Fred52", "stack": 9606, "seat_no": 7, "position": "BTN", "win_bet": 760, "net": 760, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "235160", "name": "Ptaters", "stack": 13283, "seat_no": 1, "position": "BB", "win_bet": -760, "net": -760, "hand_cards": "QcKs", "is_showdown": False, "is_showcard": False},
    ],
    "hand_history": [
        {
            "type": "preflop",
            "pot_size": 110,
            "actions": [
                {"role": "BTN", "type": "action", "action": "call", "seatNo": 7, "totalBet": 30, "amount": 30},
                {"role": "BB", "type": "action", "action": "raise", "seatNo": 1, "totalBet": 200, "amount": 200},
                {"role": "BTN", "type": "action", "action": "call", "seatNo": 7, "totalBet": 150, "amount": 150},
            ],
        },
        {"type": "flop", "pot_size": 440, "actions": [
            {"role": "BB", "type": "action", "action": "bet", "seatNo": 1, "totalBet": 220, "amount": 220},
            {"role": "BTN", "type": "action", "action": "raise", "seatNo": 7, "totalBet": 540, "amount": 540},
            {"role": "BB", "type": "action", "action": "call", "seatNo": 1, "totalBet": 320, "amount": 320},
        ]},
        {"type": "turn", "pot_size": 1520, "actions": [
            {"role": "BB", "type": "action", "action": "check", "seatNo": 1, "totalBet": 0, "amount": 0},
            {"role": "BTN", "type": "action", "action": "bet", "seatNo": 7, "totalBet": 1140, "amount": 1140},
            {"role": "BB", "type": "action", "action": "fold", "seatNo": 1, "totalBet": 0, "amount": 0},
        ]},
    ],
    "attributes": {"analysis_mode": 1},
    "win_amount_bb": -15.2,
    "post_seats": [],
    "analysis": {"bestCount": 5, "inaccurateCount": 0, "blunderCount": 0},
}


# 8-max hand with all-in-for-less CALL (not allin action).
# BB allins 13097, UTG calls 10210 but only has 8010 remaining (capped).
# Uncalled should be 13097 - 10210 = 2887. PT4 error was (238.67 vs pot: 209.80).
HAND_177876987904 = {
    "id": "1215188177876987904",
    "hole_cards": "KcKd",
    "community_cards": "8cQh9cJh9h",
    "hand_score": 5000,
    "timestamp": 1764526326000,
    "table": {
        "currency": "diamond",
        "table_id": "1215168335862562816",
        "session_id": "",
        "table_name": "HL9210",
        "small_blind": 20,
        "big_blind": 50,
        "ante": 20,
        "has_straddle": True,
        "game_type_code": "nlhe",
        "max_players": 8,
        "stack_depth": "medium",
        "ante_size": "small",
    },
    "player_position": "UTG",
    "players": [
        {"uid": "225291", "name": "Bourbon", "stack": 18480, "seat_no": 3, "position": "UTG1", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "368157", "name": "drippysauce", "stack": 3880, "seat_no": 4, "position": "MP", "win_bet": -120, "net": -120, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "395108", "name": "MikieB", "stack": 10571, "seat_no": 5, "position": "HJ", "win_bet": -120, "net": -120, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "254112", "name": "EvaElfie", "stack": 9880, "seat_no": 6, "position": "CO", "win_bet": -120, "net": -120, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "318411", "name": "VMG", "stack": 9850, "seat_no": 7, "position": "BTN", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "201321", "name": "kikiNkidz", "stack": 12756, "seat_no": 0, "position": "SB", "win_bet": -120, "net": -120, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "275816", "name": "MissBotez", "stack": 23867, "seat_no": 1, "position": "BB", "win_bet": 10750, "net": 10750, "hand_cards": "ThTc", "is_showdown": True, "is_showcard": True},
        {"uid": "235160", "name": "Ptaters", "stack": 0, "seat_no": 2, "position": "UTG", "win_bet": -10230, "net": -10230, "hand_cards": "KcKd", "is_showdown": True, "is_showcard": True},
    ],
    "hand_history": [
        {
            "type": "preflop",
            "pot_size": 330,
            "actions": [
                {"role": "UTG1", "type": "action", "action": "fold", "seatNo": 3, "totalBet": 0, "amount": 0},
                {"role": "MP", "type": "action", "action": "call", "seatNo": 4, "totalBet": 100, "amount": 100},
                {"role": "HJ", "type": "action", "action": "call", "seatNo": 5, "totalBet": 100, "amount": 100},
                {"role": "CO", "type": "action", "action": "check", "seatNo": 6, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "fold", "seatNo": 7, "totalBet": 0, "amount": 0},
                {"role": "SB", "type": "action", "action": "call", "seatNo": 0, "totalBet": 80, "amount": 80},
                {"role": "BB", "type": "action", "action": "raise", "seatNo": 1, "totalBet": 600, "amount": 600},
                {"role": "UTG", "type": "action", "action": "raise", "seatNo": 2, "totalBet": 2200, "amount": 2200},
                {"role": "MP", "type": "action", "action": "fold", "seatNo": 4, "totalBet": 0, "amount": 0},
                {"role": "HJ", "type": "action", "action": "fold", "seatNo": 5, "totalBet": 0, "amount": 0},
                {"role": "CO", "type": "action", "action": "fold", "seatNo": 6, "totalBet": 0, "amount": 0},
                {"role": "SB", "type": "action", "action": "fold", "seatNo": 0, "totalBet": 0, "amount": 0},
                {"role": "BB", "type": "action", "action": "allin", "seatNo": 1, "totalBet": 13097, "amount": 13097},
                {"role": "UTG", "type": "action", "action": "call", "seatNo": 2, "totalBet": 10210, "amount": 10210},
            ],
        },
        {"type": "flop", "pot_size": 20980, "actions": []},
        {"type": "turn", "pot_size": 20980, "actions": []},
        {"type": "river", "pot_size": 20980, "actions": []},
    ],
    "attributes": {"analysis_mode": 1},
    "win_amount_bb": -204.6,
    "post_seats": [],
    "analysis": {"bestCount": 1, "inaccurateCount": 0, "blunderCount": 1},
}


class TestErrorSet3:
    def test_headsup_pot_checked_down(self):
        """Heads-up: no antes posted, BTN=SB. SB(20)+BB(50)+call(30)=100. $1.00."""
        text = convert_hand(HAND_43959074816)
        assert extract_pot(text) == 1.00

    def test_headsup_no_ante_lines(self):
        """Heads-up hands should not have 'posts the ante' lines."""
        text = convert_hand(HAND_43959074816)
        assert not has_line_containing(text, "posts the ante")

    def test_headsup_has_sb_line(self):
        """BTN should post small blind in heads-up."""
        text = convert_hand(HAND_43959074816)
        assert has_line_containing(text, "Bvamerica97: posts small blind $0.20")

    def test_headsup_pot_with_uncalled(self):
        """Heads-up: BTN bet on turn, BB folds. Uncalled = turn bet.
        SB(20)+BB(50)+call(30)+raise_add(150)+call(150)=400 preflop.
        Flop: bet(220)+raise(540)+call(320)=1480.
        Turn: bet(1140), fold. Uncalled=1140. Effective=1480. $14.80.
        """
        text = convert_hand(HAND_735670153216)
        assert extract_pot(text) == 14.80

    def test_allin_for_less_via_call(self):
        """BB allins 13097, UTG calls but capped at 8010 (all-in for less).
        UTG street_invested=10210, BB street_invested=13097.
        Uncalled=2887=$28.87. Effective pot=$209.80.
        """
        text = convert_hand(HAND_177876987904)
        assert extract_pot(text) == 209.80

    def test_allin_for_less_via_call_uncalled(self):
        """Uncalled bet of $28.87 returned to MissBotez (BB)."""
        text = convert_hand(HAND_177876987904)
        uncalled = extract_uncalled(text)
        assert uncalled == 28.87
        assert has_line_containing(text, "Uncalled bet ($28.87) returned to MissBotez")


# ---------------------------------------------------------------------------
# Error Set 4: post_seats handling (post-to-enter = BB, not straddle)
# ---------------------------------------------------------------------------

# Hand #575459119104: 6-max straddle, 1 post_seat (seat 0, CO).
# CO posts BB ($0.50) to enter, then raises to $8.25 after HJ opens $2.50.
# PT4 error was pot $7.90 vs $8.40 (off by $0.50 = 1 post-seat).
HAND_575459119104 = {
    "id": "1297907575459119104",
    "hole_cards": "Qh6s",
    "community_cards": "",
    "hand_score": 0,
    "timestamp": 1784248167000,
    "table": {
        "currency": "diamond",
        "table_id": "1297658791320588288",
        "session_id": "",
        "table_name": "",
        "small_blind": 20,
        "big_blind": 50,
        "ante": 20,
        "has_straddle": True,
        "game_type_code": "nlhe",
        "max_players": 6,
        "stack_depth": "medium",
        "ante_size": "small",
    },
    "player_position": "BTN",
    "players": [
        {"uid": "360074", "name": "Cheesepizza97", "stack": 15596, "seat_no": 7, "position": "HJ", "win_bet": -270, "net": -270, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "233764", "name": "GaybetGary", "stack": 10520, "seat_no": 0, "position": "CO", "win_bet": 520, "net": 520, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "235160", "name": "Ptaters", "stack": 12281, "seat_no": 2, "position": "BTN", "win_bet": -20, "net": -20, "hand_cards": "Qh6s", "is_showdown": False, "is_showcard": False},
        {"uid": "601055", "name": "PourMeACup", "stack": 2868, "seat_no": 3, "position": "SB", "win_bet": -40, "net": -40, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "655241", "name": "Tralfalz", "stack": 2570, "seat_no": 4, "position": "BB", "win_bet": -70, "net": -70, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "686974", "name": "Outerspaceman", "stack": 10662, "seat_no": 5, "position": "UTG", "win_bet": -120, "net": -120, "hand_cards": "", "is_showdown": False, "is_showcard": False},
    ],
    "hand_history": [
        {
            "type": "preflop",
            "pot_size": 290,
            "actions": [
                {"role": "HJ", "type": "action", "action": "raise", "seatNo": 7, "totalBet": 250, "amount": 250},
                {"role": "CO", "type": "action", "action": "raise", "seatNo": 0, "totalBet": 825, "amount": 825},
                {"role": "BTN", "type": "action", "action": "fold", "seatNo": 2, "totalBet": 0, "amount": 0},
                {"role": "SB", "type": "action", "action": "fold", "seatNo": 3, "totalBet": 0, "amount": 0},
                {"role": "BB", "type": "action", "action": "fold", "seatNo": 4, "totalBet": 0, "amount": 0},
                {"role": "UTG", "type": "action", "action": "fold", "seatNo": 5, "totalBet": 0, "amount": 0},
                {"role": "HJ", "type": "action", "action": "fold", "seatNo": 7, "totalBet": 0, "amount": 0},
            ],
        },
    ],
    "attributes": {"analysis_mode": 0},
    "win_amount_bb": -0.4,
    "post_seats": [0],
    "analysis": {"bestCount": 0, "inaccurateCount": 0, "blunderCount": 0},
}


# Hand #555942768640: 7-max straddle, 2 post_seats (seats 0, 1).
# Both post seats fold after 3-bet. PT4 error was pot $11.10 vs $12.10.
HAND_555942768640 = {
    "id": "1297910555942768640",
    "hole_cards": "4c5c",
    "community_cards": "",
    "hand_score": 0,
    "timestamp": 1784248878000,
    "table": {
        "currency": "diamond",
        "table_id": "1297816455151448064",
        "session_id": "",
        "table_name": "",
        "small_blind": 20,
        "big_blind": 50,
        "ante": 20,
        "has_straddle": True,
        "game_type_code": "nlhe",
        "max_players": 7,
        "stack_depth": "medium",
        "ante_size": "small",
    },
    "player_position": "SB",
    "players": [
        {"uid": "686184", "name": "YNH9362", "stack": 9636, "seat_no": 7, "position": "MP", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "266497", "name": "Krabman1234", "stack": 2080, "seat_no": 0, "position": "HJ", "win_bet": -420, "net": -420, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "328519", "name": "LimpRaise2233", "stack": 7690, "seat_no": 1, "position": "CO", "win_bet": 690, "net": 690, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "206394", "name": "DAD", "stack": 9980, "seat_no": 2, "position": "BTN", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "235160", "name": "Ptaters", "stack": 16858, "seat_no": 3, "position": "SB", "win_bet": -40, "net": -40, "hand_cards": "4c5c", "is_showdown": False, "is_showcard": False},
        {"uid": "302271", "name": "Shmoosie", "stack": 15517, "seat_no": 4, "position": "BB", "win_bet": -70, "net": -70, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "437267", "name": "Gandalf92", "stack": 8242, "seat_no": 6, "position": "UTG", "win_bet": -120, "net": -120, "hand_cards": "", "is_showdown": False, "is_showcard": False},
    ],
    "hand_history": [
        {
            "type": "preflop",
            "pot_size": 310,
            "actions": [
                {"role": "MP", "type": "action", "action": "fold", "seatNo": 7, "totalBet": 0, "amount": 0},
                {"role": "HJ", "type": "action", "action": "raise", "seatNo": 0, "totalBet": 400, "amount": 400},
                {"role": "CO", "type": "action", "action": "raise", "seatNo": 1, "totalBet": 1000, "amount": 1000},
                {"role": "BTN", "type": "action", "action": "fold", "seatNo": 2, "totalBet": 0, "amount": 0},
                {"role": "SB", "type": "action", "action": "fold", "seatNo": 3, "totalBet": 0, "amount": 0},
                {"role": "BB", "type": "action", "action": "fold", "seatNo": 4, "totalBet": 0, "amount": 0},
                {"role": "UTG", "type": "action", "action": "fold", "seatNo": 6, "totalBet": 0, "amount": 0},
                {"role": "HJ", "type": "action", "action": "fold", "seatNo": 0, "totalBet": 0, "amount": 0},
            ],
        },
    ],
    "attributes": {"analysis_mode": 0},
    "win_amount_bb": -0.8,
    "post_seats": [0, 1],
    "analysis": {"bestCount": 0, "inaccurateCount": 0, "blunderCount": 0},
}


# Hand #385717567488: 8-max straddle, 1 post_seat (seat 0, HJ).
# HJ posts BB, then goes allin. Has showdown. PT4 "invalid stack" error.
HAND_385717567488 = {
    "id": "1297909385717567488",
    "hole_cards": "9h5h",
    "community_cards": "QsJc8h3sKc",
    "hand_score": 0,
    "timestamp": 1784248599000,
    "table": {
        "currency": "diamond",
        "table_id": "1297816455151448064",
        "session_id": "",
        "table_name": "",
        "small_blind": 20,
        "big_blind": 50,
        "ante": 20,
        "has_straddle": True,
        "game_type_code": "nlhe",
        "max_players": 8,
        "stack_depth": "medium",
        "ante_size": "small",
    },
    "player_position": "SB",
    "players": [
        {"uid": "437267", "name": "Gandalf92", "stack": 9880, "seat_no": 6, "position": "UTG1", "win_bet": -120, "net": -120, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "686184", "name": "YNH9362", "stack": 4926, "seat_no": 7, "position": "MP", "win_bet": -2500, "net": -2500, "hand_cards": "5cAc", "is_showdown": True, "is_showcard": True},
        {"uid": "210663", "name": "INVICTUS", "stack": 5390, "seat_no": 0, "position": "HJ", "win_bet": 2890, "net": 2890, "hand_cards": "QcKh", "is_showdown": True, "is_showcard": True},
        {"uid": "292886", "name": "snappycrappy", "stack": 13888, "seat_no": 1, "position": "CO", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "636059", "name": "NotchLifter3840", "stack": 7647, "seat_no": 2, "position": "BTN", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "235160", "name": "Ptaters", "stack": 15675, "seat_no": 3, "position": "SB", "win_bet": -40, "net": -40, "hand_cards": "9h5h", "is_showdown": False, "is_showcard": False},
        {"uid": "302271", "name": "Shmoosie", "stack": 8360, "seat_no": 4, "position": "BB", "win_bet": -70, "net": -70, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "356681", "name": "AndrewHan", "stack": 11184, "seat_no": 5, "position": "UTG", "win_bet": -120, "net": -120, "hand_cards": "", "is_showdown": False, "is_showcard": False},
    ],
    "hand_history": [
        {
            "type": "preflop",
            "pot_size": 330,
            "actions": [
                {"role": "UTG1", "type": "action", "action": "call", "seatNo": 6, "totalBet": 100, "amount": 100},
                {"role": "MP", "type": "action", "action": "raise", "seatNo": 7, "totalBet": 500, "amount": 500},
                {"role": "HJ", "type": "action", "action": "allin", "seatNo": 0, "totalBet": 2480, "amount": 2480},
                {"role": "CO", "type": "action", "action": "fold", "seatNo": 1, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "fold", "seatNo": 2, "totalBet": 0, "amount": 0},
                {"role": "SB", "type": "action", "action": "fold", "seatNo": 3, "totalBet": 0, "amount": 0},
                {"role": "BB", "type": "action", "action": "fold", "seatNo": 4, "totalBet": 0, "amount": 0},
                {"role": "UTG", "type": "action", "action": "fold", "seatNo": 5, "totalBet": 0, "amount": 0},
                {"role": "UTG1", "type": "action", "action": "fold", "seatNo": 6, "totalBet": 0, "amount": 0},
                {"role": "MP", "type": "action", "action": "call", "seatNo": 7, "totalBet": 1980, "amount": 1980},
            ],
        },
        {"type": "flop", "pot_size": 5390, "actions": []},
        {"type": "turn", "pot_size": 5390, "actions": []},
        {"type": "river", "pot_size": 5390, "actions": []},
    ],
    "attributes": {"analysis_mode": 0},
    "win_amount_bb": -0.8,
    "post_seats": [0],
    "analysis": {"bestCount": 0, "inaccurateCount": 0, "blunderCount": 0},
}


class TestErrorSet4PostSeats:
    def test_hand_575459119104_pot(self):
        """6-max straddle, 1 post_seat (CO). CO posts BB then 3-bets.
        Antes: 6*20=120, SB:20, BB:50, straddle:100, post:50(BB).
        HJ raise:250, CO raise:825(total, additional=825-50=775).
        Everyone folds. Uncalled: 825-250=575.
        Pot: 120+20+50+100+50+250+775-575 = 790. $7.90.
        """
        text = convert_hand(HAND_575459119104)
        assert extract_pot(text) == 7.90

    def test_hand_575459119104_post_line(self):
        """CO should post big blind $0.50, not $1.00."""
        text = convert_hand(HAND_575459119104)
        assert has_line_containing(text, "GaybetGary: posts big blind $0.50")
        assert not has_line_containing(text, "GaybetGary: posts big blind $1.00")

    def test_hand_555942768640_pot(self):
        """7-max straddle, 2 post_seats (HJ, CO). Both post BB then act.
        HJ raises to 400, CO 3-bets to 1000, everyone folds.
        Uncalled: 1000-400=600.
        Antes: 7*20=140, SB:20, BB:50, straddle:100, 2 posts:2*50=100.
        HJ raise additional: 400-50=350. CO raise additional: 1000-50=950.
        Total: 140+20+50+100+100+350+950=1710. Minus uncalled 600=1110. $11.10.
        """
        text = convert_hand(HAND_555942768640)
        assert extract_pot(text) == 11.10

    def test_hand_555942768640_post_lines(self):
        """Both HJ and CO should post big blind $0.50."""
        text = convert_hand(HAND_555942768640)
        assert has_line_containing(text, "Krabman1234: posts big blind $0.50")
        assert has_line_containing(text, "LimpRaise2233: posts big blind $0.50")

    def test_hand_385717567488_pot(self):
        """8-max straddle, 1 post_seat (HJ). HJ posts BB then allins.
        Antes: 8*20=160, SB:20, BB:50, straddle:100, post:50(BB).
        UTG1 call:100, MP raise:500, HJ allin:2480 (total, add=2480-50=2430).
        MP call:1980. Others fold. No uncalled (MP matches 2480 total w/ straddle).
        Pot from actions: 160+20+50+100+50+100+500+2430+1980=5390. $53.90.
        """
        text = convert_hand(HAND_385717567488)
        assert extract_pot(text) == 53.90

    def test_hand_385717567488_post_line(self):
        """HJ should post big blind $0.50."""
        text = convert_hand(HAND_385717567488)
        assert has_line_containing(text, "INVICTUS: posts big blind $0.50")
