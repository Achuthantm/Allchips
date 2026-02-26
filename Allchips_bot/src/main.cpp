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
    // Round: 2 bits, Bucket: 10 bits, History: 52 bits (Matches optimized trainer)
    return ((uint64_t)(round & 0x3) << 62) | ((uint64_t)(bucket & 0x3FF) << 52) | (history & 0xFFFFFFFFFFFFFULL);
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
    int last_street = 0;
    int sb_pos = 0;
    int bb_pos = 1;

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
        sb_pos = roundState->button;
        bb_pos = 1 - sb_pos;
        last_pip[sb_pos] = SMALL_BLIND;
        last_pip[bb_pos] = BIG_BLIND;
        last_street = 0;
    }

    void handleRoundOver(GameInfoPtr gameState, TerminalStatePtr terminalState, int active) {}

    // Reverse map opponent's bet to our abstraction
    ModelAction reverseMap(int current_opp_pip, int last_opp_pip, int my_pip, int pot_at_start) {
        if (current_opp_pip <= my_pip) return CALL;

        // Correct: Pot size if opponent just called my current commitment
        int pot_after_opp_calls_me = pot_at_start + 2 * my_pip; 
        
        // Abstraction bets (Total Pip this street):
        int d_call = my_pip;
        int d_50 = my_pip + pot_after_opp_calls_me / 2;
        int d_100 = my_pip + pot_after_opp_calls_me;
        int d_ai = STARTING_STACK;

        std::vector<std::pair<int, ModelAction>> options = {
            {d_call, CALL}, {d_50, BET_50}, {d_100, BET_100}, {d_ai, ALL_IN}
        };

        ModelAction best_a = CALL;
        double min_rel = 1e9;

        for (size_t i = 0; i < options.size(); ++i) {
            double rel = 0;
            if (current_opp_pip == options[i].first) rel = 1.0;
            else if (current_opp_pip > options[i].first) {
                if (options[i].first == 0) rel = (double)current_opp_pip;
                else rel = (double)current_opp_pip / options[i].first;
            } else {
                if (current_opp_pip == 0) rel = (double)options[i].first;
                else rel = (double)options[i].first / current_opp_pip;
            }

            if (rel < min_rel) {
                min_rel = rel;
                best_a = options[i].second;
            }
        }
        return best_a;
    }

    Action getAction(GameInfoPtr gameState, RoundStatePtr roundState, int active) {
        int street = roundState->street;
        if (street != last_street) {
            round_history_bits = 0;
            last_pip[0] = last_pip[1] = 0;
            last_street = street;
        }

        int round_idx = (street == 0) ? 0 : (street == 3 ? 1 : (street == 4 ? 2 : 3));
        int opp = 1 - active;
        int pot_at_start = 2 * STARTING_STACK - roundState->stacks[0] - roundState->stacks[1] - roundState->pips[0] - roundState->pips[1];
        
        bool we_are_first = (street == 0) ? (active == sb_pos) : (active == bb_pos);
        if (!(we_are_first && round_history_bits == 0)) {
            ModelAction opp_a = reverseMap(roundState->pips[opp], last_pip[opp], roundState->pips[active], pot_at_start);
            round_history_bits = push_history(round_history_bits, opp_a);
        }
        last_pip[opp] = roundState->pips[opp];

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

        bool legal[NUM_ACTIONS];
        int call_amt = roundState->pips[opp] - roundState->pips[active];
        int pot = pot_at_start + roundState->pips[0] + roundState->pips[1];
        int remaining = roundState->stacks[active];
        int pot_after_call = pot + call_amt;

        legal[FOLD] = (call_amt > 0);
        legal[CALL] = true;
        legal[BET_50] = (remaining > call_amt && (call_amt + pot_after_call/2) < remaining && (pot_after_call/2) >= 2);
        legal[BET_100] = (remaining > call_amt && (call_amt + pot_after_call) < remaining && pot_after_call >= 2);
        legal[ALL_IN] = (remaining > call_amt);

        ModelAction chosen_a = CALL;
        float strategy[NUM_ACTIONS];
        float sum = 0;

        if (model.find(key) != model.end()) {
            Node& n = model[key];
            for(int i=0; i<NUM_ACTIONS; ++i) {
                strategy[i] = (legal[i]) ? n.strategy_sum[i] : 0;
                sum += strategy[i];
            }
        }

        if (sum > 0) {
            float r = (float)rng() / rng.max();
            float cur = 0;
            for(int i=0; i<NUM_ACTIONS; ++i) {
                cur += strategy[i] / sum;
                if (r <= cur) { chosen_a = (ModelAction)i; break; }
            }
        } else {
            std::vector<ModelAction> choices;
            for(int i=0; i<NUM_ACTIONS; ++i) if (legal[i]) choices.push_back((ModelAction)i);
            chosen_a = choices[rng() % choices.size()];
        }

        round_history_bits = push_history(round_history_bits, chosen_a);

        if (chosen_a == FOLD) return {Action::Type::FOLD};
        if (chosen_a == CALL) {
            if (roundState->pips[active] == roundState->pips[opp]) return {Action::Type::CHECK};
            return {Action::Type::CALL};
        }
        
        auto raiseBounds = roundState->raiseBounds();
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
