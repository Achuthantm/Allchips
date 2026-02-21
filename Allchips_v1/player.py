import eval7
import pickle
import os
import numpy as np
import random
from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction
from skeleton.states import GameState, RoundState, NUM_ROUNDS, STARTING_STACK, BIG_BLIND, SMALL_BLIND
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot

# Constants from trainer
ACTIONS = ["F", "C", "B66", "AI"]

class Node:
    def __init__(self):
        self.num_actions = len(ACTIONS)
        self.regret_sum = np.zeros(self.num_actions)
        self.strategy_sum = np.zeros(self.num_actions)

    def get_strategy(self, legal_mask):
        strategy = np.maximum(self.regret_sum, 0)
        strategy *= legal_mask # Mask illegal actions
        total = np.sum(strategy)
        if total > 0:
            return strategy / total
        else:
            return legal_mask / np.sum(legal_mask)

    def get_average_strategy(self):
        total = np.sum(self.strategy_sum)
        if total > 0:
            return self.strategy_sum / total
        else:
            return np.ones(self.num_actions) / self.num_actions

class Player(Bot):
    def __init__(self):
        self.load_model()
        self.load_abstractions()
        self.history = ""
        self.current_street = 0

    def load_model(self):
        path = os.path.join(os.path.dirname(__file__), "mccfr_model.pkl")
        if os.path.exists(path):
            with open(path, "rb") as f:
                self.nodes = pickle.load(f)
        else:
            print("Warning: mccfr_model.pkl not found!")
            self.nodes = {}

    def load_abstractions(self):
        self.preflop_map = {}
        self.boundaries = {"Flop": [], "Turn": [], "River": []}
        path = os.path.join(os.path.dirname(__file__), "hand_abstractions.txt")
        if not os.path.exists(path):
            return

        with open(path, "r") as f:
            lines = f.readlines()
        current_rd = None
        for line in lines:
            if "Round 0" in line: current_rd = 0
            elif "Round Flop" in line: current_rd = 1
            elif "Round Turn" in line: current_rd = 2
            elif "Round River" in line: current_rd = 3
            elif ":" in line and current_rd == 0:
                if "Hand : BucketID" in line: continue
                parts = line.split(":")
                if len(parts) >= 2:
                    self.preflop_map[parts[0].strip()] = int(parts[1].strip())
            elif "Boundaries:" in line:
                bds = [float(x) for x in line.split("Boundaries:")[1].split(",")]
                if current_rd == 1: self.boundaries["Flop"] = bds
                elif current_rd == 2: self.boundaries["Turn"] = bds
                elif current_rd == 3: self.boundaries["River"] = bds

    def handle_new_round(self, game_state, round_state, active):
        self.history = ""
        self.current_street = 0

    def handle_round_over(self, game_state, terminal_state, active):
        pass

    def get_hand_bucket(self, hand, board, street):
        # engine street: 0, 3, 4, 5
        if street == 0:
            ranks = "23456789TJQKA"
            r1, r2 = hand[0][0], hand[1][0]
            s1, s2 = hand[0][1], hand[1][1]
            hi, lo = (ranks[max(ranks.find(r1), ranks.find(r2))], 
                      ranks[min(ranks.find(r1), ranks.find(r2))])
            hand_str = hi + lo + ("" if r1 == r2 else ("s" if s1 == s2 else "o"))
            return self.preflop_map.get(hand_str, 0)
        
        # Postflop
        from hand_abstractions import calculate_hs
        h_cards = [eval7.Card(c) for c in hand]
        b_cards = [eval7.Card(c) for c in board]
        hs = calculate_hs(h_cards, b_cards, trials=1000)
        
        rd_name = {3: "Flop", 4: "Turn", 5: "River"}[street]
        for i, threshold in enumerate(self.boundaries[rd_name]):
            if hs < threshold: return i
        return len(self.boundaries[rd_name])

    def reconstruct_history(self, round_state):
        '''
        Reconstructs the history of the current street by walking back the state tree.
        '''
        history = ""
        curr = round_state
        street_actions = []
        
        while curr is not None and curr.street == round_state.street:
            if curr.previous_state is not None and curr.previous_state.street == round_state.street:
                # Determine action taken from prev to curr
                prev = curr.previous_state
                active = prev.button % 2
                
                # Check bets/pips to see what happened
                pips_before = prev.pips
                pips_after = curr.pips
                
                if pips_after[active] == pips_before[active]: # Check
                    street_actions.append("X")
                elif pips_after[active] == pips_before[1-active]: # Call
                    street_actions.append("C")
                else: # Raise/Bet
                    # Estimate if it was B66 or AI
                    pot_before = 2 * STARTING_STACK - prev.stacks[0] - prev.stacks[1]
                    if pips_after[active] >= STARTING_STACK:
                        street_actions.append("A")
                    else:
                        street_actions.append("B")
            curr = curr.previous_state
            
        return "".join(reversed(street_actions))

    def get_action(self, game_state, round_state, active):
        street = round_state.street
        my_cards = round_state.hands[active]
        board_cards = round_state.deck[:street]
        
        # Map street to 0-3 for info_set key
        rd_idx = {0: 0, 3: 1, 4: 2, 5: 3}[street]
        bucket = self.get_hand_bucket(my_cards, board_cards, street)
        
        # Reconstruct history for this street
        self.history = self.reconstruct_history(round_state)
        info_set = f"R{rd_idx}_B{bucket}_{self.history}"
        
        legal_actions = round_state.legal_actions()
        my_stack = round_state.stacks[active]
        pot = 2 * STARTING_STACK - my_stack - round_state.stacks[1-active]
        
        # Determine strategy from model
        if info_set in self.nodes:
            strategy = self.nodes[info_set].get_average_strategy()
        else:
            # Simple fallback
            strategy = np.array([0.0, 0.7, 0.2, 0.1]) # F, C, B66, AI
            
        # Filter strategy by legal actions
        # ACTIONS = ["F", "C", "B66", "AI"]
        legal_mask = np.zeros(4)
        if FoldAction in legal_actions: legal_mask[0] = 1
        if CheckAction in legal_actions or CallAction in legal_actions: legal_mask[1] = 1
        if RaiseAction in legal_actions:
            legal_mask[2] = 1
            legal_mask[3] = 1
            
        strategy *= legal_mask
        if np.sum(strategy) > 0:
            strategy /= np.sum(strategy)
        else:
            strategy = legal_mask / np.sum(legal_mask)

        choice = np.random.choice(ACTIONS, p=strategy)
        
        if choice == "F":
            return FoldAction()
        elif choice == "C":
            if CheckAction in legal_actions: return CheckAction()
            return CallAction()
        else:
            if RaiseAction in legal_actions:
                min_raise, max_raise = round_state.raise_bounds()
                if choice == "B66": amt = int(0.66 * pot)
                else: amt = max_raise # AI
                
                amt = max(min_raise, min(max_raise, amt))
                return RaiseAction(amt)
            
            if CheckAction in legal_actions: return CheckAction()
            return CallAction()

if __name__ == '__main__':
    run_bot(Player(), parse_args())
