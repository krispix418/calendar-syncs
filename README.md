# Calendar Syncs

Automated calendar management for fitness activities:
1. **Solidcore Sync**: Automatically sync Solidcore class bookings from Gmail to Google Calendar
2. **Gym Workout Scheduler**: Generate monthly gym workout schedules that intelligently work around Solidcore classes

## What It Does

This tool searches your Gmail for Solidcore class confirmation emails, extracts the class details (date, time, location, instructor), and creates calendar events in your Google Calendar. It includes duplicate detection to avoid creating the same event multiple times.

## Setup

1. **Create a Google Cloud Project** and enable Gmail and Calendar APIs
   - Visit [Google Cloud Console](https://console.cloud.google.com/)
   - Create OAuth 2.0 credentials (Desktop app)
   - Download `credentials.json` and place it in this directory

2. **Install Python dependencies**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Run the sync**
   ```bash
   python main.py
   ```

   On first run, a browser window will open for Google OAuth authorization. This creates a `token.json` file for future automated runs.

## Usage

### Solidcore Sync

Navigate to the solidcore directory:
```bash
cd solidcore
```

**Manual Sync:**
```bash
# Sync classes from last 30 days (default)
python main.py

# Sync classes from last 60 days
python main.py --days 60

# Preview without creating events (dry run)
python main.py --dry-run

# Enable verbose logging
python main.py --verbose
```

**Automated Sync (Cron Job):**
```bash
# Run manually
./run_sync.sh

# Set up automated daily sync at 10 PM
crontab -e
# Add this line:
0 22 * * * /Users/cjhalim/Desktop/Github/Portfolio/calendar-syncs/solidcore/run_sync.sh
```

**View sync logs:**
```bash
cat sync.log
```

### Gym Workout Scheduler

Navigate to the gym-workout directory:
```bash
cd gym-workout
```

**Manual Scheduling:**
```bash
# Schedule workouts for specific month
python workout_scheduler.py --month 2025-12

# Preview without creating events (dry run)
python workout_scheduler.py --month 2025-12 --dry-run
```

**Automated Scheduling:**
```bash
# Run manually for next month
./run_gym_sync.sh

# Set up automated monthly scheduling on the 25th at 9 AM
crontab -e
# Add this line:
0 9 25 * * /Users/cjhalim/Desktop/Github/Portfolio/calendar-syncs/gym-workout/run_gym_sync.sh
```

**View gym sync logs:**
```bash
cat gym_sync.log
```

See [gym-workout/README.md](gym-workout/README.md) for detailed gym workout documentation.

## Project Structure

```
calendar-syncs/
├── auth.py                    # Shared Google API authentication
├── credentials.json           # OAuth credentials (create this - NOT in repo)
├── token.json                # Access token (generated on first run)
├── requirements.txt          # Python dependencies
├── venv/                     # Python virtual environment
│
├── solidcore/                # Solidcore sync automation
│   ├── main.py              # Main orchestration script
│   ├── email_parser.py      # Gmail parser for Solidcore emails
│   ├── calendar_manager.py  # Google Calendar event creator
│   ├── run_sync.sh          # Automation script for cron jobs
│   └── sync.log            # Log file with timestamped results
│
└── gym-workout/             # Gym workout scheduler
    ├── workout_scheduler.py # Main scheduler script
    ├── workout_plan.json    # Complete workout plan
    ├── progression_state.json # Weight/rep progression tracking
    ├── run_gym_sync.sh     # Automation script
    ├── gym_sync.log       # Log file (created on first run)
    └── README.md          # Detailed gym workout documentation
```

## Security Notes

⚠️ **IMPORTANT**: Keep `credentials.json` and `token.json` secure and NEVER commit them to version control. These files are listed in `.gitignore` to prevent accidental commits.

## Features

- Searches Gmail for Solidcore booking confirmations
- Extracts class details: name, date/time, location, instructor, door codes
- Creates Google Calendar events with proper timezone handling (Eastern Time)
- Duplicate detection (won't create the same event twice)
- Configurable search range (days back)
- Dry run mode to preview changes
- Comprehensive logging and error handling

## Requirements

- Python 3.7+
- Google account with Gmail and Calendar access
- Solidcore class booking confirmation emails in Gmail
