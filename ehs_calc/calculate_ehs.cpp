#include <iostream>
#include <fstream>
#include <vector>
#include <iomanip>
#include <chrono>
#include <algorithm>

#ifndef _Bool
#define _Bool bool
#endif

#include <phevaluator/phevaluator.h>

extern "C" {
#include <hand_index.h>
}

using namespace std;

struct EHSData {
    float ehs;
    float ehs2;
};

// --- Core Calculation Functions ---

double calculate_river_hs(const uint8_t* cards, const uint8_t* remaining) {
    // cards[0], cards[1] are hole cards
    // cards[2...6] are board cards
    int p_score = evaluate_7cards(cards[0], cards[1], cards[2], cards[3], cards[4], cards[5], cards[6]);
    
    int wins = 0;
    int ties = 0;
    
    int b1 = cards[2], b2 = cards[3], b3 = cards[4], b4 = cards[5], b5 = cards[6];

    for(int i = 0; i < 45; ++i) {
        int c1 = remaining[i];
        for(int j = i + 1; j < 45; ++j) {
            int o_score = evaluate_7cards(c1, remaining[j], b1, b2, b3, b4, b5);
            wins += (p_score < o_score);
            ties += (p_score == o_score);
        }
    }
    
    return (wins + 0.5 * ties) / 990.0;
}

// --- Table Generation Functions ---

void generate_river_table(const hand_indexer_t* indexer, vector<EHSData>& table) {
    hand_index_t size = hand_indexer_size(indexer, 3);
    table.resize(size);
    cout << "Generating River table (" << size << " hands)..." << endl;
    for (hand_index_t i = 0; i < size; ++i) {
        uint8_t cards[7];
        hand_unindex(indexer, 3, i, cards);

        uint64_t used_mask = 0;
        for(int j = 0; j < 7; ++j) used_mask |= (1ULL << cards[j]);
        
        uint8_t remaining[45];
        uint64_t free_mask = ((1ULL << 52) - 1) ^ used_mask;
        for(int j = 0; j < 45; ++j) {
            int next_card = __builtin_ctzll(free_mask);
            remaining[j] = next_card;
            free_mask ^= (1ULL << next_card);
        }

        float hs = (float)calculate_river_hs(cards, remaining);
        table[i] = {hs, hs * hs};
        if (i % 100000 == 0) cout << "\rProgress: " << fixed << setprecision(2) << (100.0 * i / size) << "%" << flush;
    }
    cout << "\rRiver table complete.          " << endl;
}

void generate_turn_table(const hand_indexer_t* indexer, const vector<EHSData>& river_table, vector<EHSData>& table) {
    hand_index_t size = hand_indexer_size(indexer, 2);
    table.resize(size);
    cout << "Generating Turn table (" << size << " hands)..." << endl;
    for (hand_index_t i = 0; i < size; ++i) {
        uint8_t cards[7];
        hand_unindex(indexer, 2, i, cards);
        uint64_t used_mask = 0;
        for(int j = 0; j < 6; ++j) used_mask |= (1ULL << cards[j]);
        
        double sum_hs = 0, sum_hs2 = 0;
        int count = 0;
        for(int c = 0; c < 52; ++c) {
            if((used_mask >> c) & 1) continue;
            cards[6] = c;
            hand_index_t r_idx = hand_index_last(indexer, cards);
            sum_hs += river_table[r_idx].ehs;
            sum_hs2 += river_table[r_idx].ehs2;
            count++;
        }
        table[i] = {(float)(sum_hs / count), (float)(sum_hs2 / count)};
        if (i % 10000 == 0) cout << "\rProgress: " << fixed << setprecision(2) << (100.0 * i / size) << "%" << flush;
    }
    cout << "\rTurn table complete.          " << endl;
}

