"""
CLI entry-point for DorkHunter.

Interactive menu interface for loading dork queries, running search
across multiple engines, and saving extracted URLs.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

from dorkhunter import __version__
from dorkhunter.config import get_config
from dorkhunter.search.free_engine import AVAILABLE_ENGINES
from dorkhunter.utils.logging import setup_logging

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BLUE = "\033[94m"
WHITE = "\033[97m"
RESET = "\033[0m"
BG_DARK = "\033[48;5;235m"

LINE = f"{CYAN}{'━' * 62}{RESET}"
LINE_THIN = f"{DIM}{'─' * 52}{RESET}"
LINE_DOT = f"{DIM}{'·' * 52}{RESET}"


def _clear_screen() -> None:
    """Clear terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{CYAN}{default}{YELLOW}]" if default else ""
    try:
        value = input(f"  {YELLOW}> {prompt}{suffix}: {RESET}").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return value or default


def _ask_int(prompt: str, default: int) -> int:
    while True:
        raw = _ask(prompt, str(default))
        try:
            val = int(raw)
            if val < 1:
                raise ValueError
            return val
        except ValueError:
            print(f"  {RED}  [!] Please enter a positive integer.{RESET}")


def _ask_yes_no(prompt: str, default: bool = True) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = _ask(prompt, hint)
    if raw in ("Y/n", "y/N"):
        return default
    return raw.lower() in ("y", "yes", "si", "s", "1", "true")


def _ask_file(prompt: str, default: str = "") -> str:
    while True:
        raw = _ask(prompt, default)
        if not raw:
            print(f"  {RED}  [!] Please provide a file path.{RESET}")
            continue
        p = Path(raw).expanduser().resolve()
        if p.is_file():
            return str(p)
        print(f"  {RED}  [!] File not found: {p}{RESET}")


def _ask_engines() -> list[str]:
    """Ask user to select search engines for free/proxyless mode."""
    print()
    print(f"  {CYAN}{BOLD}  Select Search Engine(s){RESET}")
    print(f"  {LINE_THIN}")
    print()

    engine_display = {
        "duckduckgo": ("DuckDuckGo", "Most reliable, no JS needed"),
        "bing": ("Bing", "Good results, fast"),
        "yahoo": ("Yahoo", "Decent coverage"),
        "google": ("Google", "Best results but may block scrapers"),
        "ask": ("Ask.com", "Extra coverage"),
    }

    for i, eng in enumerate(AVAILABLE_ENGINES, 1):
        name, desc = engine_display.get(eng, (eng, ""))
        print(f"  {GREEN}{BOLD}  {i} {RESET} {WHITE}{name:<15}{RESET} {DIM}{desc}{RESET}")

    print()
    print(f"  {GREEN}{BOLD}  A {RESET} {WHITE}All Engines{RESET}     {DIM}Use all available engines{RESET}")
    print()

    raw = _ask("Enter choices (comma-separated, e.g. 1,2,3 or A for all)", "1,2")

    if raw.lower().strip() == "a":
        selected = list(AVAILABLE_ENGINES)
        print(f"  {GREEN}  [+] Selected: All engines{RESET}")
        return selected

    selected = []
    for part in raw.split(","):
        part = part.strip()
        try:
            idx = int(part) - 1
            if 0 <= idx < len(AVAILABLE_ENGINES):
                selected.append(AVAILABLE_ENGINES[idx])
        except ValueError:
            # Maybe they typed the engine name directly
            if part.lower() in AVAILABLE_ENGINES:
                selected.append(part.lower())

    if not selected:
        print(f"  {YELLOW}  [*] No valid selection, defaulting to DuckDuckGo + Bing{RESET}")
        selected = ["duckduckgo", "bing"]

    names = [engine_display.get(e, (e, ""))[0] for e in selected]
    print(f"  {GREEN}  [+] Selected: {', '.join(names)}{RESET}")
    return selected


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

