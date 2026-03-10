#!/usr/bin/env python3
import requests
import sys
import argparse
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from tqdm import tqdm
import pyfiglet

VERSION = "2.0"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

BACKUP_EXTENSIONS = (
    ".zip", ".bak", ".sql", ".tar.gz", ".tar", ".gz", ".old", ".backup",
    ".bkp", ".db", ".sqlite", ".sqlite3", ".7z", ".rar", ".log", ".conf",
    ".config", ".env", ".swp", ".orig", ".tmp", ".dump", ".dmp",
)


def print_banner():
    banner = pyfiglet.figlet_format("checkurl-life", font="slant").rstrip()
    print(f"{CYAN}{BOLD}{banner}{RESET}")
    print(f"  {BOLD}v{VERSION}{RESET}  |  Wayback Machine URL Alive Checker  |  {DIM}by hernowork{RESET}")
    print(f"  {DIM}{'─' * 60}{RESET}\n")


def section(title: str):
    print(f"\n{BOLD}{CYAN}━━━━ {title} {'━' * (50 - len(title))}{RESET}")


def domain_slug(domain: str) -> str:
    host = urlparse(domain if "://" in domain else "https://" + domain).hostname or domain
    return host.replace(".", "_")


CDX_ENDPOINTS = [
    "https://web.archive.org/cdx/search/cdx",
    "http://web.archive.org/cdx/search/cdx",
]


SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
SPINNER_INTERVAL = 0.08  # seconds between display updates


def fetch_wayback_urls(domain: str) -> list[str]:
    import time
    params = {
        "url": f"{domain}/*",
        "output": "text",
        "fl": "original",
        "collapse": "urlkey",
        "matchType": "host",
        "limit": "200000",
    }
    last_err = None
    for endpoint in CDX_ENDPOINTS:
        try:
            resp = requests.get(endpoint, params=params, timeout=60, stream=True)
            resp.raise_for_status()
            urls = []
            seen = set()
            spin_i = 0
            last_update = time.monotonic()
            for line in resp.iter_lines():
                if line:
                    url = line.decode("utf-8", errors="ignore").strip()
                    if url and url not in seen:
                        seen.add(url)
                        urls.append(url)
                now = time.monotonic()
                if now - last_update >= SPINNER_INTERVAL:
                    spin = SPINNER[spin_i % len(SPINNER)]
                    spin_i += 1
                    print(f"\r  {CYAN}{spin}{RESET} Fetching ... {GREEN}{len(urls)}{RESET} URLs found", end="", flush=True)
                    last_update = now
            print(f"\r  {GREEN}[+]{RESET} Fetching ... {GREEN}{len(urls)}{RESET} URLs found")
            return urls
        except Exception as e:
            print()
            last_err = e
            print(f"  {YELLOW}[!] {endpoint} failed: {type(e).__name__} — trying next ...{RESET}")
    raise ConnectionError(f"All CDX endpoints failed. Last error: {last_err}")


def check_url(url: str, timeout: int, follow_redirects: bool):
    backup = any(urlparse(url).path.lower().endswith(ext) for ext in BACKUP_EXTENSIONS)
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=follow_redirects)
        if r.status_code in (405, 501):
            r = requests.get(url, timeout=timeout, allow_redirects=follow_redirects, stream=True)
        return url, r.status_code, None, backup
    except requests.exceptions.Timeout:
        return url, None, "Timeout", backup
    except requests.exceptions.SSLError:
        return url, None, "SSL Error", backup
    except requests.exceptions.ConnectionError:
        return url, None, "Connection Error", backup
    except requests.RequestException as e:
        return url, None, type(e).__name__, backup


def status_matches(status: int, filt: str) -> bool:
    f = filt.lower()
    if "x" in f:
        return str(status).startswith(f[0])
    return str(status) == f


