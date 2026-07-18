Scrape ClubWPT Gold hand histories and convert to PokerStars format.

Run the full scrape + convert pipeline using the provided auth token. If no token is provided, run in convert-only mode to re-convert existing raw JSON data.

Steps:
1. If a token argument is provided, run: `uv run python main.py --token "$ARGUMENTS" --output-dir ~/ssd/clubwpt_hands`
2. If no token argument is provided, run: `uv run python main.py --convert-only --output-dir ~/ssd/clubwpt_hands`
3. After conversion completes, create a zip of the output: `cd ~/ssd/clubwpt_hands && zip -j ClubWPT_HandHistory.zip pokerstars/HH_*.txt`
4. Report the total number of hands converted and the zip file location.

Working directory: ~/clubwpt-scraper
