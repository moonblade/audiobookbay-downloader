import json
import os
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin, urlparse
import re

from utils import custom_logger

logger = custom_logger(__name__)
JACKETT_API_URL = os.getenv("JACKETT_API_URL" "")
JACKETT_API_KEY = os.getenv("JACKETT_API_KEY", "")
TRANSMISSION_URL = os.getenv("TRANSMISSION_URL", "")
TRANSMISSION_USER = os.getenv("TRANSMISSION_USER", "")
TRANSMISSION_PASS = os.getenv("TRANSMISSION_PASS", "")
LABEL = os.getenv("LABEL", "audiobook")

def get_jackett_magnet(url):
    response = requests.get(url, allow_redirects=False)
    if response.status_code in [301, 302]:
        return response.headers.get("Location", url)
    return url

def search_audiobook(query):
    params = {
        "apikey": JACKETT_API_KEY,
        "Query": query,
        "Category": "audiobooks"
    }
    logger.info(f"Searching for {query}...")
    response = requests.get(str(JACKETT_API_URL), params=params)
    if response.status_code != 200:
        logger.error("Error fetching results from Jackett:", response.text)
        return []
    results = response.json()
    logger.info(f"Found {len(results.get('Results', []))} results for {query}")
    return results.get("Results", [])

def add_to_transmission(torrent_url, label=LABEL):
    torrent_url = get_jackett_magnet(torrent_url)
    session_response = requests.get(TRANSMISSION_URL, auth=(TRANSMISSION_USER, TRANSMISSION_PASS))
    session_id = session_response.headers.get("X-Transmission-Session-Id")

    if not session_id:
        print("Failed to get Transmission session ID")
        return False

    payload = {
        "method": "torrent-add",
        "arguments": {"filename": torrent_url}
    }
    headers = {"X-Transmission-Session-Id": session_id}

    response = requests.post(TRANSMISSION_URL, auth=(TRANSMISSION_USER, TRANSMISSION_PASS), json=payload, headers=headers)

    if response.status_code == 200:
        # Get the newly added torrent's ID
        try:
          torrent_id = response.json()['arguments']['torrent-added']['id']
          add_label_to_torrent(torrent_id, label) # Add the label after adding the torrent
          return True
        except (KeyError, TypeError): # Handle cases where torrent-added might not be in the response
          print("Warning: Could not retrieve torrent ID from response. Label may not be applied.")
          return True # Torrent was added, but label might have failed. You might want to return False here instead.

    return False

def add_label_to_torrent(torrent_id, label=LABEL):
    session_response = requests.get(TRANSMISSION_URL, auth=(TRANSMISSION_USER, TRANSMISSION_PASS))
    session_id = session_response.headers.get("X-Transmission-Session-Id")

    if not session_id:
        print("Failed to get Transmission session ID")
        return []

    payload = {
        "method": "torrent-set",
        "arguments": {
            "ids": [torrent_id],
            "labels": [label]
        }
    }
    headers = {"X-Transmission-Session-Id": session_id}
    response = requests.post(TRANSMISSION_URL, auth=(TRANSMISSION_USER, TRANSMISSION_PASS), json=payload, headers=headers)
    return response.status_code == 200

def get_torrents(label=LABEL):
    session_response = requests.get(TRANSMISSION_URL, auth=(TRANSMISSION_USER, TRANSMISSION_PASS))
    session_id = session_response.headers.get("X-Transmission-Session-Id")

    if not session_id:
        print("Failed to get Transmission session ID")
        return None

    payload = {
        "method": "torrent-get",
        "arguments": {
            "fields": ["id", "name", "status", "labels", "totalSize", "percentDone", "downloadedEver", "uploadedEver"]  # Added size and progress fields
        }
    }
    headers = {"X-Transmission-Session-Id": session_id}
    response = requests.post(TRANSMISSION_URL, auth=(TRANSMISSION_USER, TRANSMISSION_PASS), json=payload, headers=headers)

    if response.status_code == 200:
        torrents = response.json()['arguments']['torrents']
        filtered_torrents = []
        for torrent in torrents:
            if label in torrent.get("labels", []):
                status = get_torrent_status(torrent["status"])
                total_size = torrent["totalSize"]
                percent_done = torrent["percentDone"] * 100  # Convert to percentage
                downloaded_ever = torrent["downloadedEver"]
                uploaded_ever = torrent["uploadedEver"]

                filtered_torrents.append({
                    "id": torrent["id"],
                    "name": torrent["name"],
                    "status": status,
                    "total_size": total_size,  # Size in bytes
                    "percent_done": percent_done, # Percentage
                    "downloaded_ever": downloaded_ever, # Bytes
                    "uploaded_ever": uploaded_ever # Bytes
                })
        return filtered_torrents
    else:
        print(f"Error getting torrent list: {response.status_code}")
        return None

def get_torrent_status(status_code):  # Helper function to convert status code
    status_map = {
        0: "Stopped",
        1: "Queued to check",
        2: "Checking",
        3: "Queued to download",
        4: "Downloading",
        5: "Queued to seed",
        6: "Seeding"
    }
    return status_map.get(status_code, "Unknown")
