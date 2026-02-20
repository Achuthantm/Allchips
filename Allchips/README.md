# Heads-Up No-Limit Texas Hold'em MCCFR Model

This directory contains the implementation of a Monte Carlo Counterfactual Regret Minimization (MCCFR) agent for Heads-Up No-Limit Texas Hold'em.

## Abstractions

### 1. Hand Abstraction
We use **Percentile Hand Strength (PHS)** to squash the enormous state space of poker into a manageable number of buckets.
- **Preflop (Round 0):** 169 Buckets (Lossless canonical representation).
- **Flop (Round 1):** 100 Buckets (PHS based on win probability).
- **Turn (Round 2):** 100 Buckets (PHS based on win probability).
- **River (Round 3):** 100 Buckets (PHS based on win probability).

### 2. Betting Abstraction
To keep the game tree finite, we restrict the available actions to a discrete set of bet sizes:
- **Fold**
- **Check / Call** (Matches the current bet)
- **Bet 66% Pot** (0.66 * current_pot)
- **Raise Pot** (1.0 * current_pot)
- **All-In** (Shoves the remaining stack)

*Note: If a player is facing a bet, "Check" becomes "Call". If no bet has been made, "Raise" is treated as an opening "Bet".*

## Information State Enumeration

An **Information Set** in our model is defined by the tuple: `(Current Round, Current Hand Bucket, Betting History)`.

### Estimation of Information States:

1. **Preflop (Round 0):**
   - **Hand Buckets:** 169
   - **Betting Sequences:** Approximately 15-20 (e.g., SB Call, SB Raise -> BB Call, SB Raise -> BB 3-bet -> SB Call, etc.)
   - **States:** $169 	imes 20 \approx 3,380$

2. **Flop (Round 1):**
   - **Hand Buckets:** 100
   - **Betting Sequences:** Approximately 20 per entry state. 
   - **Entry States from Preflop:** 3 (Call, Raise-Call, 4-bet-Call).
   - **States:** $100 	imes 3 	imes 20 \approx 6,000$

3. **Turn (Round 2):**
   - **Hand Buckets:** 100
   - **Betting Sequences:** Approximately 20 per entry state.
   - **Entry States from Flop:** (Cumulative paths from previous rounds).
   - **States:** $100 	imes (	ext{Previous Sequences}) 	imes 20 \approx 25,000$

4. **River (Round 3):**
   - **Hand Buckets:** 100
   - **Betting Sequences:** Approximately 20 per entry state.
   - **States:** $100 	imes (	ext{Previous Sequences}) 	imes 20 \approx 100,000$

**Total Estimated Information States:** $\approx 135,000$ to $200,000$.

This state space is compact enough to be solved using MCCFR on modern hardware in a reasonable timeframe (hours to days for convergence), while still maintaining enough strategic depth to play high-level poker.

## MCCFR Algorithm
We use **Outcome Sampling MCCFR**, which samples a single path through the game tree in each iteration. This significantly reduces the computational cost per iteration compared to vanilla CFR.

### Regret Minimization
- **Regret Matching:** Strategies are updated based on the accumulated regret of not taking specific actions.
- **Average Strategy:** The final bot will play according to the average strategy across all iterations, which converges to a Nash Equilibrium in this zero-sum game.