def main():
    parser = argparse.ArgumentParser(
        description="Check if URLs (from Wayback Machine or a file) are alive.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 check_alive.py -d example.com\n"
            "  python3 check_alive.py -i urls.txt\n"
            "  python3 check_alive.py -d example.com --filter-status 2xx\n"
            "  python3 check_alive.py -d example.com --no-redirects -t 50\n"
        ),
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("-d", "--domain", help="Target domain — fetch URLs via Wayback Machine")
    src.add_argument("-i", "--input",  help="Input file with one URL per line")

    parser.add_argument("-t", "--threads",     type=int, default=20, help="Concurrent threads (default: 20)")
    parser.add_argument("--timeout",           type=int, default=5,  help="Request timeout in seconds (default: 5)")
    parser.add_argument("--no-redirects",      action="store_true",  help="Do not follow redirects")
    parser.add_argument("--filter-status",     metavar="CODE",       help="Only keep URLs matching status, e.g. 200, 2xx, 3xx")
    parser.add_argument("--append",            action="store_true",  help="Append to output file instead of overwriting")

    args = parser.parse_args()
    follow_redirects = not args.no_redirects

    print_banner()

    # ── FETCH ─────────────────────────────────────────────────────────────────
    section("FETCH")
    if args.domain:
        slug = domain_slug(args.domain)
        print(f"  {BOLD}Target   :{RESET} {args.domain}")
        print(f"  {BOLD}Mode     :{RESET} Wayback Machine CDX")
        print(f"  {BOLD}Threads  :{RESET} {args.threads}  |  Timeout: {args.timeout}s  |  Redirects: {'on' if follow_redirects else 'off'}")
        print()
        try:
            urls = fetch_wayback_urls(args.domain)
        except Exception as e:
            print(f"\n  {RED}[!] Wayback Machine fetch failed: {e}{RESET}")
            sys.exit(1)
    else:
        slug = os.path.splitext(os.path.basename(args.input))[0]
        print(f"  {BOLD}Input    :{RESET} {args.input}")
        print(f"  {BOLD}Mode     :{RESET} File")
        print(f"  {BOLD}Threads  :{RESET} {args.threads}  |  Timeout: {args.timeout}s  |  Redirects: {'on' if follow_redirects else 'off'}")
        print()
        try:
            with open(args.input) as f:
                urls = [l.strip() for l in f if l.strip()]
        except FileNotFoundError:
            print(f"  {RED}[!] File not found: {args.input}{RESET}")
            sys.exit(1)

    if not urls:
        print(f"  {YELLOW}[!] No URLs found. Exiting.{RESET}")
        sys.exit(0)

    output_file = f"{slug}.txt"

    # ── CHECKING ──────────────────────────────────────────────────────────────
    section("CHECKING")
    print()

    alive, dead = [], []

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {
            executor.submit(check_url, url, args.timeout, follow_redirects): url
            for url in urls
        }
        with tqdm(total=len(urls), desc="  Progress", unit="url", ncols=70) as bar:
            for future in as_completed(futures):
                url, status, reason, is_backup = future.result()

                if status is not None:
                    if args.filter_status and not status_matches(status, args.filter_status):
                        bar.update(1)
                        continue
                    if status < 400:
                        alive.append((url, status, is_backup))
                        if is_backup:
                            tqdm.write(f"  {YELLOW}[BACKUP]{RESET} {url} {YELLOW}({status}){RESET}")
                    else:
                        dead.append((url, status, None, is_backup))
                else:
                    dead.append((url, None, reason, is_backup))

                bar.update(1)

    # ── write output ──────────────────────────────────────────────────────────
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    alive_backups = sum(1 for _, _, b in alive if b)
    mode = "a" if args.append else "w"

    with open(output_file, mode) as out:
        out.write(f"# checkurl_life v{VERSION} | {args.domain or args.input} | {now}\n")
        out.write(f"# Alive: {len(alive)} | Dead: {len(dead)} | Backups found: {alive_backups}\n")
        out.write(f"# {'═' * 58}\n\n")

        if alive:
            out.write(f"[ALIVE — {len(alive)}]\n")
            for url, status, is_backup in alive:
                backup_tag = " [BACKUP]" if is_backup else ""
                out.write(f"[UP]{backup_tag} {url} ({status})\n")

        if dead:
            out.write(f"\n[DEAD — {len(dead)}]\n")
            for url, status, reason, is_backup in dead:
                backup_tag = " [BACKUP]" if is_backup else ""
                if status:
                    out.write(f"[DOWN]{backup_tag} {url} ({status})\n")
                else:
                    out.write(f"[ERR]{backup_tag} {url} ({reason})\n")

    # ── SUMMARY ───────────────────────────────────────────────────────────────
    section("SUMMARY")
    print(f"  {GREEN}[+] Alive        → {len(alive)}{RESET}")
    print(f"  {RED}[-] Dead         → {len(dead)}{RESET}")
    if alive_backups:
        print(f"  {YELLOW}[!] Alive Backups → {alive_backups}{RESET}")
    print(f"  {CYAN}[>] Saved        → {output_file}{RESET}")
    print(f"\n  {DIM}{'─' * 60}{RESET}\n")


if __name__ == "__main__":
    main()
