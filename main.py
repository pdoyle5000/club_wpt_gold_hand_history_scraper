#!/usr/bin/env python3
"""ClubWPT Gold Hand History Scraper & Converter.

Scrapes hand analysis data from the Quintace API and converts it to either
PokerStars hand history text or Open Hand History (OHH) JSON, both of which
import into PokerTracker 4 / Holdem Manager 3.
"""

import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

from converter import convert_hand
from ohh_converter import convert_hand_to_ohh_json
from scraper import load_raw_hands_by_id, scrape_all, scrape_update

# name -> (output subdirectory, file extension, per-hand renderer, separator)
FORMATS = {
    "pokerstars": ("pokerstars", ".txt", convert_hand, "\n\n\n"),
    # The OHH storage format is a sequence of JSON objects, one blank line apart.
    "ohh": ("ohh", ".ohh", convert_hand_to_ohh_json, "\n\n"),
}


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


def write_hand_files(hands: list[dict], output_dir: str, hero_uid: str | None = None,
                     fmt: str = "pokerstars") -> int:
    """Convert hands and write to date-organized files. Returns count of converted hands."""
    _subdir, extension, render, separator = FORMATS[fmt]
    os.makedirs(output_dir, exist_ok=True)
    by_date = group_hands_by_date(hands)
    total_converted = 0
    errors = 0

    for date_key in sorted(by_date.keys(), reverse=True):
        date_hands = by_date[date_key]
        filename = f"HH_{date_key}{extension}"
        filepath = os.path.join(output_dir, filename)

        converted_texts = []
        for hand in date_hands:
            try:
                converted_texts.append(render(hand, hero_uid=hero_uid))
                total_converted += 1
            except Exception as e:
                errors += 1
                print(f"  Error converting hand {hand.get('id', '?')}: {e}")

        if converted_texts:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(separator.join(converted_texts) + '\n')
            print(f"  {filename}: {len(converted_texts)} hands")

    if errors:
        print(f"\n{errors} hands failed to convert")
    return total_converted


def load_raw_hands(raw_dir: str) -> list[dict]:
    """Load every stored hand, deduplicated by hand ID and sorted oldest-first.

    Reads both the date-partitioned ``hands_*.json`` store and any legacy
    ``page_*.json`` snapshots, so nothing captured by an older version of the
    scraper is dropped.
    """
    hands = list(load_raw_hands_by_id(raw_dir).values())
    hands.sort(key=lambda h: h.get('timestamp', 0))
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
        help="Deprecated no-op: a full scrape already re-fetches every page"
    )
    parser.add_argument(
        "--refresh-recent", action="store_true",
        help="Deprecated no-op: a full scrape already re-fetches every page"
    )
    parser.add_argument(
        "--format", choices=["pokerstars", "ohh", "both"], default="pokerstars",
        help="Output format: 'pokerstars' text (default), 'ohh' (Open Hand History "
             "JSON, which models antes and straddles natively), or 'both'"
    )
    parser.add_argument(
        "--hero-uid", default=None,
        help="Override your player UID for 'Dealt to' display "
             "(default: auto-detected per-hand from table.session_id)"
    )

    args = parser.parse_args()

    raw_dir = os.path.join(args.output_dir, "raw")
    formats = ["pokerstars", "ohh"] if args.format == "both" else [args.format]

    if not args.convert_only and not args.token:
        parser.error("--token is required unless --convert-only is used")

    if args.convert_only and args.update:
        parser.error("--convert-only and --update are mutually exclusive")

    if args.overwrite and args.update:
        parser.error("--overwrite and --update are mutually exclusive")

    if args.overwrite and args.convert_only:
        parser.error("--overwrite and --convert-only are mutually exclusive")

    if args.refresh_recent and args.update:
        parser.error("--refresh-recent and --update are mutually exclusive")

    if args.refresh_recent and args.convert_only:
        parser.error("--refresh-recent and --convert-only are mutually exclusive")

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
        if args.overwrite or args.refresh_recent:
            print("Note: --overwrite/--refresh-recent are no-ops; a full scrape "
                  "always re-fetches every page.")
        asyncio.run(
            scrape_all(
                token=args.token,
                raw_dir=raw_dir,
                page_size=args.page_size,
                start_page=args.start_page,
                end_page=args.end_page,
                max_concurrent=args.max_concurrent,
            )
        )

    if args.scrape_only:
        print(f"\nScrape complete. Raw JSON saved to {raw_dir}")
        return

    if not args.convert_only and not args.update:
        # Reload from disk to dedupe by hand ID: page boundaries can shift
        # between a freshly-fetched page and a stale cached page, producing
        # the same hand twice in scrape_all's raw in-memory result.
        print("\nLoading all hands from raw JSON files...")
        all_hands = load_raw_hands(raw_dir)
        print(f"Loaded {len(all_hands)} unique hands")

    # Convert
    for fmt in formats:
        subdir = FORMATS[fmt][0]
        out_dir = os.path.join(args.output_dir, subdir)
        print("\n" + "=" * 60)
        print(f"Converting to {fmt} format...")
        print("=" * 60)
        converted = write_hand_files(all_hands, out_dir, hero_uid=args.hero_uid, fmt=fmt)
        print(f"\nDone! {converted} hands written to {out_dir}")


if __name__ == "__main__":
    main()
