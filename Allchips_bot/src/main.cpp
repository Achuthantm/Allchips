#include <skeleton/actions.h>
#include <skeleton/constants.h>
#include <skeleton/runner.h>
#include <skeleton/states.h>

#include <iostream>
#include <fstream>
#include <unordered_map>
#include <vector>
#include <cmath>
#include <random>
#include <stdint.h>
#include <utility>

#include <dat_utils.h>

#ifndef _Bool
#define _Bool bool
#endif

extern "C" {
#include <hand_index.h>
}

using namespace pokerbots::skeleton;

// --- Model Data ---
typedef uint64_t InfoSetKey;
const int NUM_ACTIONS = 5;
enum ModelAction { FOLD = 0, CALL = 1, BET_50 = 2, BET_100 = 3, ALL_IN = 4 };

struct Node {
    float regret_sum[NUM_ACTIONS];
    float strategy_sum[NUM_ACTIONS];
};

inline InfoSetKey make_key(uint8_t round, uint16_t bucket, uint64_t history) {
    return ((uint64_t)round << 60) | ((uint64_t)bucket << 48) | (history & 0xFFFFFFFFFFFFULL);
}

inline uint64_t push_history(uint64_t history, ModelAction a) {
    return (history << 4) | (a + 1);
}

class Bot {
public:
    std::unordered_map<InfoSetKey, Node> model;
    HandDataManager data_manager;
    hand_indexer_t indexer;
    std::mt19937 rng;

    // Game tracking
    uint64_t round_history_bits = 0;
    int last_pip[2] = {0, 0};
    int round_action_count = 0;

    Bot() : rng(std::random_device{}()) {
        loadModel("cpp_mccfr_model.dat");
        data_manager.loadAll("../ehs_calc/data/");
        uint8_t cards_per_round[] = {2, 3, 1, 1};
        hand_indexer_init(4, cards_per_round, &indexer);
    }

    ~Bot() {
        hand_indexer_free(&indexer);
    }

    void loadModel(const std::string& filename) {
        std::ifstream in(filename, std::ios::binary);
        if (!in) {
            std::cerr << "Error: Could not open model file " << filename << std::endl;
            return;
        }
        size_t num_nodes;
        in.read((char*)&num_nodes, sizeof(size_t));
        model.reserve(num_nodes);
        for (size_t i = 0; i < num_nodes; ++i) {
            InfoSetKey key;
            Node node;
            in.read((char*)&key, sizeof(InfoSetKey));
            in.read((char*)node.regret_sum, sizeof(float) * NUM_ACTIONS);
            in.read((char*)node.strategy_sum, sizeof(float) * NUM_ACTIONS);
            model[key] = node;
        }
        std::cout << "Loaded " << model.size() << " nodes." << std::endl;
    }

    void handleNewRound(GameInfoPtr gameState, RoundStatePtr roundState, int active) {
        round_history_bits = 0;
        last_pip[0] = last_pip[1] = 0;
        round_action_count = 0;
    }

    void handleRoundOver(GameInfoPtr gameState, TerminalStatePtr terminalState, int active) {}

    // Reverse map opponent's bet to our abstraction
    ModelAction reverseMap(int opp_bet, int my_bet, int pot_before_opp) {
        int actual_raise = opp_bet - my_bet;
        if (actual_raise <= 0) return CALL;

        int pot_after_call = pot_before_opp + actual_raise; 
        
        // Abstraction bets (Total Pip):
        int d_call = my_bet;
        int d_50 = my_bet + pot_after_call / 2;
        int d_100 = my_bet + pot_after_call;
        int d_ai = STARTING_STACK;

        // Closest relative distance mapping
        std::vector<std::pair<int, ModelAction>> options = {
            {d_call, CALL}, {d_50, BET_50}, {d_100, BET_100}, {d_ai, ALL_IN}
        };

        ModelAction best_a = CALL;
        double min_rel = 1e9;

        for (size_t i = 0; i < options.size(); ++i) {
            double rel = 0;
            if (opp_bet == options[i].first) rel = 1.0;
            else if (opp_bet > options[i].first) rel = (double)opp_bet / options[i].first;
            else rel = (double)options[i].first / opp_bet;

            if (rel < min_rel) {
                min_rel = rel;
                best_a = options[i].second;
            }
        }
        return best_a;
    }

