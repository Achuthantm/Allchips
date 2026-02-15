import os
import pickle
import random
import eval7
import numpy as np
from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import GameState, TerminalState, RoundState
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot

class Player(Bot):
    def __init__(self):
        self.model = {}
        model_path = os.path.join(os.path.dirname(__file__), "model.pkl")
        if os.path.exists(model_path):
            with open(model_path, "rb") as f:
                self.model = pickle.load(f)

    def handle_new_round(self, game_state, round_state, active):
        pass

    def handle_round_over(self, game_state, terminal_state, active):
        pass

    def get_preflop_bucket(self, cards):
        cards = [eval7.Card(c) if isinstance(c, str) else c for c in cards]
        r1, r2 = cards[0].rank, cards[1].rank
        s1, s2 = cards[0].suit, cards[1].suit
        if r1 < r2: r1, r2 = r2, r1
        suited = s1 == s2
        if r1 == r2: return r1
        if suited: return 13 + (r1 * (r1 - 1) // 2) + r2
        return 91 + (r1 * (r1 - 1) // 2) + r2

    def get_hs(self, hand, board):
        if not board: return 0.5
        hand_cards = [eval7.Card(c) if isinstance(c, str) else c for c in hand]
        board_cards = [eval7.Card(c) if isinstance(c, str) else c for c in board]
        score = eval7.evaluate(hand_cards + board_cards)
        num_samples = 15
        win = 0
        deck = [eval7.Card(s) for s in ["2c", "2d", "2h", "2s", "3c", "3d", "3h", "3s", "4c", "4d", "4h", "4s", "5c", "5d", "5h", "5s", "6c", "6d", "6h", "6s", "7c", "7d", "7h", "7s", "8c", "8d", "8h", "8s", "9c", "9d", "9h", "9s", "Tc", "Td", "Th", "Ts", "Jc", "Jd", "Jh", "Js", "Qc", "Qd", "Qh", "Qs", "Kc", "Kd", "Kh", "Ks", "Ac", "Ad", "Ah", "As"]]
        used = [str(c) for c in (hand_cards + board_cards)]
        available_deck = [c for c in deck if str(c) not in used]
        for _ in range(num_samples):
            opp_hand = random.sample(available_deck, 2)
            if score > eval7.evaluate(opp_hand + board_cards): win += 1
            elif score == eval7.evaluate(opp_hand + board_cards): win += 0.5
        return win / num_samples

    def get_bucket(self, street, hand, board):
        if street == 0: return self.get_preflop_bucket(hand)
        return int(self.get_hs(hand, board) * 10)

    def get_action(self, game_state, round_state, active):
        legal = round_state.legal_actions()
        street = round_state.street
        bucket = self.get_bucket(street, round_state.hands[active], round_state.deck[:street])
        
        actions = []
        if FoldAction in legal: actions.append(FoldAction())
        if CheckAction in legal: actions.append(CheckAction())
        if CallAction in legal: actions.append(CallAction())
        if RaiseAction in legal:
            min_r, max_r = round_state.raise_bounds()
            actions.append(RaiseAction(min_r))
            if max_r > min_r: actions.append(RaiseAction(max_r))
        
        n = len(actions)
        key = (street, bucket, round_state.pips[active], round_state.pips[1-active], n)
        
        if key in self.model:
            strategy = self.model[key]
            if len(strategy) == n:
                return actions[np.random.choice(n, p=strategy)]

        if CheckAction in legal: return CheckAction()
        return CallAction()

if __name__ == '__main__':
    run_bot(Player(), parse_args())