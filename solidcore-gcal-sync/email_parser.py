"""
Solidcore Email Parser Module

This module searches Gmail for Solidcore class confirmation emails and parses
them to extract class booking details (date, time, location, instructor, etc.).
"""

import base64
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText
from bs4 import BeautifulSoup
import pytz

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
CLASS_DURATION_MINUTES = 50
EASTERN_TZ = pytz.timezone('America/New_York')


def get_solidcore_classes(credentials, days_back=30) -> List[Dict]:
    """
    Fetches and parses Solidcore class confirmation emails from Gmail.

    Args:
        credentials: Google API credentials object from auth.py
        days_back: Number of days in the past to search for emails (default: 30)

    Returns:
        List[Dict]: List of parsed class events with fields:
            - title: Class name/type
            - start_time: ISO format datetime string
            - end_time: ISO format datetime string
            - location: Studio name/address
            - description: Additional details (instructor, door code, etc.)

    Raises:
        HttpError: If Gmail API request fails
    """
    try:
        # Build Gmail API service
        service = build('gmail', 'v1', credentials=credentials)
        logger.info("Gmail API service created successfully")

        # Calculate the date range for search
        after_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')

        # Search query for Solidcore emails
        # Solidcore uses MindBody Online for booking confirmations
        query = f'from:mindbodyonline.com subject:"you\'re CONFIRMED" after:{after_date}'
        logger.info(f"Searching for emails with query: {query}")

        # Get list of matching messages
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=100  # Adjust if you need more
        ).execute()

        messages = results.get('messages', [])
        logger.info(f"Found {len(messages)} emails from Solidcore")

        if not messages:
            logger.warning("No Solidcore emails found in the specified date range")
            return []

        # Parse each email
        parsed_classes = []
        for message in messages:
            try:
                class_event = _parse_email(service, message['id'])
                if class_event:
                    parsed_classes.append(class_event)
                    logger.info(f"Successfully parsed class: {class_event['title']}")
            except Exception as e:
                logger.error(f"Error parsing email {message['id']}: {e}")
                continue

        logger.info(f"Successfully parsed {len(parsed_classes)} classes")
        return parsed_classes

    except HttpError as error:
        logger.error(f"Gmail API error: {error}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_solidcore_classes: {e}")
        raise


def _parse_email(service, message_id: str) -> Optional[Dict]:
    """
    Parses a single email to extract class booking details.

    Args:
        service: Gmail API service object
        message_id: Gmail message ID

    Returns:
        Dict or None: Parsed class event dictionary, or None if not a booking confirmation
    """
    try:
        # Get the full message
        message = service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()

        # Extract subject and check if it's a booking confirmation
        headers = message['payload']['headers']
        subject = _get_header(headers, 'Subject')

        # Filter for confirmation emails (adjust keywords as needed)
        if not _is_booking_confirmation(subject):
            logger.debug(f"Email not a booking confirmation: {subject}")
            return None

        # Extract email body
        body = _get_email_body(message['payload'])
        if not body:
            logger.warning(f"Could not extract email body for message {message_id}")
            return None

        # Parse the email body for class details
        class_details = _extract_class_details(body, subject)

        if not class_details:
            logger.warning(f"Could not extract class details from email {message_id}")
            return None

        return class_details

    except Exception as e:
        logger.error(f"Error in _parse_email for message {message_id}: {e}")
        return None


def _get_header(headers: List[Dict], name: str) -> str:
    """Extract a specific header value from email headers."""
    for header in headers:
        if header['name'].lower() == name.lower():
            return header['value']
    return ''


def _is_booking_confirmation(subject: str) -> bool:
    """
    Check if the email subject indicates a booking confirmation.

    Common Solidcore confirmation subject patterns:
    - "Your class is confirmed"
    - "Booking confirmed"
    - "See you in class"
    """
    confirmation_keywords = [
        'confirmed',
        'booking',
        'reservation',
        'class is booked',
        'see you in class',
        'you\'re booked'
    ]

    subject_lower = subject.lower()
    return any(keyword in subject_lower for keyword in confirmation_keywords)


