# ClubWPT Gold Hand History Scraper

## Project Overview

This project scrapes NLHE cash game hand analysis data from the ClubWPT Gold Quintace API and converts it to PokerStars hand history format compatible with PokerTracker 4 and Holdem Manager 3.

## Architecture

- `scraper.py` — Async httpx client that fetches paginated hand data from `https://analysis-b2b.quintace.ai/api/players/hands`
- `converter.py` — Converts Quintace JSON hand objects to PokerStars `.txt` format
- `main.py` — CLI entry point with `--scrape-only`, `--convert-only`, and full pipeline modes
- `test_converter.py` — pytest suite (59 tests) covering all conversion logic and known edge cases
- `test_scraper.py` — pytest suite covering scraper page-freshness helpers

## Key API Details

- **Endpoint**: `GET https://analysis-b2b.quintace.ai/api/players/hands?game=nlhe&page={N}&pageSize={SIZE}`
- **Auth**: JWT token in `x-a5-authorization` header
- **Amount semantics**: For `raise`/`bet`/`allin`, `amount` is the player's TOTAL for the street. For `call`, `amount` is ADDITIONAL chips only — but see quirk #7 below.
- **Stack field**: The API `stack` is the ENDING stack, not starting. Starting = `stack - win_bet`.
- **Preflop "check" = limp**: The API reports preflop limps (and straddle calls) as `action: "check"` with `amount: 0`.

## Important Conversion Quirks

1. **Straddle handling**: PT4 doesn't support `posts the straddle`. Straddle is emitted as a synthetic preflop raise from UTG.
2. **Preflop "check" = implicit call**: The API reports preflop limps and straddle calls as "check" with amount=0. Any preflop "check" where the player hasn't matched the current bet is converted to a call (applies to both straddle and non-straddle games).
3. **All-in-for-less uncalled bets**: When a player goes all-in for less than the current bet, the difference must be returned as an uncalled bet to the last aggressor.
4. **Uncalled bet calculation**: Uses inline max/second-max computation on per-player `street_invested` values, which are correctly capped at available stack during action processing. This handles all-in-for-less via call correctly.
5. **Hand IDs**: The API uses 19-digit IDs; these are truncated to 12 digits (`id % 1_000_000_000_000`) for PT4 compatibility.
6. **Post-to-enter (post_seats)**: Players who post to enter always post BB amount (not straddle). PT4 interprets `posts big blind $X` where X > BB as having a dead component, which breaks street investment tracking.
7. **Preflop call amounts**: The API under-reports preflop `call` amounts for non-blind players (the reported value is short by `big_blind` chips). This affects both straddle and non-straddle games. The converter computes the correct call amount from its own `current_bet` tracking instead of trusting the API value.
8. **Split pot rounding**: When multiple players split the pot, the converter uses floor division and distributes remainder chips to earliest seat(s), ensuring collected amounts always sum to exactly the pot total.
9. **Board-plays-itself splits**: When all showdown players have `win_bet=0` (exact split where the board plays itself), they are treated as winners splitting the pot equally.
10. **Rake**: The analysis API returns rake-free, zero-sum data (`sum(net) == 0` across players), so rake is computed and re-applied from the [published ClubWPT Gold rake structure](https://support.clubwptgold.com/portal/en/kb/articles/rake) in `compute_rake()`. Rake is a percentage of the contested (post-uncalled-bet) pot, capped by stake and by the number of players dealt in (2P / 3–4P / 5P+ tiers). The `Total pot` line reports the gross pot; winners collect the pot net of rake. Two conventions not stated on the rake page are applied: **no flop, no rake** (hands ending preflop are unraked) and **round-half-up to the nearest cent**. Stakes absent from the table are unraked. `RAKE_TABLE` is keyed by `(small_blind, big_blind)` in chips (cents).

## Scraper Caching

- By default, `scrape_all` (the full-pipeline mode) trusts the on-disk `raw/page_*.json` cache for every page (except page 1, which is always fetched fresh for metadata).
- `--refresh-recent`: The API returns hands newest-first, so every new hand played shifts all older hands to a later page — a cached page near the front can go stale as soon as new hands are played. With this flag, `scrape_all` never trusts the on-disk cache for pages that might still contain hands from the last `FRESH_WINDOW_MS` (3 days, rolling from the current time) — it walks those pages sequentially, always re-fetching and overwriting the cache. Once a page is entirely older than that window, every later page is guaranteed to be older too, so the scraper falls back to the normal cache-aware, concurrently-batched fetch for the stable historical tail. Mutually exclusive with `--update` and `--convert-only`.
- `--overwrite` bypasses the cache entirely and re-downloads every page in range, regardless of freshness. Mutually exclusive with `--update` and `--convert-only`.
- `--update` (`scrape_update`) is unaffected by either flag — it already always walks fresh from page 1 and stops on the first duplicate hand ID.

## Running Tests

```bash
uv run pytest -v
```

## Running the Scraper

```bash
# Full pipeline (scrape + convert)
uv run python main.py --token "YOUR_JWT_TOKEN"

# Scrape only (save raw JSON)
uv run python main.py --token "YOUR_JWT_TOKEN" --scrape-only

# Convert only (from previously saved raw JSON)
uv run python main.py --convert-only

# Custom output directory
uv run python main.py --token "YOUR_JWT_TOKEN" --output-dir /path/to/output

# Force a full re-download, ignoring the cache entirely
uv run python main.py --token "YOUR_JWT_TOKEN" --overwrite

# Re-fetch pages that might hold hands from the last 3 days, trust cache for the rest
uv run python main.py --token "YOUR_JWT_TOKEN" --refresh-recent
```

## Output Structure

```
output/
  raw/              # Raw JSON pages from API (page_00001.json, ...)
  pokerstars/       # Converted hand history files (HH_2026-07-17.txt, ...)
```
