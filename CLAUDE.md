# ClubWPT Gold Hand History Scraper

## Project Overview

This project scrapes NLHE cash game hand analysis data from the ClubWPT Gold Quintace API and converts it to PokerStars hand history format compatible with PokerTracker 4 and Holdem Manager 3.

## Architecture

- `scraper.py` — Async httpx client that fetches paginated hand data from `https://analysis-b2b.quintace.ai/api/players/hands`
- `converter.py` — Converts Quintace JSON hand objects to PokerStars `.txt` format
- `main.py` — CLI entry point with `--scrape-only`, `--convert-only`, and full pipeline modes
- `test_converter.py` — pytest suite (45 tests) covering all conversion logic and known edge cases

## Key API Details

- **Endpoint**: `GET https://analysis-b2b.quintace.ai/api/players/hands?game=nlhe&page={N}&pageSize={SIZE}`
- **Auth**: JWT token in `x-a5-authorization` header
- **Amount semantics**: For `raise`/`bet`/`allin`, `amount` is the player's TOTAL for the street. For `call`, `amount` is ADDITIONAL chips only.
- **Stack field**: The API `stack` is the ENDING stack, not starting. Starting = `stack - win_bet`.

## Important Conversion Quirks

1. **Straddle handling**: PT4 doesn't support `posts the straddle`. Straddle is emitted as a synthetic preflop raise from UTG.
2. **Preflop "check" in straddle games**: The API sometimes reports a "check" for players who haven't matched the straddle — this is actually a call and must be converted accordingly.
3. **All-in-for-less uncalled bets**: When a player goes all-in for less than the current bet, the difference must be returned as an uncalled bet to the last aggressor.
4. **Uncalled bet calculation**: Uses inline max/second-max computation on per-player `street_invested` values, which are correctly capped at available stack during action processing. This handles all-in-for-less via call correctly.
5. **Hand IDs**: The API uses 19-digit IDs; these are truncated to 12 digits (`id % 1_000_000_000_000`) for PT4 compatibility.

## Running Tests

```bash
uv run pytest test_converter.py -v
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
```

## Output Structure

```
output/
  raw/              # Raw JSON pages from API (page_00001.json, ...)
  pokerstars/       # Converted hand history files (HH_2026-07-17.txt, ...)
```
