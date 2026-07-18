#!/usr/bin/env python3
"""Quick test: convert one hand from sample data and print it."""

import json
from converter import convert_hand

# First hand from the sample API response (5c5s on BTN)
sample_hand = {
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
        "ante_size": "small"
    },
    "player_position": "BTN",
    "players": [
        {"uid": "266497", "name": "Krabman1234", "stack": 2060, "seat_no": 0, "position": "MP", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "328519", "name": "LimpRaise2233", "stack": 7670, "seat_no": 1, "position": "HJ", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "206394", "name": "DAD", "stack": 9980, "seat_no": 2, "position": "CO", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "235160", "name": "Ptaters", "stack": 17528, "seat_no": 3, "position": "BTN", "win_bet": 670, "net": 670, "hand_cards": "5c5s", "is_showdown": True, "is_showcard": True},
        {"uid": "302271", "name": "Shmoosie", "stack": 15247, "seat_no": 4, "position": "SB", "win_bet": -270, "net": -270, "hand_cards": "5h3h", "is_showdown": True, "is_showcard": True},
        {"uid": "437267", "name": "Gandalf92", "stack": 8172, "seat_no": 6, "position": "BB", "win_bet": -70, "net": -70, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "686184", "name": "YNH9362", "stack": 9366, "seat_no": 7, "position": "UTG", "win_bet": -270, "net": -270, "hand_cards": "4s6d", "is_showdown": True, "is_showcard": True}
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
                {"role": "UTG", "type": "action", "action": "call", "seatNo": 7, "totalBet": 150, "amount": 150}
            ]
        },
        {
            "type": "flop",
            "pot_size": 940,
            "actions": [
                {"role": "SB", "type": "action", "action": "check", "seatNo": 4, "totalBet": 0, "amount": 0},
                {"role": "UTG", "type": "action", "action": "check", "seatNo": 7, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "check", "seatNo": 3, "totalBet": 0, "amount": 0}
            ]
        },
        {
            "type": "turn",
            "pot_size": 940,
            "actions": [
                {"role": "SB", "type": "action", "action": "check", "seatNo": 4, "totalBet": 0, "amount": 0},
                {"role": "UTG", "type": "action", "action": "check", "seatNo": 7, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "check", "seatNo": 3, "totalBet": 0, "amount": 0}
            ]
        },
        {
            "type": "river",
            "pot_size": 940,
            "actions": [
                {"role": "SB", "type": "action", "action": "check", "seatNo": 4, "totalBet": 0, "amount": 0},
                {"role": "UTG", "type": "action", "action": "check", "seatNo": 7, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "check", "seatNo": 3, "totalBet": 0, "amount": 0}
            ]
        }
    ],
    "attributes": {"analysis_mode": 1},
    "win_amount_bb": 13.4,
    "post_seats": [],
    "analysis": {"bestCount": 4, "inaccurateCount": 0, "blunderCount": 0}
}

# Second hand: multiway pot with bet on flop, opponent wins (As3s hand with showdown)
sample_hand_2 = {
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
        "ante_size": "small"
    },
    "player_position": "BTN",
    "players": [
        {"uid": "509451", "name": "ComeAlongThen", "stack": 9860, "seat_no": 2, "position": "MP", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "680102", "name": "Indycards48", "stack": 4640, "seat_no": 3, "position": "HJ", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "635355", "name": "The original doc", "stack": 2220, "seat_no": 4, "position": "CO", "win_bet": -20, "net": -20, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "235160", "name": "Ptaters", "stack": 14454, "seat_no": 5, "position": "BTN", "win_bet": 3102, "net": 3102, "hand_cards": "As3s", "is_showdown": True, "is_showcard": True},
        {"uid": "527897", "name": "TrashTripp", "stack": 12502, "seat_no": 6, "position": "SB", "win_bet": -2852, "net": -2852, "hand_cards": "8d8c", "is_showdown": True, "is_showcard": True},
        {"uid": "561387", "name": "12Whiskey", "stack": 4670, "seat_no": 7, "position": "BB", "win_bet": -70, "net": -70, "hand_cards": "", "is_showdown": False, "is_showcard": False},
        {"uid": "307100", "name": "FRANCISPURU", "stack": 3826, "seat_no": 1, "position": "UTG", "win_bet": -120, "net": -120, "hand_cards": "", "is_showdown": False, "is_showcard": False}
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
                {"role": "BTN", "type": "action", "action": "call", "seatNo": 5, "totalBet": 750, "amount": 750}
            ]
        },
        {
            "type": "flop",
            "pot_size": 2290,
            "actions": [
                {"role": "SB", "type": "action", "action": "check", "seatNo": 6, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "check", "seatNo": 5, "totalBet": 0, "amount": 0}
            ]
        },
        {
            "type": "turn",
            "pot_size": 2290,
            "actions": [
                {"role": "SB", "type": "action", "action": "check", "seatNo": 6, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "check", "seatNo": 5, "totalBet": 0, "amount": 0}
            ]
        },
        {
            "type": "river",
            "pot_size": 2290,
            "actions": [
                {"role": "SB", "type": "action", "action": "check", "seatNo": 6, "totalBet": 0, "amount": 0},
                {"role": "BTN", "type": "action", "action": "bet", "seatNo": 5, "totalBet": 1832, "amount": 1832},
                {"role": "SB", "type": "action", "action": "call", "seatNo": 6, "totalBet": 1832, "amount": 1832}
            ]
        }
    ],
    "attributes": {"analysis_mode": 1},
    "win_amount_bb": 62.04,
    "post_seats": [],
    "analysis": {"bestCount": 4, "inaccurateCount": 0, "blunderCount": 1}
}

print("=" * 70)
print("HAND 1: 5c5s on BTN, checked down, showdown")
print("=" * 70)
print(convert_hand(sample_hand))

print("\n\n")

print("=" * 70)
print("HAND 2: As3s on BTN vs 8d8c, 3-bet pot, river bet + call")
print("=" * 70)
print(convert_hand(sample_hand_2))
