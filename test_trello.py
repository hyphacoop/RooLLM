#!/usr/bin/env python3
"""Test script to verify Trello API connectivity.

Usage:
    TRELLO_API_KEY=your_key TRELLO_TOKEN=your_token python test_trello.py
"""
import os
import sys
import requests

api_key = os.getenv('TRELLO_API_KEY')
token = os.getenv('TRELLO_TOKEN')

if not api_key or not token:
    print("Error: TRELLO_API_KEY and TRELLO_TOKEN environment variables must be set")
    print("Usage: TRELLO_API_KEY=your_key TRELLO_TOKEN=your_token python test_trello.py")
    sys.exit(1)

params = {'key': api_key, 'token': token}

print("=" * 50)
print("TRELLO API DIRECT TEST")
print("=" * 50)

# First, get member info and their boards
print("\n1. Getting your Trello member info...")
r = requests.get('https://api.trello.com/1/members/me', params=params)
print(f"   Status: {r.status_code}")
if r.status_code == 200:
    me = r.json()
    print(f"   Username: {me.get('username')}")
    print(f"   Full Name: {me.get('fullName')}")
else:
    print(f"   Error: {r.text}")

# Get all boards
print("\n2. Your Trello Boards:")
r = requests.get('https://api.trello.com/1/members/me/boards', params=params)
print(f"   Status: {r.status_code}")
if r.status_code == 200:
    boards = r.json()
    if boards:
        for board in boards:
            print(f"\n   Board: {board.get('name')}")
            print(f"   ID: {board.get('id')}")
            print(f"   URL: {board.get('url')}")
            print(f"   Closed: {board.get('closed', False)}")
    else:
        print("   (No boards found)")
else:
    print(f"   Error: {r.text}")

print("\n" + "=" * 50)
