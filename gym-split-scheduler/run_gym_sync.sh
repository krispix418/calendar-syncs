#!/bin/bash

# Gym Workout Calendar Sync Runner
# This script is designed to be run manually or via cron for automated monthly scheduling

# Navigate to script directory
cd "$(dirname "$0")"

# Activate virtual environment (in parent directory)
source ../venv/bin/activate

# Get next month (for automated monthly runs)
# Note: On macOS, use 'date -v+1m', on Linux use 'date -d "next month"'
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    NEXT_MONTH=$(date -v+1m +%Y-%m)
else
    # Linux
    NEXT_MONTH=$(date -d "next month" +%Y-%m)
fi

echo "Running gym workout scheduler for: $NEXT_MONTH"
echo "Log file: gym_sync.log"
echo "----------------------------------------"

# Run the scheduler (append to log file)
python workout_scheduler.py --month "$NEXT_MONTH" >> gym_sync.log 2>&1

# Capture exit code
EXIT_CODE=$?

# Deactivate virtual environment
deactivate

# Report status
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ Gym sync completed successfully"
else
    echo "✗ Gym sync failed with exit code: $EXIT_CODE"
    echo "Check gym_sync.log for details"
fi

exit $EXIT_CODE
