Scrape ClubWPT Gold hand histories and convert to PokerStars format.

Run the scrape + convert pipeline using the provided auth token. If no token is provided, run in convert-only mode to re-convert existing raw JSON data.

Steps:
1. If a token argument is provided, run: `uv run python main.py --token "$ARGUMENTS" --update --output-dir ~/ssd/clubwpt_hands`
   - This does an incremental scrape (fetches hands not already on disk, stopping after 3 consecutive pages with nothing new) then converts all hands.
   - If the update reports that hands on the server are still missing locally, re-run with no scrape flag at all to sweep the full history.
   - To write Open Hand History JSON instead (models antes and straddles natively), add `--format ohh`; `--format both` writes both.
2. If no token argument is provided, run: `uv run python main.py --convert-only --output-dir ~/ssd/clubwpt_hands`
3. After conversion completes, create a zip of the output: `cd ~/ssd/clubwpt_hands && zip -j ClubWPT_HandHistory.zip pokerstars/HH_*.txt`
   - For OHH output, zip `ohh/HH_*.ohh` instead.
4. Report the total number of hands converted and the zip file location.

Working directory: ~/clubwpt-scraper
