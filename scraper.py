"""Async API client for scraping ClubWPT Gold hand history data.

Raw hands are stored in date-partitioned files (``hands_YYYY-MM-DD.json``)
keyed by hand ID, and every write is a merge. Nothing here caches or
overwrites by page *index*: the API returns hands newest-first, so page N
holds different hands every time somebody plays a hand, and any scheme that
treats ``page_00042.json`` as "the contents of page 42" silently loses hands.
See ``merge_raw_hands`` and the module docstring in ``main.py``.
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone

import httpx

BASE_URL = "https://analysis-b2b.quintace.ai/api/players/hands"
DEFAULT_PAGE_SIZE = 100
# The API returns an empty body (no JSON at all) for pageSize > 100.
MAX_PAGE_SIZE = 100
MAX_CONCURRENT = 10
DELAY_BETWEEN_BATCHES = 0.1  # seconds
# How many consecutive already-known pages an incremental walk needs to see
# before it believes it has caught up. More than one, because the server has
# small holes in its own history and a single known page is not proof.
UPDATE_CONFIRM_PAGES = 3

LEGACY_PAGE_PREFIX = "page_"
HANDS_FILE_PREFIX = "hands_"


async def fetch_page(
    client: httpx.AsyncClient,
    token: str,
    page: int,
    page_size: int,
    semaphore: asyncio.Semaphore,
) -> dict | None:
    """Fetch a single page of hand data from the API.

    No ``filter`` parameter is sent, which is what makes the response the
    *complete* history: the UI's "Analyzed"/"Not analyzed" toggles send
    ``filter=analysis_mode:eq:N``, and the unfiltered totals equal the sum of
    all three modes, so the default response already includes hands the
    coach has never analyzed.
    """
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
            except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException,
                    json.JSONDecodeError) as e:
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


# --------------------------------------------------------------------------
# Raw storage: date-partitioned, keyed by hand ID, merge-only.
# --------------------------------------------------------------------------

def hand_date_key(hand: dict) -> str:
    """UTC date a hand belongs to, matching main.group_hands_by_date."""
    ts = hand.get('timestamp', 0) / 1000.0
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%d')


def iter_raw_files(raw_dir: str):
    """Every raw file worth reading, newest storage format first.

    Legacy ``page_*.json`` snapshots are still read so that hands captured
    before the storage change (including any the server has since dropped)
    are never lost.
    """
    if not os.path.exists(raw_dir):
        return
    for filename in sorted(os.listdir(raw_dir)):
        if not filename.endswith('.json'):
            continue
        if filename.startswith((HANDS_FILE_PREFIX, LEGACY_PAGE_PREFIX)):
            yield os.path.join(raw_dir, filename)


def load_raw_hands_by_id(raw_dir: str) -> dict[str, dict]:
    """Load every stored hand, deduplicated by hand ID."""
    hands: dict[str, dict] = {}
    for path in iter_raw_files(raw_dir):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  Warning: could not load {os.path.basename(path)}: {e}")
            continue
        for hand in data.get('data', []):
            hand_id = str(hand.get('id', ''))
            if hand_id:
                hands.setdefault(hand_id, hand)
    return hands


def load_existing_hand_ids(raw_dir: str) -> set[str]:
    """Load all hand IDs already stored on disk."""
    return set(load_raw_hands_by_id(raw_dir))


def merge_raw_hands(raw_dir: str, hands: list[dict]) -> int:
    """Merge hands into date-partitioned files. Returns the number newly added.

    A hand already on disk is left as-is, and no existing hand is ever
    dropped, so a partial or interrupted run can only ever add data.
    """
    os.makedirs(raw_dir, exist_ok=True)

    by_date: dict[str, dict[str, dict]] = {}
    for hand in hands:
        hand_id = str(hand.get('id', ''))
        if hand_id:
            by_date.setdefault(hand_date_key(hand), {})[hand_id] = hand

    added = 0
    for date_key, incoming in by_date.items():
        path = os.path.join(raw_dir, f"{HANDS_FILE_PREFIX}{date_key}.json")
        existing: dict[str, dict] = {}
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    for hand in json.load(f).get('data', []):
                        existing[str(hand.get('id', ''))] = hand
            except (json.JSONDecodeError, IOError) as e:
                print(f"  Warning: rebuilding corrupt {os.path.basename(path)}: {e}")

        new_ids = [i for i in incoming if i not in existing]
        if not new_ids:
            continue
        existing.update(incoming)
        added += len(new_ids)

        merged = sorted(existing.values(), key=lambda h: h.get('timestamp', 0))
        tmp = f"{path}.tmp"
        with open(tmp, 'w') as f:
            json.dump({"date": date_key, "count": len(merged), "data": merged}, f)
        os.replace(tmp, path)

    return added


def _save_raw_page(raw_dir: str, page: int, data: dict):
    """Deprecated: writing raw files by page index loses hands.

    Kept only so that older callers fail loudly instead of silently
    corrupting the store.
    """
    raise NotImplementedError(
        "raw pages are no longer stored by page index; use merge_raw_hands()"
    )


# --------------------------------------------------------------------------
# Scraping
# --------------------------------------------------------------------------

async def _walk_until_known(
    client: httpx.AsyncClient,
    token: str,
    raw_dir: str,
    page_size: int,
    total_pages: int,
    known_ids: set[str],
    confirm_pages: int,
    first_page: dict | None = None,
    label: str = "Update",
) -> list[dict]:
    """Walk pages from 1 until `confirm_pages` consecutive pages are all known.

    This is the only correct way to catch up incrementally: it follows the
    newest-first ordering forward from page 1, so it cannot be fooled by
    hands shifting to later pages while it runs.
    """
    semaphore = asyncio.Semaphore(1)
    new_hands: list[dict] = []
    consecutive_known = 0
    page = 1

    while page <= total_pages:
        result = first_page if (page == 1 and first_page is not None) else \
            await fetch_page(client, token, page, page_size, semaphore)
        if result is None:
            print(f"  {label}: page {page} failed, stopping walk.")
            break

        hands = result.get('data', [])
        if not hands:
            break

        fresh = [h for h in hands if str(h.get('id', '')) not in known_ids]
        for h in fresh:
            known_ids.add(str(h.get('id', '')))
        new_hands.extend(fresh)
        merge_raw_hands(raw_dir, hands)

        if fresh:
            consecutive_known = 0
        else:
            consecutive_known += 1

        print(f"  {label}: page {page}/{total_pages} — {len(hands)} hands, "
              f"{len(fresh)} new ({len(new_hands)} new so far)")

        if consecutive_known >= confirm_pages:
            print(f"  {label}: {confirm_pages} consecutive pages already known, caught up.")
            break

        page += 1

    return new_hands


async def scrape_all(
    token: str,
    raw_dir: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    start_page: int = 1,
    end_page: int | None = None,
    max_concurrent: int = MAX_CONCURRENT,
    confirm_pages: int = UPDATE_CONFIRM_PAGES,
) -> list[dict]:
    """Sweep every page of history and merge the result into the raw store.

    Every page in range is fetched — there is deliberately no page-index
    cache. Because hands are returned newest-first, a hand played while the
    sweep is running shifts existing hands toward later pages, so a hand can
    slip past an already-fetched page; the sweep is therefore followed by an
    incremental walk from page 1 to pick up anything that drifted.

    Returns the list of all hands now on disk for the scraped range.
    """
    os.makedirs(raw_dir, exist_ok=True)
    semaphore = asyncio.Semaphore(max_concurrent)
    start_time = time.time()
    page_size = min(page_size, MAX_PAGE_SIZE)

    async with httpx.AsyncClient(http2=False) as client:
        print("Fetching metadata...")
        first_page = await fetch_metadata(client, token, page_size)
        meta = first_page['metadata']
        total_pages = meta['total_pages']
        total_hands = meta['total']
        actual_end = min(end_page, total_pages) if end_page else total_pages

        print(f"Total hands on server: {total_hands}")
        print(f"Total pages: {total_pages} (pageSize={page_size})")
        print(f"Sweeping pages {start_page} to {actual_end} (no page cache)")

        fetched: dict[str, dict] = {}
        failed_pages: list[int] = []

        if start_page == 1:
            for h in first_page.get('data', []):
                fetched[str(h.get('id', ''))] = h
            pages = list(range(2, actual_end + 1))
        else:
            pages = list(range(start_page, actual_end + 1))

        batch_size = max_concurrent * 2
        for batch_start in range(0, len(pages), batch_size):
            batch = pages[batch_start:batch_start + batch_size]
            results = await asyncio.gather(*[
                fetch_page(client, token, p, page_size, semaphore) for p in batch
            ])
            batch_hands = []
            for p, result in zip(batch, results):
                if result is None:
                    failed_pages.append(p)
                    continue
                for h in result.get('data', []):
                    hand_id = str(h.get('id', ''))
                    if hand_id and hand_id not in fetched:
                        fetched[hand_id] = h
                        batch_hands.append(h)
            merge_raw_hands(raw_dir, batch_hands)

            done = batch_start + len(batch)
            elapsed = time.time() - start_time
            rate = done / elapsed if elapsed > 0 else 0
            eta = (len(pages) - done) / rate if rate > 0 else 0
            print(f"  Pages {batch[0]}-{batch[-1]}/{actual_end} "
                  f"({done}/{len(pages)} fetched, {len(fetched)} unique hands, "
                  f"{rate:.1f} pages/s, ETA {eta:.0f}s)")

            if batch_start + batch_size < len(pages):
                await asyncio.sleep(DELAY_BETWEEN_BATCHES)

        # Retry any page that failed all its attempts, rather than leaving a hole.
        if failed_pages:
            print(f"Retrying {len(failed_pages)} failed page(s)...")
            still_failed = []
            for p in failed_pages:
                result = await fetch_page(client, token, p, page_size, semaphore)
                if result is None:
                    still_failed.append(p)
                    continue
                merge_raw_hands(raw_dir, result.get('data', []))
                for h in result.get('data', []):
                    fetched[str(h.get('id', ''))] = h
            failed_pages = still_failed

        # Catch hands that shifted to a later page while the sweep ran.
        if start_page == 1 and actual_end == total_pages:
            print("Confirming nothing drifted during the sweep...")
            drifted = await _walk_until_known(
                client, token, raw_dir, page_size, total_pages,
                known_ids=set(fetched), confirm_pages=confirm_pages,
                label="Drift check",
            )
            for h in drifted:
                fetched[str(h.get('id', ''))] = h
            if drifted:
                print(f"  Picked up {len(drifted)} hand(s) that shifted mid-sweep.")

    elapsed_total = time.time() - start_time
    print(f"\nSwept {len(fetched)} unique hands in {elapsed_total:.1f}s")

    if failed_pages:
        print(f"WARNING: {len(failed_pages)} page(s) could not be fetched: "
              f"{failed_pages[:20]}{'...' if len(failed_pages) > 20 else ''}")
    if start_page == 1 and actual_end == total_pages and len(fetched) < total_hands:
        print(f"WARNING: server reported {total_hands} hands but only "
              f"{len(fetched)} were captured ({total_hands - len(fetched)} short)")

    return list(fetched.values())


async def scrape_update(
    token: str,
    raw_dir: str,
    page_size: int = DEFAULT_PAGE_SIZE,
    confirm_pages: int = UPDATE_CONFIRM_PAGES,
) -> list[dict]:
    """Fetch only hands not already on disk, walking forward from page 1.

    Stops once `confirm_pages` consecutive pages contain nothing new.
    Returns the list of newly fetched hand dicts.
    """
    os.makedirs(raw_dir, exist_ok=True)
    page_size = min(page_size, MAX_PAGE_SIZE)

    print("Loading existing hand IDs...")
    known_ids = load_existing_hand_ids(raw_dir)
    print(f"Found {len(known_ids)} existing hands")

    async with httpx.AsyncClient(http2=False) as client:
        print("Fetching metadata...")
        first_page = await fetch_metadata(client, token, page_size)
        meta = first_page['metadata']
        total_pages = meta['total_pages']
        total_hands = meta['total']
        print(f"Total hands on server: {total_hands} ({total_pages} pages)")

        new_hands = await _walk_until_known(
            client, token, raw_dir, page_size, total_pages,
            known_ids=known_ids, confirm_pages=confirm_pages,
            first_page=first_page, label="Update",
        )

    on_disk = len(known_ids)
    print(f"\nUpdate complete. {len(new_hands)} new hands fetched; "
          f"{on_disk} now on disk (server reports {total_hands}).")
    if on_disk < total_hands:
        print(f"NOTE: {total_hands - on_disk} hand(s) on the server are not on disk. "
              f"Run without --update to sweep the full history.")
    return new_hands
