# mm2Hunter

Automated search and validation tool for discovering Roblox **Murder Mystery 2** (MM2) item shops. Finds e-commerce sites selling MM2 items, verifies they use **Stripe** as a payment gateway, have an **Add Funds / Wallet** system, and checks that the **Harvester** item is in stock at **$6.00 or less**.

## Features

- **Interactive Menu** -- modern, colorful terminal UI with 8 operations
- **Two Search Modes**:
  - **API Mode** -- Serper.dev API with auto-rotation and multi-page support
  - **Free Mode** -- DuckDuckGo + Bing scraping (no API keys or proxy required!)
- **Validate Raw URLs** -- skip search entirely and validate URLs from a text file
- **Load Custom Queries** -- load search queries from a TXT file (default: `query.txt`)
- **Runtime Parameters** -- configure concurrency and pages-per-query at startup
- **Multi-Page Search** -- fetch multiple result pages per query for more results
- **API Key Auto-Rotation** -- pool of Serper.dev keys with automatic failover on 403/429
- **Pre-Validation URL Export** -- saves all discovered URLs to `discovered_urls.txt` before validation starts
- **Real-time File Updates** -- output files are updated incrementally with throttled flushing
- **Two-Tier Validation**:
  - **Fast Scan** -- aiohttp with 500+ concurrent connections, pre-compiled regex (500+ URLs/sec)
  - **Deep Scan** (optional) -- Playwright headless Chromium with 8-layer Stripe detection
- **Proxy Support** -- route requests through rotating proxies to avoid IP bans
- **Reporting** -- exports results to **JSON** and **CSV**
- **Web Dashboard** -- lightweight aiohttp dashboard with stats, table, and download buttons

## Project Structure

```
mm2Hunter/
├── mm2hunter/
│   ├── __init__.py
│   ├── cli.py                 # Interactive menu entry-point
│   ├── config.py              # Central configuration (env-driven)
│   ├── orchestrator.py        # Wires search -> validate -> report
│   ├── search/
│   │   ├── engine.py          # Serper.dev search client (API mode)
│   │   ├── free_engine.py     # DuckDuckGo/Bing search (Free mode)
│   │   └── key_manager.py     # API key pool & rotation
│   ├── scraper/
│   │   └── validator.py       # Two-tier site validator (fast + deep)
│   ├── reporting/
│   │   ├── exporter.py        # JSON / CSV export + RealtimeExporter
│   │   └── dashboard.py       # Web dashboard (aiohttp)
│   └── utils/
│       └── logging.py         # Structured logging helper
├── tests/                     # 104 tests (all passing)
│   ├── test_config.py
│   ├── test_key_manager.py
│   ├── test_validator.py
│   ├── test_exporter.py
│   ├── test_orchestrator.py
│   ├── test_search_engine.py
│   ├── test_free_engine.py
│   └── test_dashboard.py
├── query.txt                  # Default queries file
├── pyproject.toml
├── requirements.txt
├── .env.example
└── .gitignore
```

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USER/mm2Hunter.git
cd mm2Hunter

python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"

# Install Playwright browsers (only needed for deep scan)
playwright install chromium
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env:
#   - For API mode: add SERPER_API_KEYS=your_key_1,your_key_2
#   - For Free mode: no configuration needed!
```

### 3. Run

```bash
mm2hunter
```

The tool displays an interactive menu:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ██╗  ██╗██╗   ██╗███╗   ██╗████████╗███████╗██████╗
  ██║  ██║██║   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗
  ███████║██║   ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝
  ██╔══██║██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗
  ██║  ██║╚██████╔╝██║ ╚████║   ██║   ███████╗██║  ██║
  ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝

  MM2 Shop Discovery Tool  v3.0.0

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  OPERATIONS
  ──────────────────────────────────────────────────

  1  Search             Run search & validation (API)
  2  Free Search        No API keys needed (DDG/Bing)
  3  Validate URLs      Validate URLs from a file
  4  Dashboard          Start the web dashboard only
  5  Full Pipeline      Search + validate + dashboard
  6  Load Queries       Load queries from file, search
  7  Settings           View current configuration

  0  Exit
```

### 4. Operations Explained

