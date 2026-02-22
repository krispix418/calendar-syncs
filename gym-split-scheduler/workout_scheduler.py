#!/usr/bin/env python3
"""
Gym Workout Calendar Scheduler

Generates a full month of gym workout calendar events based on:
- Pre-defined workout plan (workout_plan.json)
- Current progression state (progression_state.json)
- Existing Solidcore class schedule (from Google Calendar)
- Scheduling rules (weekday/weekend timing logic)

Usage:
    python workout_scheduler.py --month YYYY-MM [--dry-run]
"""

import sys
import os
import json
import argparse
import logging
from datetime import datetime, timedelta
from calendar import monthrange
import pytz

# Add parent directory to path to import auth module
sys.path.append('..')

# Import Google Calendar API
from googleapiclient.discovery import build

# Import auth module after changing to parent directory context
def authenticate():
    """
    Authenticate with Google Calendar API.
    Changes to parent directory to access credentials.json and token.json,
    then returns to original directory.

    Returns:
        credentials: Google API credentials object
    """
    # Save current directory
    original_dir = os.getcwd()

    try:
        # Change to parent directory where credentials.json is located
        parent_dir = os.path.dirname(original_dir)
        os.chdir(parent_dir)

        # Import and call get_credentials
        from auth import get_credentials
        credentials = get_credentials()

        return credentials
    finally:
        # Always return to original directory
        os.chdir(original_dir)

# Constants
EASTERN = pytz.timezone('US/Eastern')
CALENDAR_ID = 'primary'

# Workout title mappings
WORKOUT_TITLES = {
    "upper_push": "Upper Push",
    "lower_hamstring_posterior": "Lower Body - Hamstrings",
    "upper_pull": "Upper Pull",
    "lower_quad_glute": "Lower Body - Quads"
}

