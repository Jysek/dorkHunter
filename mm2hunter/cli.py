"""
CLI entry-point for MM2 Shop Discovery Tool.

Interactive menu interface -- the user selects an operation and configures
runtime parameters (threads, concurrency, pages) via keyboard input.

Features a modern, colorful terminal UI with clear sections and
support for both API and free (no-key) search modes.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from mm2hunter import __version__
from mm2hunter.config import get_config
from mm2hunter.utils.logging import setup_logging

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
WHITE = "\033[97m"
RESET = "\033[0m"
BG_DARK = "\033[48;5;235m"

LINE = f"{DIM}{'━' * 60}{RESET}"
LINE_THIN = f"{DIM}{'─' * 50}{RESET}"


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def _ask(prompt: str, default: str = "") -> str:
    """Prompt the user; return stripped input or *default*."""
    suffix = f" [{CYAN}{default}{YELLOW}]" if default else ""
    try:
        value = input(f"  {YELLOW}▸ {prompt}{suffix}: {RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return value or default


def _ask_int(prompt: str, default: int) -> int:
    """Prompt for an integer, re-ask on bad input."""
    while True:
        raw = _ask(prompt, str(default))
        try:
            val = int(raw)
            if val < 1:
                raise ValueError
            return val
        except ValueError:
            print(f"  {RED}  ✗ Please enter a positive integer.{RESET}")


def _ask_yes_no(prompt: str, default: bool = True) -> bool:
    """Prompt for a yes/no answer."""
    hint = "Y/n" if default else "y/N"
    raw = _ask(prompt, hint)
    if raw in ("Y/n", "y/N"):
        return default
    return raw.lower() in ("y", "yes", "si", "s", "1", "true")


def _ask_file(prompt: str, default: str = "") -> str:
    """Prompt for a file path, re-ask until a valid file is given."""
    while True:
        raw = _ask(prompt, default)
        if not raw:
            print(f"  {RED}  ✗ Please provide a file path.{RESET}")
            continue
        p = Path(raw).expanduser().resolve()
        if p.is_file():
            return str(p)
        print(f"  {RED}  ✗ File not found: {p}{RESET}")


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

def _show_banner() -> None:
    """Print the application banner."""
    print()
    print(LINE)
    print()
    print(f"  {BOLD}{CYAN}  ██╗  ██╗██╗   ██╗███╗   ██╗████████╗███████╗██████╗{RESET}")
    print(f"  {BOLD}{CYAN}  ██║  ██║██║   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗{RESET}")
    print(f"  {BOLD}{CYAN}  ███████║██║   ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝{RESET}")
    print(f"  {BOLD}{CYAN}  ██╔══██║██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗{RESET}")
    print(f"  {BOLD}{CYAN}  ██║  ██║╚██████╔╝██║ ╚████║   ██║   ███████╗██║  ██║{RESET}")
    print(f"  {BOLD}{CYAN}  ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝{RESET}")
    print()
    print(f"  {BOLD}{WHITE}  MM2 Shop Discovery Tool{RESET}  {DIM}v{__version__}{RESET}")
    print(f"  {DIM}  High-performance MM2 shop finder & validator{RESET}")
    print()
    print(LINE)
    print()


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

def _show_menu() -> str:
    """Display the operation menu and return the user's choice."""
    _show_banner()

    print(f"  {BOLD}{WHITE}OPERATIONS{RESET}")
    print(f"  {LINE_THIN}")
    print()
    menu_items = [
        ("1", "Search", "Run search & validation (API)"),
        ("2", "Free Search", "No API keys needed (DDG/Bing)"),
        ("3", "Validate URLs", "Validate URLs from a file"),
        ("4", "Dashboard", "Start the web dashboard only"),
        ("5", "Full Pipeline", "Search + validate + dashboard"),
        ("6", "Load Queries", "Load queries from file, search"),
        ("7", "Settings", "View current configuration"),
    ]
    for num, label, desc in menu_items:
        print(
            f"  {GREEN}{BOLD}  {num} {RESET} "
            f"{WHITE}{label:<18}{RESET} {DIM}{desc}{RESET}"
        )
    print()
    print(f"  {RED}{BOLD}  0 {RESET} {DIM}Exit{RESET}")
    print()

    valid = {"0", "1", "2", "3", "4", "5", "6", "7"}
    while True:
        choice = _ask("Select an operation (0-7)")
        if choice in valid:
            return choice
        print(f"  {RED}  ✗ Invalid choice. Enter a number between 0 and 7.{RESET}")


# ---------------------------------------------------------------------------
# Runtime parameters
# ---------------------------------------------------------------------------

