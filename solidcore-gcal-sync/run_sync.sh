#!/bin/bash

# Solidcore Calendar Sync - Automated Run Script
# This script activates the virtual environment and runs the sync

# Navigate to script directory
cd "$(dirname "$0")"

# Activate virtual environment (in parent directory)
source ../venv/bin/activate

# Run the sync script and log output with timestamps
echo "========================================" >> sync.log
echo "Sync started at: $(date)" >> sync.log
echo "========================================" >> sync.log

python3 main.py >> sync.log 2>&1

echo "Sync completed at: $(date)" >> sync.log
echo "" >> sync.log

# Deactivate virtual environment
deactivate
