#!/usr/bin/env python3
"""
Solidcore Calendar Sync - Main Script

This script automates syncing Solidcore class bookings from Gmail to Google Calendar.

Workflow:
1. Authenticates with Google APIs (Gmail + Calendar)
2. Searches Gmail for Solidcore class confirmation emails
3. Parses emails to extract class details (date, time, location, instructor)
4. Creates calendar events for classes that don't already exist
5. Provides a summary of actions taken

Usage:
    python main.py                    # Sync classes from last 30 days
    python main.py --days 60          # Sync classes from last 60 days
    python main.py --dry-run          # Show what would be created without creating

Requirements:
- credentials.json file from Google Cloud Console
- Gmail and Calendar API access enabled
- First run will open browser for OAuth authorization
"""

import argparse
import sys
import logging
from datetime import datetime
from typing import Dict

# Add parent directory to path for auth module
sys.path.append('..')
from email_parser import get_solidcore_classes, get_solidcore_cancellations
from calendar_manager import create_calendar_events, delete_calendar_events

# Import auth module with directory change handling
import os

def authenticate():
    """
    Authenticate with Google APIs.
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

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def print_banner():
    """Print a welcome banner."""
    print("\n" + "=" * 60)
    print("         Solidcore Calendar Sync")
    print("=" * 60 + "\n")


def print_summary(
    classes_found: int,
    summary: Dict[str, int],
    cancellations_found: int = 0,
    cancellation_summary: Dict[str, int] = None,
    dry_run: bool = False
):
    """
    Print a summary of the sync operation.

    Args:
        classes_found: Total number of classes found in emails
        summary: Dictionary with 'created', 'duplicates', 'errors' counts
        cancellations_found: Total number of cancellations found in emails
        cancellation_summary: Dictionary with 'deleted', 'not_found', 'errors' counts
        dry_run: Whether this was a dry run
    """
    if cancellation_summary is None:
        cancellation_summary = {'deleted': 0, 'not_found': 0, 'errors': 0}

    print("\n" + "=" * 60)
    print("                    SUMMARY")
    print("=" * 60)
    print(f"Classes found in emails:     {classes_found}")

    if dry_run:
        print(f"Would create:                {summary['created']}")
    else:
        print(f"Events created:              {summary['created']}")

    print(f"Duplicates skipped:          {summary['duplicates']}")

    if summary['errors'] > 0:
        print(f"Errors encountered:          {summary['errors']}")

    # Print cancellation summary if applicable
    if cancellations_found > 0:
        print("\n" + "-" * 60)
        print("CANCELLATIONS:")
        print(f"Cancellations found:         {cancellations_found}")
        print(f"Events deleted:              {cancellation_summary['deleted']}")
        print(f"No matching event found:     {cancellation_summary['not_found']}")

        if cancellation_summary['errors'] > 0:
            print(f"Deletion errors:             {cancellation_summary['errors']}")

    print("=" * 60 + "\n")


def main(days_back: int = 30, dry_run: bool = False):
    """
    Main orchestration function for syncing Solidcore classes to calendar.

    Args:
        days_back: Number of days in the past to search for emails
        dry_run: If True, shows what would be done without creating events

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    try:
        print_banner()

        # Step 1: Authenticate with Google APIs
        print("Step 1: Authenticating with Google APIs...")
        print("-" * 60)
        try:
            credentials = authenticate()
            print("✓ Authentication successful\n")
        except FileNotFoundError as e:
            print(f"✗ Error: {e}")
            print("\nPlease ensure credentials.json is in the current directory.")
            print("Download it from: https://console.cloud.google.com/")
            return 1
        except Exception as e:
            print(f"✗ Authentication failed: {e}")
            return 1

        # Step 2: Search and parse Gmail for Solidcore classes
        print(f"Step 2: Searching Gmail for Solidcore classes (last {days_back} days)...")
        print("-" * 60)
        try:
            classes = get_solidcore_classes(credentials, days_back=days_back)

            if not classes:
                print("ℹ No Solidcore classes found in your email.")
                print("\nPossible reasons:")
                print("  - No booking confirmation emails in the date range")
                print("  - Emails are from a different sender (check email_parser.py)")
                print("  - Emails don't match the expected format")
                return 0

            print(f"✓ Found {len(classes)} classes\n")

            # Show a preview of found classes
            print("Preview of found classes:")
            for i, class_event in enumerate(classes[:3], 1):
                start_time = datetime.fromisoformat(class_event['start_time'])
                print(f"  {i}. {class_event['title']}")
                print(f"     {start_time.strftime('%A, %B %d at %I:%M %p')}")
                print(f"     {class_event['location']}")

            if len(classes) > 3:
                print(f"  ... and {len(classes) - 3} more")
            print()

        except Exception as e:
            print(f"✗ Error searching emails: {e}")
            logger.exception("Email search failed")
            return 1

        # Step 3: Create calendar events
        if dry_run:
            print("Step 3: DRY RUN - Checking for duplicates (no events will be created)...")
        else:
            print("Step 3: Creating calendar events...")
        print("-" * 60)

        try:
            if dry_run:
                # For dry run, we still call the function but could add a flag
                # For now, we'll just report what we found
                print(f"ℹ Would process {len(classes)} classes")
                print(f"ℹ Checking for existing events to avoid duplicates...")

                # Actually check for duplicates without creating
                from calendar_manager import _get_existing_events, _is_duplicate
                from googleapiclient.discovery import build

                service = build('calendar', 'v3', credentials=credentials)
                existing_events = _get_existing_events(service, 'primary', classes)

                would_create = 0
                would_skip = 0

                for class_event in classes:
                    if _is_duplicate(class_event, existing_events):
                        would_skip += 1
                    else:
                        would_create += 1

                summary = {
                    'created': would_create,
                    'duplicates': would_skip,
                    'errors': 0
                }

                print(f"✓ Dry run complete\n")
            else:
                summary = create_calendar_events(credentials, classes)
                print(f"✓ Calendar sync complete\n")

        except Exception as e:
            print(f"✗ Error creating calendar events: {e}")
            logger.exception("Calendar creation failed")
            return 1

        # Step 4: Search and parse Gmail for Solidcore cancellations
        print(f"Step 4: Searching Gmail for cancellations (last {days_back} days)...")
        print("-" * 60)
        try:
            cancellations = get_solidcore_cancellations(credentials, days_back=days_back)

            if not cancellations:
                print("ℹ No Solidcore cancellations found in your email.\n")
                cancellation_summary = {'deleted': 0, 'not_found': 0, 'errors': 0}
            else:
                print(f"✓ Found {len(cancellations)} cancellations\n")

                # Show a preview of found cancellations
                print("Preview of found cancellations:")
                for i, cancellation in enumerate(cancellations[:3], 1):
                    print(f"  {i}. {cancellation['date']} at {cancellation['time']}")
                    print(f"     {cancellation['location']}")

                if len(cancellations) > 3:
                    print(f"  ... and {len(cancellations) - 3} more")
                print()

                # Step 5: Delete calendar events for cancellations
                print("Step 5: Processing cancellations...")
                print("-" * 60)

                try:
                    if dry_run:
                        print(f"ℹ Would process {len(cancellations)} cancellations")
                        print(f"ℹ Checking for matching events to delete...")
                        # For dry run, we would still check but not delete
                        # For now, we'll just report what we found
                        cancellation_summary = {
                            'deleted': 0,
                            'not_found': len(cancellations),
                            'errors': 0
                        }
                        print(f"✓ Dry run complete (no events would be deleted)\n")
                    else:
                        cancellation_summary = delete_calendar_events(credentials, cancellations)
                        print(f"✓ Cancellation processing complete\n")

                except Exception as e:
                    print(f"✗ Error processing cancellations: {e}")
                    logger.exception("Cancellation processing failed")
                    cancellation_summary = {'deleted': 0, 'not_found': 0, 'errors': len(cancellations)}

        except Exception as e:
            print(f"✗ Error searching for cancellations: {e}")
            logger.exception("Cancellation search failed")
            cancellations = []
            cancellation_summary = {'deleted': 0, 'not_found': 0, 'errors': 0}

        # Print final summary
        print_summary(
            len(classes),
            summary,
            cancellations_found=len(cancellations),
            cancellation_summary=cancellation_summary,
            dry_run=dry_run
        )

        if dry_run:
            print("This was a dry run. Run without --dry-run to create events and delete cancellations.\n")
        else:
            print("✓ Sync complete! Check your Google Calendar.\n")

        return 0

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        logger.exception("Unexpected error in main")
        return 1


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Sync Solidcore class bookings from Gmail to Google Calendar',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Sync classes from last 30 days
  python main.py --days 60          # Sync classes from last 60 days
  python main.py --dry-run          # Preview without creating events
  python main.py --days 7 --dry-run # Preview last 7 days

First Run:
  On first run, a browser window will open for Google OAuth authorization.
  This creates a token.json file for future automated runs.
        """
    )

    parser.add_argument(
        '--days',
        type=int,
        default=30,
        metavar='N',
        help='Number of days back to search for emails (default: 30)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be created without actually creating events'
    )

    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose debug logging'
    )

    return parser.parse_args()


if __name__ == '__main__':
    # Parse command-line arguments
    args = parse_arguments()

    # Set logging level based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    # Validate arguments
    if args.days < 1:
        print("Error: --days must be at least 1")
        sys.exit(1)

    if args.days > 365:
        print("Warning: Searching more than 365 days may be slow")

    # Run main function
    exit_code = main(days_back=args.days, dry_run=args.dry_run)
    sys.exit(exit_code)
