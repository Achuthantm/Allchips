# Each person initially puts in an ante of 1 
# bp, bb, pp, pbp, pbb
import random

# We let our 2 actions, PASS and BET correspond to 0 and 1 respectively.
PASS = 0
BET = 1
NUM_ACTIONS = 2

class Node:
    def __init__(self, info_set):
        # (Kuhn node definitions)
        self.info_set = info_set
        self.regret_sum = [0.0] * NUM_ACTIONS
        self.strategy = [0.0] * NUM_ACTIONS
        self.strategy_sum = [0.0] * NUM_ACTIONS

    # (Get current information set mixed strategy through regret-matching)
    def get_strategy(self, realization_weight):
        normalizing_sum = 0.0
        for a in range(NUM_ACTIONS):
            self.strategy[a] = self.regret_sum[a] if self.regret_sum[a] > 0 else 0.0
            normalizing_sum += self.strategy[a]
        
        for a in range(NUM_ACTIONS):
            if normalizing_sum > 0:
                self.strategy[a] /= normalizing_sum
            else:
                self.strategy[a] = 1.0 / NUM_ACTIONS
            self.strategy_sum[a] += realization_weight * self.strategy[a]
            
        return self.strategy

    # (Get average information set mixed strategy across all training iterations)
    # What converges to a minimal regret strategy is the average strategy across all iterations.
    def get_average_strategy(self):
        avg_strategy = [0.0] * NUM_ACTIONS
        normalizing_sum = 0.0
        
        for a in range(NUM_ACTIONS):
            normalizing_sum += self.strategy_sum[a]
            
        for a in range(NUM_ACTIONS):
            if normalizing_sum > 0:
                avg_strategy[a] = self.strategy_sum[a] / normalizing_sum
            else:
                avg_strategy[a] = 1.0 / NUM_ACTIONS
                
        return avg_strategy

    # (Get information set string representation)
    def __str__(self):
        avg_strat = self.get_average_strategy()
        return f"{self.info_set:>4}: [{avg_strat[0]:.4f}, {avg_strat[1]:.4f}]"


class KuhnTrainer:
    def __init__(self):
        # We store our information sets in a dictionary called nodeMap, indexed by String representations.
        self.node_map = {}

    # (Train Kuhn poker)
    def train(self, iterations):
        cards = [1, 2, 3]
        util = 0.0
        
        for i in range(iterations):
            # (Shuffle cards)
            # Cards are shuffled according to the Durstenfeld version of the Fisher-Yates shuffle.
            random.shuffle(cards)
            
            # Make the initial call to the recursive CFR algorithm with the shuffled cards, an empty action history, and a probability of 1 for each player.
            util += self.cfr(cards, "", 1.0, 1.0)
            
        print(f"Average game value: {util / iterations}")
        for node in self.node_map.values():
            print(node)

    # (Counterfactual regret minimization iteration)
    def cfr(self, cards, history, p0, p1):
        # The recursive CFR method begins by computing the player and opponent numbers from the history length.
        plays = len(history)
        player = plays % 2
        opponent = 1 - player

        # (Return payoff for terminal states)
        # Check for the two conditions for a terminal state: a terminal pass after the first action, or a double bet.
        if plays > 1:
            terminal_pass = history[-1] == 'p'
            double_bet = history[-2:] == "bb"
            is_player_card_higher = cards[player] > cards[opponent]
            
            if terminal_pass:
                if history == "pp":
                    return 1 if is_player_card_higher else -1
                else:
                    return 1
            elif double_bet:
                return 2 if is_player_card_higher else -2

        # Computing the information set string representation by concatenating the current player card with the history of player actions.
        info_set = str(cards[player]) + history

        # (Get information set node or create it if nonexistant)
        if info_set not in self.node_map:
            self.node_map[info_set] = Node(info_set)
        node = self.node_map[info_set]

        # (For each action, recursively call cfr with additional history and probability)
        strategy = node.get_strategy(p0 if player == 0 else p1)
        util = [0.0] * NUM_ACTIONS
        node_util = 0.0
        
        for a in range(NUM_ACTIONS):
            next_history = history + ("p" if a == 0 else "b")
            
            if player == 0:
                util[a] = -self.cfr(cards, next_history, p0 * strategy[a], p1)
            else:
                util[a] = -self.cfr(cards, next_history, p0, p1 * strategy[a])
                
            node_util += strategy[a] * util[a]

        # (For each action, compute and accumulate counterfactual regret)
        # Cumulative regrets are cumulative counterfactual regrets, weighted by the probability that the opponent plays to the current information set.
        for a in range(NUM_ACTIONS):
            regret = util[a] - node_util
            node.regret_sum[a] += (p1 if player == 0 else p0) * regret

        return node_util

if __name__ == "__main__":
    # CFR training is initialized by creating a new trainer object and initiating training for a given number of iterations.
    iterations = 3000000
    trainer = KuhnTrainer()
    trainer.train(iterations)