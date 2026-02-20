import pickle
import numpy as np
import os

# Redefine Node for pickle
class Node:
    def __init__(self):
        self.num_actions = 5
        self.regret_sum = np.zeros(self.num_actions)
        self.strategy_sum = np.zeros(self.num_actions)

def analyze():
    path = os.path.join(os.path.dirname(__file__), "mccfr_model.pkl")
    if not os.path.exists(path):
        print("Model file not found.")
        return

    with open(path, "rb") as f:
        nodes = pickle.load(f)

    total_nodes = len(nodes)
    round_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    total_regret = 0
    total_visited_nodes = 0

    for key, node in nodes.items():
        # Key format: R{round_idx}_B{bucket}_{history}
        rd = int(key.split("_")[0][1])
        round_counts[rd] += 1
        
        pos_regret = np.sum(np.maximum(node.regret_sum, 0))
        total_regret += pos_regret
        
        if np.sum(node.strategy_sum) > 0:
            total_visited_nodes += 1

    print(f"--- MCCFR Convergence Analysis ---")
    print(f"Total Nodes Discovered: {total_nodes}")
    for rd, count in round_counts.items():
        rd_name = ["Preflop", "Flop", "Turn", "River"][rd]
        print(f"  {rd_name}: {count} nodes")
    
    print(f"\nTraining Stats:")
    print(f"  Nodes with data: {total_visited_nodes} ({total_visited_nodes/total_nodes*100:.1f}%)")
    print(f"  Average Positive Regret: {total_regret/max(1, total_visited_nodes):.4f}")
    
    # Qualitative assessment
    print(f"\nAssessment:")
    if total_visited_nodes < 100000:
        print("  Status: EARLY STAGES")
        print("  Comment: You have only scratched the surface of the game tree.")
        print("  Recommendation: Run for at least 1,000,000 iterations to see basic strategic patterns.")
    elif total_regret/total_visited_nodes > 10:
        print("  Status: EXPLORING")
        print("  Comment: Regret is still high, meaning the bot is still changing its mind frequently.")
    else:
        print("  Status: CONVERGING")
        print("  Comment: Strategy is starting to stabilize.")

if __name__ == "__main__":
    analyze()
