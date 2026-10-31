# Step 1: crawl every AqarExit resale listing

# What this script does:
#   1. Downloads the site's sitemap which lists the URL of every listing
#   2. Visits each listing page with Playwright slowly in order to respect Cloudflare
#   3. Saves the visible text of each listing to raw/<listing id>.json
# parser.py later reads those JSON files and turns them into CSV files
# Saving the raw text first so that that if the parser has a bug we can fix it and re-run the parser without having to crawl the whole site again
# Pages that are already saved are skipped so the crawl can be stopped at any time and resumed by running the script again
# -> I did that because the script took a long time to run and I didn't want to have to start over if it was interrupted

# Run using: python crawler.py

import json # to save each listing as a .json file
import random # to pick a random wait time between requests
import re # regular expressions -> to find listing ids in the sitemap
import sys # to read the optional command-line limit
import time # time.sleep() to pause between requests
from datetime import datetime # to record when each listing was scraped
from pathlib import Path # for building file paths

from playwright.sync_api import sync_playwright # the browser-automation library


# The sitemap is an XML file that lists every page on the site
SITEMAP = "https://aqarexit.com/sitemap.xml"

# The English version of a listing page. {} is replaced by the listing id
LISTING_URL = "https://aqarexit.com/en/buy/opportunity/{}"

# Folder where the downloaded listings are saved
RAW_DIR = Path(__file__).parent / "raw"

# Wait a random 1-2 seconds between requests
# Cloudflare protects the site and blocks IPs that send requests too fast
DELAY = (1.0, 2.0)

# How many times to retry a page before giving up
MAX_TRIES = 4

# Identify ourselves as a normal Chrome browser
# Some sites reject requests that don't look like they come from a browser
# I started seeing HTTP 403 "Forbidden" errors when I didn't set a User-Agent
# Because, from what I understood, Cloudflare was blocking requests that didn't look like they came from a real browser
# As Playwright's default User-Agent makes it look like a bot/automated client, making us targets for rate-limiting
USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


# Helper functions

# Download the sitemap and return the id of every listing in it
def listing_ids(request):

    # Download the sitemap XML as one big string
    xml = request.get(SITEMAP).text()

    # Each listing URL looks like .../buy/opportunity/<36-character id>
    # findall returns every id that matches the pattern
    ids = re.findall(r"/buy/opportunity/([0-9a-f-]{36})", xml)
   
    # The same id can appear more than once so we removeduplicates while keeping the original order
    return list(dict.fromkeys(ids))

# Download one page and return its HTML
# Returns None if the listing was removed from the site (HTTP 404)
# If the site is busy or rate-limits us wait longer and try again
def fetch(request, url):

    # Try up to MAX_TRIES times
    for attempt in range(1, MAX_TRIES + 1):
        try:
            # Send the HTTP GET request (give up after 30 seconds)
            resp = request.get(url, timeout=30000)
            # 404 = page not found: i assume that the listing was sold or taken down
            if resp.status == 404:
                return None
            # resp.ok is True for success codes (200-299)
            if resp.ok:
                return resp.text()
            # Any other code (e.g. 429 "too many requests", 403 blocked)
            print(f"  HTTP {resp.status} on {url}")
        except Exception as e:
            # for network problems or timeouts
            print(f"  {type(e).__name__} on {url}")
        # Back off before retrying: 30s, then 60s, then 90s, etc
        time.sleep(30 * attempt)
    # Every attempt failed: stop the crawl so we don't keep hammering the site
    raise RuntimeError(f"gave up on {url} after {MAX_TRIES} tries")

# Turn a listing's HTML into its visible text
# Returns (page title, listing text)
# The text is cut at the end of the listing so ads for other units and the contact form are not included
def page_text(page, html):

    # Load the HTML into the headless browser tab
    page.set_content(html)
    
    # inner_text gives the text the way a person would see it on screen with each field on its own line
    # <main> is the page's main content
    text = page.inner_text("main")

    # The listing starts right after the "Back to opportunities" link
    text = text[text.find("Back to opportunities"):]

    # Cut off everything after the listing itself 
    # The "Similar featured" ads also say "Featured" (which i found to have confused the parser)
    for marker in ("Similar featured opportunities", "Want to reserve"):
        text = text.split(marker)[0]   # keep only the part before the marker
    
    # Return the browser-tab title (used as the property title) and the text
    return page.title(), text


def main():
    # If a number was passed on the command line only crawl that many (i used it for testing purposes)
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    
    # Create the raw/ folder if it doesn't exist yet
    RAW_DIR.mkdir(exist_ok=True)

    # Start Playwright 
    # The "with" block shuts it down cleanly at the end
    with sync_playwright() as p:
        # An HTTP client for downloading pages
        # It's much faster than opening every page in a full browser
        # The site already sends the listing data in the HTML
        request = p.request.new_context(extra_http_headers={"User-Agent": USER_AGENT})

        # A headless (invisible) Chromium browser -> used only to turn HTML into readable text
        browser = p.chromium.launch()
        # Turn off JavaScript as we only need HTML
        context = browser.new_context(java_script_enabled=False)
        # Block every network request from this browser (images, CSS, fonts, ...)
        # All the text we need is already in the HTML
        context.route("**/*", lambda route: route.abort())
        # One browser tab reused for every listing
        page = context.new_page()

        # Get the list of listing ids from the sitemap
        # Keep only the first `limit` ids if a number was given (limit is None otherwise, which keeps all)
        ids = listing_ids(request)[:limit]
       
        # Skip listings that were already saved in an earlier run
        todo = [i for i in ids if not (RAW_DIR / f"{i}.json").exists()]
        print(f"{len(ids)} listings in sitemap, {len(ids) - len(todo)} already saved, "
              f"{len(todo)} to go")

        # Count listings that were removed from the site since the sitemap was made
        missing = 0
        # Go through the listings one by one (n counts from 1)
        for n, listing_id in enumerate(todo, 1):
            # Build the full URL of this listing
            url = LISTING_URL.format(listing_id)
            # Download it
            html = fetch(request, url)
            if html is None:
                # The listing is gone so there's nothing to save
                missing += 1
            else:
                # Extract the title and the listing text
                title, text = page_text(page, html)
                # Everything we keep about this listing
                record = {
                    "url": url,
                    "title": title,
                    "text": text,
                    # Current time e.g. "2026-10-27T14:03:11"
                    "scraped_at": datetime.now().isoformat(timespec="seconds"),
                }
                # Write it to raw/<id>.json
                # ensure_ascii = False keeps the Arabic text readable in the file instead of \u escapes (only method that worked for me)
                (RAW_DIR / f"{listing_id}.json").write_text(
                    json.dumps(record, ensure_ascii=False), encoding="utf-8")

            # Print progress every 50 listings and at the very end
            if n % 50 == 0 or n == len(todo):
                print(f"{n}/{len(todo)} done ({missing} removed from site)")

            # Wait a random 1-2 seconds before the next request
            # Why not fixed wait time? I found that a fixed wait time was still triggering Cloudflare's rate-limiting but a random wait time worked fine
            time.sleep(random.uniform(*DELAY))

        # Close the browser and the HTTP client
        browser.close()
        request.dispose()


if __name__ == "__main__":
    main()
