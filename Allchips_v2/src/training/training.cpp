#include <iostream>
#include <vector>
#include <string>
#include <unordered_map>
#include <algorithm>
#include <cmath>
#include <random>
#include <chrono>
#include <fstream>
#include <stdint.h>

// Include the data utility from ehs_calc
#include <dat_utils.h>

#ifndef _Bool
#define _Bool bool
#endif

#include <phevaluator/phevaluator.h>

extern "C" {
#include <hand_index.h>
}

using namespace std;

// --- Betting Abstraction Constants ---
enum Action { FOLD = 0, CALL = 1, BET_50 = 2, BET_100 = 3, ALL_IN = 4, NUM_ACTIONS = 5 };
const int STACK = 400;
const int SB = 1;
const int BB = 2;

typedef uint64_t InfoSetKey;

struct Node {
    double regret_sum[NUM_ACTIONS];
    double strategy_sum[NUM_ACTIONS];

    Node() {
        for (int i = 0; i < NUM_ACTIONS; ++i) {
            regret_sum[i] = 0.0;
            strategy_sum[i] = 0.0;
        }
    }

    void get_strategy(float* strategy, const bool* legal_actions) {
        double normalizing_sum = 0;
        for (int i = 0; i < NUM_ACTIONS; ++i) {
            strategy[i] = (legal_actions[i] && regret_sum[i] > 0) ? (float)regret_sum[i] : 0;
            normalizing_sum += strategy[i];
        }

        for (int i = 0; i < NUM_ACTIONS; ++i) {
            if (normalizing_sum > 0) {
                strategy[i] /= (float)normalizing_sum;
            } else {
                int count = 0;
                for (int j = 0; j < NUM_ACTIONS; ++j) if (legal_actions[j]) count++;
                strategy[i] = legal_actions[i] ? 1.0f / count : 0;
            }
        }
    }
};

class MCCFRTrainer {
public:
    unordered_map<InfoSetKey, Node> nodes;
    HandDataManager data_manager;
    hand_indexer_t indexer;
    mt19937 rng;
    uniform_real_distribution<float> dist_01;
    long long iter_count = 0;

    MCCFRTrainer() : rng(chrono::system_clock::now().time_since_epoch().count()), dist_01(0.0f, 1.0f) {
        if (!data_manager.loadAll("../../ehs_calc/data/")) {
            cerr << "Error: Failed to load hand abstraction data. Check if ../../ehs_calc/data/ exists." << endl;
            exit(1);
        }
        uint8_t cards_per_round[] = {2, 3, 1, 1};
        hand_indexer_init(4, cards_per_round, &indexer);
        nodes.reserve(2000000);
    }

    ~MCCFRTrainer() {
        hand_indexer_free(&indexer);
    }

    void get_legal_actions(bool* legal, int my_bet, int opp_bet, int my_chips) {
        int call_amt = opp_bet - my_bet;
        legal[FOLD] = (call_amt > 0);
        legal[CALL] = true; 
        
        int pot = my_bet + opp_bet;
        int remaining = my_chips - my_bet;

        if (remaining > call_amt) {
            int pot_after_call = pot + call_amt;
            int b50 = call_amt + pot_after_call / 2;
            int b100 = call_amt + pot_after_call;
            
            legal[BET_50] = (b50 > call_amt && b50 < remaining && (pot_after_call/2) >= 2);
            legal[BET_100] = (b100 > call_amt && b100 < remaining && pot_after_call >= 2);
            legal[ALL_IN] = (remaining > call_amt);
        } else {
            legal[BET_50] = legal[BET_100] = legal[ALL_IN] = false;
        }
    }

    int get_action_bet(Action a, int my_bet, int opp_bet, int my_chips) {
        int call_amt = opp_bet - my_bet;
        int pot_after_call = (my_bet + opp_bet) + call_amt;
        switch (a) {
            case CALL: return opp_bet;
            case BET_50: return min(my_chips, opp_bet + pot_after_call / 2);
            case BET_100: return min(my_chips, opp_bet + pot_after_call);
            case ALL_IN: return my_chips;
            default: return my_bet;
        }
    }

    inline InfoSetKey make_key(uint8_t round, uint16_t bucket, uint64_t history) {
        // Round: 2 bits, Bucket: 10 bits, History: 52 bits
        return ((uint64_t)(round & 0x3) << 62) | ((uint64_t)(bucket & 0x3FF) << 52) | (history & 0xFFFFFFFFFFFFFULL);
    }