def _show_banner() -> None:
    _clear_screen()
    print()
    print(f"  {LINE}")
    print()
    print(f"  {BOLD}{CYAN}  ██████╗  ██████╗ ██████╗ ██╗  ██╗{RESET}")
    print(f"  {BOLD}{CYAN}  ██╔══██╗██╔═══██╗██╔══██╗██║ ██╔╝{RESET}")
    print(f"  {BOLD}{CYAN}  ██║  ██║██║   ██║██████╔╝█████╔╝ {RESET}")
    print(f"  {BOLD}{CYAN}  ██║  ██║██║   ██║██╔══██╗██╔═██╗ {RESET}")
    print(f"  {BOLD}{CYAN}  ██████╔╝╚██████╔╝██║  ██║██║  ██╗{RESET}")
    print(f"  {BOLD}{CYAN}  ╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝{RESET}")
    print()
    print(f"  {BOLD}{MAGENTA}  ██╗  ██╗██╗   ██╗███╗   ██╗████████╗███████╗██████╗{RESET}")
    print(f"  {BOLD}{MAGENTA}  ██║  ██║██║   ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗{RESET}")
    print(f"  {BOLD}{MAGENTA}  ███████║██║   ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝{RESET}")
    print(f"  {BOLD}{MAGENTA}  ██╔══██║██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗{RESET}")
    print(f"  {BOLD}{MAGENTA}  ██║  ██║╚██████╔╝██║ ╚████║   ██║   ███████╗██║  ██║{RESET}")
    print(f"  {BOLD}{MAGENTA}  ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝{RESET}")
    print()
    print(f"  {BOLD}{WHITE}  Dork Query URL Extraction Tool{RESET}  {DIM}v{__version__}{RESET}")
    print(f"  {DIM}  Load dorks, search engines, extract raw URLs{RESET}")
    print()
    print(f"  {LINE}")
    print()


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

def _show_menu() -> str:
    _show_banner()

    print(f"  {BOLD}{WHITE}  OPERATIONS{RESET}")
    print(f"  {LINE_THIN}")
    print()

    menu_items = [
        ("1", "API Search", "Serper.dev API (requires keys)"),
        ("2", "Free Search", "Proxyless search (pick engines)"),
        ("3", "Load Dorks", "Load dorks from file, then search"),
        ("4", "Settings", "View current configuration"),
        ("5", "Help", "Usage guide & tips"),
    ]
    for num, label, desc in menu_items:
        print(
            f"  {GREEN}{BOLD}  [{num}] {RESET}"
            f"{WHITE}{label:<16}{RESET} {DIM}{desc}{RESET}"
        )

    print()
    print(f"  {RED}{BOLD}  [0] {RESET} {DIM}Exit{RESET}")
    print()

    valid = {"0", "1", "2", "3", "4", "5"}
    while True:
        choice = _ask("Select an operation")
        if choice in valid:
            return choice
        print(f"  {RED}  [!] Invalid choice. Enter 0-5.{RESET}")


# ---------------------------------------------------------------------------
# Runtime parameters
# ---------------------------------------------------------------------------

def _ask_runtime_params(
    mode: str = "api",
    show_engines: bool = False,
) -> dict:
    print()
    print(f"  {CYAN}{BOLD}  Runtime Parameters{RESET}")
    print(f"  {LINE_THIN}")
    print()

    params: dict = {}

    if show_engines:
        params["engines"] = _ask_engines()
        print()

    params["pages_per_dork"] = _ask_int("Pages per dork query", default=1)
    params["threads"] = _ask_int("Max concurrent threads", default=10)

    if mode == "api":
        params["search_concurrency"] = _ask_int("API concurrency", default=10)

    # Output format
    print()
    print(f"  {CYAN}  Output Format:{RESET}")
    print(f"    {GREEN}1{RESET} TXT only   {GREEN}2{RESET} JSON only   "
          f"{GREEN}3{RESET} CSV only   {GREEN}4{RESET} All formats")
    fmt_choice = _ask("Select output format", "4")
    fmt_map = {"1": "txt", "2": "json", "3": "csv", "4": "all"}
    params["output_format"] = fmt_map.get(fmt_choice, "all")

    print()
    return params


def _apply_params(cfg, params: dict) -> None:
    """Apply user-supplied runtime parameters to the config."""
    cfg.search.pages_per_dork = params.get("pages_per_dork", 1)
    cfg.search.max_threads = params.get("threads", 10)
    cfg.output_format = params.get("output_format", "all")

    if "search_concurrency" in params:
        cfg.serper.search_concurrency = params["search_concurrency"]
    if "engines" in params:
        cfg.search.free_engines = params["engines"]

    cfg.serper.pages_per_query = params.get("pages_per_dork", 1)


# ---------------------------------------------------------------------------
# Settings display
# ---------------------------------------------------------------------------

def _show_settings(cfg) -> None:
    print()
    print(f"  {CYAN}{BOLD}  Current Configuration{RESET}")
    print(f"  {LINE_THIN}")
    print()

    keys_count = len(cfg.serper.api_keys)
    keys_str = (
        f"{GREEN}{keys_count} key(s) configured{RESET}"
        if keys_count > 0
        else f"{RED}NONE (use Free Search){RESET}"
    )

    qf = cfg.serper.queries_file
    if qf and Path(qf).is_file():
        qf_str = f"{GREEN}{qf}{RESET}"
    elif qf:
        qf_str = f"{YELLOW}{qf} (not found){RESET}"
    else:
        qf_str = f"{DIM}None{RESET}"

    settings = [
        ("API Keys", keys_str),
        ("Pages per Dork", str(cfg.serper.pages_per_query)),
        ("Max Threads", str(cfg.search.max_threads)),
        ("API Concurrency", str(cfg.serper.search_concurrency)),
        ("Search Timeout (ms)", str(cfg.search.timeout_ms)),
        ("Free Engines", ", ".join(cfg.search.free_engines)),
        ("Proxy", cfg.search.proxy_url or f"{DIM}None{RESET}"),
        ("Data Directory", str(cfg.data_dir)),
        ("Dorks File", qf_str),
    ]

    for label, value in settings:
        print(f"    {WHITE}{label:<22}{RESET} {value}")

    print()
    input(f"  {DIM}  Press Enter to return...{RESET}")


