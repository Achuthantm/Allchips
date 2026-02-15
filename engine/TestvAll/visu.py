import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
import os

def main():
    if not os.path.exists('results.json'):
        print("results.json not found.")
        return

    with open('results.json', 'r') as f:
        results = json.load(f)

    # Extract bot names
    bots = set()
    for match in results.values():
        bots.update(match.keys())
    
    bot_list = sorted(list(bots))
    n = len(bot_list)
    
    # Create a matrix for the heatmap
    # Row: Bot A, Col: Bot B. Value: Bot A's bankroll
    matrix = np.zeros((n, n))
    
    for match_name, match_results in results.items():
        players = list(match_results.keys())
        p1, p2 = players[0], players[1]
        idx1, idx2 = bot_list.index(p1), bot_list.index(p2)
        
        matrix[idx1, idx2] = match_results[p1]
        matrix[idx2, idx1] = match_results[p2]

    # Create DataFrame for seaborn
    df = pd.DataFrame(matrix, index=bot_list, columns=bot_list)

    # Set up the matplotlib figure
    plt.figure(figsize=(12, 10))
    
    # Create a custom diverging palette (Red to Green)
    cmap = sns.diverging_palette(10, 133, as_cmap=True)

    # Draw the heatmap
    sns.heatmap(df, annot=True, fmt=".0f", cmap=cmap, center=0,
                square=True, linewidths=.5, cbar_kws={"label": "Bankroll Delta"})

    plt.title('Poker Bot Comparison (Row vs Column)')
    plt.xlabel('Opponent Bot')
    plt.ylabel('Subject Bot')
    
    output_file = 'results_heatmap.png'
    plt.savefig(output_file, bbox_inches='tight')
    print(f"Visualization saved to {output_file}")

if __name__ == "__main__":
    main()