    inline uint64_t push_history(uint64_t history, Action a) {
        return (history << 4) | (a + 1);
    }

    float mccfr(uint8_t* board, 
                uint64_t history_bits, int round, int p1_bet, int p2_bet, 
                int active_player, int traversing_player, int history_len,
                hand_indexer_state_t p1_state, hand_indexer_state_t p2_state,
                hand_index_t p1_idx, hand_index_t p2_idx,
                int s1, int s2) {
        
        // Terminal Check: Fold
        if (history_len > 0 && ((history_bits & 0xF) == (FOLD + 1))) {
            // active_player is the one who was SUPPOSED to act. 
            // This means the OTHER player folded.
            // If active_player == 0, it means Player 1 folded. P0 wins p2_bet.
            // If active_player == 1, it means Player 0 folded. P0 loses p1_bet.
            return (active_player == 0) ? (float)p2_bet : (float)-p1_bet;
        }

        // Terminal Check: Round Transition or Showdown
        if (p1_bet == p2_bet && history_len >= 2) {
            if (round == 3) {
                // Showdown utility for Player 0
                if (s1 < s2) return (float)p2_bet;  // P0 wins P1's contribution
                if (s1 > s2) return (float)-p1_bet; // P0 loses their contribution
                return 0.0f;
            } else {
                hand_indexer_state_t next_p1_state = p1_state;
                hand_indexer_state_t next_p2_state = p2_state;
                uint8_t* next_cards = (round == 0) ? board : (round == 1 ? board + 3 : board + 4);
                hand_index_t next_p1_idx = hand_index_next_round(&indexer, next_cards, &next_p1_state);
                hand_index_t next_p2_idx = hand_index_next_round(&indexer, next_cards, &next_p2_state);
                
                // Heads-up: BB (1) acts first post-flop
                return mccfr(board, 0, round + 1, p1_bet, p2_bet, 1, traversing_player, 0, 
                             next_p1_state, next_p2_state, next_p1_idx, next_p2_idx, s1, s2);
            }
        }

        hand_index_t my_idx = (active_player == 0) ? p1_idx : p2_idx;
        uint16_t my_bucket = data_manager.getBucket(round, my_idx);
        InfoSetKey key = make_key(round, my_bucket, history_bits);
        
        bool legal[NUM_ACTIONS];
        get_legal_actions(legal, (active_player == 0 ? p1_bet : p2_bet), 
                                 (active_player == 0 ? p2_bet : p1_bet), STACK);

        Node& node = nodes[key];
        float strategy[NUM_ACTIONS];
        node.get_strategy(strategy, legal);

        if (active_player == traversing_player) {
            float action_utils[NUM_ACTIONS] = {0};
            for (int a = 0; a < NUM_ACTIONS; ++a) {
                if (!legal[a]) continue;
                
                int n1 = p1_bet, n2 = p2_bet;
                if (a == CALL) {
                    if (active_player == 0) n1 = p2_bet; else n2 = p1_bet;
                } else if (a != FOLD) {
                    int bet = get_action_bet((Action)a, (active_player == 0 ? p1_bet : p2_bet), 
                                                        (active_player == 0 ? p2_bet : p1_bet), STACK);
                    if (active_player == 0) n1 = bet; else n2 = bet;
                }

                action_utils[a] = mccfr(board, 
                                        push_history(history_bits, (Action)a), 
                                        round, n1, n2, 1 - active_player, traversing_player, history_len + 1,
                                        p1_state, p2_state, p1_idx, p2_idx, s1, s2);
            }

            float util = 0;
            for (int a = 0; a < NUM_ACTIONS; ++a) util += strategy[a] * action_utils[a];
            for (int a = 0; a < NUM_ACTIONS; ++a) {
                if (legal[a]) {
                    // Regret calculation for traversing player
                    float regret = (active_player == 0) ? (action_utils[a] - util) : (util - action_utils[a]);
                    node.regret_sum[a] = max(0.0, node.regret_sum[a] + (double)regret); // RM+
                }
            }
            return util;
        } else {
            // Epsilon-Greedy Sampling to break passivity deadlocks
            int a;
            if (dist_01(rng) < 0.1f) {
                vector<int> choices;
                for(int i=0; i<NUM_ACTIONS; ++i) if (legal[i]) choices.push_back(i);
                a = choices[rng() % choices.size()];
            } else {
                float r = dist_01(rng);
                float cumulative = 0;
                a = NUM_ACTIONS - 1;
                for (int i = 0; i < NUM_ACTIONS; ++i) {
                    cumulative += strategy[i];
                    if (r < cumulative) { a = i; break; }
                }
            }
            
            double weight = (double)iter_count;
            for (int i = 0; i < NUM_ACTIONS; ++i) node.strategy_sum[i] += weight * (double)strategy[i];

            int n1 = p1_bet, n2 = p2_bet;
            if (a == CALL) {
                if (active_player == 0) n1 = p2_bet; else n2 = p1_bet;
            } else if (a != FOLD) {
                int bet = get_action_bet((Action)a, (active_player == 0 ? p1_bet : p2_bet), 
                                                    (active_player == 0 ? p2_bet : p1_bet), STACK);
                if (active_player == 0) n1 = bet; else n2 = bet;
            }
            return mccfr(board, 
                         push_history(history_bits, (Action)a), 
                         round, n1, n2, 1 - active_player, traversing_player, history_len + 1,
                         p1_state, p2_state, p1_idx, p2_idx, s1, s2);
        }
    }

