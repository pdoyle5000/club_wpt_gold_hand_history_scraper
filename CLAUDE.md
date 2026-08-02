# ClubWPT Gold Hand History Scraper

## Project Overview

This project scrapes NLHE cash game hand analysis data from the ClubWPT Gold Quintace API and converts it to PokerStars hand history text or Open Hand History (OHH) JSON, both compatible with PokerTracker 4 and Holdem Manager 3.

## Architecture

- `scraper.py` — Async httpx client that fetches paginated hand data from `https://analysis-b2b.quintace.ai/api/players/hands`
- `hand_replay.py` — Reconstructs a hand from the raw API JSON: starting stacks, forced bets, resolved per-action chip amounts, uncalled bet, rake and winners. All the API quirks below are handled here once, so the two renderers can't drift apart.
- `converter.py` — Renders a replayed hand as PokerStars `.txt`
- `ohh_converter.py` — Renders a replayed hand as [Open Hand History](https://hh-specs.handhistory.org) JSON
- `main.py` — CLI entry point with `--scrape-only`, `--convert-only`, `--format`, and full pipeline modes
- `test_converter.py` — pytest suite covering PokerStars conversion logic and known edge cases
- `test_ohh_converter.py` — pytest suite covering the OHH document, action amounts and pot reconciliation
- `test_scraper.py` / `test_main.py` — scraper page-freshness helpers and CLI routing

## Key API Details

- **Endpoint**: `GET https://analysis-b2b.quintace.ai/api/players/hands?game=nlhe&page={N}&pageSize={SIZE}`
- **Auth**: JWT token in `x-a5-authorization` header
- **Amount semantics**: For `raise`/`bet`/`allin`, `amount` is the player's TOTAL for the street. For `call`, `amount` is ADDITIONAL chips only — but see quirk #7 below.
- **Stack field**: The API `stack` is the ENDING stack, not starting. Starting = `stack - win_bet`.
- **Preflop "check" = limp**: The API reports preflop limps (and straddle calls) as `action: "check"` with `amount: 0`.

## Output Formats

`--format pokerstars` (default) and `--format ohh` render the *same* `hand_replay.HandReplay`, so any change to hand reconstruction must be made in `hand_replay.py`, not in a renderer.

The PokerStars renderer calls `replay_hand(..., pokerstars_compat=True)`. That flag turns on the forced-bet compromises the text format needs — quirks 1, 6, 11 and 12 below — because PT4's text parser rejects or misreads the faithful version. The OHH renderer uses the default (faithful) model. **The PokerStars output is byte-for-byte unchanged by the OHH work and should stay that way**; it is verified against the full raw corpus, not just the unit tests.

OHH-specific notes:

- Action `amount` is the chips put in *by that action*, not the street total (per spec: a re-raise to 20 after betting 2 has `amount` 18).
- `pots[0].amount` is the contested pot including rake; `win_amount` is net of rake. The uncalled bet is excluded from the pot but stays in the raising player's action amount — matching the OHH reference examples.
- One pot object is emitted even for multi-way all-ins (the API exposes no side-pot structure), but each winner's `win_amount` is their *exact* take, derived as `win_bet + contributed - returned`. This is right even when a side-pot winner finishes the hand down money, which a proportional split of one pot cannot represent.
- Files are a run of JSON objects separated by one blank line, extension `.ohh`, per the OHH storage format.

## Important Conversion Quirks

1. **Straddle handling**: PT4 doesn't support `posts the straddle` in the PokerStars text format, so it is emitted as a synthetic preflop raise from UTG. OHH has a `Straddle` action and uses it.
2. **Preflop "check" = implicit call**: The API reports preflop limps and straddle calls as "check" with amount=0. Any preflop "check" where the player hasn't matched the current bet is converted to a call (applies to both straddle and non-straddle games).
3. **All-in-for-less uncalled bets**: When a player goes all-in for less than the current bet, the difference must be returned as an uncalled bet to the last aggressor.
4. **Uncalled bet calculation**: Uses inline max/second-max computation on per-player `street_invested` values, which are correctly capped at available stack during action processing. This handles all-in-for-less via call correctly.
5. **Hand IDs**: The API uses 19-digit IDs; these are truncated to 12 digits (`id % 1_000_000_000_000`) for PT4 compatibility.
6. **Post-to-enter (post_seats)**: A post-to-enter matches the current opening bet, so in a straddle game it is the straddle (2x BB), confirmed against `win_bet` for every player in the corpus who posted and then folded. The PokerStars renderer has to understate it as the BB amount, because PT4 reads `posts big blind $X` where X > BB as having a dead component, which breaks street investment tracking. OHH posts the real amount as `Post Extra Blind`.
7. **Preflop call amounts**: The API under-reports preflop `call` amounts for non-blind players (the reported value is short by `big_blind` chips). This affects both straddle and non-straddle games. The converter computes the correct call amount from its own `current_bet` tracking instead of trusting the API value.
8. **Split pot rounding**: When multiple players split the pot, the converter uses floor division and distributes remainder chips to earliest seat(s), ensuring collected amounts always sum to exactly the pot total.
9. **Board-plays-itself splits**: When all showdown players have `win_bet=0` (exact split where the board plays itself), they are treated as winners splitting the pot equally.
10. **Undeclared posts**: `post_seats` is incomplete — in ~2% of hands a late-position player is charged a post that is never listed. Because the data is rake-free and zero-sum, a player who doesn't win contributed exactly `-win_bet`, so a shortfall of exactly one post against what the replay charged them gives it away. `_infer_undeclared_posts` recovers those and replays the hand once more with them in place. Only an exact-post shortfall is treated this way; anything else is left alone. Faithful model only (OHH).
11. **Antes when two players are dealt in**: antes are always paid, including heads-up. The legacy PokerStars model assumes `ante == SB` heads-up and charges no ante, which is wrong whenever they differ (e.g. 50 ante at 100/200). Faithful model charges them.
12. **Small blind with two players dealt in**: the API gives the small blind the position `BTN` and no seat has `SB`. This happens on any table size, not just 2-max tables; the legacy PokerStars model only recognises it at 2-max and otherwise drops the small blind entirely. Faithful model: the button posts it.

    Quirks 11 and 12 were found by checking every hand's forced bets against the API's own `hand_history[0].pot_size`, which equals `ante * players + SB + BB + straddle` for all 61,726 hands in the corpus. That figure excludes posts (declared or not).
13. **Rake**: The analysis API returns rake-free, zero-sum data (`sum(net) == 0` across players), so rake is computed and re-applied from the [published ClubWPT Gold rake structure](https://support.clubwptgold.com/portal/en/kb/articles/rake) in `hand_replay.compute_rake()`. Rake is a percentage of the contested (post-uncalled-bet) pot, capped by stake and by the number of players dealt in (2P / 3–4P / 5P+ tiers). The `Total pot` line reports the gross pot; winners collect the pot net of rake. Two conventions not stated on the rake page are applied: **no flop, no rake** (hands ending preflop are unraked) and **round-half-up to the nearest cent**. Stakes absent from the table are unraked. `RAKE_TABLE` is keyed by `(small_blind, big_blind)` in chips (cents).

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

# Write Open Hand History JSON instead of PokerStars text (or 'both')
uv run python main.py --token "YOUR_JWT_TOKEN" --format ohh

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
  pokerstars/       # PokerStars text files (HH_2026-07-17.txt, ...)
  ohh/              # Open Hand History files (HH_2026-07-17.ohh, ...)
```
