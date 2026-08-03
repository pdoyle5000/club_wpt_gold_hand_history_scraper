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

Both renderers call `replay_hand(..., post_as_big_blind=True)`. That flag does one thing: it charges a post-to-enter as a big blind instead of its real size, because PT4 misreads a larger post in *either* format (quirk 6). Everything else is the same faithful reconstruction both formats use. Quirk 1 (straddle as a synthetic raise) is a rendering choice in `converter.py`, not a replay difference.

Any change to either renderer should be checked by converting the whole raw corpus with the previous version and diffing, not just by running the unit tests — the tests cover a few dozen hands out of 61,726. For OHH, also re-check the invariant PT4 enforces on import: summing every action `amount`, deducting the uncalled bet (highest street investment minus second-highest, with a post counted only up to the big blind), must equal `pots[0].amount`, which must in turn equal the winners' `win_amount`s plus `rake`.

OHH-specific notes:

- Action `amount` is the chips put in *by that action*, not the street total (per spec: a re-raise to 20 after betting 2 has `amount` 18).
- `pots[0].amount` is the contested pot including rake; `win_amount` is net of rake. The uncalled bet is excluded from the pot but stays in the raising player's action amount — matching the OHH reference examples.
- One pot object is emitted even for multi-way all-ins (the API exposes no side-pot structure), but each winner's `win_amount` is their *exact* take, derived as `win_bet + contributed - returned`. This is right even when a side-pot winner finishes the hand down money, which a proportional split of one pot cannot represent.
- Files are a run of JSON objects separated by one blank line, extension `.ohh`, per the OHH storage format.

## Important Conversion Quirks

1. **Straddle handling**: PT4 doesn't support `posts the straddle` in the PokerStars text format, so it is emitted as a synthetic preflop raise from UTG. OHH has a `Straddle` action and uses it — PT4 reads a straddle as fully live, unlike a post (quirk 6).
2. **Preflop "check" = implicit call**: The API reports preflop limps and straddle calls as "check" with amount=0. Any preflop "check" where the player hasn't matched the current bet is converted to a call (applies to both straddle and non-straddle games).
3. **All-in-for-less uncalled bets**: When a player goes all-in for less than the current bet, the difference must be returned as an uncalled bet to the last aggressor.
4. **Uncalled bet calculation**: Uses inline max/second-max computation on per-player `street_invested` values, which are correctly capped at available stack during action processing. This handles all-in-for-less via call correctly.
5. **Hand IDs**: The API uses 19-digit IDs; these are truncated to 12 digits (`id % 1_000_000_000_000`) for PT4 compatibility.
6. **Post-to-enter (post_seats)**: A post-to-enter matches the current opening bet, so in a straddle game it is the straddle (2x BB), confirmed against `win_bet` for every player in the corpus who posted and then folded. **Both** formats have to understate it as the BB amount: PT4 reads any post above the big blind as part live and part dead, so it disagrees with the replay about how much of the poster's money was matched, and therefore about the size of the uncalled bet and the pot. In the text format that shows up as broken street-investment tracking; in OHH it shows up as `Error: Standardized: Invalid pot size` and the hand is refused outright. Emitting `Post Extra Blind` at the real amount cost 73 rejected hands out of the 9,984 imported for 2026-07-09..31 — every one of them a hand with a post above the big blind.

    The compromise misstates two players' money by (post − BB) in the ~2.5% of hands where somebody posts and never acts again: the poster loses one BB less than they really did, and the winner collects one BB less. Across the whole corpus that moves the hero's net by $1.25 out of $1,638. Every other hand, and every player's money in them, is exact; the documents are internally consistent (money in equals money out) in all 61,726 hands. The alternative — `Post Extra Blind` at the BB plus `Post Dead` for the excess — would keep the nets exact, but PT4's arithmetic on dead money could not be reproduced from the import log in 37 of the hands examined, so it isn't worth the risk of a fresh class of rejections.
7. **Preflop call amounts**: The API under-reports preflop `call` amounts for non-blind players (the reported value is short by `big_blind` chips). This affects both straddle and non-straddle games. The converter computes the correct call amount from its own `current_bet` tracking instead of trusting the API value.
8. **Split pot rounding**: When multiple players split the pot, the converter uses floor division and distributes remainder chips to earliest seat(s), ensuring collected amounts always sum to exactly the pot total.
9. **Board-plays-itself splits**: When all showdown players have `win_bet=0` (exact split where the board plays itself), they are treated as winners splitting the pot equally.
10. **Undeclared posts**: `post_seats` is incomplete — in ~2% of hands a late-position player is charged a post that is never listed. Because the data is rake-free and zero-sum, a player who doesn't win contributed exactly `-win_bet`, so a shortfall of exactly one post against what the replay charged them gives it away. `_infer_undeclared_posts` recovers those and replays the hand once more with them in place. Only an exact-post shortfall is treated this way; anything else is left alone. The post is *recognised* at its true size but *charged* at `post_amount`, so a recovered post still lands as a big blind in both formats (quirk 6).
11. **Antes when two players are dealt in**: antes are always paid, including heads-up. The ante is not the small blind — they differ at most stakes (e.g. 50 ante at 100/200).
12. **Small blind with two players dealt in**: the API gives the small blind the position `BTN` and no seat has `SB`. This happens on any table size, not just 2-max tables, so the fallback keys off the missing `SB` position rather than `max_players`.

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
