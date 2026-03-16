# DorkHunter

Automated dork query URL extraction tool. Load Google dork queries, process them through multiple search engines, and save all extracted URLs in raw format (TXT, JSON, CSV).

## Features

- **Interactive CLI** -- modern terminal UI with colorful menus
- **Two Search Modes**:
  - **API Mode** -- Serper.dev API with key auto-rotation and multi-page support
  - **Free Mode (Proxyless)** -- choose from 5 search engines, no API keys needed
- **5 Search Engines** (Free Mode):
  - DuckDuckGo (most reliable)
  - Bing
  - Yahoo
  - Google (may block scrapers)
  - Ask.com
- **Multi-Page Search** -- fetch multiple result pages per dork for deeper coverage
- **Concurrent Execution** -- configurable thread count for parallel processing
- **Multiple Output Formats** -- TXT, JSON, CSV, or all at once
- **Real-time File Updates** -- URLs are written to disk as they are discovered
- **De-duplication** -- automatic removal of duplicate URLs
- **Junk Filtering** -- filters out search engine domains, social media, etc.
- **API Key Auto-Rotation** -- pool of Serper.dev keys with automatic failover
- **78 Tests** -- comprehensive test coverage (all passing)

## Project Structure

```
dorkhunter/
├── dorkhunter/
│   ├── __init__.py
│   ├── cli.py                 # Interactive menu entry-point
│   ├── config.py              # Central configuration (env-driven)
│   ├── orchestrator.py        # Wires search -> export pipeline
│   ├── search/
│   │   ├── engine.py          # Serper.dev search client (API mode)
│   │   ├── free_engine.py     # Multi-engine free search (DDG/Bing/Yahoo/Google/Ask)
│   │   └── key_manager.py     # API key pool & rotation
│   ├── reporting/
│   │   └── exporter.py        # TXT / JSON / CSV export + RealtimeExporter
│   └── utils/
│       └── logging.py         # Structured logging helper
├── tests/                     # 78 tests (all passing)
│   ├── test_config.py
│   ├── test_key_manager.py
│   ├── test_free_engine.py
│   ├── test_search_engine.py
│   ├── test_orchestrator.py
│   └── test_exporter.py
├── dorks.txt                  # Sample dork queries file
├── pyproject.toml
├── requirements.txt
├── .env.example
└── .gitignore
```

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USER/dorkhunter.git
cd dorkhunter

python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env:
#   - For API mode: add SERPER_API_KEYS=your_key_1,your_key_2
#   - For Free mode: no configuration needed!
```

### 3. Create Your Dorks File

```bash
# Edit dorks.txt (one dork per line)
cat > dorks.txt << 'EOF'
inurl:admin intitle:"login"
intitle:"index of" "parent directory"
site:example.com filetype:pdf
inurl:"/phpmyadmin/"
EOF
```

### 4. Run

```bash
dorkhunter
```

The tool displays an interactive menu:

```
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    ██████╗  ██████╗ ██████╗ ██╗  ██╗
    ██╔══██╗██╔═══██╗██╔══██╗██║ ██╔╝
    ██║  ██║██║   ██║██████╔╝█████╔╝
    ██║  ██║██║   ██║██╔══██╗██╔═██╗
    ██████╔╝╚██████╔╝██║  ██║██║  ██╗
    ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝

    ██╗  ██╗██╗   ██╗███╗   ██╗████████╗███████╗██████╗
    ██║  ██║██║   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗
    ███████║██║   ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝
    ██╔══██║██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗
    ██║  ██║╚██████╔╝██║ ╚████║   ██║   ███████╗██║  ██║
    ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝

    Dork Query URL Extraction Tool  v4.0.0

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    OPERATIONS
    ────────────────────────────────────────────────

    [1]  API Search       Serper.dev API (requires keys)
    [2]  Free Search      Proxyless search (pick engines)
    [3]  Load Dorks       Load dorks from file, then search
    [4]  Settings         View current configuration
    [5]  Help             Usage guide & tips

    [0]  Exit
```

### 5. Operations Explained

| # | Operation | Description |
|---|-----------|-------------|
| 1 | **API Search** | Search via Serper.dev API (fast, requires API keys) |
| 2 | **Free Search** | Proxyless search -- choose engines (DDG, Bing, Yahoo, Google, Ask) |
| 3 | **Load Dorks** | Load dorks file, pick mode and engines, then search |
| 4 | **Settings** | View current configuration and parameters |
| 5 | **Help** | Usage guide and tips |
| 0 | **Exit** | Exit the tool |

### 6. Free Mode -- Engine Selection

When using Free Search (option 2), you are asked which engines to use:

```
  Select Search Engine(s)
  ────────────────────────────────────────────────

    1  DuckDuckGo      Most reliable, no JS needed
    2  Bing            Good results, fast
    3  Yahoo           Decent coverage
    4  Google          Best results but may block scrapers
    5  Ask.com         Extra coverage

    A  All Engines     Use all available engines

  > Enter choices (comma-separated, e.g. 1,2,3 or A for all): 1,2
```

### 7. Dork File Format

One dork query per line. Lines starting with `#` are comments:

```text
# Admin panel dorks
inurl:admin intitle:"login"
inurl:wp-login.php

# Directory listing dorks
intitle:"index of" "parent directory"
intitle:"index of" ".env"

# File type dorks
site:example.com filetype:pdf
filetype:sql "insert into"
```

### 8. View Results

Extracted URLs are saved in the `data/` directory:

- **`data/urls.txt`** -- One URL per line (raw, no formatting)
- **`data/urls.json`** -- JSON format with metadata
- **`data/urls.csv`** -- Numbered CSV format
- **`data/stats.json`** -- Extraction statistics

## Configuration

All settings can be set via environment variables (or a `.env` file).
Runtime parameters entered via the CLI menu **override** env defaults.

| Variable | Default | Description |
|---|---|---|
| `SERPER_API_KEYS` | *(optional)* | Comma-separated Serper.dev API keys |
| `SERPER_PAGES_PER_QUERY` | `1` | Number of result pages per dork |
| `SERPER_RESULTS_PER_QUERY` | `100` | Results per page (Serper max: 100) |
| `SERPER_SEARCH_CONCURRENCY` | `10` | Concurrent API calls |
| `QUERIES_FILE` | `dorks.txt` | Path to dork queries file |
| `SEARCH_TIMEOUT_MS` | `15000` | HTTP timeout in milliseconds |
| `SEARCH_MAX_THREADS` | `10` | Max concurrent threads |
| `FREE_SEARCH_ENGINES` | `duckduckgo,bing` | Engines for free mode |
| `PROXY_URL` | *(none)* | Optional proxy URL |

## Running Tests

```bash
python -m pytest tests/ -v
```

All 78 tests pass covering: config, key manager, free engine (all 5 engines), search engine, orchestrator, and exporter.

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| Search API | Serper.dev (API mode) |
| Free Search | DuckDuckGo, Bing, Yahoo, Google, Ask.com |
| HTTP client | httpx |
| Config | python-dotenv |
| Testing | pytest + pytest-asyncio (78 tests) |

## License

MIT