| # | Operation | Description |
|---|-----------|-------------|
| 1 | **Search** | API-based search via Serper.dev (requires API keys) |
| 2 | **Free Search** | Search via DuckDuckGo + Bing -- **no API keys or proxy needed** |
| 3 | **Validate URLs** | Provide a file with URLs (one per line) to validate directly |
| 4 | **Dashboard** | Start the web dashboard to view existing results |
| 5 | **Full Pipeline** | Search + validate + serve dashboard (supports both modes) |
| 6 | **Load Queries** | Load queries from a TXT file, then run search + validate |
| 7 | **Settings** | View current configuration and runtime parameters |
| 0 | **Exit** | Exit the tool |

### 5. Query / URL File Format

**Queries file** (`query.txt`, one query per line, `#` for comments):

```text
# My custom MM2 search queries
"Murder Mystery 2" "Harvester" buy cheap stripe
"MM2" godly shop "add funds" wallet
"Roblox MM2" items store harvester
```

**Raw URLs file** (one URL per line, `#` for comments):

```text
# URLs to validate
https://mm2shop.example.com
https://another-store.example.com/harvester
```

### 6. View Results

- **Dashboard**: open `http://localhost:8080` in your browser
- **Discovered URLs** (pre-validation): `data/discovered_urls.txt`
- **JSON**: `data/results.json`
- **CSV**: `data/results.csv`

## Configuration

All settings are driven by environment variables (or a `.env` file).
Runtime parameters entered via the interactive menu **override** env defaults.

| Variable | Default | Description |
|---|---|---|
| `SERPER_API_KEYS` | *(optional)* | Comma-separated Serper.dev API keys (not needed for Free mode) |
| `SERPER_PAGES_PER_QUERY` | `1` | Number of result pages per query |
| `SERPER_RESULTS_PER_QUERY` | `100` | Results per page |
| `SERPER_SEARCH_CONCURRENCY` | `10` | Concurrent Serper API calls |
| `QUERIES_FILE` | `query.txt` | Path to a TXT file with custom queries |
| `SCRAPER_HEADLESS` | `true` | Run Playwright in headless mode |
| `SCRAPER_TIMEOUT_MS` | `12000` | HTTP timeout in milliseconds |
| `SCRAPER_MAX_CONCURRENCY` | `500` | Max concurrent HTTP connections (fast scan) |
| `SCRAPER_DEEP_SCAN_CONCURRENCY` | `5` | Max concurrent Playwright tabs (deep scan) |
| `ENABLE_DEEP_SCAN` | `true` | Enable/disable Playwright deep scan |
| `PROXY_URL` | *(none)* | Optional rotating proxy URL |
| `DASHBOARD_HOST` | `0.0.0.0` | Dashboard bind address |
| `DASHBOARD_PORT` | `8080` | Dashboard port |

## Validation Criteria

A site **passes** when all of the following are true:

1. Stripe payment gateway detected (deep 8-layer detection)
2. "Add Funds" / Wallet system detected
3. Harvester item found on the site
4. Harvester is currently in stock
5. Harvester price is **<= $6.00**

### Stripe Detection Layers (Deep Scan)

| Layer | Method | What It Checks |
|-------|--------|----------------|
| 1 | HTML string scan | `js.stripe.com`, `pk_live_`, `powered by stripe`, etc. |
| 2 | Network interception | Stripe domains in outgoing requests |
| 3 | Inline `<script>` analysis | `Stripe(`, `loadStripe(`, `confirmCardPayment`, etc. |
| 4 | External script `src` | Script tags loading Stripe URLs |
| 5 | DOM element inspection | `[data-stripe]`, `.StripeElement`, etc. |
| 6 | iframe deep inspection | Stripe URLs in page frames |
| 7 | JavaScript globals | `window.Stripe`, `__stripe_mid`, cookies |
| 8 | CSP meta tags | Whitelisted Stripe domains |

## Running Tests

```bash
python -m pytest tests/ -v
```

All 104 tests pass covering: config, key manager, validator, exporter, orchestrator, search engine, free engine, and dashboard.

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| Search API | Serper.dev (API mode) |
| Free Search | DuckDuckGo + Bing HTML scraping |
| Fast Scan | aiohttp (500+ concurrent connections) |
| Deep Scan | Playwright (async Chromium) |
| HTTP client | httpx |
| Dashboard | aiohttp |
| Config | python-dotenv |
| Testing | pytest + pytest-asyncio (104 tests) |

## License

MIT