def _get_email_body(payload: Dict) -> str:
    """
    Extract email body from the payload.
    Handles both plain text and HTML emails, including nested multipart messages.
    """
    def extract_body_recursive(part):
        """Recursively extract body from nested parts."""
        if part.get('mimeType') == 'text/html':
            if 'data' in part.get('body', {}):
                return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
        elif part.get('mimeType') == 'text/plain':
            if 'data' in part.get('body', {}):
                return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')

        # Check nested parts
        if 'parts' in part:
            for subpart in part['parts']:
                result = extract_body_recursive(subpart)
                if result:
                    return result
        return None

    return extract_body_recursive(payload) or ''


def _extract_class_details(body: str, subject: str) -> Optional[Dict]:
    """
    Extract class details from email body.

    This function uses regex patterns to find:
    - Class name/type (e.g., "Signature50: Full Body")
    - Date and time
    - Location/studio
    - Instructor name
    - Additional details (door codes, etc.)
    """
    try:
        # Parse HTML if present
        soup = BeautifulSoup(body, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)

        # Extract class type/name
        # Common patterns: "Signature50", "Foundations", "Full Body", etc.
        class_name = _extract_class_name(text, subject)

        # Extract date and time
        class_datetime = _extract_datetime(text)
        if not class_datetime:
            logger.warning("Could not extract date/time from email")
            return None

        # Calculate end time (50 minutes after start)
        end_datetime = class_datetime + timedelta(minutes=CLASS_DURATION_MINUTES)

        # Extract location/studio
        location = _extract_location(text)

        # Extract instructor
        instructor = _extract_instructor(text)

        # Extract door code or other details
        additional_details = _extract_additional_details(text)

        # Build description
        description_parts = []
        if instructor:
            description_parts.append(f"Instructor: {instructor}")
        if additional_details:
            description_parts.append(additional_details)

        # Add note that this was auto-created
        description_parts.append("\n---\nAuto-created by Solidcore Calendar Sync")

        description = '\n'.join(description_parts)

        # Build the event dictionary
        event = {
            'title': class_name or 'Solidcore Class',
            'start_time': class_datetime.isoformat(),
            'end_time': end_datetime.isoformat(),
            'location': location or 'Solidcore Studio',
            'description': description
        }

        return event

    except Exception as e:
        logger.error(f"Error extracting class details: {e}")
        return None


