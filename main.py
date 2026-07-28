#!/usr/bin/env python3
"""ClubWPT Gold Hand History Scraper & PokerStars Converter.

Scrapes hand analysis data from the Quintace API and converts to
PokerStars hand history format compatible with PokerTracker/HM.
"""

import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

from converter import convert_hand
from scraper import scrape_all, scrape_update


def group_hands_by_date(hands: list[dict]) -> dict[str, list[dict]]:
    """Group hands by date (YYYY-MM-DD) based on timestamp."""
    by_date = defaultdict(list)
    for hand in hands:
        ts = hand.get('timestamp', 0) / 1000.0
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        date_key = dt.strftime('%Y-%m-%d')
        by_date[date_key].append(hand)
    # Sort hands within each date by timestamp
    for date_key in by_date:
        by_date[date_key].sort(key=lambda h: h.get('timestamp', 0))
    return dict(by_date)


def write_hand_files(hands: list[dict], output_dir: str, hero_uid: str = "235160") -> int:
    """Convert hands and write to date-organized files. Returns count of converted hands."""
    os.makedirs(output_dir, exist_ok=True)
    by_date = group_hands_by_date(hands)
    total_converted = 0
    errors = 0

    for date_key in sorted(by_date.keys(), reverse=True):
        date_hands = by_date[date_key]
        filename = f"HH_{date_key}.txt"
        filepath = os.path.join(output_dir, filename)

        converted_texts = []
        for hand in date_hands:
            try:
                text = convert_hand(hand, hero_uid=hero_uid)
                converted_texts.append(text)
                total_converted += 1
            except Exception as e:
                errors += 1
                print(f"  Error converting hand {hand.get('id', '?')}: {e}")

        if converted_texts:
            with open(filepath, 'w') as f:
                f.write('\n\n\n'.join(converted_texts) + '\n')
            print(f"  {filename}: {len(converted_texts)} hands")

    if errors:
        print(f"\n{errors} hands failed to convert")
    return total_converted


def load_raw_hands(raw_dir: str) -> list[dict]:
    """Load all hands from raw JSON page files, deduplicating by hand ID.

    Pages are loaded in order (page 1 first), so after an --update run
    that overwrites early pages, the newest version of shifted hands is kept.
    """
    hands = []
    seen_ids: set[str] = set()
    if not os.path.exists(raw_dir):
        return hands

    files = sorted(f for f in os.listdir(raw_dir) if f.startswith('page_') and f.endswith('.json'))
    for filename in files:
        filepath = os.path.join(raw_dir, filename)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            for hand in data.get('data', []):
                hand_id = str(hand.get('id', ''))
                if hand_id and hand_id not in seen_ids:
                    seen_ids.add(hand_id)
                    hands.append(hand)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  Warning: Could not load {filename}: {e}")
    return hands


def main():
    parser = argparse.ArgumentParser(
        description="Scrape ClubWPT Gold hands and convert to PokerStars format"
    )
    parser.add_argument(
        "--token", required=False, default="",
        help="JWT token from x-a5-authorization header (required unless --convert-only)"
    )
    parser.add_argument(
        "--output-dir", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"),
        help="Base output directory (default: ./output)"
    )
    parser.add_argument(
        "--page-size", type=int, default=100,
        help="Number of hands per API page (default: 100)"
    )
    parser.add_argument(
        "--start-page", type=int, default=1,
        help="First page to scrape (default: 1)"
    )
    parser.add_argument(
        "--end-page", type=int, default=None,
        help="Last page to scrape (default: all)"
    )
    parser.add_argument(
        "--max-concurrent", type=int, default=10,
        help="Max concurrent API requests (default: 10)"
    )
    parser.add_argument(
        "--scrape-only", action="store_true",
        help="Only scrape raw JSON, don't convert"
    )
    parser.add_argument(
        "--convert-only", action="store_true",
        help="Only convert existing raw JSON, don't scrape"
    )
    parser.add_argument(
        "--update", action="store_true",
        help="Incremental scrape: fetch new hands and stop on first duplicate"
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Ignore the on-disk cache entirely and re-download every page"
    )
    parser.add_argument(
        "--hero-uid", default="235160",
        help="Your player UID for 'Dealt to' display (default: 235160)"
    )

    args = parser.parse_args()

    raw_dir = os.path.join(args.output_dir, "raw")
    ps_dir = os.path.join(args.output_dir, "pokerstars")

    if not args.convert_only and not args.token:
        parser.error("--token is required unless --convert-only is used")

    if args.convert_only and args.update:
        parser.error("--convert-only and --update are mutually exclusive")

    if args.overwrite and args.update:
        parser.error("--overwrite and --update are mutually exclusive")

    if args.overwrite and args.convert_only:
        parser.error("--overwrite and --convert-only are mutually exclusive")

    if args.convert_only:
        # Load from raw JSON files
        print("Loading hands from raw JSON files...")
        all_hands = load_raw_hands(raw_dir)
        if not all_hands:
            print("No raw JSON files found. Run scraper first.")
            sys.exit(1)
        print(f"Loaded {len(all_hands)} hands from raw files")
    elif args.update:
        # Incremental scrape: fetch new hands, stop on duplicate
        print("=" * 60)
        print("ClubWPT Gold Hand History Scraper (update)")
        print("=" * 60)
        asyncio.run(
            scrape_update(
                token=args.token,
                raw_dir=raw_dir,
                page_size=args.page_size,
            )
        )
        # Load all hands (old + new, deduped) for conversion
        print("\nLoading all hands from raw JSON files...")
        all_hands = load_raw_hands(raw_dir)
        print(f"Loaded {len(all_hands)} unique hands")
    else:
        # Full scrape
        print("=" * 60)
        print("ClubWPT Gold Hand History Scraper")
        print("=" * 60)
        all_hands = asyncio.run(
            scrape_all(
                token=args.token,
                raw_dir=raw_dir,
                page_size=args.page_size,
                start_page=args.start_page,
                end_page=args.end_page,
                max_concurrent=args.max_concurrent,
                overwrite=args.overwrite,
            )
        )

    if args.scrape_only:
        print(f"\nScrape complete. Raw JSON saved to {raw_dir}")
        return

    # Convert
    print("\n" + "=" * 60)
    print("Converting to PokerStars format...")
    print("=" * 60)
    converted = write_hand_files(all_hands, ps_dir, hero_uid=args.hero_uid)
    print(f"\nDone! {converted} hands written to {ps_dir}")


if __name__ == "__main__":
    main()