    void train(int iterations) {
        auto total_start = chrono::high_resolution_clock::now();
        auto last_report = total_start;
        int last_i = 0;

        for (int i = 1; i <= iterations; ++i) {
            iter_count = i;
            uint8_t deck[52];
            for (int j = 0; j < 52; ++j) deck[j] = j;
            shuffle(deck, deck + 52, rng);
            
            uint8_t p1_cards[2] = {deck[0], deck[1]};
            uint8_t p2_cards[2] = {deck[2], deck[3]};
            uint8_t board[5] = {deck[4], deck[5], deck[6], deck[7], deck[8]};

            int s1 = evaluate_7cards(p1_cards[0], p1_cards[1], board[0], board[1], board[2], board[3], board[4]);
            int s2 = evaluate_7cards(p2_cards[0], p2_cards[1], board[0], board[1], board[2], board[3], board[4]);
            
            hand_indexer_state_t p1_state, p2_state;
            hand_indexer_state_init(&indexer, &p1_state);
            hand_indexer_state_init(&indexer, &p2_state);
            hand_index_t p1_idx = hand_index_next_round(&indexer, p1_cards, &p1_state);
            hand_index_t p2_idx = hand_index_next_round(&indexer, p2_cards, &p2_state);

            for (int t = 0; t < 2; ++t) {
                mccfr(board, 0, 0, SB, BB, 0, t, 0, p1_state, p2_state, p1_idx, p2_idx, s1, s2);
            }

            if (i % 200000 == 0) {
                auto now = chrono::high_resolution_clock::now();
                chrono::duration<double> elapsed = now - last_report;
                int it_per_sec = (int)((i - last_i) / elapsed.count());
                cout << "Iteration " << i << " | Nodes: " << nodes.size() 
                     << " | Instant Speed: " << it_per_sec << " it/s" << endl;
                last_report = now;
                last_i = i;
            }
        }
    }

    void save(const string& filename) {
        cout << "Saving model to " << filename << "..." << endl;
        ofstream out(filename, ios::binary);
        size_t num_nodes = nodes.size();
        out.write((char*)&num_nodes, sizeof(size_t));
        for (auto const& it : nodes) {
            InfoSetKey key = it.first;
            const Node& node = it.second;
            out.write((char*)&key, sizeof(InfoSetKey));
            
            float r_sum[NUM_ACTIONS], s_sum[NUM_ACTIONS];
            for(int i=0; i<NUM_ACTIONS; ++i) {
                r_sum[i] = (float)node.regret_sum[i];
                s_sum[i] = (float)node.strategy_sum[i];
            }
            out.write((char*)r_sum, sizeof(float) * NUM_ACTIONS);
            out.write((char*)s_sum, sizeof(float) * NUM_ACTIONS);
        }
        out.close();
    }
};

int main() {
    MCCFRTrainer trainer;
    cout << "Starting Optimized MCCFR Training..." << endl;
    trainer.train(100000000); 
    trainer.save("cpp_mccfr_model.dat");
    return 0;
}
