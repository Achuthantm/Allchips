import sys
import os
import pickle
import time
import random
import eval7
import numpy as np

# Add the current directory to sys.path so we can import skeleton
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import RoundState, TerminalState, STARTING_STACK, BIG_BLIND, SMALL_BLIND

class MockDeck:
    def __init__(self, cards): self.cards = cards
    def peek(self, n): return self.cards[:n]

def get_preflop_bucket(cards):
    r1, r2 = cards[0].rank, cards[1].rank
    s1, s2 = cards[0].suit, cards[1].suit
    if r1 < r2: r1, r2 = r2, r1
    suited = s1 == s2
    if r1 == r2: return r1
    if suited: return 13 + (r1 * (r1 - 1) // 2) + r2
    return 91 + (r1 * (r1 - 1) // 2) + r2

def get_hs(hand, board):
    if not board: return 0.5
    score = eval7.evaluate(hand + board)
    num_samples = 10
    win = 0
    deck = [eval7.Card(s) for s in ["2c", "2d", "2h", "2s", "3c", "3d", "3h", "3s", "4c", "4d", "4h", "4s", "5c", "5d", "5h", "5s", "6c", "6d", "6h", "6s", "7c", "7d", "7h", "7s", "8c", "8d", "8h", "8s", "9c", "9d", "9h", "9s", "Tc", "Td", "Th", "Ts", "Jc", "Jd", "Jh", "Js", "Qc", "Qd", "Qh", "Qs", "Kc", "Kd", "Kh", "Ks", "Ac", "Ad", "Ah", "As"]]
    used = [str(c) for c in (hand + board)]
    available_deck = [c for c in deck if str(c) not in used]
    for _ in range(num_samples):
        opp_hand = random.sample(available_deck, 2)
        s = eval7.evaluate(opp_hand + board)
        if score > s: win += 1
        elif score == s: win += 0.5
    return win / num_samples

def get_bucket(street, hand, board):
    if street == 0: return get_preflop_bucket(hand)
    return int(get_hs(hand, board) * 10)

class InfoSet:
    def __init__(self, n_actions):
        self.regret_sum = np.zeros(n_actions)
        self.strategy_sum = np.zeros(n_actions)
        self.n_actions = n_actions
    def get_strategy(self, weight):
        regrets = np.maximum(self.regret_sum, 0)
        s = np.sum(regrets)
        strategy = regrets / s if s > 0 else np.ones(self.n_actions) / self.n_actions
        self.strategy_sum += weight * strategy
        return strategy
    def get_average_strategy(self):
        s = np.sum(self.strategy_sum)
        return self.strategy_sum / s if s > 0 else np.ones(self.n_actions) / self.n_actions

def custom_showdown(state):
    score0 = eval7.evaluate(state.deck.peek(5) + state.hands[0])
    score1 = eval7.evaluate(state.deck.peek(5) + state.hands[1])
    if score0 > score1: delta = STARTING_STACK - state.stacks[1]
    elif score0 < score1: delta = state.stacks[0] - STARTING_STACK
    else: delta = (state.stacks[0] - state.stacks[1]) // 2
    return TerminalState([delta, -delta], state)

class CFRTrainer:
    def __init__(self):
        self.infosets = {}
        self.deck_cards = [eval7.Card(s) for s in ["2c", "2d", "2h", "2s", "3c", "3d", "3h", "3s", "4c", "4d", "4h", "4s", "5c", "5d", "5h", "5s", "6c", "6d", "6h", "6s", "7c", "7d", "7h", "7s", "8c", "8d", "8h", "8s", "9c", "9d", "9h", "9s", "Tc", "Td", "Th", "Ts", "Jc", "Jd", "Jh", "Js", "Qc", "Qd", "Qh", "Qs", "Kc", "Kd", "Kh", "Ks", "Ac", "Ad", "Ah", "As"]]

    def train(self, iterations, timeout=8):
        start = time.time()
        for i in range(iterations):
            if i % 100 == 0 and time.time() - start > timeout: break
            random.shuffle(self.deck_cards)
            hands = [self.deck_cards[0:2], self.deck_cards[2:4]]
            deck = MockDeck(self.deck_cards[4:9])
            state = RoundState(0, 0, [SMALL_BLIND, BIG_BLIND], [STARTING_STACK-SMALL_BLIND, STARTING_STACK-BIG_BLIND], hands, deck, None)
            self.mccfr(state, 0, 1.0, 1.0)
            self.mccfr(state, 1, 1.0, 1.0)

    def mccfr(self, state, p, prob0, prob1):
        if isinstance(state, TerminalState): return state.deltas[p]
        if state.street == 5: return custom_showdown(state).deltas[p]

        active = state.button % 2
        legal = state.legal_actions()
        actions = []
        if FoldAction in legal: actions.append(FoldAction())
        if CheckAction in legal: actions.append(CheckAction())
        if CallAction in legal: actions.append(CallAction())
        if RaiseAction in legal:
            min_r, max_r = state.raise_bounds()
            actions.append(RaiseAction(min_r))
            if max_r > min_r: actions.append(RaiseAction(max_r))
        
        n = len(actions)
        bucket = get_bucket(state.street, state.hands[active], state.deck.peek(state.street if state.street > 0 else 0))
        key = (state.street, bucket, state.pips[active], state.pips[1-active], n)
        if key not in self.infosets: self.infosets[key] = InfoSet(n)
        info = self.infosets[key]
        
        strategy = info.get_strategy(prob0 if active == 0 else prob1)
        if active == p:
            idx = np.random.choice(n, p=strategy)
            p_action = strategy[idx]
            util = self.mccfr(state.proceed(actions[idx]), p, prob0*p_action if active == 0 else prob0, prob1*p_action if active == 1 else prob1)
            w = util / p_action
            for i in range(n):
                info.regret_sum[i] += w * (1 - strategy[i]) if i == idx else -w * strategy[i]
            return util
        else:
            idx = np.random.choice(n, p=strategy)
            return self.mccfr(state.proceed(actions[idx]), p, prob0*strategy[idx] if active == 0 else prob0, prob1*strategy[idx] if active == 1 else prob1)

if __name__ == "__main__":
    trainer = CFRTrainer()
    trainer.train(100000, timeout=8)
    model = {key: info.get_average_strategy() for key, info in trainer.infosets.items()}
    with open(os.path.join(os.path.dirname(__file__), "model.pkl"), "wb") as f:
        pickle.dump(model, f)
    print(f"Saved model with {len(model)} states")