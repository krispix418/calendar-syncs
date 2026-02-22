"""
Google Calendar Manager Module

This module handles creating and managing Solidcore class events in Google Calendar.
It includes duplicate detection to avoid creating the same event multiple times.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pytz

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
EASTERN_TZ = pytz.timezone('America/New_York')


def create_calendar_events(
    credentials,
    classes: List[Dict],
    calendar_id: str = 'primary'
) -> Dict[str, int]:
    """
    Creates Google Calendar events for Solidcore classes.

    This function:
    1. Checks for existing events to avoid duplicates
    2. Creates new calendar events for classes that don't exist yet
    3. Returns a summary of created vs. skipped events

    Args:
        credentials: Google API credentials object from auth.py
        classes: List of class dictionaries with fields:
            - title: Class name/type
            - start_time: ISO format datetime string
            - end_time: ISO format datetime string
            - location: Studio name/address
            - description: Additional details
        calendar_id: Calendar ID to add events to (default: 'primary')

    Returns:
        Dict with summary:
            - 'created': Number of events created
            - 'duplicates': Number of duplicates skipped
            - 'errors': Number of errors encountered

    Raises:
        HttpError: If Calendar API request fails
    """
    try:
        # Build Calendar API service
        service = build('calendar', 'v3', credentials=credentials)
        logger.info(f"Calendar API service created successfully")
        logger.info(f"Processing {len(classes)} classes for calendar '{calendar_id}'")

        # Initialize counters
        created_count = 0
        duplicate_count = 0
        error_count = 0

        # Get existing events to check for duplicates
        existing_events = _get_existing_events(service, calendar_id, classes)
        logger.info(f"Found {len(existing_events)} existing calendar events")

        # Process each class
        for class_event in classes:
            try:
                # Check if event already exists
                if _is_duplicate(class_event, existing_events):
                    logger.info(
                        f"Skipping duplicate: {class_event['title']} at "
                        f"{class_event['start_time']}"
                    )
                    duplicate_count += 1
                    continue

                # Create the event
                created_event = _create_event(service, calendar_id, class_event)

                if created_event:
                    logger.info(
                        f"Created event: {class_event['title']} at "
                        f"{class_event['start_time']}"
                    )
                    created_count += 1
                else:
                    error_count += 1

            except Exception as e:
                logger.error(
                    f"Error processing class '{class_event.get('title', 'Unknown')}': {e}"
                )
                error_count += 1
                continue

        # Log summary
        summary = {
            'created': created_count,
            'duplicates': duplicate_count,
            'errors': error_count
        }

        logger.info(f"\n=== Summary ===")
        logger.info(f"Events created: {created_count}")
        logger.info(f"Duplicates skipped: {duplicate_count}")
        logger.info(f"Errors: {error_count}")

        return summary

    except HttpError as error:
        logger.error(f"Calendar API error: {error}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in create_calendar_events: {e}")
        raise


def _get_existing_events(
    service,
    calendar_id: str,
    classes: List[Dict]
) -> List[Dict]:
    """
    Fetch existing calendar events within the date range of the classes.

    Args:
        service: Calendar API service object
        calendar_id: Calendar ID to query
        classes: List of class dictionaries (to determine date range)

    Returns:
        List of existing calendar events
    """
    if not classes:
        return []

    try:
        # Determine the date range from the classes
        start_times = [
            datetime.fromisoformat(c['start_time']) for c in classes
        ]
        min_date = min(start_times)
        max_date = max(start_times) + timedelta(days=1)

        # Query calendar for events in this range
        logger.info(
            f"Checking for existing events between {min_date.date()} and {max_date.date()}"
        )

        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=min_date.isoformat(),
            timeMax=max_date.isoformat(),
            singleEvents=True,
            orderBy='startTime',
            maxResults=500  # Adjust if you have more events
        ).execute()

        events = events_result.get('items', [])
        return events

    except HttpError as e:
        logger.error(f"Error fetching existing events: {e}")
        return []


def _is_duplicate(class_event: Dict, existing_events: List[Dict]) -> bool:
    """
    Check if a class event already exists in the calendar.

    An event is considered a duplicate if it has:
    - Same title (or very similar)
    - Same start time (within 1 minute tolerance)

    Args:
        class_event: Class dictionary to check
        existing_events: List of existing calendar events

    Returns:
        bool: True if duplicate found, False otherwise
    """
    try:
        class_title = class_event['title'].lower().strip()
        class_start = datetime.fromisoformat(class_event['start_time'])

        for existing in existing_events:
            existing_title = existing.get('summary', '').lower().strip()

            # Get start time from existing event
            start_field = existing.get('start', {})
            existing_start_str = start_field.get('dateTime') or start_field.get('date')

            if not existing_start_str:
                continue

            existing_start = datetime.fromisoformat(
                existing_start_str.replace('Z', '+00:00')
            )

            # Ensure both datetimes are timezone-aware for comparison
            # If class_start is naive, localize it to Eastern Time
            if class_start.tzinfo is None:
                class_start = EASTERN_TZ.localize(class_start)

            # If existing_start is naive, localize it to Eastern Time
            if existing_start.tzinfo is None:
                existing_start = EASTERN_TZ.localize(existing_start)

            # Check if titles match (allowing for minor variations)
            title_match = (
                class_title == existing_title or
                'solidcore' in class_title and 'solidcore' in existing_title and
                _titles_similar(class_title, existing_title)
            )

            # Check if start times match (within 1 minute tolerance)
            time_diff = abs((class_start - existing_start).total_seconds())
            time_match = time_diff < 60  # 1 minute tolerance

            if title_match and time_match:
                return True

        return False

    except Exception as e:
        logger.error(f"Error checking for duplicate: {e}")
        # If we can't determine, assume it's not a duplicate to be safe
        return False


def _titles_similar(title1: str, title2: str) -> bool:
    """
    Check if two titles are similar enough to be considered the same event.

    Args:
        title1: First title (lowercase)
        title2: Second title (lowercase)

    Returns:
        bool: True if titles are similar
    """
    # Extract key words (remove common words)
    common_words = {'at', 'with', 'w/', 'the', 'a', 'an', 'in', 'on', 'class'}

    words1 = set(title1.split()) - common_words
    words2 = set(title2.split()) - common_words

    # Calculate overlap
    if not words1 or not words2:
        return False

    overlap = len(words1 & words2)
    min_length = min(len(words1), len(words2))

    # If 70% or more words overlap, consider similar
    return (overlap / min_length) >= 0.7


def _create_event(service, calendar_id: str, class_event: Dict) -> Dict:
    """
    Create a single calendar event.

    Args:
        service: Calendar API service object
        calendar_id: Calendar ID to add event to
        class_event: Class dictionary with event details

    Returns:
        Dict: Created event object, or None if creation failed
    """
    try:
        # Parse datetime strings
        start_dt = datetime.fromisoformat(class_event['start_time'])
        end_dt = datetime.fromisoformat(class_event['end_time'])

        # Build event object for Calendar API
        event = {
            'summary': class_event['title'],
            'location': class_event.get('location', ''),
            'description': class_event.get('description', ''),
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'America/New_York',
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'America/New_York',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 60},  # 1 hour before
                    {'method': 'popup', 'minutes': 15},  # 15 minutes before
                ],
            },
            'colorId': '9',  # Optional: Use color to distinguish Solidcore classes
        }

        # Create the event
        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event
        ).execute()

        logger.debug(f"Event created with ID: {created_event.get('id')}")
        return created_event

    except HttpError as e:
        logger.error(f"HTTP error creating event: {e}")
        return None
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        return None


def delete_calendar_events(
    credentials,
    cancellations: List[Dict],
    calendar_id: str = 'primary'
) -> Dict[str, int]:
    """
    Deletes Google Calendar events for cancelled Solidcore classes.

    This function:
    1. Iterates through cancellation records with date, time, and location
    2. Searches calendar for matching events (must match all three criteria)
    3. Deletes matched events with careful verification to avoid accidental deletions
    4. Returns a summary of deleted vs. not found

    Args:
        credentials: Google API credentials object from auth.py
        cancellations: List of cancellation dictionaries with fields:
            - date: Date string (e.g., "11/23/2025")
            - time: Time string (e.g., "10:00 AM")
            - location: Studio location
            - original_datetime: Timezone-aware datetime object
        calendar_id: Calendar ID to delete events from (default: 'primary')

    Returns:
        Dict with summary:
            - 'deleted': Number of events deleted
            - 'not_found': Number of cancellations with no matching event
            - 'errors': Number of errors encountered

    Raises:
        HttpError: If Calendar API request fails
    """
    try:
        # Build Calendar API service
        service = build('calendar', 'v3', credentials=credentials)
        logger.info(f"Calendar API service created successfully")
        logger.info(f"Processing {len(cancellations)} cancellations for calendar '{calendar_id}'")

        # Initialize counters
        deleted_count = 0
        not_found_count = 0
        error_count = 0

        # Get existing events
        # We'll search within a reasonable window around each cancellation
        existing_events = _get_all_calendar_events(service, calendar_id)
        logger.info(f"Retrieved {len(existing_events)} existing calendar events")

        # Process each cancellation
        for cancellation in cancellations:
            try:
                # Find matching event(s)
                matching_events = _find_matching_events(
                    cancellation,
                    existing_events
                )

                if not matching_events:
                    logger.warning(
                        f"No matching event found for cancellation: "
                        f"{cancellation['date']} at {cancellation['time']} "
                        f"({cancellation['location']})"
                    )
                    not_found_count += 1
                    continue

                # Delete each matching event
                for event in matching_events:
                    try:
                        event_id = event['id']
                        event_title = event.get('summary', 'Unknown')
                        event_start = event.get('start', {}).get('dateTime', 'Unknown')

                        service.events().delete(
                            calendarId=calendar_id,
                            eventId=event_id
                        ).execute()

                        logger.info(
                            f"Deleted event: {event_title} at {event_start} "
                            f"(matching cancellation: {cancellation['date']} "
                            f"{cancellation['time']})"
                        )
                        deleted_count += 1

                    except Exception as e:
                        logger.error(
                            f"Error deleting event {event.get('id')}: {e}"
                        )
                        error_count += 1
                        continue

            except Exception as e:
                logger.error(
                    f"Error processing cancellation "
                    f"{cancellation.get('date', 'Unknown')} "
                    f"{cancellation.get('time', 'Unknown')}: {e}"
                )
                error_count += 1
                continue

        # Log summary
        summary = {
            'deleted': deleted_count,
            'not_found': not_found_count,
            'errors': error_count
        }

        logger.info(f"\n=== Cancellation Summary ===")
        logger.info(f"Events deleted: {deleted_count}")
        logger.info(f"Cancellations with no matching event: {not_found_count}")
        logger.info(f"Errors: {error_count}")

        return summary

    except HttpError as error:
        logger.error(f"Calendar API error: {error}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in delete_calendar_events: {e}")
        raise


def _get_all_calendar_events(service, calendar_id: str) -> List[Dict]:
    """
    Fetch all calendar events (or at least a large range).

    Args:
        service: Calendar API service object
        calendar_id: Calendar ID to query

    Returns:
        List of calendar events
    """
    try:
        # Get events for a wide date range (past 6 months to future 6 months)
        now = datetime.now(EASTERN_TZ)
        time_min = (now - timedelta(days=180)).isoformat()
        time_max = (now + timedelta(days=180)).isoformat()

        logger.info(
            f"Retrieving calendar events between {time_min} and {time_max}"
        )

        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime',
            maxResults=1000  # Increase if needed
        ).execute()

        events = events_result.get('items', [])
        return events

    except HttpError as e:
        logger.error(f"Error fetching calendar events: {e}")
        return []


def _find_matching_events(
    cancellation: Dict,
    existing_events: List[Dict]
) -> List[Dict]:
    """
    Find calendar events matching a cancellation.

    An event matches if:
    1. Start time matches within 2 minutes (accounts for timezone handling)
    2. Location contains the cancellation location (fuzzy match)
    3. Event is a Solidcore class (optional: "solidcore" in title)

    Args:
        cancellation: Cancellation dictionary with date, time, location, original_datetime
        existing_events: List of existing calendar events

    Returns:
        List of matching events (usually 0 or 1)
    """
    try:
        matches = []

        cancel_datetime = cancellation.get('original_datetime')
        cancel_location = cancellation.get('location', '').lower().strip()

        if not cancel_datetime:
            logger.warning(f"No datetime for cancellation: {cancellation}")
            return matches

        logger.debug(
            f"Searching for events matching: {cancel_datetime.isoformat()} "
            f"at {cancel_location}"
        )

        for event in existing_events:
            try:
                # Get event start time
                start_field = event.get('start', {})
                event_start_str = start_field.get('dateTime') or start_field.get('date')

                if not event_start_str:
                    continue

                # Parse event start time
                event_start = datetime.fromisoformat(
                    event_start_str.replace('Z', '+00:00')
                )

                # Check if times match (within 2 minutes tolerance for timezone handling)
                time_diff_seconds = abs((cancel_datetime - event_start).total_seconds())
                time_match = time_diff_seconds < 120  # 2 minutes tolerance

                if not time_match:
                    continue

                # Check location match
                event_location = event.get('location', '').lower().strip()
                location_match = (
                    cancel_location in event_location or
                    event_location in cancel_location or
                    _locations_similar(cancel_location, event_location)
                )

                if not location_match:
                    logger.debug(
                        f"Location mismatch: '{cancel_location}' vs '{event_location}'"
                    )
                    continue

                # Optionally check if event is Solidcore-related
                event_title = event.get('summary', '').lower()
                is_solidcore = 'solidcore' in event_title or 'signature50' in event_title

                logger.debug(
                    f"Potential match found: {event.get('summary')} at "
                    f"{event_start.isoformat()} (time_diff: {time_diff_seconds}s, "
                    f"solidcore: {is_solidcore})"
                )

                # Add to matches
                matches.append(event)

            except Exception as e:
                logger.debug(f"Error checking event for match: {e}")
                continue

        logger.info(f"Found {len(matches)} matching event(s) for cancellation")
        return matches

    except Exception as e:
        logger.error(f"Error finding matching events: {e}")
        return []


def _locations_similar(location1: str, location2: str) -> bool:
    """
    Check if two location strings are similar enough to be considered the same.

    Args:
        location1: First location string (lowercase)
        location2: Second location string (lowercase)

    Returns:
        bool: True if locations are similar
    """
    try:
        # Extract key words (remove common words)
        common_words = {'at', 'the', 'a', 'an', 'in', 'on', 'studio', 'location', 'class'}

        words1 = set(location1.split()) - common_words
        words2 = set(location2.split()) - common_words

        if not words1 or not words2:
            return location1 == location2

        # Check if any significant words overlap
        overlap = len(words1 & words2)
        min_length = min(len(words1), len(words2))

        # If 50% or more words overlap, consider similar
        similarity = (overlap / min_length) >= 0.5
        logger.debug(
            f"Location similarity: '{location1}' vs '{location2}' = {similarity} "
            f"(overlap: {overlap}/{min_length})"
        )
        return similarity

    except Exception as e:
        logger.debug(f"Error comparing locations: {e}")
        return False


def delete_solidcore_events(
    credentials,
    start_date: datetime,
    end_date: datetime,
    calendar_id: str = 'primary',
    dry_run: bool = True
) -> int:
    """
    Delete Solidcore events from calendar (useful for testing/cleanup).

    Args:
        credentials: Google API credentials
        start_date: Start of date range
        end_date: End of date range
        calendar_id: Calendar ID (default: 'primary')
        dry_run: If True, only show what would be deleted (default: True)

    Returns:
        int: Number of events deleted (or would be deleted if dry_run=True)
    """
    try:
        service = build('calendar', 'v3', credentials=credentials)

        # Get events in date range
        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_date.isoformat(),
            timeMax=end_date.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        # Filter for Solidcore events
        solidcore_events = [
            e for e in events
            if 'solidcore' in e.get('summary', '').lower()
        ]

        deleted_count = 0

        for event in solidcore_events:
            event_title = event.get('summary', 'Unknown')
            event_start = event.get('start', {}).get('dateTime', 'Unknown time')

            if dry_run:
                logger.info(f"[DRY RUN] Would delete: {event_title} at {event_start}")
            else:
                try:
                    service.events().delete(
                        calendarId=calendar_id,
                        eventId=event['id']
                    ).execute()
                    logger.info(f"Deleted: {event_title} at {event_start}")
                except Exception as e:
                    logger.error(f"Error deleting event {event['id']}: {e}")
                    continue

            deleted_count += 1

        if dry_run:
            logger.info(f"\n[DRY RUN] Would delete {deleted_count} events")
        else:
            logger.info(f"\nDeleted {deleted_count} events")

        return deleted_count

    except Exception as e:
        logger.error(f"Error in delete_solidcore_events: {e}")
        return 0


if __name__ == "__main__":
    """
    Test the calendar manager when running this file directly.
    This creates a test event to verify functionality.
    """
    from auth import get_credentials

    print("Testing Google Calendar integration...")
    try:
        # Get credentials
        creds = get_credentials()

        # Create a test event
        test_class = {
            'title': 'TEST: Solidcore Class - DELETE ME',
            'start_time': (datetime.now(EASTERN_TZ) + timedelta(days=1)).isoformat(),
            'end_time': (datetime.now(EASTERN_TZ) + timedelta(days=1, minutes=50)).isoformat(),
            'location': 'Test Studio',
            'description': 'This is a test event. Please delete.'
        }

        print("\nCreating test event...")
        summary = create_calendar_events(creds, [test_class])

        print(f"\n✓ Calendar integration successful!")
        print(f"  Created: {summary['created']}")
        print(f"  Duplicates: {summary['duplicates']}")
        print(f"  Errors: {summary['errors']}")
        print(f"\nPlease check your calendar and delete the test event.")

    except Exception as e:
        print(f"\n✗ Error: {e}")
