#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <unordered_map>
#include <stdint.h>
#include <iomanip>
#include <algorithm>

using namespace std;

typedef uint64_t InfoSetKey;
const int NUM_ACTIONS = 5;
const string ACTION_NAMES[] = {"F", "C", "B50", "B100", "AI"};

struct NodeData {
    InfoSetKey key;
    float regret_sum[NUM_ACTIONS];
    float strategy_sum[NUM_ACTIONS];
    float total_strat;
};

void analyze_model(const string& filename) {
    ifstream in(filename, ios::binary);
    if (!in) {
        cerr << "Error: Could not open " << filename << endl;
        return;
    }

    size_t num_nodes;
    in.read((char*)&num_nodes, sizeof(size_t));

    cout << "Analyzing model: " << filename << endl;
    cout << "Total Nodes: " << num_nodes << endl;
    cout << "------------------------------------------" << endl;

    vector<NodeData> all_nodes;
    all_nodes.reserve(num_nodes);

    double total_pos_regret = 0;
    size_t nodes_per_round[4] = {0};
    double normalized_regret_per_round[4] = {0};

    for (size_t i = 0; i < num_nodes; ++i) {
        NodeData data;
        in.read((char*)&data.key, sizeof(InfoSetKey));
        in.read((char*)data.regret_sum, sizeof(float) * NUM_ACTIONS);
        in.read((char*)data.strategy_sum, sizeof(float) * NUM_ACTIONS);

        data.total_strat = 0;
        float node_pos_regret = 0;
        for (int a = 0; a < NUM_ACTIONS; ++a) {
            data.total_strat += data.strategy_sum[a];
            if (data.regret_sum[a] > 0) node_pos_regret += data.regret_sum[a];
        }

        uint8_t round = (uint8_t)(data.key >> 62);
        nodes_per_round[round]++;
        
        if (data.total_strat > 0) {
            normalized_regret_per_round[round] += (node_pos_regret / data.total_strat);
            total_pos_regret += (node_pos_regret / data.total_strat);
        }

        all_nodes.push_back(data);
    }

    cout << left << setw(10) << "Round" << setw(15) << "Nodes" << setw(20) << "Norm. Avg Regret" << endl;
    for (int r = 0; r < 4; ++r) {
        double avg_r = (nodes_per_round[r] > 0) ? (normalized_regret_per_round[r] / nodes_per_round[r]) : 0;
        string rd_name = (r == 0 ? "Preflop" : (r == 1 ? "Flop" : (r == 2 ? "Turn" : "River")));
        cout << left << setw(10) << rd_name 
             << setw(15) << nodes_per_round[r] 
             << setw(20) << fixed << setprecision(6) << avg_r << endl;
    }

    cout << "------------------------------------------" << endl;
    cout << "Global Normalized Regret: " << (total_pos_regret / num_nodes) << " (Should approach 0)" << endl;
    
    // Sort nodes by visit frequency (total_strat)
    sort(all_nodes.begin(), all_nodes.end(), [](const NodeData& a, const NodeData& b) {
        return a.total_strat > b.total_strat;
    });

    cout << "\nTop 5 Most Visited Nodes (Strategies):" << endl;
    for (int i = 0; i < min((int)num_nodes, 5); ++i) {
        uint8_t round = (uint8_t)(all_nodes[i].key >> 62);
        uint16_t bucket = (uint16_t)((all_nodes[i].key >> 52) & 0x3FF);
        cout << "Round " << (int)round << " | Bucket " << bucket << " | Visits: " << (int)all_nodes[i].total_strat << endl;
        cout << "  Strategy: ";
        for (int a = 0; a < NUM_ACTIONS; ++a) {
            float prob = all_nodes[i].strategy_sum[a] / all_nodes[i].total_strat;
            cout << ACTION_NAMES[a] << ":" << fixed << setprecision(3) << prob << "  ";
        }
        cout << endl;
    }

    in.close();
}

int main(int argc, char** argv) {
    string file = "cpp_mccfr_model.dat";
    if (argc > 1) file = argv[1];
    analyze_model(file);
    return 0;
}
