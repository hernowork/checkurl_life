# checkurl_life

Check if URLs from the Wayback Machine (or a file) are currently alive. Results are saved to a single file sorted alive-first, with backup files flagged.

## Install

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Fetch from Wayback Machine and check
python3 check_alive.py -d example.com

# Use an existing URL list
python3 check_alive.py -i urls.txt

# Only keep 2xx responses, 50 threads
python3 check_alive.py -d example.com --filter-status 2xx -t 50

# Don't follow redirects
python3 check_alive.py -d example.com --no-redirects

# Append results instead of overwriting
python3 check_alive.py -d example.com --append
```

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `-d, --domain` | — | Target domain (pulls URLs from Wayback Machine) |
| `-i, --input` | — | Input file with one URL per line |
| `-t, --threads` | 20 | Number of concurrent threads |
| `--timeout` | 5 | Request timeout in seconds |
| `--no-redirects` | off | Disable redirect following |
| `--filter-status` | off | Keep only matching status codes (`200`, `2xx`, `3xx`) |
| `--append` | off | Append to output instead of overwriting |

## Output

Results are saved to `<domain>.txt` (e.g. `example_com.txt`):

```
# ── ALIVE ──────────────────────────────────────────
https://example.com/page (200)
https://example.com/backup.zip (200) [BACKUP]

# ── DEAD / ERROR ────────────────────────────────────
https://example.com/old (404)
https://example.com/gone (Timeout)
```
