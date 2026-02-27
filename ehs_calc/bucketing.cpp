// Memory-optimized sorting and bucketing for large data files.
#include <iostream>
#include <fstream>
#include <vector>
#include <algorithm>
#include <stdint.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>

using namespace std;

const int buckets[] = {169, 100, 100, 100};
const int HISTOGRAM_BINS = 1000000;

struct EHSData {
    float ehs;
    float ehs2;
};

void process_street(const char* input_file, const char* output_file, int num_buckets) {
    int fd = open(input_file, O_RDONLY);
    if (fd == -1) {
        cerr << "Error: Could not open " << input_file << " for reading." << endl;
        return;
    }

    struct stat st;
    if (fstat(fd, &st) == -1) {
        cerr << "Error: Could not stat " << input_file << endl;
        close(fd);
        return;
    }

    size_t fileSize = st.st_size;
    size_t num_hands = fileSize / sizeof(EHSData);
    if (num_hands == 0) {
        cerr << "Error: " << input_file << " is empty." << endl;
        close(fd);
        return;
    }

    cout << "Processing " << input_file << " (" << num_hands << " hands) with Histogram Method..." << endl;
    
    void* mmapped_data = mmap(NULL, fileSize, PROT_READ, MAP_SHARED, fd, 0);
    if (mmapped_data == MAP_FAILED) {
        cerr << "Error: mmap failed for " << input_file << endl;
        close(fd);
        return;
    }
    EHSData* data = (EHSData*)mmapped_data;

    // --- Pass 1: Build Histogram ---
    cout << "Pass 1: Building histogram..." << endl;
    vector<size_t> histogram(HISTOGRAM_BINS, 0);
    for (size_t i = 0; i < num_hands; ++i) {
        float val = data[i].ehs2;
        int bin = (int)(val * (HISTOGRAM_BINS - 1));
        if (bin < 0) bin = 0;
        if (bin >= HISTOGRAM_BINS) bin = HISTOGRAM_BINS - 1;
        histogram[bin]++;
    }

    // --- Boundary Calculation ---
    cout << "Calculating quantile boundaries..." << endl;
    vector<float> boundaries;
    boundaries.reserve(num_buckets);
    size_t current_sum = 0;
    int current_bucket = 1;
    for (int i = 0; i < HISTOGRAM_BINS; ++i) {
        current_sum += histogram[i];
        size_t target = (size_t)((long long)current_bucket * num_hands / num_buckets);
        if (current_sum >= target && current_bucket < num_buckets) {
            boundaries.push_back((float)i / (HISTOGRAM_BINS - 1));
            current_bucket++;
        }
    }

    // --- Pass 2: Assign Buckets and Stream to Disk ---
    cout << "Pass 2: Assigning buckets and writing to " << output_file << "..." << endl;
    ofstream out(output_file, ios::binary);
    if (!out) {
        cerr << "Error: Could not open " << output_file << " for writing." << endl;
        munmap(mmapped_data, fileSize);
        close(fd);
        return;
    }

    const size_t BUFFER_SIZE = 1024 * 1024; // 1MB buffer for streaming
    vector<uint8_t> buffer;
    buffer.reserve(BUFFER_SIZE);

    for (size_t i = 0; i < num_hands; ++i) {
        float val = data[i].ehs2;
        // Use binary search on the boundaries to find the bucket index
        auto it = lower_bound(boundaries.begin(), boundaries.end(), val);
        uint8_t bucket_id = (uint8_t)distance(boundaries.begin(), it);
        
        buffer.push_back(bucket_id);
        if (buffer.size() >= BUFFER_SIZE) {
            out.write((char*)buffer.data(), buffer.size());
            buffer.clear();
        }
    }
    if (!buffer.empty()) {
        out.write((char*)buffer.data(), buffer.size());
    }

    out.close();
    munmap(mmapped_data, fileSize);
    close(fd);
    cout << "Street completed successfully." << endl << endl;
}

int main() {
    process_street("data/preflop_ehs.dat", "data/preflop_buckets.dat", buckets[0]);
    process_street("data/flop_ehs.dat", "data/flop_buckets.dat", buckets[1]);
    process_street("data/turn_ehs.dat", "data/turn_buckets.dat", buckets[2]);
    process_street("data/river_ehs.dat", "data/river_buckets.dat", buckets[3]);
    return 0;
}
