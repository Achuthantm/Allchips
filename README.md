# PokerBot

A high-performance Texas Hold'em bot using Monte Carlo Counterfactual Regret Minimization (MCCFR) and advanced hand abstraction. This repository contains tools for exact Effective Hand Strength (EHS) calculation, optimized C++ model training, and a fast bot compatible with the **MIT Pokerbots** engine.

---

## Features

*   **Native C++ Implementation**: The core engine, trainer, and bot are written in C++ for maximum performance and throughput.
*   **Optimized MCCFR**: High-speed solver achieving over 1 million iterations per minute, enabling training on deep game trees.
*   **Advanced Hand Abstraction**: 
    *   **10-bit EHS Bucketing**: Clustering hands based on exact EHS and $EHS^2$ data.
    *   **52-bit History Encoding**: Fine-grained information sets capturing the full betting sequence.
*   **Exact EHS Calculation**: Avoids sampling noise by performing exhaustive DP-based calculations across all streets.
*   **High-Speed Evaluation**: Leverages the `phevaluator` and `hand-isomorphism` libraries for near-instantaneous hand indexing and evaluation.

---

## Getting Started

### Prerequisites
*   **C++14** (GCC or Clang)
*   **CMake** (3.10+)
*   **Python 3.8+** (for running the engine)
*   **Make**

### 1. Generating Hand Abstraction Caches
To build and generate the exact EHS and bucket caches:
```bash
cd ehs_calc
./run.sh
```
*This performs exhaustive calculations from River to Preflop and saves binary `.dat` files.*

### 2. Building and Training the Model
To build the trainer and run the MCCFR loop:
```bash
cd Allchips_v2
./build.sh
./build/training/training
```
*The trainer will generate `cpp_mccfr_model.dat` after completing the specified iterations (default: 10M).*

### 3. Running the Bot
The bot integrates directly with the MIT Pokerbots engine.
```bash
# Start the engine
python engine.py

# In a separate terminal, run the bot
cd Allchips_v2
./run.sh --port 5005
```

---

## Project Structure

*   `ehs_calc/`: C++ tool for exact EHS and $EHS^2$ calculation and state abstraction.
*   `Allchips_v2/`: Core C++ implementation of the MCCFR trainer and the game bot.
*   `SanityCheckBots/`: Baseline bots (Random, All-In, Min-Raise) for validation.
*   `engine.py`: Local instance of the MIT Pokerbots game engine.

---

## Technical Approach

### Exact EHS Calculation
Unlike many poker tools that use Monte Carlo simulation to estimate hand strength, our tool performs an **exact calculation** of EHS. 
*   **Recursive DP Approach**: The engine works backwards from the River.
    1.  **River**: Exhaustively evaluates every possible opponent hand (990 combinations) to get a perfect Hand Strength (HS).
    2.  **Turn/Flop/Preflop**: Calculates the EHS for earlier rounds by averaging the cached values of all possible future canonical states similar to a dynamic programming style method. 
*   **Accuracy**: This eliminates sampling noise and provides a stable foundation for clustering and CFR training.

### Betting Abstraction
The bot uses a discrete betting model to manage state complexity while retaining strategic depth:
*   **Actions**: FOLD, CALL, 50% POT, 100% POT, ALL-IN.
*   **Action Translation**: Opponent bets of any size are "reverse mapped" to the nearest abstraction using techniques described in the **Tartanian** paper. This allows the bot to respond intelligently to any bet size by translating it into its own strategic framework.

---

## Background and References

### Betting Abstraction and Action Translation
The strategy for mapping continuous betting spaces into discrete actions and translating opponent actions:
*   **Paper**: [Gilpin et al., "A Better Strategy for Strategic Betting" (AAMAS 2008)](https://www.cs.cmu.edu/~sandholm/tartanian.AAMAS08.pdf).

### Hand Abstraction
We use a hand abstraction based on **Effective Hand Strength (EHS)** and its second moment, **$EHS^2$**.
*   **Paper**: [Johanson et al., "Efficient Approximation of Control States in Extensive-Form Games" (AAMAS 2013)](https://poker.cs.ualberta.ca/publications/AAMAS13-abstraction.pdf).

### Hand Isomorphism
To manage the number of possible game states, we map suit-equivalent hands to canonical indices.
*   **Paper**: [Waugh et al., "State Space Compression in Games of Perfect Information" (2013)](https://www.cs.cmu.edu/~kwaugh/publications/isomorphism13.pdf).
*   **Library**: [Hand Isomorphism](https://github.com/kdub0/hand-isomorphism).

---

## License
This project is for research and educational purposes. MIT Pokerbots engine components are subject to their respective licenses.
