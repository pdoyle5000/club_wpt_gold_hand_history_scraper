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
FRESH_WINDOW_MS = 3 * 24 * 60 * 60 * 1000  # rolling window that always bypasses the on-disk cache


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


def _page_is_stale(page_data: dict, cutoff_ts_ms: float) -> bool:
    """True if every hand on this page is older than cutoff_ts_ms.

    Pages are returned newest-hand-first, so once a page is entirely
    stale, every later page is guaranteed to be stale too.
    """
    hands = page_data.get('data', [])
    if not hands:
        return True
    return all(hand.get('timestamp', 0) < cutoff_ts_ms for hand in hands)


async def scrape_all(
    token: str,
    raw_dir: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    start_page: int = 1,
    end_page: int | None = None,
    max_concurrent: int = MAX_CONCURRENT,
    overwrite: bool = False,
    refresh_recent: bool = False,
) -> list[dict]:
    """Scrape all pages and save raw JSON. Returns list of all hand dicts.

    If refresh_recent is True, pages that may contain hands within the
    rolling FRESH_WINDOW_MS window (newest activity) are always re-fetched
    from the API, ignoring any on-disk cache, since new hands constantly
    shift older hands to later pages. Older, stable pages still use the
    on-disk cache to speed up repeated runs. If refresh_recent is False
    (the default), the on-disk cache is trusted for every page as usual.

    If overwrite is True, the on-disk cache is ignored entirely and every
    page in range is re-fetched (the sequential fresh-window walk is
    skipped since the batched fetch below already covers everything).
    """
    os.makedirs(raw_dir, exist_ok=True)
    semaphore = asyncio.Semaphore(max_concurrent)
    all_hands = []
    start_time = time.time()
    cutoff_ts_ms = start_time * 1000 - FRESH_WINDOW_MS

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
        next_page = start_page
        fresh_walk_active = False
        if start_page == 1:
            _save_raw_page(raw_dir, 1, first_page)
            all_hands.extend(first_page.get('data', []))
            print(f"  Page 1/{actual_end} - {len(first_page.get('data', []))} hands")
            next_page = 2
            fresh_walk_active = (
                refresh_recent and not overwrite and not _page_is_stale(first_page, cutoff_ts_ms)
            )

        # Phase A: walk forward sequentially, always bypassing the cache,
        # for as long as pages may still contain hands in the fresh window.
        fresh_pages_fetched = 0
        while fresh_walk_active and next_page <= actual_end:
            result = await fetch_page(client, token, next_page, page_size, semaphore)
            if result is None:
                print(f"  Page {next_page} failed during fresh-window walk, stopping walk.")
                break
            _save_raw_page(raw_dir, next_page, result)
            all_hands.extend(result.get('data', []))
            fresh_pages_fetched += 1
            print(f"  Page {next_page}/{actual_end} - {len(result.get('data', []))} hands (fresh, cache bypassed)")
            fresh_walk_active = not _page_is_stale(result, cutoff_ts_ms)
            next_page += 1

        if fresh_pages_fetched:
            print(f"Fresh-window walk complete: {fresh_pages_fetched} page(s) re-fetched (cache bypassed)")

        # Phase B: for remaining (stable/older) pages, use the on-disk
        # cache when available, else queue for batched concurrent fetch.
        pages_to_fetch = []
        cached_count = 0
        for page in range(next_page, actual_end + 1):
            raw_path = os.path.join(raw_dir, f"page_{page:05d}.json")
            if not overwrite and os.path.exists(raw_path):
                # Resume: load from disk
                try:
                    with open(raw_path, 'r') as f:
                        cached = json.load(f)
                    all_hands.extend(cached.get('data', []))
                    cached_count += 1
                    continue
                except (json.JSONDecodeError, IOError):
                    pass  # Re-fetch corrupted files
            pages_to_fetch.append(page)

        if not pages_to_fetch:
            if cached_count:
                print(f"Remaining pages already downloaded. {cached_count} pages loaded from cache.")
            print(f"\nDone! Scraped {len(all_hands)} hands in {time.time() - start_time:.1f}s")
            return all_hands

        if cached_count > 0:
            print(f"Resuming: {cached_count} pages loaded from cache, {len(pages_to_fetch)} remaining")

        # Fetch remaining pages in batches
        batch_size = max_concurrent * 2

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


def load_existing_hand_ids(raw_dir: str) -> set[str]:
    """Load all hand IDs from existing raw JSON page files."""
    ids = set()
    if not os.path.exists(raw_dir):
        return ids
    for filename in sorted(os.listdir(raw_dir)):
        if not (filename.startswith('page_') and filename.endswith('.json')):
            continue
        filepath = os.path.join(raw_dir, filename)
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            for hand in data.get('data', []):
                hand_id = hand.get('id')
                if hand_id:
                    ids.add(str(hand_id))
        except (json.JSONDecodeError, IOError):
            continue
    return ids


async def scrape_update(
    token: str,
    raw_dir: str,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> list[dict]:
    """Fetch only new hands, stopping when a duplicate is found.

    Pages are fetched sequentially from page 1 (newest first).
    Stops as soon as any hand on a page already exists in the
    previously scraped raw JSON files.

    Returns the list of newly fetched hand dicts.
    """
    os.makedirs(raw_dir, exist_ok=True)
    semaphore = asyncio.Semaphore(1)

    print("Loading existing hand IDs...")
    known_ids = load_existing_hand_ids(raw_dir)
    print(f"Found {len(known_ids)} existing hands")

    new_hands = []

    async with httpx.AsyncClient(http2=False) as client:
        print("Fetching metadata...")
        first_page = await fetch_metadata(client, token, page_size)
        meta = first_page['metadata']
        total_pages = meta['total_pages']
        total_hands = meta['total']
        print(f"Total hands on server: {total_hands} ({total_pages} pages)")

        page = 1
        while page <= total_pages:
            if page == 1:
                result = first_page
            else:
                result = await fetch_page(client, token, page, page_size, semaphore)

            if result is None:
                print(f"  Page {page} failed, stopping.")
                break

            hands = result.get('data', [])
            _save_raw_page(raw_dir, page, result)

            # Check for overlap
            found_duplicate = False
            for hand in hands:
                hand_id = str(hand.get('id', ''))
                if hand_id in known_ids:
                    found_duplicate = True
                else:
                    new_hands.append(hand)

            print(f"  Page {page}/{total_pages} — {len(hands)} hands"
                  f" ({len(new_hands)} new so far)")

            if found_duplicate:
                print(f"Found existing hand on page {page}, stopping.")
                break

            page += 1

    print(f"\nUpdate complete. {len(new_hands)} new hands fetched across {page} page(s).")
    return new_hands


def _save_raw_page(raw_dir: str, page: int, data: dict):
    """Save a raw JSON page to disk."""
    path = os.path.join(raw_dir, f"page_{page:05d}.json")
    with open(path, 'w') as f:
        json.dump(data, f)
