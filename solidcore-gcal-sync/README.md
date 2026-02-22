# Solidcore → Google Calendar Sync

Automated sync tool that reads Solidcore class bookings from Gmail and creates/manages Google Calendar events with full class details.

## What It Does

This tool automatically:
- 📧 Scans Gmail for Solidcore booking confirmation emails (MindBody Online)
- 📅 Creates Google Calendar events with class details
- 🗑️ Processes cancellation emails and removes cancelled classes
- 🔄 Prevents duplicate events
- ⏰ Handles timezone conversion (Eastern Time)
- 📍 Includes location, instructor, and door code information

## Features

### Email Parsing
- Parses MindBody Online confirmation emails
- Extracts class name, date, time, location, instructor, door codes
- Supports multiple email formats (Solidcore Class, Signature50, Focus50, Advanced65)

### Calendar Management
- Creates events with formatted descriptions
- Duplicate detection (won't create the same event twice)
- Cancellation handling (automatically deletes cancelled classes)
- 30-day lookback window for recent bookings

### Smart Scheduling
- Timezone-aware (US/Eastern)
- Handles various class types (Full Body, Upper Body, Lower Body)
- Preserves class metadata (instructor names, studio location, door codes)

## Usage

### Prerequisites
- Python 3.9+
- Google Calendar API credentials (`credentials.json` in parent directory)
- Gmail API access

### Running the Sync

```bash
# Navigate to the directory
cd calendar-syncs/solidcore-gcal-sync

# Activate virtual environment (from parent directory)
source ../venv/bin/activate

# Run the sync
python main.py

# Or use the bash wrapper
./run_sync.sh
```

### Automated Sync (Optional)

Set up a cron job to run daily:

```bash
# Edit crontab
crontab -e

# Add this line (runs daily at 9 AM)
0 9 * * * /path/to/calendar-syncs/solidcore-gcal-sync/run_sync.sh
```

## File Structure

```
solidcore-gcal-sync/
├── main.py                # Main entry point
├── email_parser.py        # Gmail parsing and data extraction
├── calendar_manager.py    # Google Calendar event creation/deletion
├── run_sync.sh           # Bash wrapper for automation
└── README.md             # This file
```

## How It Works

1. **Authenticate**: Connects to Gmail and Google Calendar APIs using OAuth2
2. **Search Emails**: Looks for MindBody confirmation emails from the last 30 days
3. **Parse Details**: Extracts class information (name, date, time, location, instructor)
4. **Create Events**: Generates calendar events with full details
5. **Handle Cancellations**: Searches for cancellation emails and removes corresponding events
6. **Avoid Duplicates**: Checks for existing events before creating new ones

## Example Output

```
============================================================
         Solidcore Calendar Sync
============================================================

Step 1: Authenticating with Google APIs...
✓ Authentication successful

Step 2: Searching Gmail for Solidcore classes (last 30 days)...
✓ Found 22 classes

Step 3: Creating calendar events...
✓ Calendar sync complete

Step 4: Searching Gmail for cancellations (last 30 days)...
✓ Found 10 cancellations

Step 5: Processing cancellations...
✓ Cancellation processing complete

============================================================
                    SUMMARY
============================================================
Classes found in emails:     22
Events created:              7
Duplicates skipped:          15

CANCELLATIONS:
Cancellations found:         10
Events deleted:              7
No matching event found:     3
============================================================

✓ Sync complete! Check your Google Calendar.
```

## Dependencies

Shared with parent `calendar-syncs` project:
- `google-auth`
- `google-auth-oauthlib`
- `google-auth-httplib2`
- `google-api-python-client`
- `pytz`
- `beautifulsoup4`
- `lxml`

Install from parent directory:
```bash
cd calendar-syncs
pip install -r requirements.txt
```

## Authentication Setup

1. Create a Google Cloud project
2. Enable Gmail API and Google Calendar API
3. Download OAuth 2.0 credentials as `credentials.json`
4. Place in parent `calendar-syncs/` directory
5. First run will open browser for authorization
6. Token saved to `token.json` for future runs

## Troubleshooting

### No emails found
- Check that you're using the correct Gmail account
- Verify MindBody Online emails aren't filtered/archived
- Ensure the 30-day lookback window includes your bookings

### Duplicate events
- The tool prevents duplicates by checking existing calendar events
- If duplicates appear, they may be from manual entry or different sources

### Timezone issues
- All times are converted to US/Eastern timezone
- Verify your calendar timezone settings match

## Future Enhancements

- [ ] Support for multiple studio locations
- [ ] SMS notifications for upcoming classes
- [ ] Class attendance tracking
- [ ] Integration with other fitness studios

## Built With

This is a personal automation project demonstrating:
- API integration (Gmail, Google Calendar)
- Email parsing and data extraction
- OAuth2 authentication flow
- Python automation and scheduling
- Error handling and duplicate prevention

---

**Part of the [Calendar Automation Suite](../) - keeping my fitness schedule organized!**
