#!/bin/bash

# Exit on any error
set -e

echo "--- Building project ---"
make clean
make -j$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 1)

echo ""
echo "--- Generating EHS tables ---"
# This might take a long time, especially the river table
./calculate_ehs

echo ""
echo "--- Generating Buckets ---"
./bucketing

echo ""
echo "--- Done! ---"
echo "Generated files:"
ls -lh *.dat