# Workout durations (in minutes)
WORKOUT_DURATIONS = {
    "upper_push": 85,          # 60 min weights + 25 min stairmaster
    "lower_hamstring_posterior": 105,  # 60 min weights + 45 min walking
    "upper_pull": 85,          # 60 min weights + 25 min stairmaster
    "lower_quad_glute": 105,   # 60 min weights + 45 min walking
    "cardio_only": 25          # 25 min stairmaster only (post-Solidcore)
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gym_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_json(filepath):
    """
    Load and parse JSON file.

    Args:
        filepath: Path to JSON file

    Returns:
        dict: Parsed JSON data

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If invalid JSON
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(filepath, 'r') as f:
        return json.load(f)


def save_json(filepath, data):
    """
    Save data to JSON file with pretty formatting.

    Args:
        filepath: Path to save JSON file
        data: Dictionary to save
    """
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved JSON to {filepath}")


def get_month_calendar_events(credentials, year, month):
    """
    Fetch all calendar events for a given month.

    Args:
        credentials: Google API credentials
        year: Integer year (e.g., 2025)
        month: Integer month (1-12)

    Returns:
        list: List of calendar event dictionaries from Google Calendar API
    """
    service = build('calendar', 'v3', credentials=credentials)

    # Define time range for the entire month
    time_min = datetime(year, month, 1, 0, 0, 0, tzinfo=EASTERN).isoformat()

    # Get last day of month
    _, last_day = monthrange(year, month)
    time_max = datetime(year, month, last_day, 23, 59, 59, tzinfo=EASTERN).isoformat()

    logger.info(f"Fetching calendar events from {time_min} to {time_max}")

    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    events = events_result.get('items', [])
    logger.info(f"Found {len(events)} total events in calendar for {year}-{month:02d}")

    return events


def identify_solidcore_classes(events):
    """
    Filter events to find Solidcore classes.

    Args:
        events: List of calendar events

    Returns:
        dict: Map of {date_string: {start_time, end_time, is_afternoon}}
              where date_string is "YYYY-MM-DD"
              is_afternoon is True if class starts after 12:00 PM
    """
    solidcore_schedule = {}

    for event in events:
        title = event.get('summary', '').lower()

        # Skip gym workout events (don't match our own cardio sessions or gym workouts)
        if any(keyword in title for keyword in ['cardio session', 'upper push', 'upper pull', 'lower body']):
            continue

        # Check if event is a Solidcore class (matches: solidcore, signature50, focus50, or advanced65)
        if any(keyword in title for keyword in ['solidcore', 'signature50', 'focus50', 'advanced65']):
            # Parse start and end times
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))

            # Convert to datetime objects
            start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))

            # Convert to Eastern timezone
            start_dt = start_dt.astimezone(EASTERN)
            end_dt = end_dt.astimezone(EASTERN)

            # Check if afternoon (starts at or after 12:00 PM)
            is_afternoon = start_dt.hour >= 12

            date_string = start_dt.strftime('%Y-%m-%d')

            # Only store if we haven't already found a Solidcore class on this date
            # (This handles cases where there might be multiple classes - we use the first one)
            if date_string not in solidcore_schedule:
                solidcore_schedule[date_string] = {
                    'start_time': start_dt,
                    'end_time': end_dt,
                    'is_afternoon': is_afternoon
                }

                logger.info(f"Solidcore class found: {date_string} at {start_dt.strftime('%H:%M')} "
                           f"(afternoon: {is_afternoon})")

    logger.info(f"Total Solidcore classes identified: {len(solidcore_schedule)}")
    return solidcore_schedule


def delete_gym_events(credentials, year, month, dry_run=False):
    """
    Delete existing gym workout events from target month.

    Args:
        credentials: Google API credentials
        year: Integer year
        month: Integer month
        dry_run: If True, only log what would be deleted

    Returns:
        int: Number of events deleted (or would be deleted)

    Gym events identified by title containing:
    - "Upper Push"
    - "Lower Body"
    - "Upper Pull"
    - "Cardio Session"
    """
    service = build('calendar', 'v3', credentials=credentials)

    # Get all events for the month
    events = get_month_calendar_events(credentials, year, month)

    gym_event_keywords = ['Upper Push', 'Lower Body', 'Upper Pull', 'Cardio Session']
    events_to_delete = []

    for event in events:
        title = event.get('summary', '')

        # Check if this is a gym workout event
        if any(keyword in title for keyword in gym_event_keywords):
            events_to_delete.append(event)

            if dry_run:
                logger.info(f"[DRY RUN] Would delete: {title} on "
                           f"{event['start'].get('dateTime', event['start'].get('date'))}")
            else:
                logger.info(f"Deleting: {title} on "
                           f"{event['start'].get('dateTime', event['start'].get('date'))}")

    # Delete events if not dry run
    if not dry_run:
        for event in events_to_delete:
            try:
                service.events().delete(
                    calendarId=CALENDAR_ID,
                    eventId=event['id']
                ).execute()
            except Exception as e:
                logger.error(f"Error deleting event {event.get('summary')}: {e}")

    logger.info(f"{'[DRY RUN] Would delete' if dry_run else 'Deleted'} "
               f"{len(events_to_delete)} gym workout events")

    return len(events_to_delete)


def determine_event_type(date, day_of_week, solidcore_schedule):
    """
    Determine what type of event to create based on V2 rules.

    Args:
        date: datetime object for the day
        day_of_week: Integer (0=Monday, 6=Sunday)
        solidcore_schedule: Dict from identify_solidcore_classes()

    Returns:
        tuple: (event_type, start_time_or_rule)
            event_type: "full_workout" or "cardio_only"
            start_time_or_rule: datetime object or "after_solidcore_plus_30min" or None

    V2 Logic:
        Weekdays (Mon-Fri):
            - Mon/Fri WITHOUT Solidcore: full_workout at 7:15 AM (morning)
            - Mon/Fri WITH Solidcore: cardio_only after Solidcore + 30 min
            - Tue/Wed/Thu WITH Solidcore: cardio_only after Solidcore + 30 min
            - Tue/Wed/Thu WITHOUT Solidcore: full_workout at 8 PM

        Weekends (Sat/Sun):
            - Always full_workout
            - WITH Solidcore: after Solidcore + 30 min
            - WITHOUT Solidcore: 3 PM
    """
    date_string = date.strftime('%Y-%m-%d')
    solidcore = solidcore_schedule.get(date_string)

    # Weekdays: Monday (0), Tuesday (1), Wednesday (2), Thursday (3), Friday (4)
    if day_of_week in [0, 1, 2, 3, 4]:
        # Monday or Friday
        if day_of_week in [0, 4]:
            if solidcore:
                # WITH Solidcore: Cardio only after Solidcore
                buffer = timedelta(minutes=30)
                start_time = solidcore['end_time'] + buffer
                return ("cardio_only", start_time)
            else:
                # WITHOUT Solidcore: Full workout at 7:15 AM
                return ("full_workout", EASTERN.localize(datetime(date.year, date.month, date.day, 7, 15)))

        # Tuesday, Wednesday, Thursday
        else:
            if solidcore:
                # Cardio only after Solidcore
                buffer = timedelta(minutes=30)
                start_time = solidcore['end_time'] + buffer
                return ("cardio_only", start_time)
            else:
                # Full workout at 8 PM
                return ("full_workout", EASTERN.localize(datetime(date.year, date.month, date.day, 20, 0)))

    # Weekends: Saturday (5), Sunday (6)
    elif day_of_week in [5, 6]:
        # Always full workout on weekends
        if solidcore:
            buffer = timedelta(minutes=30)
            start_time = solidcore['end_time'] + buffer
            return ("full_workout", start_time)
        else:
            return ("full_workout", EASTERN.localize(datetime(date.year, date.month, date.day, 15, 0)))

    return (None, None)


def get_ramping_weights(progression_state):
    """
    Get current ramping weights for squats.

    Args:
        progression_state: Loaded progression_state.json dict

    Returns:
        list: [weight1, weight2, weight3] for the three squat sets
    """
    if 'ramping_exercises' in progression_state and 'squats' in progression_state['ramping_exercises']:
        return progression_state['ramping_exercises']['squats']['current_ramp']
    else:
        # Fallback to default
        return [30, 40, 55]


def determine_workout_schedule(year, month, solidcore_schedule, workout_rotation):
    """
    Generate gym workout schedule for the month using V2 logic.

    Args:
        year: Integer year
        month: Integer month
        solidcore_schedule: Dict from identify_solidcore_classes()
        workout_rotation: List of workout types to cycle through

    Returns:
        list: List of dicts with {date, event_type, workout_type, start_time, duration_minutes}

    V2 Scheduling Logic:

    Two Event Types:
        1. full_workout: Complete workout (weights + cardio) - ADVANCES rotation
        2. cardio_only: Just cardio after Solidcore - DOES NOT advance rotation

    Weekdays:
        Monday/Friday: full_workout at 7:15 AM (finish by 9 AM)
        Tue/Wed/Thu:
            - WITH Solidcore: cardio_only after Solidcore + 30 min
            - WITHOUT Solidcore: full_workout at 8 PM

    Weekends:
        Saturday/Sunday:
            - Always full_workout
            - WITH Solidcore: after Solidcore + 30 min
            - WITHOUT Solidcore: 3 PM

    Rotation:
        Only full_workout events advance the rotation
        Cardio-only sessions do NOT advance rotation
    """
    schedule = []
    rotation_index = 0

    # Get all days in the month
    _, last_day = monthrange(year, month)

    for day in range(1, last_day + 1):
        date = datetime(year, month, day)
        date_string = date.strftime('%Y-%m-%d')
        day_of_week = date.weekday()  # 0=Monday, 6=Sunday

        # Determine event type and start time using V2 logic
        event_type, start_time = determine_event_type(date, day_of_week, solidcore_schedule)

        if not event_type or not start_time:
            continue

        # Assign workout type based on event type
        if event_type == "full_workout":
            workout_type = workout_rotation[rotation_index % len(workout_rotation)]
            duration = WORKOUT_DURATIONS[workout_type]

            # Adjust start time for Monday/Friday based on duration
            if day_of_week in [0, 4]:
                if duration == 105:  # Lower body workouts
                    start_time = EASTERN.localize(datetime(year, month, day, 7, 15))
                else:  # Upper body workouts (85 min)
                    start_time = EASTERN.localize(datetime(year, month, day, 7, 30))

            schedule.append({
                'date': date,
                'event_type': event_type,
                'workout_type': workout_type,
                'start_time': start_time,
                'duration_minutes': duration
            })

            logger.info(f"Scheduled FULL WORKOUT: {WORKOUT_TITLES[workout_type]} on {date_string} "
                       f"at {start_time.strftime('%H:%M')} ({duration} min)")

            # Advance rotation for full workouts
            rotation_index += 1

        elif event_type == "cardio_only":
            workout_type = "cardio_only"
            duration = WORKOUT_DURATIONS["cardio_only"]

            schedule.append({
                'date': date,
                'event_type': event_type,
                'workout_type': workout_type,
                'start_time': start_time,
                'duration_minutes': duration
            })

            logger.info(f"Scheduled CARDIO-ONLY SESSION on {date_string} "
                       f"at {start_time.strftime('%H:%M')} ({duration} min)")

            # Do NOT advance rotation for cardio-only sessions

    full_workout_count = sum(1 for w in schedule if w['event_type'] == 'full_workout')
    cardio_only_count = sum(1 for w in schedule if w['event_type'] == 'cardio_only')

    logger.info(f"Generated schedule for {year}-{month:02d}: "
               f"{full_workout_count} full workouts + {cardio_only_count} cardio sessions = {len(schedule)} total events")
    return schedule


def format_workout_description(workout_type, workout_plan, progression_state):
    """
    Format detailed workout description for calendar event.

    Args:
        workout_type: String key (e.g., "upper_push", "cardio_only")
        workout_plan: Loaded workout_plan.json dict
        progression_state: Loaded progression_state.json dict

    Returns:
        str: Formatted multiline description with:
            - Workout name and focus
            - Warmup exercises
            - Main exercises with current weights/reps from progression_state
            - Notes and form cues
            - Cardio details
            - Cooldown
    """
    # Handle cardio-only sessions
    if workout_type == "cardio_only":
        cardio_session = workout_plan['cardio_only_session']
        lines = [
            f"🏃 {cardio_session['name'].upper()}",
            "",
            cardio_session['description'],
            "",
            f"💨 CARDIO:",
            f"{cardio_session['cardio']['type']} - {cardio_session['cardio']['duration_minutes']} minutes",
            f"Intensity: {cardio_session['cardio']['intensity']}",
            "",
            f"Note: {cardio_session['cardio']['notes']}"
        ]
        return '\n'.join(lines)

    # Handle full workout sessions
    workout = workout_plan['workouts'][workout_type]
    state = progression_state['workout_states'][workout_type]

    # V2: Use workout completion count for deload instead of week number
    total_workouts = progression_state['workout_completion_count']['total']
    next_deload_at = progression_state['deload_schedule']['next_deload_at_workout_count']
    is_deload = total_workouts >= next_deload_at

    # Start with workout name and focus
    lines = [
        f"🔥 {workout['name'].upper()}",
        f"Focus: {workout['focus']}",
        ""
    ]

    # Deload indicator
    if is_deload:
        lines.extend([
            "⚠️ DELOAD WEEK - Reduce weights by 20%",
            ""
        ])

    # Warmup section
    lines.extend([
        f"⏱️ WARMUP ({workout['warmup']['duration_minutes']} min):"
    ])
    for exercise in workout['warmup']['exercises']:
        lines.append(f"• {exercise}")
    lines.append("")

    # Main workout section
    lines.extend([
        "💪 MAIN WORKOUT:",
        ""
    ])

    for i, exercise_plan in enumerate(workout['main_exercises'], 1):
        exercise_name = exercise_plan['exercise']

        # Get current progression for this exercise (match by exercise key)
        exercise_key = None
        for key in state['exercises'].keys():
            # Match exercise names (simplified matching)
            if exercise_name.lower().replace(' ', '_').replace('-', '_') in key:
                exercise_key = key
                break

        if exercise_key:
            exercise_state = state['exercises'][exercise_key]
            current_weight = exercise_state['current_weight_lbs']
            current_reps = exercise_state['current_reps']

            # V2: Handle ramping for squats
            if exercise_name.lower() == "squats":
                ramp_weights = get_ramping_weights(progression_state)

                # Apply deload if applicable
                if is_deload:
                    ramp_weights = [int(w * 0.8) for w in ramp_weights]

                # Format with ramping weights
                lines.extend([
                    f"{i}. {exercise_name} ({exercise_plan['primary_equipment']})",
                    f"   Set 1: {current_reps} reps @ {ramp_weights[0]} lbs",
                    f"   Set 2: {current_reps} reps @ {ramp_weights[1]} lbs",
                    f"   Set 3: {current_reps} reps @ {ramp_weights[2]} lbs",
                    f"   Rest: {exercise_plan['rest_seconds']}s",
                    f"   → {exercise_plan['notes']}",
                    ""
                ])
                continue

            # Apply deload if applicable (non-ramping exercises)
            if is_deload:
                current_weight = int(current_weight * 0.8)
        else:
            # Fallback to starting weight if not found
            current_weight = exercise_plan['starting_weight_lbs']
            current_reps = 12

        # Format exercise info (standard exercises)
        lines.extend([
            f"{i}. {exercise_name} ({exercise_plan['primary_equipment']})",
            f"   {exercise_plan['sets']} sets x {current_reps} reps @ {current_weight} lbs | Rest: {exercise_plan['rest_seconds']}s",
            f"   → {exercise_plan['notes']}",
            ""
        ])

    # Cardio section
    cardio = workout['cardio']
    lines.extend([
        "🏃 CARDIO:",
        f"{cardio['type']} - {cardio['duration_minutes']} minutes ({cardio['intensity']})",
        ""
    ])

    # Cooldown section
    lines.extend([
        f"🧘 COOLDOWN ({workout['cooldown']['duration_minutes']} min):",
        workout['cooldown']['notes']
    ])

    return '\n'.join(lines)


def create_calendar_event(credentials, title, description, start_datetime, duration_minutes, dry_run=False):
    """
    Create a Google Calendar event.

    Args:
        credentials: Google API credentials
        title: Event title (e.g., "Upper Push")
        description: Detailed workout description
        start_datetime: datetime object with timezone
        duration_minutes: Integer duration
        dry_run: If True, only log what would be created

    Returns:
        dict: Created event object (or None if dry_run)
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would create event: {title} on "
                   f"{start_datetime.strftime('%Y-%m-%d %H:%M')} ({duration_minutes} min)")
        return None

    service = build('calendar', 'v3', credentials=credentials)

    end_datetime = start_datetime + timedelta(minutes=duration_minutes)

    event = {
        'summary': title,
        'description': description,
        'location': 'Planet Fitness',
        'start': {
            'dateTime': start_datetime.isoformat(),
            'timeZone': 'America/New_York',
        },
        'end': {
            'dateTime': end_datetime.isoformat(),
            'timeZone': 'America/New_York',
        },
    }

    try:
        created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        logger.info(f"Created event: {title} on {start_datetime.strftime('%Y-%m-%d %H:%M')}")
        return created_event
    except Exception as e:
        logger.error(f"Error creating event {title}: {e}")
        return None


