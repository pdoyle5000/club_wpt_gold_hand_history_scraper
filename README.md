# ClubWPT Gold Hand History Scraper

Scrapes NLHE cash game hand analysis data from ClubWPT Gold and converts it to PokerStars hand history format for import into PokerTracker 4 or Holdem Manager 3.

![PokerTracker 4 results from imported ClubWPT hands](clubwptpokertracker.jpeg)

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cd clubwpt-scraper
uv sync
```

## Getting Your Auth Token

The scraper needs a JWT token from the ClubWPT Gold hand analysis site. Here's how to get it:

1. Open **Chrome** (or any Chromium-based browser) and log in to [ClubWPT Gold](https://www.clubwpt.com/).

2. Navigate to the **Hand Analysis** page. It will load the Quintace analysis interface.

3. Open **Developer Tools** (`F12` or `Ctrl+Shift+I` on Linux/Windows, `Cmd+Option+I` on Mac).

4. Go to the **Network** tab.

5. In the filter bar, type `hands` to narrow down the requests.

6. Reload the page or click through the hand history interface so that an API request fires.

7. Find a request to `analysis-b2b.quintace.ai/api/players/hands` in the list and click on it.

8. In the **Headers** panel, scroll down to **Request Headers** and find the `x-a5-authorization` header.

9. Copy the entire value (it starts with `eyJ...`). This is your JWT token.

The token is valid for several months (check the `exp` claim in a JWT decoder if needed).

## Usage

### Full Pipeline (Scrape + Convert)

```bash
uv run python main.py --token "eyJ..."
```

### Scrape Only

Save raw JSON from the API without converting:

```bash
uv run python main.py --token "eyJ..." --scrape-only
```

### Convert Only

Re-convert previously scraped raw JSON (no token needed):

```bash
uv run python main.py --convert-only
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--token` | *(required unless `--convert-only`)* | JWT from `x-a5-authorization` header |
| `--output-dir` | `./output` | Base output directory |
| `--page-size` | `100` | Hands per API page |
| `--start-page` | `1` | First page to scrape |
| `--end-page` | all | Last page to scrape |
| `--max-concurrent` | `10` | Max concurrent API requests |
| `--hero-uid` | `235160` | Your player UID (for "Dealt to" lines) |
| `--scrape-only` | | Only scrape, don't convert |
| `--convert-only` | | Only convert existing raw data |

### Finding Your Player UID

Your UID appears in the raw JSON hand data. After scraping at least one page, search the raw JSON for your screen name:

```bash
grep -r '"name": "YourScreenName"' output/raw/ | head -1
```

The `uid` field next to your name is the value to pass to `--hero-uid`.

## Output

```
output/
  raw/              # Raw JSON pages (page_00001.json ... page_00547.json)
  pokerstars/       # PokerStars format files (HH_2026-07-17.txt, ...)
```

The `pokerstars/` files can be directly imported into PokerTracker 4 or Holdem Manager 3 via their hand history import feature.

## Running Tests

```bash
uv run pytest test_converter.py -v
```
