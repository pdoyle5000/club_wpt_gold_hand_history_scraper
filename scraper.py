"""Async API client for scraping ClubWPT Gold hand history data."""

import asyncio
import json
import os
import time

import httpx

BASE_URL = "https://analysis-b2b.quintace.ai/api/players/hands"
DEFAULT_PAGE_SIZE = 100
MAX_CONCURRENT = 10
DELAY_BETWEEN_BATCHES = 0.1  # seconds


async def fetch_page(
    client: httpx.AsyncClient,
    token: str,
    page: int,
    page_size: int,
    semaphore: asyncio.Semaphore,
) -> dict | None:
    """Fetch a single page of hand data from the API."""
    async with semaphore:
        headers = {
            "x-a5-authorization": token,
            "accept": "*/*",
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
            "referer": f"https://analysis-b2b.quintace.ai/?page={page}",
        }
        params = {"game": "nlhe", "page": page, "pageSize": page_size}

        for attempt in range(3):
            try:
                resp = await client.get(BASE_URL, headers=headers, params=params, timeout=30.0)
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as e:
                if attempt < 2:
                    wait = 2 ** attempt
                    print(f"  Page {page} attempt {attempt+1} failed: {e}. Retrying in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    print(f"  Page {page} FAILED after 3 attempts: {e}")
                    return None


async def fetch_metadata(client: httpx.AsyncClient, token: str, page_size: int) -> dict:
    """Fetch the first page to get metadata (total pages, total hands)."""
    semaphore = asyncio.Semaphore(1)
    result = await fetch_page(client, token, 1, page_size, semaphore)
    if result is None:
        raise RuntimeError("Failed to fetch first page. Check your token.")
    return result


async def scrape_all(
    token: str,
    raw_dir: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    start_page: int = 1,
    end_page: int | None = None,
    max_concurrent: int = MAX_CONCURRENT,
) -> list[dict]:
    """Scrape all pages and save raw JSON. Returns list of all hand dicts."""
    os.makedirs(raw_dir, exist_ok=True)
    semaphore = asyncio.Semaphore(max_concurrent)
    all_hands = []

    async with httpx.AsyncClient(http2=False) as client:
        # Get metadata
        print("Fetching metadata...")
        first_page = await fetch_metadata(client, token, page_size)
        meta = first_page['metadata']
        total_pages = meta['total_pages']
        total_hands = meta['total']
        actual_end = min(end_page, total_pages) if end_page else total_pages

        print(f"Total hands: {total_hands}")
        print(f"Total pages: {total_pages} (pageSize={page_size})")
        print(f"Scraping pages {start_page} to {actual_end}")

        # Save and collect first page hands if in range
        if start_page == 1:
            _save_raw_page(raw_dir, 1, first_page)
            all_hands.extend(first_page.get('data', []))
            print(f"  Page 1/{actual_end} - {len(first_page.get('data', []))} hands")

        # Determine which pages still need fetching
        pages_to_fetch = []
        first_done = 1 if start_page == 1 else 0
        for page in range(max(start_page, 1 + first_done), actual_end + 1):
            raw_path = os.path.join(raw_dir, f"page_{page:05d}.json")
            if os.path.exists(raw_path):
                # Resume: load from disk
                try:
                    with open(raw_path, 'r') as f:
                        cached = json.load(f)
                    all_hands.extend(cached.get('data', []))
                    continue
                except (json.JSONDecodeError, IOError):
                    pass  # Re-fetch corrupted files
            pages_to_fetch.append(page)

        if not pages_to_fetch:
            print(f"All pages already downloaded. {len(all_hands)} hands loaded from cache.")
            return all_hands

        cached_count = actual_end - start_page + 1 - len(pages_to_fetch) - first_done
        if cached_count > 0:
            print(f"Resuming: {cached_count} pages loaded from cache, {len(pages_to_fetch)} remaining")

        # Fetch remaining pages in batches
        batch_size = max_concurrent * 2
        start_time = time.time()

        for batch_start in range(0, len(pages_to_fetch), batch_size):
            batch = pages_to_fetch[batch_start:batch_start + batch_size]
            tasks = [
                fetch_page(client, token, page, page_size, semaphore)
                for page in batch
            ]
            results = await asyncio.gather(*tasks)

            for page, result in zip(batch, results):
                if result is not None:
                    _save_raw_page(raw_dir, page, result)
                    hands = result.get('data', [])
                    all_hands.extend(hands)

            done = batch_start + len(batch)
            total_to_fetch = len(pages_to_fetch)
            elapsed = time.time() - start_time
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total_to_fetch - done) / rate if rate > 0 else 0

            last_page = batch[-1]
            print(f"  Pages {batch[0]}-{last_page}/{actual_end} "
                  f"({done}/{total_to_fetch} fetched, {len(all_hands)} hands, "
                  f"{rate:.1f} pages/s, ETA {eta:.0f}s)")

            if batch_start + batch_size < len(pages_to_fetch):
                await asyncio.sleep(DELAY_BETWEEN_BATCHES)

    elapsed_total = time.time() - start_time
    print(f"\nDone! Scraped {len(all_hands)} hands in {elapsed_total:.1f}s")
    return all_hands


def _save_raw_page(raw_dir: str, page: int, data: dict):
    """Save a raw JSON page to disk."""
    path = os.path.join(raw_dir, f"page_{page:05d}.json")
    with open(path, 'w') as f:
        json.dump(data, f)