void generate_flop_table(const hand_indexer_t* indexer, const vector<EHSData>& turn_table, vector<EHSData>& table) {
    hand_index_t size = hand_indexer_size(indexer, 1);
    table.resize(size);
    cout << "Generating Flop table (" << size << " hands)..." << endl;
    for (hand_index_t i = 0; i < size; ++i) {
        uint8_t cards[7] = {0};
        hand_unindex(indexer, 1, i, cards);
        uint64_t used_mask = 0;
        for(int j = 0; j < 5; ++j) used_mask |= (1ULL << cards[j]);
        
        double sum_hs = 0, sum_hs2 = 0;
        int count = 0;
        for(int c = 0; c < 52; ++c) {
            if((used_mask >> c) & 1) continue;
            cards[5] = c;
            hand_index_t indices[4];
            hand_index_all(indexer, cards, indices);
            hand_index_t t_idx = indices[2]; // Round 2 (Turn)
            sum_hs += turn_table[t_idx].ehs;
            sum_hs2 += turn_table[t_idx].ehs2;
            count++;
        }
        table[i] = {(float)(sum_hs / count), (float)(sum_hs2 / count)};
        if (i % 1000 == 0) cout << "\rProgress: " << fixed << setprecision(2) << (100.0 * i / size) << "%" << flush;
    }
    cout << "\rFlop table complete.          " << endl;
}

void generate_preflop_table(const hand_indexer_t* indexer, const vector<EHSData>& flop_table, vector<EHSData>& table) {
    hand_index_t size = hand_indexer_size(indexer, 0);
    table.resize(size);
    cout << "Generating Preflop table (" << size << " hands)..." << endl;
    for (hand_index_t i = 0; i < size; ++i) {
        uint8_t cards[7] = {0};
        hand_unindex(indexer, 0, i, cards);
        uint64_t used_mask = 0;
        for(int j = 0; j < 2; ++j) used_mask |= (1ULL << cards[j]);
        
        double sum_hs = 0, sum_hs2 = 0;
        int count = 0;
        for(int c1 = 0; c1 < 52; ++c1) {
            if((used_mask >> c1) & 1) continue;
            cards[2] = c1;
            for(int c2 = c1 + 1; c2 < 52; ++c2) {
                if((used_mask >> c2) & 1) continue;
                cards[3] = c2;
                for(int c3 = c2 + 1; c3 < 52; ++c3) {
                    if((used_mask >> c3) & 1) continue;
                    cards[4] = c3;
                    hand_index_t indices[4];
                    hand_index_all(indexer, cards, indices);
                    hand_index_t f_idx = indices[1]; // Round 1 (Flop)
                    sum_hs += flop_table[f_idx].ehs;
                    sum_hs2 += flop_table[f_idx].ehs2;
                    count++;
                }
            }
        }
        table[i] = {(float)(sum_hs / count), (float)(sum_hs2 / count)};
        cout << "\rPreflop Progress: " << fixed << setprecision(2) << (100.0 * i / size) << "%" << flush;
    }
    cout << "\rPreflop table complete.          " << endl;
}

void save_table(const char* filename, const vector<EHSData>& table) {
    cout << "Saving table to " << filename << "..." << endl;
    ofstream out(filename, ios::binary);
    if (!out) {
        cerr << "Error: Could not open " << filename << " for writing." << endl;
        return;
    }
    out.write((const char*)table.data(), table.size() * sizeof(EHSData));
    out.close();
}

// --- Main Execution ---

int main(int argc, char** argv) {
    hand_indexer_t indexer;
    uint8_t cards_per_round[] = {2, 3, 1, 1}; 
    hand_indexer_init(4, cards_per_round, &indexer);

    auto total_start = chrono::system_clock::now();

    vector<EHSData> river_table;
    generate_river_table(&indexer, river_table);

    vector<EHSData> turn_table;
    generate_turn_table(&indexer, river_table, turn_table);

    vector<EHSData> flop_table;
    generate_flop_table(&indexer, turn_table, flop_table);

    vector<EHSData> preflop_table;
    generate_preflop_table(&indexer, flop_table, preflop_table);

    save_table("preflop_ehs.dat", preflop_table);
    save_table("flop_ehs.dat", flop_table);
    save_table("turn_ehs.dat", turn_table);
    save_table("river_ehs.dat", river_table);

    auto total_end = chrono::system_clock::now();
    chrono::duration<double> total_elapsed = total_end - total_start;
    cout << "Total time: " << (int)total_elapsed.count() << "s" << endl;
    cout << "All tables generated and saved successfully." << endl;

    hand_indexer_free(&indexer);
    return 0;
}