def _ask_runtime_params(show_search: bool = True, show_deep: bool = True) -> dict:
    """Ask the user for concurrency and pages-per-query."""
    print()
    print(f"  {CYAN}{BOLD}  Runtime Parameters{RESET}")
    print(f"  {LINE_THIN}")
    print()

    concurrency = _ask_int("Max concurrent connections (fast scan)", default=500)

    pages = 1
    search_conc = 10
    if show_search:
        pages = _ask_int("Pages per query (search results)", default=1)
        search_conc = _ask_int("Search API concurrency", default=10)

    deep_scan = False
    deep_concurrency = 5
    if show_deep:
        deep_scan = _ask_yes_no("Enable deep scan (Playwright)?", default=False)
        if deep_scan:
            deep_concurrency = _ask_int("Deep scan concurrency (browser tabs)", default=5)

    print()
    return {
        "concurrency": concurrency,
        "pages": pages,
        "search_concurrency": search_conc,
        "deep_scan": deep_scan,
        "deep_concurrency": deep_concurrency,
    }


def _apply_params(cfg, params: dict) -> None:
    """Apply user-supplied runtime parameters to the config object."""
    cfg.scraper.max_concurrency = params["concurrency"]
    cfg.serper.pages_per_query = params["pages"]
    cfg.serper.search_concurrency = params["search_concurrency"]
    cfg.scraper.enable_deep_scan = params["deep_scan"]
    cfg.scraper.deep_scan_concurrency = params["deep_concurrency"]


# ---------------------------------------------------------------------------
# Settings display
# ---------------------------------------------------------------------------

def _show_settings(cfg) -> None:
    """Display current configuration."""
    print()
    print(f"  {CYAN}{BOLD}  Current Configuration{RESET}")
    print(f"  {LINE_THIN}")
    print()

    keys_count = len(cfg.serper.api_keys)
    keys_str = (
        f"{GREEN}{keys_count} key(s) configured{RESET}"
        if keys_count > 0
        else f"{RED}NONE{RESET}"
    )

    qf = cfg.serper.queries_file
    if qf and Path(qf).is_file():
        qf_str = f"{GREEN}{qf}{RESET}"
    elif qf:
        qf_str = f"{YELLOW}{qf} (not found){RESET}"
    else:
        qf_str = f"{DIM}Built-in defaults{RESET}"

    settings = [
        ("API Keys", keys_str),
        ("Search Mode", cfg.search_mode),
        ("Pages per Query", str(cfg.serper.pages_per_query)),
        ("Fast Scan Concurrency", str(cfg.scraper.max_concurrency)),
        ("Search API Concurrency", str(cfg.serper.search_concurrency)),
        (
            "Deep Scan Enabled",
            f"{GREEN}Yes{RESET}"
            if cfg.scraper.enable_deep_scan
            else f"{RED}No{RESET}",
        ),
        ("Deep Scan Concurrency", str(cfg.scraper.deep_scan_concurrency)),
        ("HTTP Timeout (ms)", str(cfg.scraper.timeout_ms)),
        ("Proxy", cfg.scraper.proxy_url or f"{DIM}None{RESET}"),
        ("Dashboard", f"http://{cfg.dashboard.host}:{cfg.dashboard.port}"),
        ("Data Directory", str(cfg.data_dir)),
        ("Queries File", qf_str),
    ]

    for label, value in settings:
        print(f"    {WHITE}{label:<25}{RESET} {value}")

    print()
    input(f"  {DIM}  Press Enter to return to the menu...{RESET}")


# ---------------------------------------------------------------------------
# Operation runners
# ---------------------------------------------------------------------------

def _run_search_api(cfg) -> None:
    """Option 1 -- API-based search & validate."""
    if not cfg.serper.api_keys:
        print()
        print(f"  {RED}{BOLD}  ✗ No API keys configured!{RESET}")
        print(f"  {DIM}    Set SERPER_API_KEYS in .env or use Free Search (option 2).{RESET}")
        print()
        input(f"  {DIM}  Press Enter to return to the menu...{RESET}")
        return

    cfg.search_mode = "api"
    params = _ask_runtime_params(show_search=True, show_deep=True)
    _apply_params(cfg, params)

    from mm2hunter.orchestrator import run_pipeline
    asyncio.run(run_pipeline(cfg))


