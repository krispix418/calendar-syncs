# Calendar Syncs

Personal fitness calendar automation — syncs Solidcore class bookings from Gmail and generates intelligent gym workout schedules around them.

## What It Does

Two scripts work together to keep a fitness calendar fully automated:

1. **Solidcore Sync** — scans Gmail for MindBody booking/cancellation emails and creates (or removes) the corresponding Google Calendar events
2. **Gym Scheduler** — generates a month of gym workout events, scheduling around Solidcore classes, rest days, and vacation blocks

## Architecture

```
Gmail (MindBody emails)
        │
        ▼
solidcore-gcal-sync/
  email_parser.py      ← parses booking + cancellation emails
  calendar_manager.py  ← creates/deletes Google Calendar events
        │
        ▼
Google Calendar (Solidcore events)
        │
        ▼
gym-split-scheduler/
  workout_scheduler.py ← reads calendar, applies scheduling logic, creates gym events
        │
        ▼
Google Calendar (full month of gym + cardio events)
```

Both scripts share a single OAuth2 credential and virtual environment at the repo root.

## Scheduling Logic (V3)

### Solidcore Sync
- Looks back 30 days for booking confirmations (configurable with `--days`)
- Supports all class types: Signature50, Focus50, Advanced65, Power30, Foundations50
- Cancellation emails trigger automatic event deletion
- Duplicate-safe — checks for existing events before creating

### Gym Scheduler
- **Tuesday / Thursday**: rest days — always skipped
- **Monday / Friday**: full workout at 7:15 AM (skipped if Solidcore that day)
- **Wednesday**: full workout at 8:00 PM (skipped if Solidcore that day)
- **Saturday / Sunday**: full workout always (Solidcore doesn't block weekends)
- **Vacation days**: multi-day all-day calendar events are detected and skipped automatically

### Workout Rotation
4-day upper/lower split cycling through: Upper Push → Lower Hamstrings → Upper Pull → Lower Quads

Each calendar event includes full exercise details, current weights/reps, and cardio.

## Project Structure

```
calendar-syncs/
├── auth.py                        # Shared Google OAuth2 authentication
├── requirements.txt               # Python dependencies
├── credentials.json               # OAuth credentials (not in repo — create your own)
├── token.json                     # Generated on first auth run (not in repo)
│
├── solidcore-gcal-sync/           # Solidcore email → Calendar sync
│   ├── main.py                    # Orchestration
│   ├── email_parser.py            # Gmail parser for MindBody emails
│   ├── calendar_manager.py        # Calendar event creation/deletion
│   └── run_sync.sh                # Shell wrapper for cron
│
└── gym-split-scheduler/           # Monthly gym workout scheduler
    ├── workout_scheduler.py       # Main scheduler
    ├── workout_plan.json          # Exercises, sets, reps, cardio
    ├── progression_state.json     # Tracks weights + deload cycle
    └── run_gym_sync.sh            # Shell wrapper for cron
```

## Setup

### 1. Google Cloud credentials
- Create a project at [Google Cloud Console](https://console.cloud.google.com/)
- Enable Gmail API and Google Calendar API
- Create OAuth 2.0 credentials (Desktop app type)
- Download as `credentials.json` and place at repo root

### 2. Python environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. First run (triggers browser OAuth)
```bash
cd solidcore-gcal-sync && python main.py
```

## Usage

### Solidcore Sync
```bash
cd solidcore-gcal-sync
source ../venv/bin/activate

python main.py              # sync last 30 days
python main.py --days 60    # sync last 60 days
python main.py --dry-run    # preview only
```

### Gym Scheduler
```bash
cd gym-split-scheduler
source ../venv/bin/activate

python workout_scheduler.py --month 2026-04
python workout_scheduler.py --month 2026-04 --dry-run
```

## Design Decisions

- **Shared auth layer** — one `credentials.json` and `token.json` at root, imported by both scripts via `auth.py`. Avoids duplicating OAuth boilerplate across scripts.
- **Solidcore-first pipeline** — the gym scheduler reads existing Solidcore events from the calendar rather than re-parsing emails, keeping the two scripts decoupled.
- **Vacation detection** — multi-day all-day events are treated as travel/vacation blocks. Gym events are skipped entirely for those dates.
- **No cardio-after-Solidcore on weekdays (V3)** — simplified from V2 which scheduled post-Solidcore cardio sessions. Recovery matters more than volume.

## Security

`credentials.json` and `token.json` are gitignored. Never commit them.

## Requirements

- Python 3.9+
- Google account with Gmail and Calendar API access
