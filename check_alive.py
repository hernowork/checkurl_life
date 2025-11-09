#!/usr/bin/env python3
import requests
import sys
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def check_url(url):
    try:
        r = requests.head(url, timeout=5, allow_redirects=True)
        return url, r.status_code
    except requests.RequestException:
        return url, None

def main():
    parser = argparse.ArgumentParser(
        description="Check if URLs from a file are alive and save the results."
    )
    parser.add_argument("-i", "--input", required=True, help="Input file containing list of URLs")
    parser.add_argument("-o", "--output", required=True, help="Output file to save alive URLs")
    parser.add_argument("-t", "--threads", type=int, default=20, help="Number of concurrent threads (default: 20)")
    args = parser.parse_args()

    # Read URLs
    try:
        with open(args.input, "r") as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"{RED}[!] Input file '{args.input}' not found.{RESET}")
        sys.exit(1)

    alive = []
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {executor.submit(check_url, url): url for url in urls}
        for future in as_completed(futures):
            url, status = future.result()
            if status and status < 400:
                print(f"{GREEN}[UP]{RESET}   {url} {YELLOW}({status}){RESET}")
                alive.append(url)
            else:
                print(f"{RED}[DOWN]{RESET} {url}")

    # Save alive URLs
    with open(args.output, "w") as out:
        out.write("\n".join(alive))

    print(f"\n{GREEN}[+] Done. {len(alive)} alive URLs saved to {args.output}{RESET}")

if __name__ == "__main__":
    main()
