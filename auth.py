"""
Google API Authentication Module

This module handles OAuth2 authentication for Google Gmail and Calendar APIs.
It manages token creation, storage, and automatic refresh.
"""

import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Define the scopes for Gmail (read-only) and Calendar (read/write) access
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar'
]

def get_credentials():
    """
    Authenticates with Google APIs and returns valid credentials.

    This function:
    1. Checks if a valid token.json file exists
    2. If valid token exists, uses it
    3. If token is expired, refreshes it automatically
    4. If no token exists, initiates OAuth2 flow using credentials.json
    5. Saves the token to token.json for future use

    Returns:
        google.oauth2.credentials.Credentials: Authenticated credentials object

    Raises:
        FileNotFoundError: If credentials.json is not found
        Exception: For other authentication errors
    """
    creds = None

    # Check if we have previously saved credentials
    if os.path.exists('token.json'):
        try:
            # Load credentials from token.json
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            print("Loading existing credentials from token.json")
        except Exception as e:
            print(f"Error loading token.json: {e}")
            creds = None

    # If there are no valid credentials available, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Token exists but is expired - refresh it
            try:
                print("Token expired. Refreshing...")
                creds.refresh(Request())
                print("Token refreshed successfully")
            except Exception as e:
                print(f"Error refreshing token: {e}")
                print("Need to re-authenticate")
                creds = None

        # If refresh failed or no credentials exist, run OAuth flow
        if not creds:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError(
                    "credentials.json not found. Please download it from Google Cloud Console."
                )

            print("Starting OAuth2 authentication flow...")
            print("A browser window will open for you to authorize access.")

            # Create OAuth2 flow from credentials.json
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES
            )

            # Run local server to handle OAuth callback
            # This will open a browser window for user authorization
            creds = flow.run_local_server(port=0)
            print("Authentication successful!")

        # Save credentials to token.json for future use
        try:
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
            print("Credentials saved to token.json")
        except Exception as e:
            print(f"Warning: Could not save token.json: {e}")

    return creds


if __name__ == "__main__":
    """
    Test the authentication when running this file directly.
    This helps verify that authentication is working correctly.
    """
    print("Testing Google API authentication...")
    try:
        credentials = get_credentials()
        print("\n✓ Authentication successful!")
        print(f"✓ Token valid: {credentials.valid}")
        print(f"✓ Scopes granted: {credentials.scopes}")
    except Exception as e:
        print(f"\n✗ Authentication failed: {e}")
