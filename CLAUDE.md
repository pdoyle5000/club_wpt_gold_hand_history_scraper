# ClubWPT Gold Hand History Scraper

## Project Overview

This project scrapes NLHE cash game hand analysis data from the ClubWPT Gold Quintace API and converts it to PokerStars hand history text or Open Hand History (OHH) JSON, both compatible with PokerTracker 4 and Holdem Manager 3.

## Architecture

- `scraper.py` — Async httpx client that fetches paginated hand data from `https://analysis-b2b.quintace.ai/api/players/hands`, plus the merge-only raw hand store (`merge_raw_hands`, `load_raw_hands_by_id`)
- `hand_replay.py` — Reconstructs a hand from the raw API JSON: starting stacks, forced bets, resolved per-action chip amounts, uncalled bet, rake and winners. All the API quirks below are handled here once, so the two renderers can't drift apart.
- `converter.py` — Renders a replayed hand as PokerStars `.txt`
- `ohh_converter.py` — Renders a replayed hand as [Open Hand History](https://hh-specs.handhistory.org) JSON
- `main.py` — CLI entry point with `--scrape-only`, `--convert-only`, `--format`, and full pipeline modes
- `test_converter.py` — pytest suite covering PokerStars conversion logic and known edge cases
- `test_ohh_converter.py` — pytest suite covering the OHH document, action amounts and pot reconciliation
- `test_scraper.py` / `test_main.py` — raw store merge semantics, both scrape strategies (including regression tests for the page-index data loss), and CLI routing

## Key API Details

- **Endpoint**: `GET https://analysis-b2b.quintace.ai/api/players/hands?game=nlhe&page={N}&pageSize={SIZE}`
- **Auth**: JWT token in `x-a5-authorization` header
- **Amount semantics**: For `raise`/`bet`/`allin`, `amount` is the player's TOTAL for the street. For `call`, `amount` is ADDITIONAL chips only — but see quirk #7 below.
- **Stack field**: The API `stack` is the ENDING stack, not starting. Starting = `stack - win_bet`.
- **Preflop "check" = limp**: The API reports preflop limps (and straddle calls) as `action: "check"` with `amount: 0`.

## Output Formats

`--format pokerstars` (default) and `--format ohh` render the *same* `hand_replay.HandReplay`, so any change to hand reconstruction must be made in `hand_replay.py`, not in a renderer.

Both renderers call `replay_hand(..., post_as_big_blind=True)`. That flag does one thing: it charges a post-to-enter as a big blind instead of its real size, because PT4 misreads a larger post in *either* format (quirk 6). Everything else is the same faithful reconstruction both formats use. Quirk 1 (straddle as a synthetic raise) is a rendering choice in `converter.py`, not a replay difference.

Any change to either renderer should be checked by converting the whole raw corpus with the previous version and diffing, not just by running the unit tests — the tests cover a few dozen hands out of 70,408. (Figures quoted below as "out of 61,726" were measured on the corpus as it stood before the 2026-08-20 storage fix recovered the missing 12%; they have not been re-measured.) For OHH, also re-check the invariant PT4 enforces on import: summing every action `amount`, deducting the uncalled bet (highest street investment minus second-highest, with a post counted only up to the big blind), must equal `pots[0].amount`, which must in turn equal the winners' `win_amount`s plus `rake`.

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

## Raw Storage and Scrape Strategies

**Never key raw storage or caching on page index.** The API returns hands newest-first, so page N holds different hands every time anybody plays a hand. Treating `page_00042.json` as "the contents of page 42" loses hands, and did: it cost 8,682 hands (12% of the corpus), including every hand after 2026-08-08 and whole days *inside* the scraped range. Two independent bugs, both now removed:

1. `scrape_all` trusted the on-disk page cache for every page but page 1. Between runs, new hands shift the corpus toward later pages, so everything newer than the cached snapshot except the newest 100 hands was never fetched. The corpus showed this as page 1 ending at 2026-08-08 21:23 and page 2 starting at 2026-08-01 16:28 — a 7-day hole. `--refresh-recent` only narrowed the window (it keyed off a fixed 3-day window rather than the newest hand on disk), so any gap longer than 3 days between runs still lost hands.
2. `scrape_update` called `_save_raw_page` for pages 1..N, overwriting those files with fresh content and destroying the older hands stored under those indexes. That is what punched holes inside the already-scraped range. `_save_raw_page` now raises rather than silently corrupting the store.

Current design:

- **Storage** — `raw/hands_YYYY-MM-DD.json`, partitioned by the hand's UTC date and keyed by hand ID. `merge_raw_hands` is the only writer, and it merges: no run can remove or replace a stored hand, so an interrupted or partial run can only add data. Writes are atomic (`.tmp` + `os.replace`). Legacy `page_*.json` files are still read by `load_raw_hands_by_id`, which is how the 2 hands the server has since dropped are retained.
- **Full scrape** (default, no flag) — sweeps every page, no cache. ~705 pages / ~2-35 min depending on how hard the API is throttling. Failed pages are retried individually rather than left as holes, and the run warns if the captured count falls short of the server's reported total. Because a hand played mid-sweep shifts hands toward pages already fetched, the sweep is followed by a drift check: an incremental walk from page 1 until `UPDATE_CONFIRM_PAGES` consecutive pages contain nothing new.
- **`--update`** — walks forward from page 1 and stops after `UPDATE_CONFIRM_PAGES` (3) consecutive pages with no new hands. It requires several confirming pages rather than stopping on the first known hand, because the server has small holes in its own history. It reports when hands on the server are still absent locally and tells you to run a full scrape.
- `--overwrite` and `--refresh-recent` are accepted as no-ops (the full scrape subsumes both) so existing scripts keep working.

## API Surface (verified 2026-08-20)

The API has *not* changed in any way that hides hands. The UI's new session view added endpoints and fields but did not narrow `/api/players/hands`.

- `GET /api/players/hands?game=nlhe&page=N&pageSize=100` — unchanged. `pageSize` is capped at 100: a larger value returns an empty body, not an error, so `MAX_PAGE_SIZE` clamps it.
- **The unfiltered response is the complete history, analyzed or not.** The UI's filters send `filter=<field>:eq:<n>`: `analysis_mode:eq:0` (not analyzed) = 51,800 hands, `:eq:1` (analyzed) = 15,347, `:eq:2` (advanced) = 3,261 — summing to exactly the 70,408 the unfiltered call reports. The scraper deliberately sends no `filter`. Other known filter fields: `saved_hands:eq:1`, `table_type:eq:4` (compete), `table_type:eq:5` (imported).
- `GET /api/players/sessions?game=nlhe&page=N&pageSize=100` — new, backs the session-first UI. One row per session with `stats.total_hands_played`. Useful as an independent check on coverage.
- `GET /api/players/stats` — reports `total_hands`, handy for a sanity check, but it disagrees slightly with `/hands` (71,228 vs 70,408); don't treat it as authoritative.
- New fields on each hand: `table.session_id` (`{table_id}|0|{player_id}|{YYYYMMDD}`, and `""` for 2,932 older hands with no session) and `analysis`. New top-level `jobs` key.
- `nlhe` is the only game type with any hands (`plo4`, `mtt`, `squid` all return 0).
- **The server itself has gaps and duplicates.** The sessions view claims 71,226 hands vs the 70,408 `/hands` returns; 82 sessions (2,987 hands) return no hands at all, all in 2026-03/04. `/hands` also serves 2 hand IDs twice across pages. Nothing after 2026-06 is affected — for July and August every hand the sessions view knows about is retrievable — so this is upstream data loss, not a scraper bug, and not worth chasing.

When investigating a suspected scrape gap, the reliable check is an ID-level diff: sweep the API into a scratch directory, then compare that ID set against `load_raw_hands_by_id(raw_dir)`. Per-date counts are misleading unless both sides use UTC.

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

# Fast incremental top-up (stops after 3 consecutive pages with nothing new)
uv run python main.py --token "YOUR_JWT_TOKEN" --update
```

## Output Structure

```
output/
  raw/              # Raw hands, one merge-only file per UTC date (hands_2026-08-20.json, ...)
                    # plus legacy page_*.json from older versions, still read
  pokerstars/       # PokerStars text files (HH_2026-07-17.txt, ...)
  ohh/              # Open Hand History files (HH_2026-07-17.ohh, ...)
```
