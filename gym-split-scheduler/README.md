# Gym Workout Calendar Scheduler

Automated gym workout calendar scheduling that integrates with your existing Solidcore class schedule.

## Overview

This system automatically generates a full month of gym workout calendar events based on:
- Pre-defined workout plan with 4-day rotation (upper/lower split)
- Current progression state tracking weights and reps
- Existing Solidcore class schedule from Google Calendar
- Smart scheduling rules for weekday/weekend timing

## Features

- **Dual Event Types (V2)**:
  - **Full Workouts**: Complete weight training + cardio (advances rotation)
  - **Cardio-Only Sessions**: 25-min Stairmaster after Solidcore classes (doesn't advance rotation)
- **4-Day Workout Rotation**: Upper Push, Lower Hamstrings, Upper Pull, Lower Quads
- **Smart Scheduling**: Automatically adjusts gym workout times based on Solidcore classes
- **Progressive Overload Tracking**: Manual tracking of weights and reps in progression_state.json
- **Workout-Based Deload**: Automatically reduces weights by 20% every 8 full workouts (not weeks)
- **Ramping Squats**: Progressive weight increases across 3 sets (30 lbs → 40 lbs → 55 lbs)
- **Detailed Event Descriptions**: Each calendar event includes warmup, exercises with current weights/reps, and cardio
- **Dry Run Mode**: Preview changes before creating events
- **Automatic Cleanup**: Deletes existing gym events before creating new ones

## Files

- `workout_scheduler.py` - Main scheduler script
- `workout_plan.json` - Complete workout plan with all exercises
- `progression_state.json` - Tracks current weights, reps, and progression
- `run_gym_sync.sh` - Bash wrapper for manual or cron execution
- `gym_sync.log` - Log file (created on first run)

## Usage

### Manual Execution

```bash
# Navigate to gym-workout directory
cd /Users/cjhalim/Desktop/Github/Portfolio/calendar-syncs/gym-workout

# Activate virtual environment
source ../venv/bin/activate

# Schedule workouts for a specific month
python workout_scheduler.py --month 2025-12

# Preview without creating events (dry run)
python workout_scheduler.py --month 2025-12 --dry-run

# Deactivate virtual environment
deactivate
```

### Using Bash Runner

```bash
# Run for next month (automatically calculated)
./run_gym_sync.sh
```

### Cron Automation

To automatically schedule the next month on the 25th of each month:

```bash
# Edit crontab
crontab -e

# Add this line (adjust path as needed):
0 9 25 * * /Users/cjhalim/Desktop/Github/Portfolio/calendar-syncs/gym-workout/run_gym_sync.sh
```

## Scheduling Logic (V2)

### Two Event Types
1. **Full Workout**: Complete weight training + cardio
   - Advances the 4-workout rotation
   - Counts toward deload tracking
2. **Cardio-Only Session**: 25 min Stairmaster only (after Solidcore)
   - Does NOT advance rotation
   - Does NOT count toward deload

### Weekday Rules (Mon-Fri)

**Monday & Friday:**
- **WITHOUT Solidcore**: Full workout at 7:15 AM
- **WITH Solidcore**: Cardio-only session 30 min after Solidcore ends

**Tuesday, Wednesday, Thursday:**
- **WITH Solidcore**: Cardio-only session 30 min after Solidcore ends
- **WITHOUT Solidcore**: Full workout at 8:00 PM

### Weekend Rules (Sat-Sun)

**Saturday & Sunday:**
- **Always Full Workouts** (even with Solidcore)
- **WITH Solidcore**: 30 min after Solidcore ends
- **WITHOUT Solidcore**: 3:00 PM

## Workout Rotation

The system cycles through 4 workouts in order:

1. **Upper Push** (85 min): Chest, Shoulders, Triceps + 25 min Stairmaster
2. **Lower Hamstrings** (105 min): Hamstrings, Glutes, Posterior Chain + 45 min Walking
3. **Upper Pull** (85 min): Back, Rear Delts + 25 min Stairmaster
4. **Lower Quads** (105 min): Quads, Glutes + 45 min Walking

## Progression System (V2)

### Standard Exercises
- **Starting**: 3 sets × 12 reps
- **Target**: 3 sets × 15 reps
- **Progression**: When you hit 3×15 with good form, increase weight by 5 lbs and return to 3×12

### Ramping Squats
- **Set 1**: 30 lbs × 12 reps
- **Set 2**: 40 lbs × 12 reps
- **Set 3**: 55 lbs × 12 reps
- **Progression**: After completing 2 quad/glute workouts, increase each weight by 5 lbs

### Deload Tracking
- **Trigger**: Every 8 **full workouts** (not weeks, not cardio sessions)
- **Effect**: Reduce all weights by 20% while maintaining reps
- **Example**: If you've completed 8 full workouts, the next workout will be a deload

### Manual Tracking Required
**IMPORTANT**: The scheduler does NOT automatically track completed workouts. You must manually update `progression_state.json` after each workout:
1. Increment the specific workout counter (e.g., `"upper_push": 1` → `"upper_push": 2`)
2. Increment the total counter (e.g., `"total": 2` → `"total": 3`)
3. Update exercise weights/reps as you progress
4. Check if you've reached deload threshold (every 8 workouts)

## Configuration Files

### workout_plan.json
Contains complete workout details:
- Exercise names and equipment
- Sets, reps, rest periods
- Form cues and notes
- Warmup and cooldown routines
- Cardio specifications

### progression_state.json
Tracks your progression (V2):
- Workout completion counts by type (upper_push, lower_hamstring_posterior, etc.)
- Total workout count
- Next deload at workout count (every 8 workouts)
- Ramping exercise progression (squats)
- Current weight and reps for each exercise
- Progression history

## Dependencies

All dependencies are shared with the parent calendar-syncs project:
- google-auth
- google-auth-oauthlib
- google-auth-httplib2
- google-api-python-client
- pytz

Uses existing `credentials.json` and `token.json` from parent directory.

## Troubleshooting

### Import Errors
The script adds `..` to Python path to import the shared `auth.py` module. Ensure you run the script from the `gym-workout/` directory.

### Authentication Issues
The script uses the same Google Calendar credentials as the Solidcore sync. If you encounter auth errors:
1. Ensure `../credentials.json` exists
2. Delete `../token.json` to force re-authentication
3. Run `python ../auth.py` to test authentication

### No Solidcore Classes Detected
- Check that Solidcore events contain one of: "solidcore", "signature50", "focus50", or "advanced65" (case-insensitive) in the title
- Verify calendar access permissions include reading existing events
- Make sure gym workout events (cardio sessions) aren't being misidentified as Solidcore classes

### Dry Run Recommended
Always run with `--dry-run` first to preview the schedule before creating events:
```bash
python workout_scheduler.py --month 2025-12 --dry-run
```

## Example Output

```
======================================================================
GYM WORKOUT CALENDAR SCHEDULER - 2025-12
======================================================================

1. SETUP
----------------------------------------------------------------------
Authenticating with Google Calendar API...
Loading workout plan...
Loading progression state...
Current week: 1
Next deload week: 5

2. CALENDAR ANALYSIS
----------------------------------------------------------------------
Fetching calendar events from 2025-12-01 to 2025-12-31
Found 57 total events in calendar for 2025-12
Solidcore class found: 2025-12-04 at 18:00 (afternoon: True)
Solidcore class found: 2025-12-05 at 18:30 (afternoon: True)
...
Total Solidcore classes identified: 12

3. DELETE EXISTING GYM EVENTS
----------------------------------------------------------------------
Deleted 31 gym workout events

4. GENERATE WORKOUT SCHEDULE
----------------------------------------------------------------------
Scheduled FULL WORKOUT: Upper Push on 2025-12-01 at 07:30 (85 min)
Scheduled FULL WORKOUT: Lower Body - Hamstrings on 2025-12-02 at 20:00 (105 min)
Scheduled CARDIO-ONLY SESSION on 2025-12-04 at 19:20 (25 min)
Scheduled CARDIO-ONLY SESSION on 2025-12-05 at 19:50 (25 min)
...
Generated schedule for 2025-12: 23 full workouts + 8 cardio sessions = 31 total events

5. CREATE CALENDAR EVENTS
----------------------------------------------------------------------
Created event: Upper Push on 2025-12-01 07:30
Created event: Cardio Session - Post Solidcore on 2025-12-04 19:20
...

6. PROGRESSION STATE
----------------------------------------------------------------------
Current progression state:
  - Total workouts completed: 2
  - Current week: 1
  - Next deload at: 8 workouts

Note: Manually update progression_state.json after each completed workout.

7. SUMMARY
======================================================================
Month: 2025-12
Solidcore classes found: 12
Gym events deleted: 31

Events created:
  - Full workouts: 23
  - Cardio sessions: 8
  - Total events: 31

✓ Successfully scheduled 31 events!
======================================================================
```

## Future Enhancements

- Interactive prompts to adjust individual workout days
- Automatic progression adjustments based on completion tracking
- Export workout plans to PDF
- Integration with fitness tracking apps
- Performance analytics and recommendations

## Questions or Issues?

Check `gym_sync.log` for detailed execution logs with timestamps.
