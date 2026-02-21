import eval7
import random
import numpy as np
import time

def get_all_169_hands():
    ranks = '23456789TJQKA'
    pairs = [r + r for r in ranks]
    suited = []
    offsuit = []
    for i in range(len(ranks)):
        for j in range(i + 1, len(ranks)):
            suited.append(ranks[j] + ranks[i] + 's')
            offsuit.append(ranks[j] + ranks[i] + 'o')
    return pairs + suited + offsuit

def hand_to_cards(hand_str):
    r1, r2 = hand_str[0], hand_str[1]
    if len(hand_str) == 2: # Pair
        return [eval7.Card(r1 + 's'), eval7.Card(r2 + 'h')]
    elif hand_str[2] == 's':
        return [eval7.Card(r1 + 's'), eval7.Card(r2 + 's')]
    else:
        return [eval7.Card(r1 + 's'), eval7.Card(r2 + 'h')]

def calculate_hs(hand_cards, board_cards, trials=1000):
    deck = eval7.Deck()
    # Remove known cards from the deck
    for c in hand_cards + board_cards:
        try:
            deck.cards.remove(c)
        except ValueError:
            pass
    
    wins = 0
    for _ in range(trials):
        deck.shuffle()
        # Draw remaining board cards
        remaining_board = 5 - len(board_cards)
        full_board = board_cards + deck.cards[:remaining_board]
        # Draw opponent hand
        opp_hand = deck.cards[remaining_board:remaining_board+2]
        
        our_score = eval7.evaluate(hand_cards + full_board)
        opp_score = eval7.evaluate(opp_hand + full_board)
        
        if our_score > opp_score:
            wins += 1
        elif our_score == opp_score:
            wins += 0.5
            
    return wins / trials

def generate_abstraction():
    print("Generating 169 preflop hand strengths...")
    all_169 = get_all_169_hands()
    preflop_hs = {}
    for hand in all_169:
        hc = hand_to_cards(hand)
        preflop_hs[hand] = calculate_hs(hc, [], trials=2000)
    
    # Sort hands by HS for 30 buckets
    num_preflop_buckets = 30
    sorted_preflop = sorted(preflop_hs.items(), key=lambda x: x[1])
    
    # Map each hand to one of 30 buckets
    preflop_mapping = {}
    for i, (hand, hs) in enumerate(sorted_preflop):
        bucket_id = int(i * num_preflop_buckets / len(sorted_preflop))
        preflop_mapping[hand] = bucket_id

    # Postflop sampling
    rounds = {
        "Flop": (3, 10),
        "Turn": (4, 10),
        "River": (5, 10)
    }
    
    boundaries = {}
    
    for rd_name, (board_size, num_buckets) in rounds.items():
        print(f"Sampling for {rd_name}...")
        sampled_data = []
        for _ in range(3000): # Increased sample size for better coverage
            deck = eval7.Deck()
            cards = deck.sample(2 + board_size)
            hand = cards[:2]
            board = cards[2:]
            hs = calculate_hs(hand, board, trials=500)
            sampled_data.append((hs, hand, board))
        
        # Sort by HS
        sampled_data.sort(key=lambda x: x[0])
        hs_values = [x[0] for x in sampled_data]
        
        # Get boundaries
        rd_boundaries = [hs_values[int(len(hs_values) * i / num_buckets)] for i in range(1, num_buckets)]
        boundaries[rd_name] = rd_boundaries
        

    # Save to file
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, "hand_abstractions.txt")
    with open(output_path, "w") as f:
        f.write(f"Round 0 (Preflop) - {num_preflop_buckets} Buckets\n")
        f.write("Hand : BucketID : HS\n")
        for hand, hs in sorted_preflop:
            f.write(f"{hand} : {preflop_mapping[hand]} : {hs:.4f}\n")
        
        for rd_name, bds in boundaries.items():
            f.write(f"\nRound {rd_name} - {len(bds)} Buckets (PHS)\n")
            f.write("Boundaries: " + ", ".join([f"{b:.4f}" for b in bds]) + "\n")

    print("Abstraction generated and saved to hand_abstractions.txt")

if __name__ == "__main__":
    start_time = time.time()
    generate_abstraction()
    print(f"Total time: {time.time() - start_time:.2f} seconds")