def _extract_class_name(text: str, subject: str) -> Optional[str]:
    """Extract class name/type from email text or subject."""
    # MindBody format: "Signature50: Full BodyAnisha Goel" - extract just the class part
    # Pattern matches "Signature50: Full Body" stopping before the instructor name
    mindbody_pattern = r'(Signature50:\s*(?:Full Body|Upper Body|Lower Body|Core & More))'
    match = re.search(mindbody_pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Common Solidcore class types
    class_patterns = [
        r'(Foundations[:\s]*[A-Za-z\s]*)',
        r'(Full Body)',
        r'(Upper Body)',
        r'(Lower Body)',
        r'(Core & More)',
    ]

    # Try to find class type in text first
    for pattern in class_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Fall back to checking subject
    for pattern in class_patterns:
        match = re.search(pattern, subject, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return None


def _extract_datetime(text: str) -> Optional[datetime]:
    """
    Extract date and time from email text.

    Common patterns:
    - "8:00 AM, Sunday, 10/19/2025" (MindBody format)
    - "Monday, January 15, 2024 at 6:00 PM"
    - "Jan 15, 2024 6:00 PM"
    - "1/15/2024 6:00 PM"
    """
    # Pattern for various date/time formats
    datetime_patterns = [
        # Format: "8:00 AM, Sunday, 10/19/2025" (MindBody Online)
        (r'(\d{1,2}:\d{2}\s*[AP]M),\s*([A-Za-z]+),\s*(\d{1,2}/\d{1,2}/\d{4})', '%I:%M %p %A %m/%d/%Y'),
        # Format: "Monday, January 15, 2024 at 6:00 PM"
        (r'([A-Za-z]+,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}\s+at\s+\d{1,2}:\d{2}\s*[AP]M)', '%A, %B %d, %Y at %I:%M %p'),
        # Format: "January 15, 2024 at 6:00 PM"
        (r'([A-Za-z]+\s+\d{1,2},\s+\d{4}\s+at\s+\d{1,2}:\d{2}\s*[AP]M)', '%B %d, %Y at %I:%M %p'),
        # Format: "Jan 15, 2024 6:00 PM"
        (r'([A-Za-z]+\s+\d{1,2},\s+\d{4}\s+\d{1,2}:\d{2}\s*[AP]M)', '%b %d, %Y %I:%M %p'),
        # Format: "1/15/2024 6:00 PM"
        (r'(\d{1,2}/\d{1,2}/\d{4}\s+\d{1,2}:\d{2}\s*[AP]M)', '%m/%d/%Y %I:%M %p'),
    ]

    for pattern, fmt in datetime_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                # Special handling for MindBody format with multiple capture groups
                if len(match.groups()) == 3:
                    # Reconstruct datetime string from groups (time, day, date)
                    datetime_str = f"{match.group(1)} {match.group(2)} {match.group(3)}"
                else:
                    datetime_str = match.group(1)

                dt = datetime.strptime(datetime_str, fmt)
                # Localize to Eastern Time
                dt_eastern = EASTERN_TZ.localize(dt)
                return dt_eastern

            except Exception as e:
                logger.debug(f"Error parsing datetime '{datetime_str}' with format '{fmt}': {e}")
                continue

    return None


def _extract_location(text: str) -> Optional[str]:
    """Extract studio location from email text."""
    # Pattern for location/studio
    # Common patterns: "101 Middlesex Turnpike Unit 310 Burlington MA 01803"
    location_patterns = [
        # MindBody format: full address after date, stops before BURLINGTON DOOR CODE
        r'\d{1,2}/\d{1,2}/\d{4}([0-9A-Za-z\s,#]+?)(?:\s+[A-Z]+\s+DOOR CODE|DOOR CODE|things to know)',
        # Generic patterns
        r'Studio[:\s]+([A-Za-z\s,]+?)(?:\n|<br>|\|)',
        r'Location[:\s]+([A-Za-z\s,]+?)(?:\n|<br>|\|)',
        r'([A-Za-z\s]+)\s+Studio',
    ]

    for pattern in location_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            # Clean up common artifacts
            location = re.sub(r'\s+', ' ', location)
            # Remove leading/trailing commas or spaces
            location = location.strip(', ')
            return location

    return None


def _extract_instructor(text: str) -> Optional[str]:
    """Extract instructor name from email text."""
    # MindBody format: "Signature50: Full BodyAnisha Goel 8:00 AM"
    # Extract name between class type and time
    mindbody_pattern = r'(?:Full Body|Upper Body|Lower Body|Core & More)([A-Z][a-z]+\s+[A-Z][a-z]+)\s+\d{1,2}:\d{2}'
    match = re.search(mindbody_pattern, text)
    if match:
        return match.group(1).strip()

    # Generic patterns
    instructor_patterns = [
        r'Instructor[:\s]+([A-Za-z\s]+?)(?:\n|<br>|\|)',
        r'with\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
        r'Coach[:\s]+([A-Za-z\s]+?)(?:\n|<br>|\|)',
    ]

    for pattern in instructor_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            instructor = match.group(1).strip()
            # Clean up
            instructor = re.sub(r'\s+', ' ', instructor)
            return instructor

    return None


def _extract_additional_details(text: str) -> str:
    """Extract additional details like door codes."""
    details = []

    # Look for door code (MindBody format: "BURLINGTON DOOR CODE: 3176#Use the...")
    # Match only digits and # symbol, stop at first uppercase letter
    door_code_pattern = r'DOOR\s+CODE[:\s]+([0-9#]+)'
    match = re.search(door_code_pattern, text, re.IGNORECASE)
    if match:
        details.append(f"Door Code: {match.group(1)}")

    # Look for parking info
    if 'parking' in text.lower():
        parking_pattern = r'(parking[:\s][^\n<]+)'
        match = re.search(parking_pattern, text, re.IGNORECASE)
        if match:
            details.append(match.group(1).strip())

    return '\n'.join(details)


def get_solidcore_cancellations(credentials, days_back=30) -> List[Dict]:
    """
    Fetches and parses Solidcore class cancellation emails from Gmail.

    Searches for emails with subject containing "Your class reservation has been canceled"
    and parses them to extract class cancellation details (date, time, location).

    Args:
        credentials: Google API credentials object from auth.py
        days_back: Number of days in the past to search for emails (default: 30)

    Returns:
        List[Dict]: List of parsed cancellations with fields:
            - date: Date string (e.g., "11/23/2025")
            - time: Time string (e.g., "10:00 AM")
            - location: Location/studio string
            - original_datetime: Timezone-aware datetime object for matching

    Raises:
        HttpError: If Gmail API request fails
    """
    try:
        # Build Gmail API service
        service = build('gmail', 'v1', credentials=credentials)
        logger.info("Gmail API service created successfully for cancellation search")

        # Calculate the date range for search
        after_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')

        # Search query for cancellation emails
        # Subject: "Your class reservation has been canceled"
        # From: Business458110@mindbodyonline.com or similar MindBody account
        query = f'from:mindbodyonline.com subject:"Your class reservation has been canceled" after:{after_date}'
        logger.info(f"Searching for cancellation emails with query: {query}")

        # Get list of matching messages
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=100  # Adjust if you need more
        ).execute()

        messages = results.get('messages', [])
        logger.info(f"Found {len(messages)} cancellation emails from Solidcore")

        if not messages:
            logger.info("No Solidcore cancellation emails found in the specified date range")
            return []

        # Parse each cancellation email
        parsed_cancellations = []
        for message in messages:
            try:
                cancellation = _parse_cancellation_email(service, message['id'])
                if cancellation:
                    parsed_cancellations.append(cancellation)
                    logger.info(f"Successfully parsed cancellation: {cancellation['date']} at {cancellation['time']}")
            except Exception as e:
                logger.error(f"Error parsing cancellation email {message['id']}: {e}")
                continue

        logger.info(f"Successfully parsed {len(parsed_cancellations)} cancellations")
        return parsed_cancellations

    except HttpError as error:
        logger.error(f"Gmail API error: {error}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_solidcore_cancellations: {e}")
        raise


def _parse_cancellation_email(service, message_id: str) -> Optional[Dict]:
    """
    Parses a single cancellation email to extract class cancellation details.

    Args:
        service: Gmail API service object
        message_id: Gmail message ID

    Returns:
        Dict or None: Parsed cancellation dictionary, or None if not a cancellation
    """
    try:
        # Get the full message
        message = service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()

        # Extract subject and verify it's a cancellation
        headers = message['payload']['headers']
        subject = _get_header(headers, 'Subject')

        # Filter for cancellation emails
        if "Your class reservation has been canceled" not in subject:
            logger.debug(f"Email not a cancellation: {subject}")
            return None

        # Extract email body
        body = _get_email_body(message['payload'])
        if not body:
            logger.warning(f"Could not extract email body for message {message_id}")
            return None

        # Parse the email body for cancellation details
        cancellation_details = _extract_cancellation_details(body)

        if not cancellation_details:
            logger.warning(f"Could not extract cancellation details from email {message_id}")
            return None

        return cancellation_details

    except Exception as e:
        logger.error(f"Error in _parse_cancellation_email for message {message_id}: {e}")
        return None


def _extract_cancellation_details(body: str) -> Optional[Dict]:
    """
    Extract cancellation details from email body.

    Handles two email body formats:
    FORMAT 1: "Your class reservation on [DATE] at [TIME] under the blue lights of [LOCATION] has been canceled."
    FORMAT 2: "Your reservation on [DATE] at [TIME] for [LOCATION] has been canceled."

    Args:
        body: Email body text (HTML or plain text)

    Returns:
        Dict or None: Parsed cancellation with date, time, location, original_datetime, or None
    """
    try:
        # Parse HTML if present
        soup = BeautifulSoup(body, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)

        logger.debug(f"Parsing cancellation email body: {text[:200]}...")

        # Try FORMAT 1: "Your class reservation on [DATE] at [TIME] under the blue lights of [LOCATION]"
        format1_pattern = r"Your class reservation on\s+(\d{1,2}/\d{1,2}/\d{4})\s+at\s+(\d{1,2}:\d{2}\s*[AP]M)\s+under the blue lights of\s+([^.]+)\s+has been canceled"
        match = re.search(format1_pattern, text, re.IGNORECASE)

        if match:
            date_str = match.group(1)
            time_str = match.group(2)
            location_str = match.group(3).strip()

            logger.info(f"Matched FORMAT 1 cancellation: {date_str} {time_str} at {location_str}")

            # Parse the datetime
            datetime_obj = _parse_cancellation_datetime(date_str, time_str)
            if datetime_obj:
                return {
                    'date': date_str,
                    'time': time_str,
                    'location': location_str,
                    'original_datetime': datetime_obj
                }
            else:
                logger.warning(f"Could not parse datetime for cancellation: {date_str} {time_str}")
                return None

        # Try FORMAT 2: "Your reservation on [DATE] at [TIME] for [LOCATION] has been canceled."
        format2_pattern = r"Your reservation on\s+(\d{1,2}/\d{1,2}/\d{4})\s+at\s+(\d{1,2}:\d{2}\s*[AP]M)\s+for\s+([^.]+)\s+has been canceled"
        match = re.search(format2_pattern, text, re.IGNORECASE)

        if match:
            date_str = match.group(1)
            time_str = match.group(2)
            location_str = match.group(3).strip()

            logger.info(f"Matched FORMAT 2 cancellation: {date_str} {time_str} at {location_str}")

            # Parse the datetime
            datetime_obj = _parse_cancellation_datetime(date_str, time_str)
            if datetime_obj:
                return {
                    'date': date_str,
                    'time': time_str,
                    'location': location_str,
                    'original_datetime': datetime_obj
                }
            else:
                logger.warning(f"Could not parse datetime for cancellation: {date_str} {time_str}")
                return None

        logger.warning(f"Could not match any cancellation format in email body")
        return None

    except Exception as e:
        logger.error(f"Error extracting cancellation details: {e}")
        return None


def _parse_cancellation_datetime(date_str: str, time_str: str) -> Optional[datetime]:
    """
    Parse cancellation date and time into a timezone-aware datetime object.

    Args:
        date_str: Date string (e.g., "11/23/2025")
        time_str: Time string (e.g., "10:00 AM")

    Returns:
        datetime: Timezone-aware datetime object in Eastern Time, or None if parsing fails
    """
    try:
        # Combine date and time strings
        datetime_combined = f"{date_str} {time_str}"

        # Parse with format: "M/D/YYYY H:MM AM/PM"
        dt = datetime.strptime(datetime_combined, '%m/%d/%Y %I:%M %p')

        # Localize to Eastern Time
        dt_eastern = EASTERN_TZ.localize(dt)
        logger.debug(f"Parsed cancellation datetime: {dt_eastern.isoformat()}")
        return dt_eastern

    except Exception as e:
        logger.error(f"Error parsing cancellation datetime '{date_str}' '{time_str}': {e}")
        return None


if __name__ == "__main__":
    """
    Test the email parser when running this file directly.
    Requires authentication via auth.py first.
    """
    from auth import get_credentials

    print("Testing Solidcore email parser...")
    try:
        # Get credentials
        creds = get_credentials()

        # Fetch and parse classes
        classes = get_solidcore_classes(creds, days_back=30)

        print(f"\n✓ Found {len(classes)} Solidcore classes")

        # Display first few classes as examples
        for i, class_event in enumerate(classes[:5], 1):
            print(f"\nClass {i}:")
            print(f"  Title: {class_event['title']}")
            print(f"  Start: {class_event['start_time']}")
            print(f"  End: {class_event['end_time']}")
            print(f"  Location: {class_event['location']}")
            if class_event['description']:
                print(f"  Details: {class_event['description']}")

        # Also test cancellations
        print("\n\nTesting Solidcore cancellation parser...")
        cancellations = get_solidcore_cancellations(creds, days_back=30)

        print(f"\n✓ Found {len(cancellations)} Solidcore cancellations")

        # Display cancellations
        for i, cancellation in enumerate(cancellations[:5], 1):
            print(f"\nCancellation {i}:")
            print(f"  Date: {cancellation['date']}")
            print(f"  Time: {cancellation['time']}")
            print(f"  Location: {cancellation['location']}")

    except Exception as e:
        print(f"\n✗ Error: {e}")