def _run_search_free(cfg) -> None:
    """Option 2 -- Free search (no API keys needed)."""
    print()
    print(f"  {MAGENTA}{BOLD}  Free Search Mode{RESET}")
    print(f"  {DIM}  Uses DuckDuckGo & Bing -- no API keys or proxy required.{RESET}")
    print(f"  {DIM}  Slower but completely free.{RESET}")
    print()

    cfg.search_mode = "free"

    # Ask if they want to load custom queries
    use_custom = _ask_yes_no("Load custom queries from file?", default=False)
    custom_queries = None
    if use_custom:
        qf = cfg.serper.queries_file or "query.txt"
        query_file = _ask_file("Path to queries file", default=qf)
        from mm2hunter.orchestrator import _load_queries_from_file
        custom_queries = _load_queries_from_file(query_file)
        if not custom_queries:
            print(f"  {YELLOW}  No queries loaded, using defaults.{RESET}")
            custom_queries = None

    params = _ask_runtime_params(show_search=False, show_deep=True)
    _apply_params(cfg, params)

    from mm2hunter.orchestrator import run_pipeline
    asyncio.run(run_pipeline(cfg, custom_queries=custom_queries))


def _run_validate_raw(cfg) -> None:
    """Option 3 -- validate raw URLs from a file."""
    print()
    url_file = _ask_file("Path to file with URLs (one per line)")
    params = _ask_runtime_params(show_search=False, show_deep=True)
    _apply_params(cfg, params)

    from mm2hunter.orchestrator import run_validate_raw
    asyncio.run(run_validate_raw(cfg, url_file))


def _run_dashboard(cfg) -> None:
    """Option 4 -- dashboard only."""
    from mm2hunter.orchestrator import run_dashboard
    asyncio.run(run_dashboard(cfg))


def _run_full(cfg) -> None:
    """Option 5 -- search + dashboard."""
    if not cfg.serper.api_keys:
        print()
        use_free = _ask_yes_no(
            "No API keys found. Use Free Search mode?", default=True,
        )
        if use_free:
            cfg.search_mode = "free"
        else:
            print(f"  {RED}  ✗ Cannot proceed without API keys.{RESET}")
            return
    else:
        mode = _ask("Search mode: (a)pi or (f)ree?", "a")
        cfg.search_mode = "free" if mode.lower().startswith("f") else "api"

    params = _ask_runtime_params(
        show_search=(cfg.search_mode == "api"),
        show_deep=True,
    )
    _apply_params(cfg, params)

    from mm2hunter.orchestrator import run_full
    asyncio.run(run_full(cfg))


def _run_load_queries(cfg) -> None:
    """Option 6 -- load queries from file, then search."""
    print()
    qf_default = cfg.serper.queries_file or "query.txt"
    query_file = _ask_file("Path to queries file", default=qf_default)

    from mm2hunter.orchestrator import _load_queries_from_file
    queries = _load_queries_from_file(query_file)
    if not queries:
        print(f"  {RED}  ✗ No queries found in file.{RESET}")
        return

    print(f"  {GREEN}  ✓ Loaded {len(queries)} queries{RESET}")

    # Choose search mode
    if cfg.serper.api_keys:
        mode = _ask("Search mode: (a)pi or (f)ree?", "a")
        cfg.search_mode = "free" if mode.lower().startswith("f") else "api"
    else:
        print(f"  {YELLOW}  No API keys found -- using Free Search.{RESET}")
        cfg.search_mode = "free"

    if cfg.search_mode == "api":
        cfg.serper.queries_file = query_file

    params = _ask_runtime_params(
        show_search=(cfg.search_mode == "api"),
        show_deep=True,
    )
    _apply_params(cfg, params)

    from mm2hunter.orchestrator import run_pipeline
    asyncio.run(run_pipeline(
        cfg,
        custom_queries=queries if cfg.search_mode == "free" else None,
    ))


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

def main() -> None:
    setup_logging()
    cfg = get_config()

    while True:
        choice = _show_menu()

        if choice == "0":
            print()
            print(f"  {CYAN}  Goodbye!{RESET}")
            print()
            sys.exit(0)

        dispatch = {
            "1": _run_search_api,
            "2": _run_search_free,
            "3": _run_validate_raw,
            "4": _run_dashboard,
            "5": _run_full,
            "6": _run_load_queries,
            "7": lambda c: _show_settings(c),
        }

        try:
            dispatch[choice](cfg)
        except KeyboardInterrupt:
            print(f"\n  {YELLOW}  Interrupted by user.{RESET}")
            continue
        except Exception as exc:
            print(f"\n  {RED}{BOLD}  Error: {exc}{RESET}")
            import traceback
            traceback.print_exc()
            continue

        # After operation, pause before returning to menu
        if choice not in ("7", "0"):
            print()
            input(f"  {DIM}  Press Enter to return to the menu...{RESET}")


if __name__ == "__main__":
    main()
