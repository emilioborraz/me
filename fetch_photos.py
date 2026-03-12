#!/usr/bin/env python3
"""
fetch_photos.py

Fetches your 36 most popular Unsplash photos and updates docs/index.html
with the real photo data (dimensions + URLs).

Requirements:
    pip install requests python-dotenv

Setup:
    cp .env.example .env   # then fill in your credentials

Usage:
    python fetch_photos.py
"""

import json
import math
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

# ── Config ─────────────────────────────────────────────────────────────────────
load_dotenv()

ACCESS_KEY   = os.getenv("UNSPLASH_ACCESS_KEY")
USERNAME     = os.getenv("UNSPLASH_USERNAME")
TARGET_COUNT = 36
MAX_PER_PAGE = 30   # Unsplash API hard limit

HTML_PATH    = Path(__file__).parent / "docs" / "index.html"
API_BASE     = "https://api.unsplash.com"

# ── Validation ─────────────────────────────────────────────────────────────────
if not ACCESS_KEY:
    sys.exit("Error: UNSPLASH_ACCESS_KEY is not set in .env")
if not USERNAME:
    sys.exit("Error: UNSPLASH_USERNAME is not set in .env")
if not HTML_PATH.exists():
    sys.exit(f"Error: {HTML_PATH} not found")

# ── Fetch ──────────────────────────────────────────────────────────────────────
def fetch_user_photos(username: str, count: int) -> list[dict]:
    """Return up to `count` most-popular photos for `username`."""
    headers = {"Authorization": f"Client-ID {ACCESS_KEY}"}
    photos  = []
    pages   = math.ceil(count / MAX_PER_PAGE)

    for page in range(1, pages + 1):
        per_page = min(MAX_PER_PAGE, count - len(photos))
        resp = requests.get(
            f"{API_BASE}/users/{username}/photos",
            headers=headers,
            params={"order_by": "popular", "per_page": per_page, "page": page},
            timeout=15,
        )

        if resp.status_code == 401:
            sys.exit("Error: invalid access key (401 Unauthorized)")
        if resp.status_code == 404:
            sys.exit(f"Error: user '{username}' not found (404)")
        if not resp.ok:
            sys.exit(f"API error {resp.status_code}: {resp.text}")

        batch = resp.json()
        if not batch:
            break
        photos.extend(batch)

    return photos[:count]

# ── Format ─────────────────────────────────────────────────────────────────────
def best_title(photo: dict) -> str:
    """description → alt_description → 'untitled'"""
    raw = (photo.get("description") or photo.get("alt_description") or "untitled")
    raw = raw.replace("\n", " ").strip()
    return raw[:60].rstrip() + ("..." if len(raw) > 60 else "")

def escape_js_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')

def build_js_array(photos: list[dict]) -> str:
    """Render the photos list as an indented JS array literal."""
    entries  = []
    title_w  = max(len(best_title(p)) for p in photos)

    for p in photos:
        title   = escape_js_string(best_title(p))
        w       = p["width"]
        h       = p["height"]
        regular = p["urls"]["regular"]
        full    = p["urls"]["full"]
        pad     = " " * (title_w - len(title))

        entries.append(
            f'  {{ title: "{title}",{pad} w: {w:5d}, h: {h:5d},'
            f' regular: "{regular}",'
            f' full:    "{full}" }}'
        )

    return "[\n" + ",\n".join(entries) + "\n]"

# ── Patch HTML ─────────────────────────────────────────────────────────────────
def patch_html(html: str, js_array: str) -> str:
    """Replace the `const photos = [...]` block."""
    pattern     = r'(const photos = )\[.*?\];'
    replacement = r'\g<1>' + js_array.replace("\\", "\\\\") + ";"
    result, n   = re.subn(pattern, replacement, html, count=1, flags=re.DOTALL)
    if n == 0:
        sys.exit("Error: could not find `const photos = [...]` in index.html")
    return result

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print(f"Fetching {TARGET_COUNT} most popular photos for @{USERNAME} …")
    raw = fetch_user_photos(USERNAME, TARGET_COUNT)
    print(f"  Retrieved {len(raw)} photo(s).")

    js_array = build_js_array(raw)
    html     = HTML_PATH.read_text(encoding="utf-8")
    html     = patch_html(html, js_array)
    HTML_PATH.write_text(html, encoding="utf-8")

    print(f"  Wrote {HTML_PATH}")
    print("Done. Open docs/index.html in a browser to preview.")

if __name__ == "__main__":
    main()
