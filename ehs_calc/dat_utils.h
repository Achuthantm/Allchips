// Using MMAP for speedy .dat access without loading all the data to RAM
#ifndef DAT_UTILS_H
#define DAT_UTILS_H

#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdint.h>

struct EHSData {
    float ehs;
    float ehs2;
};

inline uint8_t stringToCard(const std::string& s) {
    std::string ranks = "23456789TJQKA";
    std::string suits = "cdhs";
    int r = ranks.find(s[0]);
    int s_idx = suits.find(s[1]);
    return (uint8_t)(r * 4 + s_idx);
}

class HandDataManager {
public:
    HandDataManager() {
        for (int i = 0; i < 4; ++i) {
            ehs_maps[i] = nullptr;
            bucket_maps[i] = nullptr;
            ehs_sizes[i] = 0;
            bucket_sizes[i] = 0;
        }
    }

    ~HandDataManager() {
        for (int i = 0; i < 4; ++i) {
            if (ehs_maps[i]) munmap(ehs_maps[i], ehs_sizes[i]);
            if (bucket_maps[i]) munmap(bucket_maps[i], bucket_sizes[i]);
        }
    }

    bool loadAll(const std::string& prefix = "data/") {
        const char* streets[] = {"preflop", "flop", "turn", "river"};
        bool success = true;

        for (int i = 0; i < 4; ++i) {
            std::string ehs_file = prefix + streets[i] + "_ehs.dat";
            std::string bucket_file = prefix + streets[i] + "_buckets.dat";

            if (!mapFile(ehs_file, (void**)&ehs_maps[i], &ehs_sizes[i])) {
                std::cerr << "Warning: Could not map " << ehs_file << std::endl;
                success = false;
            }

            if (!mapFile(bucket_file, (void**)&bucket_maps[i], &bucket_sizes[i])) {
                std::cerr << "Warning: Could not map " << bucket_file << std::endl;
                success = false;
            }
        }
        return success;
    }

    inline const EHSData& getEHS(int round, uint64_t index) const {
        return ehs_maps[round][index];
    }

    inline uint8_t getBucket(int round, uint64_t index) const {
        return bucket_maps[round][index];
    }

private:
    EHSData* ehs_maps[4];
    uint8_t* bucket_maps[4];
    size_t ehs_sizes[4];
    size_t bucket_sizes[4];

    bool mapFile(const std::string& filename, void** map_ptr, size_t* size_ptr) {
        int fd = open(filename.c_str(), O_RDONLY);
        if (fd == -1) return false;

        struct stat st;
        if (fstat(fd, &st) == -1) {
            close(fd);
            return false;
        }

        *size_ptr = st.st_size;
        *map_ptr = mmap(NULL, *size_ptr, PROT_READ, MAP_SHARED, fd, 0);
        close(fd);

        if (*map_ptr == MAP_FAILED) {
            *map_ptr = nullptr;
            return false;
        }
        return true;
    }
};

#endif // DAT_UTILS_H