    Action getAction(GameInfoPtr gameState, RoundStatePtr roundState, int active) {
        auto legalActions = roundState->legalActions();
        int street = roundState->street;
        
        // Map engine street to our round index
        int round_idx = (street == 0) ? 0 : (street == 3 ? 1 : (street == 4 ? 2 : 3));

        // Update history based on opponent's last move
        int opp = 1 - active;
        if (roundState->pips[opp] > last_pip[opp]) {
            int pot_before = 2 * STARTING_STACK - roundState->stacks[0] - roundState->stacks[1] - roundState->pips[0] - roundState->pips[1];
            ModelAction opp_a = reverseMap(roundState->pips[opp], roundState->pips[active], pot_before);
            round_history_bits = push_history(round_history_bits, opp_a);
            round_action_count++;
        }
        last_pip[opp] = roundState->pips[opp];

        // Hand Indexing
        hand_indexer_state_t state;
        hand_indexer_state_init(&indexer, &state);
        uint8_t cards[2];
        cards[0] = stringToCard(roundState->hands[active][0]);
        cards[1] = stringToCard(roundState->hands[active][1]);
        hand_index_t h_idx = hand_index_next_round(&indexer, cards, &state);
        
        if (round_idx >= 1) {
            uint8_t board[3];
            for(int i=0; i<3; ++i) board[i] = stringToCard(roundState->deck[i]);
            h_idx = hand_index_next_round(&indexer, board, &state);
        }
        if (round_idx >= 2) {
            uint8_t card = stringToCard(roundState->deck[3]);
            h_idx = hand_index_next_round(&indexer, &card, &state);
        }
        if (round_idx >= 3) {
            uint8_t card = stringToCard(roundState->deck[4]);
            h_idx = hand_index_next_round(&indexer, &card, &state);
        }

        uint16_t bucket = data_manager.getBucket(round_idx, h_idx);
        InfoSetKey key = make_key(round_idx, bucket, round_history_bits);

        ModelAction chosen_a = CALL;
        if (model.find(key) != model.end()) {
            Node& n = model[key];
            
            // Mask illegal actions
            bool legal[NUM_ACTIONS];
            int call_amt = roundState->pips[opp] - roundState->pips[active];
            int pot = (2 * STARTING_STACK - roundState->stacks[0] - roundState->stacks[1]);
            
            legal[FOLD] = (call_amt > 0);
            legal[CALL] = true;
            int remaining = roundState->stacks[active];
            int pot_after_call = pot + call_amt;
            legal[BET_50] = (remaining > call_amt && (call_amt + pot_after_call/2) < remaining);
            legal[BET_100] = (remaining > call_amt && (call_amt + pot_after_call) < remaining);
            legal[ALL_IN] = (remaining > call_amt);

            float strategy[NUM_ACTIONS];
            float sum = 0;
            for(int i=0; i<NUM_ACTIONS; ++i) {
                strategy[i] = (legal[i]) ? n.strategy_sum[i] : 0;
                sum += strategy[i];
            }

            if (sum > 0) {
                float r = (float)rng() / rng.max();
                float cur = 0;
                for(int i=0; i<NUM_ACTIONS; ++i) {
                    cur += strategy[i] / sum;
                    if (r <= cur) { chosen_a = (ModelAction)i; break; }
                }
            }
        }

        // Map back to engine actions
        round_history_bits = push_history(round_history_bits, chosen_a);
        round_action_count++;

        if (chosen_a == FOLD) return {Action::Type::FOLD};
        if (chosen_a == CALL) {
            if (roundState->pips[active] == roundState->pips[opp]) return {Action::Type::CHECK};
            return {Action::Type::CALL};
        }
        
        auto raiseBounds = roundState->raiseBounds();
        int pot = (2 * STARTING_STACK - roundState->stacks[0] - roundState->stacks[1]);
        int call_amt = roundState->pips[opp] - roundState->pips[active];
        int pot_after_call = pot + call_amt;
        
        int raise_to = roundState->pips[opp];
        if (chosen_a == BET_50) raise_to += pot_after_call / 2;
        else if (chosen_a == BET_100) raise_to += pot_after_call;
        else if (chosen_a == ALL_IN) raise_to = STARTING_STACK;

        raise_to = std::max(raiseBounds[0], std::min(raiseBounds[1], raise_to));
        last_pip[active] = raise_to;
        return {Action::Type::RAISE, raise_to};
    }
};

int main(int argc, char *argv[]) {
  auto [host, port] = parseArgs(argc, argv);
  runBot<Bot>(host, port);
  return 0;
}
