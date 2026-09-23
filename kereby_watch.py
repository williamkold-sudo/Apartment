"""
Kereby apartment watcher.
Checks https://kereby.dk/bolig/ and posts new listings to a Discord webhook.
State (already-seen listings) is kept in seen.json.
"""
import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://kereby.dk/bolig/"
STATE_FILE = Path(__file__).with_name("seen.json")
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")
HEADERS = {"User-Agent": "Mozilla/5.0 (personal apartment alert; checks every 15 min)"}
LISTING_LINK = re.compile(r"^(?:https?://(?:www\.)?kereby\.dk)?/bolig/([^/?#]+)/?$")


def text_of(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True))


def find_link(card):
    """Look for a /bolig/<slug>/ link on the card, inside it, or wrapping it."""
    candidates = [card] + card.find_all(True) + list(card.parents)
    for el in candidates:
        if not hasattr(el, "attrs"):
            continue
        for attr in ("href", "data-href", "data-url", "onclick"):
            val = el.attrs.get(attr)
            if not val:
                continue
            m = re.search(r"(?:https?://(?:www\.)?kereby\.dk)?/bolig/[^/'\"?#\s]+/?", val)
            if m and LISTING_LINK.match(m.group(0)):
                link = m.group(0)
                return link if link.startswith("http") else "https://kereby.dk" + link
    return None


def parse_listings(html):
    soup = BeautifulSoup(html, "html.parser")
    listings = {}
    # Every listing card has exactly one small map-marker icon next to the address.
    for marker in soup.select('img[src*="small-map-marker"]'):
        address = text_of(marker.parent)
        # Walk up until we reach the element holding the whole card (has the price).
        card = marker.parent
        while card is not None and "kr./md" not in card.get_text():
            card = card.parent
        if card is None or len(card.select('img[src*="small-map-marker"]')) > 1:
            continue

        txt = text_of(card)
        price = re.search(r"([\d.]+)\s*kr\./md", txt)
        rooms = re.search(r"(\d+)\s*værelser", txt)
        size = re.search(r"(\d+)\s*m2", txt)
        status = "Reserveret" if "Reserveret" in txt else "Udlejet" if "Udlejet" in txt else "Ledig"
        img = card.select_one('img[src*="media.jorato.com"]')
        link = find_link(card)

        # Title = the text line between address/status and price
        title = ""
        after = txt.split(address, 1)[-1]
        after = after.replace("Reserveret", "").replace("Udlejet", "")
        tm = re.match(r"\s*(.*?)\s*[\d.]+\s*kr\./md", after)
        if tm:
            title = tm.group(1).strip()

        key = link or address
        listings[key] = {
            "address": address,
            "title": title,
            "price": price.group(1) if price else "?",
            "rooms": rooms.group(1) if rooms else "?",
            "size": size.group(1) if size else "?",
            "status": status,
            "image": img["src"] if img else None,
            "link": link or URL,
        }
    return listings


def post_to_discord(item, reason):
    colors = {"Ledig": 0x2ECC71, "Reserveret": 0xF1C40F, "Udlejet": 0x95A5A6}
    embed = {
        "title": f"🏠 {item['address']}",
        "url": item["link"],
        "description": item["title"],
        "color": colors.get(item["status"], 0x3498DB),
        "fields": [
            {"name": "Husleje", "value": f"{item['price']} kr./md.", "inline": True},
            {"name": "Værelser", "value": item["rooms"], "inline": True},
            {"name": "Størrelse", "value": f"{item['size']} m²", "inline": True},
            {"name": "Status", "value": item["status"], "inline": True},
        ],
    }
    if item["image"]:
        embed["image"] = {"url": item["image"]}
    r = requests.post(WEBHOOK, json={"content": reason, "embeds": [embed]}, timeout=20)
    r.raise_for_status()


def main():
    if not WEBHOOK:
        sys.exit("Set the DISCORD_WEBHOOK_URL environment variable.")

    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    current = parse_listings(resp.text)
    if not current:
        sys.exit("Found 0 listings - the page layout may have changed.")

    first_run = not STATE_FILE.exists()
    seen = {} if first_run else json.loads(STATE_FILE.read_text(encoding="utf-8"))

    if first_run:
        print(f"First run: saving {len(current)} existing listings without posting.")
        requests.post(WEBHOOK, json={"content": f"✅ Kereby-watcher er sat op. Følger {len(current)} boliger og giver besked om nye."}, timeout=20)
    else:
        for key, item in current.items():
            if key not in seen:
                print("NEW:", item["address"])
                post_to_discord(item, "**Ny bolig på Kereby!**")
            elif seen[key].get("status") != "Ledig" and item["status"] == "Ledig":
                print("AVAILABLE AGAIN:", item["address"])
                post_to_discord(item, "**Bolig er ledig igen!**")

    # Remember everything ever seen, updated with the latest status.
    seen.update({k: {"address": v["address"], "status": v["status"]} for k, v in current.items()})
    STATE_FILE.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Checked {len(current)} listings.")


if __name__ == "__main__":
    main()