# ---------------------------------------------------------------------------
# Help screen
# ---------------------------------------------------------------------------

def _show_help() -> None:
    print()
    print(f"  {CYAN}{BOLD}  DorkHunter - Usage Guide{RESET}")
    print(f"  {LINE_THIN}")
    print()
    print(f"  {WHITE}{BOLD}  What is DorkHunter?{RESET}")
    print(f"  {DIM}  A tool for processing Google dork queries through multiple")
    print(f"  search engines and extracting the discovered URLs.{RESET}")
    print()
    print(f"  {WHITE}{BOLD}  Dork File Format:{RESET}")
    print(f"  {DIM}  One dork query per line. Lines starting with # are comments.")
    print(f'  Example: inurl:admin intitle:"login page"')
    print(f'           site:example.com filetype:pdf')
    print(f'           "index of" "parent directory"{RESET}')
    print()
    print(f"  {WHITE}{BOLD}  Search Modes:{RESET}")
    print(f"  {GREEN}  API Mode{RESET}{DIM}     Uses Serper.dev API (fast, reliable, needs keys)")
    print(f"  {GREEN}  Free Mode{RESET}{DIM}    Scrapes search engines directly (no keys needed)")
    print(f"               Engines: DuckDuckGo, Bing, Yahoo, Google, Ask.com{RESET}")
    print()
    print(f"  {WHITE}{BOLD}  Output:{RESET}")
    print(f"  {DIM}  Extracted URLs are saved in data/ directory:")
    print(f"    urls.txt  - One URL per line (raw)")
    print(f"    urls.json - JSON format with metadata")
    print(f"    urls.csv  - Numbered CSV format{RESET}")
    print()
    print(f"  {WHITE}{BOLD}  Tips:{RESET}")
    print(f"  {DIM}  - Use more pages per dork for deeper results")
    print(f"  - DuckDuckGo + Bing are the most reliable free engines")
    print(f"  - Google may block after a few requests (use with caution)")
    print(f"  - Add delays between runs to avoid IP bans{RESET}")
    print()
    input(f"  {DIM}  Press Enter to return...{RESET}")


# ---------------------------------------------------------------------------
# Operation runners
# ---------------------------------------------------------------------------

def _run_search_api(cfg) -> None:
    """Option 1 -- API-based search."""
    if not cfg.serper.api_keys:
        print()
        print(f"  {RED}{BOLD}  [!] No API keys configured!{RESET}")
        print(f"  {DIM}    Set SERPER_API_KEYS in .env or use Free Search (option 2).{RESET}")
        print()
        input(f"  {DIM}  Press Enter to return...{RESET}")
        return

    cfg.search_mode = "api"

    # Ask for dorks file
    print()
    qf = cfg.serper.queries_file or "dorks.txt"
    dork_file = _ask_file("Path to dorks file", default=qf)

    from dorkhunter.orchestrator import load_dorks_from_file
    dorks = load_dorks_from_file(dork_file)
    if not dorks:
        print(f"  {RED}  [!] No dorks found in file.{RESET}")
        return
    print(f"  {GREEN}  [+] Loaded {len(dorks)} dork queries{RESET}")

    params = _ask_runtime_params(mode="api", show_engines=False)
    _apply_params(cfg, params)

    _run_pipeline(cfg, dorks)


def _run_search_free(cfg) -> None:
    """Option 2 -- Free/proxyless search."""
    print()
    print(f"  {MAGENTA}{BOLD}  Free Search Mode (Proxyless){RESET}")
    print(f"  {DIM}  Search engines directly -- no API keys needed.{RESET}")
    print()

    cfg.search_mode = "free"

    # Ask for dorks file
    qf = cfg.serper.queries_file or "dorks.txt"
    dork_file = _ask_file("Path to dorks file", default=qf)

    from dorkhunter.orchestrator import load_dorks_from_file
    dorks = load_dorks_from_file(dork_file)
    if not dorks:
        print(f"  {RED}  [!] No dorks found in file.{RESET}")
        return
    print(f"  {GREEN}  [+] Loaded {len(dorks)} dork queries{RESET}")

    params = _ask_runtime_params(mode="free", show_engines=True)
    _apply_params(cfg, params)

    _run_pipeline(cfg, dorks)


