// Basic of sorting by E[HS^2] will eventually change it to something based on K-means with (E[HS], E[HS^2])
#include <iostream>
#include <fstream>
#include <vector>
#include <algorithm>
#include <stdint.h>

using namespace std;
const int buckets[] = {30, 10, 10, 10};

struct EHSData {
    float ehs;
    float ehs2;
};

struct HandEntry {
    uint32_t index;
    float ehs2;
};

bool compareHandEntry(const HandEntry& a, const HandEntry& b) {
    if (a.ehs2 != b.ehs2) return a.ehs2 < b.ehs2;
    return a.index < b.index;
}

void process_street(const char* input_file, const char* output_file, int num_buckets) {
    ifstream in(input_file, ios::binary);
    if (!in) {
        cerr << "Error: Could not open " << input_file << " for reading." << endl;
        return;
    }

    in.seekg(0, ios::end);
    streampos fileSize = in.tellg();
    in.seekg(0, ios::beg);

    size_t num_hands = fileSize / sizeof(EHSData);
    if (num_hands == 0) {
        cerr << "Error: " << input_file << " is empty." << endl;
        return;
    }

    cout << "Reading " << input_file << " (" << num_hands << " hands)..." << endl;
    vector<EHSData> data(num_hands);
    in.read((char*)data.data(), fileSize);
    in.close();

    cout << "Sorting hands by EHS..." << endl;
    vector<HandEntry> entries(num_hands);
    for (size_t i = 0; i < num_hands; ++i) {
        entries[i].index = (uint32_t)i;
        entries[i].ehs2 = data[i].ehs2;
    }

    sort(entries.begin(), entries.end(), compareHandEntry);

    cout << "Assigning to " << num_buckets << " buckets..." << endl;
    vector<uint8_t> buckets(num_hands);
    for (size_t i = 0; i < num_hands; ++i) {
        int bucket_id = (int)((long long)i * num_buckets / num_hands);
        if (bucket_id >= num_buckets) bucket_id = num_buckets - 1;
        buckets[entries[i].index] = (uint8_t)bucket_id;
    }

    cout << "Writing to " << output_file << "..." << endl;
    ofstream out(output_file, ios::binary);
    if (!out) {
        cerr << "Error: Could not open " << output_file << " for writing." << endl;
        return;
    }
    out.write((char*)buckets.data(), buckets.size());
    out.close();
    cout << "Street completed successfully." << endl << endl;
}

int main() {
    process_street("preflop_ehs.dat", "preflop_buckets.dat", buckets[0]);
    process_street("flop_ehs.dat", "flop_buckets.dat", buckets[1]);
    process_street("turn_ehs.dat", "turn_buckets.dat", buckets[2]);
    process_street("river_ehs.dat", "river_buckets.dat", buckets[3]);
    return 0;
}
