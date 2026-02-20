import eval7
import random
import numpy as np
import os
import pickle
import time

# --- Constants & Abstractions ---
ACTIONS = ["F", "C", "B66", "RP", "AI"] # Fold, Check/Call, Bet 66%, Raise Pot, All-In
SB = 1
BB = 2
STACK = 200

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
            # Equal prob over legal actions
            return legal_mask / np.sum(legal_mask)

    def get_average_strategy(self):
        total = np.sum(self.strategy_sum)
        if total > 0:
            return self.strategy_sum / total
        else:
            return np.ones(self.num_actions) / self.num_actions

class MCCFRTrainer:
    def __init__(self):
        self.nodes = {} # InfoSet string -> Node
        self.load_abstractions()

    def load_abstractions(self):
        self.preflop_map = {}
        self.boundaries = {"Flop": [], "Turn": [], "River": []}
        path = os.path.join(os.path.dirname(__file__), "hand_abstractions.txt")
        if not os.path.exists(path):
            print("Warning: hand_abstractions.txt not found.")
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
                if "Hand : BucketID" in line:
                    continue
                parts = line.split(":")
                if len(parts) >= 2:
                    self.preflop_map[parts[0].strip()] = int(parts[1].strip())
            elif "Boundaries:" in line:
                bds = [float(x) for x in line.split("Boundaries:")[1].split(",")]
                if current_rd == 1: self.boundaries["Flop"] = bds
                elif current_rd == 2: self.boundaries["Turn"] = bds
                elif current_rd == 3: self.boundaries["River"] = bds

    def get_hand_bucket(self, hand, board, round_idx):
        if round_idx == 0:
            r1, r2 = hand[0].rank, hand[1].rank
            s1, s2 = hand[0].suit, hand[1].suit
            ranks = "23456789TJQKA"
            hi, lo = (ranks[max(r1, r2)], ranks[min(r1, r2)])
            hand_str = hi + lo + ("" if r1 == r2 else ("s" if s1 == s2 else "o"))
            return self.preflop_map.get(hand_str, 0)
        
        from hand_abstractions import calculate_hs
        hs = calculate_hs(hand, board, trials=100)
        rd_name = ["", "Flop", "Turn", "River"][round_idx]
        for i, threshold in enumerate(self.boundaries[rd_name]):
            if hs < threshold: return i
        return 99

    def get_legal_mask(self, last_bet, player_chips, opp_bet):
        mask = np.zeros(len(ACTIONS))
        mask[0] = 1 # Fold is always legal if facing a bet
        mask[1] = 1 # Call/Check is always legal
        
        call_amt = opp_bet - last_bet
        pot = last_bet + opp_bet
        remaining = player_chips - last_bet
        
        if remaining > call_amt:
            # ACTIONS = ["F", "C", "B66", "RP", "AI"]
            if int(0.66 * pot) > call_amt and int(0.66 * pot) < remaining: mask[2] = 1
            if pot > call_amt and pot < remaining: mask[3] = 1
            mask[4] = 1 # AI
        return mask

    def mccfr(self, p1_hand, p2_hand, board, history, round_idx, p1_bet, p2_bet, active_player, deck, p1_bucket, p2_bucket):
        # 1. Terminal Check: Fold
        if history.endswith("F"):
            if active_player == 0: return p2_bet
            else: return -p1_bet

        # 2. Terminal Check: Showdown or Round Transition
        is_round_over = (history.endswith("C") and len(history) >= 1) 
        
        if is_round_over:
            if round_idx == 3: # River over -> Showdown
                s1 = eval7.evaluate(p1_hand + board)
                s2 = eval7.evaluate(p2_hand + board)
                if s1 > s2: return p2_bet
                elif s1 < s2: return -p1_bet
                else: return 0
            else: # Next Round: Chance Node
                next_deck = eval7.Deck()
                for c in p1_hand + p2_hand + board:
                    try: next_deck.cards.remove(c)
                    except ValueError: pass
                next_deck.shuffle()
                new_cards = next_deck.deal(3 if round_idx == 0 else 1)
                new_board = board + new_cards
                # RE-CALCULATE BUCKETS ONCE PER ROUND
                new_p1_bucket = self.get_hand_bucket(p1_hand, new_board, round_idx + 1)
                new_p2_bucket = self.get_hand_bucket(p2_hand, new_board, round_idx + 1)
                return self.mccfr(p1_hand, p2_hand, new_board, "", round_idx + 1, p1_bet, p2_bet, 0, next_deck, new_p1_bucket, new_p2_bucket)

        # 3. Get Node/InfoSet
        bucket = p1_bucket if active_player == 0 else p2_bucket
        info_set = f"R{round_idx}_B{bucket}_{history}"
        
        legal_mask = self.get_legal_mask(p1_bet if active_player == 0 else p2_bet, 
                                         STACK, 
                                         p2_bet if active_player == 0 else p1_bet)
        
        if info_set not in self.nodes:
            self.nodes[info_set] = Node()
        node = self.nodes[info_set]

        # 4. MCCFR Sampling
        strategy = node.get_strategy(legal_mask)
        if active_player == 0: # Update P1 strategy
            action_utils = np.zeros(len(ACTIONS))
            for a_idx, action_code in enumerate(ACTIONS):
                if legal_mask[a_idx] == 0: continue
                
                # Simulate action
                new_p1_bet = p1_bet
                if action_code == "C": new_p1_bet = p2_bet
                elif action_code == "B66": new_p1_bet = min(STACK, p1_bet + int(0.66 * (p1_bet+p2_bet)))
                elif action_code == "RP": new_p1_bet = min(STACK, p1_bet + (p1_bet+p2_bet))
                elif action_code == "AI": new_p1_bet = STACK
                
                action_utils[a_idx] = self.mccfr(p1_hand, p2_hand, board, history + action_code, round_idx, 
                                                 new_p1_bet, p2_bet, 1, deck, p1_bucket, p2_bucket)
            
            util = np.sum(action_utils * strategy)
            regrets = (action_utils - util) * legal_mask
            node.regret_sum += regrets
            return util
        else: # Sample P2 action
            a_idx = np.random.choice(len(ACTIONS), p=strategy)
            action_code = ACTIONS[a_idx]
            node.strategy_sum[a_idx] += 1
            
            new_p2_bet = p2_bet
            if action_code == "C": new_p2_bet = p1_bet
            elif action_code == "B66": new_p2_bet = min(STACK, p2_bet + int(0.66 * (p1_bet+p2_bet)))
            elif action_code == "RP": new_p2_bet = min(STACK, p2_bet + (p1_bet+p2_bet))
            elif action_code == "AI": new_p2_bet = STACK
            
            return self.mccfr(p1_hand, p2_hand, board, history + action_code, round_idx, 
                              p1_bet, new_p2_bet, 0, deck, p1_bucket, p2_bucket)

    def train(self, iterations):
        for i in range(1, iterations + 1):
            deck = eval7.Deck()
            deck.shuffle()
            p1_hand = deck.deal(2)
            p2_hand = deck.deal(2)
            
            p1_bucket = self.get_hand_bucket(p1_hand, [], 0)
            p2_bucket = self.get_hand_bucket(p2_hand, [], 0)
            
            self.mccfr(p1_hand, p2_hand, [], "", 0, SB, BB, 0, deck, p1_bucket, p2_bucket)
            if i % 100 == 0:
                print(f"Iteration {i}/{iterations} - Nodes: {len(self.nodes)}")

if __name__ == "__main__":
    trainer = MCCFRTrainer()
    trainer.train(10000)
    with open("mccfr_model.pkl", "wb") as f:
        pickle.dump(trainer.nodes, f)