def _run_load_dorks(cfg) -> None:
    """Option 3 -- Load dorks from file, choose mode, then search."""
    print()
    qf = cfg.serper.queries_file or "dorks.txt"
    dork_file = _ask_file("Path to dorks file", default=qf)

    from dorkhunter.orchestrator import load_dorks_from_file
    dorks = load_dorks_from_file(dork_file)
    if not dorks:
        print(f"  {RED}  [!] No dorks found in file.{RESET}")
        return

    print(f"  {GREEN}  [+] Loaded {len(dorks)} dork queries{RESET}")
    print()

    # Preview first few dorks
    print(f"  {CYAN}  Preview:{RESET}")
    for i, d in enumerate(dorks[:5], 1):
        print(f"  {DIM}    {i}. {d[:70]}{RESET}")
    if len(dorks) > 5:
        print(f"  {DIM}    ... and {len(dorks) - 5} more{RESET}")
    print()

    # Choose mode
    if cfg.serper.api_keys:
        print(f"  {WHITE}  Search mode:{RESET}")
        print(f"    {GREEN}1{RESET} API (Serper.dev)   {GREEN}2{RESET} Free (proxyless)")
        mode_choice = _ask("Select mode", "2")
        cfg.search_mode = "free" if mode_choice == "2" else "api"
    else:
        print(f"  {YELLOW}  [*] No API keys -- using Free Search mode.{RESET}")
        cfg.search_mode = "free"

    show_engines = cfg.search_mode == "free"
    params = _ask_runtime_params(mode=cfg.search_mode, show_engines=show_engines)
    _apply_params(cfg, params)

    _run_pipeline(cfg, dorks)


def _run_pipeline(cfg, dorks: list[str]) -> None:
    """Execute the search pipeline and display results summary."""
    print()
    print(f"  {CYAN}{BOLD}  Starting Search...{RESET}")
    print(f"  {LINE_THIN}")
    print()

    from dorkhunter.orchestrator import run_pipeline
    urls = asyncio.run(run_pipeline(cfg, custom_dorks=dorks))

    # Results summary
    print()
    print(f"  {LINE}")
    print()
    print(f"  {BOLD}{WHITE}  RESULTS SUMMARY{RESET}")
    print(f"  {LINE_THIN}")
    print()
    print(f"    {WHITE}Dorks Processed:{RESET}  {GREEN}{len(dorks)}{RESET}")
    print(f"    {WHITE}URLs Extracted:{RESET}   {GREEN}{BOLD}{len(urls)}{RESET}")
    print(f"    {WHITE}Search Mode:{RESET}      {cfg.search_mode.upper()}")

    if cfg.search_mode == "free":
        engines_str = ", ".join(cfg.search.free_engines)
        print(f"    {WHITE}Engines Used:{RESET}     {engines_str}")

    print(f"    {WHITE}Output Dir:{RESET}       {cfg.data_dir}")
    print()

    if urls:
        # Show output files
        print(f"  {GREEN}{BOLD}  Output Files:{RESET}")
        for fname in ["urls.txt", "urls.json", "urls.csv", "stats.json"]:
            fpath = cfg.data_dir / fname
            if fpath.exists():
                size = fpath.stat().st_size
                if size > 1024:
                    size_str = f"{size / 1024:.1f} KB"
                else:
                    size_str = f"{size} B"
                print(f"    {GREEN}[+]{RESET} {fname:<15} {DIM}({size_str}){RESET}")
        print()

        # Preview first few URLs
        print(f"  {CYAN}  Preview (first 10 URLs):{RESET}")
        for i, url in enumerate(urls[:10], 1):
            print(f"  {DIM}    {i:>3}. {url[:80]}{RESET}")
        if len(urls) > 10:
            print(f"  {DIM}    ... and {len(urls) - 10} more{RESET}")
    else:
        print(f"  {YELLOW}  [*] No URLs were extracted. Try different dorks or engines.{RESET}")

    print()


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
            "3": _run_load_dorks,
            "4": lambda c: _show_settings(c),
            "5": lambda c: _show_help(),
        }

        try:
            dispatch[choice](cfg)
        except KeyboardInterrupt:
            print(f"\n  {YELLOW}  [*] Interrupted by user.{RESET}")
            continue
        except Exception as exc:
            print(f"\n  {RED}{BOLD}  Error: {exc}{RESET}")
            import traceback
            traceback.print_exc()
            continue

        if choice not in ("4", "5", "0"):
            print()
            input(f"  {DIM}  Press Enter to return to the menu...{RESET}")


if __name__ == "__main__":
    main()
