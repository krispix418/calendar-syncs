#!/usr/bin/env python3
"""
Debug script to examine Solidcore emails and understand their format.
"""

import base64
from auth import get_credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

def debug_emails():
    """Fetch and display raw email content to understand format."""
    creds = get_credentials()
    service = build('gmail', 'v1', credentials=creds)

    # Search for Solidcore emails
    after_date = (datetime.now() - timedelta(days=30)).strftime('%Y/%m/%d')
    query = f'from:mindbodyonline.com subject:"you\'re CONFIRMED" after:{after_date}'

    results = service.users().messages().list(
        userId='me',
        q=query,
        maxResults=5
    ).execute()

    messages = results.get('messages', [])
    print(f"Found {len(messages)} emails\n")

    for i, msg in enumerate(messages, 1):
        print(f"\n{'='*80}")
        print(f"EMAIL {i}")
        print('='*80)

        message = service.users().messages().get(
            userId='me',
            id=msg['id'],
            format='full'
        ).execute()

        # Get headers
        headers = message['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No subject')
        from_addr = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')

        print(f"From: {from_addr}")
        print(f"Subject: {subject}\n")

        # Get body - handle nested multipart messages
        payload = message['payload']
        body = ''

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

        body = extract_body_recursive(payload)

        # Parse HTML and show text
        if body:
            soup = BeautifulSoup(body, 'html.parser')
            text = soup.get_text(separator='\n', strip=True)

            # Show first 1500 characters
            print("Email Content (first 1500 chars):")
            print('-'*80)
            print(text[:1500])
            print('-'*80)

            # Also save full HTML to file for inspection
            with open(f'debug_email_{i}.html', 'w') as f:
                f.write(body)
            print(f"\nFull HTML saved to: debug_email_{i}.html")
        else:
            print("Could not extract email body")

if __name__ == '__main__':
    debug_emails()
