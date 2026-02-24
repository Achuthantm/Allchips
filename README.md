# PokerBot

A Texas Hold'em bot using Counterfactual Regret Minimization (CFR) and card indexing. This repository contains tools for generating hand abstractions, training models, and running bots compatible with the **MIT Pokerbots** engine.

---

## Getting Started

### Prerequisites
*   **C++11/14** (GCC or Clang) for EHS calculations.
*   **Python 3.8+** for the training environment and bot runtime.
*   **Make** for building the C++ tools.

### 1. Generating Hand Abstraction Caches
To build the EHS and potential caches:
```bash
cd ehs_calc
make calculate_ehs
./calculate_ehs
```
*This generates binary `.dat` files for Preflop, Flop, Turn, and River states, which are used by the C++ MCCFR solver.*

### 2. Running a Bot (MIT Pokerbots Engine)
Our bots use the MIT Pokerbots skeleton. To run a session:
```bash
# Start the engine
python engine.py

# In a separate terminal, run the bot
python Allchips_v1/skeleton/runner.py --port 5005
```

### 3. Training the MCCFR Model
To train the Python-based MCCFR model:
```bash
cd Allchips_v1
python mccfr_trainer.py
```

---

## Project Structure

*   `ehs_calc/`: C++ tool for EHS and $EHS^2$ calculation and state abstraction.
*   `Allchips_v1/`: Prototype MCCFR bot in Python with coarse hand abstraction.
*   `SanityCheckBots/`: Baseline bots (Random, All-In, Min-Raise) for validation.
*   `engine.py`: Local instance of the MIT Pokerbots game engine.

---

## Technical Approach

### 1. Current Status: `Allchips_v1`
The current prototype uses a Python-based MCCFR trainer with basic hand buckets.

### 2. C++ Core Implementation
Heavy computations are being moved to C++:
- [x] **Hand Bucketing**: A tool to cluster hands based on EHS/$EHS^2$ data.
- [ ] **C++ MCCFR Loop**: A solver focused on execution speed.
- [ ] **Multithreading**: Adding multithreading to the EHS calculation and the MCCFR loop.

#### Exact EHS Calculation (`ehs_calc`)
Unlike many poker tools that use Monte Carlo simulation to estimate hand strength, `ehs_calc` performs an **exact calculation** of EHS. 
*   **Recursive DP Approach**: The engine works backwards from the River.
    1.  **River**: Exhaustively evaluates every possible opponent hand (990 combinations) to get a perfect Hand Strength (HS).
    2.  **Turn/Flop/Preflop**: Calculates the EHS for earlier rounds by averaging the cached values of all possible future canonical states. 
*   **Accuracy**: This eliminates sampling noise and provides a stable foundation for clustering and CFR training.

---

## Background and References

This implementation is based on several papers and existing libraries:

### Hand Abstraction
We use a hand abstraction based on **Effective Hand Strength (EHS)** and its second moment, **$EHS^2$**.
*   **Paper**: [Johanson et al., "Efficient Approximation of Control States in Extensive-Form Games" (AAMAS 2013)](https://poker.cs.ualberta.ca/publications/AAMAS13-abstraction.pdf).
*   *Note*: EHS captures the expected value, while $EHS^2$ captures the potential of the hand to improve or be outdrawn.

### Hand Isomorphism
To manage the number of possible game states, we map suit-equivalent hands to canonical indices.
*   **Paper**: [Waugh et al., "State Space Compression in Games of Perfect Information" (2013)](https://www.cs.cmu.edu/~kwaugh/publications/isomorphism13.pdf).
*   **Library**: [Hand Isomorphism](https://github.com/kdub0/hand-isomorphism).

---

## License
This project is for research and educational purposes. MIT Pokerbots engine components are subject to their respective licenses.