def update_progression_state(progression_state, schedule):
    """
    Update progression state after scheduling month (V2).

    Args:
        progression_state: Current progression_state dict
        schedule: List of scheduled workouts from determine_workout_schedule()

    Returns:
        dict: Updated progression_state

    V2 Logic:
    - Count full workouts by type (cardio-only does NOT count)
    - Update workout_completion_count for each workout type
    - Check if deload threshold reached (every 8 full workouts)
    - Update next_deload_at_workout_count if needed
    - Increment current_week based on full workouts (approximate)
    - Add entry to progression_history with changes
    """
    old_week = progression_state['current_week']
    old_total = progression_state['workout_completion_count']['total']

    # Count full workouts by type (ignore cardio-only)
    workout_counts = {}
    for workout in schedule:
        if workout['event_type'] == 'full_workout':
            workout_type = workout['workout_type']
            workout_counts[workout_type] = workout_counts.get(workout_type, 0) + 1

    # Update progression state
    for workout_type, count in workout_counts.items():
        progression_state['workout_completion_count'][workout_type] += count

    # Update total
    new_total_workouts = sum(workout_counts.values())
    progression_state['workout_completion_count']['total'] = old_total + new_total_workouts

    # Update current week (approximate, based on ~4 workouts per week)
    num_weeks = max(1, new_total_workouts // 4)
    new_week = old_week + num_weeks
    progression_state['current_week'] = new_week

    progression_state['last_updated'] = datetime.now().strftime('%Y-%m-%d')

    # Check if we've reached deload threshold
    next_deload_at = progression_state['deload_schedule']['next_deload_at_workout_count']
    if progression_state['workout_completion_count']['total'] >= next_deload_at:
        # Schedule next deload 8 workouts from now
        progression_state['deload_schedule']['next_deload_at_workout_count'] = next_deload_at + 8
        logger.info(f"Deload threshold reached! Next deload will be at workout count {next_deload_at + 8}")

    # Add to history
    history_entry = {
        'date': progression_state['last_updated'],
        'old_week': old_week,
        'new_week': new_week,
        'weeks_scheduled': num_weeks,
        'full_workouts_added': new_total_workouts,
        'total_workout_count': progression_state['workout_completion_count']['total']
    }

    if 'changes' not in progression_state['progression_history']:
        progression_state['progression_history']['changes'] = []

    progression_state['progression_history']['changes'].append(history_entry)

    logger.info(f"Progression updated: Week {old_week} → Week {new_week}, "
               f"Total workouts: {old_total} → {progression_state['workout_completion_count']['total']}")

    return progression_state


def main():
    """Main execution function."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Generate gym workout calendar events for a month'
    )
    parser.add_argument(
        '--month',
        required=True,
        help='Target month in YYYY-MM format (e.g., 2025-12)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be created without actually creating events'
    )

    args = parser.parse_args()

    # Parse month argument
    try:
        year, month = map(int, args.month.split('-'))
        if not (1 <= month <= 12):
            raise ValueError("Month must be between 1 and 12")
    except ValueError as e:
        logger.error(f"Invalid month format: {args.month}. Use YYYY-MM format (e.g., 2025-12)")
        sys.exit(1)

    dry_run = args.dry_run

    logger.info("=" * 70)
    logger.info(f"GYM WORKOUT CALENDAR SCHEDULER - {year}-{month:02d}")
    if dry_run:
        logger.info("[DRY RUN MODE - No changes will be made]")
    logger.info("=" * 70)

    try:
        # 1. SETUP
        logger.info("\n1. SETUP")
        logger.info("-" * 70)

        # Authenticate
        logger.info("Authenticating with Google Calendar API...")
        credentials = authenticate()

        # Load workout plan and progression state
        logger.info("Loading workout plan...")
        workout_plan = load_json('workout_plan.json')

        logger.info("Loading progression state...")
        progression_state = load_json('progression_state.json')

        logger.info(f"Current week: {progression_state['current_week']}")
        logger.info(f"Total workouts completed: {progression_state['workout_completion_count']['total']}")
        logger.info(f"Next deload at workout count: {progression_state['deload_schedule']['next_deload_at_workout_count']}")

        # 2. CALENDAR ANALYSIS
        logger.info("\n2. CALENDAR ANALYSIS")
        logger.info("-" * 70)

        events = get_month_calendar_events(credentials, year, month)
        solidcore_schedule = identify_solidcore_classes(events)

        # 3. DELETE EXISTING GYM EVENTS
        logger.info("\n3. DELETE EXISTING GYM EVENTS")
        logger.info("-" * 70)

        deleted_count = delete_gym_events(credentials, year, month, dry_run)

        # 4. GENERATE WORKOUT SCHEDULE
        logger.info("\n4. GENERATE WORKOUT SCHEDULE")
        logger.info("-" * 70)

        workout_rotation = workout_plan['scheduling_rules']['workout_rotation']
        schedule = determine_workout_schedule(year, month, solidcore_schedule, workout_rotation)

        # 5. CREATE CALENDAR EVENTS
        logger.info("\n5. CREATE CALENDAR EVENTS")
        logger.info("-" * 70)

        created_count = 0
        full_workout_count = 0
        cardio_only_count = 0

        for workout in schedule:
            # Handle different titles for event types
            if workout['workout_type'] == 'cardio_only':
                title = "Cardio Session - Post Solidcore"
                cardio_only_count += 1
            else:
                title = WORKOUT_TITLES[workout['workout_type']]
                full_workout_count += 1

            description = format_workout_description(
                workout['workout_type'],
                workout_plan,
                progression_state
            )

            event = create_calendar_event(
                credentials,
                title,
                description,
                workout['start_time'],
                workout['duration_minutes'],
                dry_run
            )

            if event or dry_run:
                created_count += 1

        # 6. UPDATE PROGRESSION STATE
        logger.info("\n6. PROGRESSION STATE")
        logger.info("-" * 70)

        # NOTE: Progression state is NOT automatically updated by the scheduler.
        # The scheduler only SCHEDULES workouts - it doesn't track completion.
        # You must manually update progression_state.json as you complete workouts.
        logger.info(f"Current progression state:")
        logger.info(f"  - Total workouts completed: {progression_state['workout_completion_count']['total']}")
        logger.info(f"  - Current week: {progression_state['current_week']}")
        logger.info(f"  - Next deload at: {progression_state['deload_schedule']['next_deload_at_workout_count']} workouts")
        logger.info(f"\nNote: Manually update progression_state.json after each completed workout.")

        # 7. SUMMARY
        logger.info("\n7. SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Month: {year}-{month:02d}")
        logger.info(f"Solidcore classes found: {len(solidcore_schedule)}")
        logger.info(f"Gym events deleted: {deleted_count}")
        logger.info(f"\nEvents created:")
        logger.info(f"  - Full workouts: {full_workout_count}")
        logger.info(f"  - Cardio sessions: {cardio_only_count}")
        logger.info(f"  - Total events: {created_count}")
        if dry_run:
            logger.info("\n[DRY RUN] No changes were made to calendar or progression state")
        else:
            logger.info(f"\n✓ Successfully scheduled {created_count} events!")
        logger.info("=" * 70)

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
