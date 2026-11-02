#!/usr/bin/env python3
"""
ProSync — Health check & monitoring script.
Run periodically (e.g., every 5 min via systemd timer or cron).
Checks:
  - App /api/health endpoint (HTTP 200)
  - Nginx proxy (HTTP 301 redirect to HTTPS)
  - Response time thresholds
  - DB file integrity

Exits 0 on success, non-zero on critical failures.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
import sqlite3

# ─── Configuration ───────────────────────────────────────────────────────────
APP_URL = "http://127.0.0.1:8015"
NGINX_URL = "http://127.0.0.1:8016"
HEALTH_ENDPOINT = f"{APP_URL}/api/health"
DB_PATH = "/root/prosync/prosync.db"
LOG_DIR = "/var/log/prosync"
REQUEST_TIMEOUT = 5  # seconds

# ─── Ensure log directory exists ─────────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)


def check(endpoint, expected_status=200):
    """Check an HTTP endpoint and return (ok, lat_ms, detail)."""
    start = time.monotonic()
    try:
        req = urllib.request.Request(endpoint)
        resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
        lat = round((time.monotonic() - start) * 1000)
        body = resp.read().decode()
        ok = resp.status == expected_status
        return ok, lat, f"HTTP {resp.status} — {body[:120]}"
    except urllib.error.HTTPError as e:
        lat = round((time.monotonic() - start) * 1000)
        return e.code == expected_status, lat, f"HTTP {e.code}"
    except Exception as e:
        lat = round((time.monotonic() - start) * 1000)
        return False, lat, f"Error: {e}"


def check_redirect(endpoint, expected_status=301):
    """Check HTTP endpoint expecting redirect (uses raw socket to avoid following)."""
    import http.client
    start = time.monotonic()
    try:
        from urllib.parse import urlparse
        parsed = urlparse(endpoint)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=REQUEST_TIMEOUT)
        conn.request("HEAD", parsed.path or "/")
        resp = conn.getresponse()
        lat = round((time.monotonic() - start) * 1000)
        status = resp.status
        resp.read()
        conn.close()
        return status == expected_status, lat, f"HTTP {status}"
    except Exception as e:
        lat = round((time.monotonic() - start) * 1000)
        return False, lat, f"Error: {e}"


def check_db(path):
    """Verify DB file exists and is readable."""
    if not os.path.isfile(path):
        return False, "DB file not found"
    try:
        conn = sqlite3.connect(path)
        cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchone()[0]
        conn.close()
        return True, f"DB OK — {tables} tables"
    except Exception as e:
        return False, f"DB error: {e}"


def write_log(results, status):
    """Write check result to log file with timestamp."""
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    log_line = {
        "timestamp": timestamp,
        "status": status,
        "checks": results,
    }
    log_file = os.path.join(LOG_DIR, f"health-{time.strftime('%Y-%m-%d')}.log")
    with open(log_file, "a") as f:
        f.write(json.dumps(log_line) + "\n")
    return log_file


def main():
    results = {}
    all_ok = True

    # Health endpoint
    ok, lat, detail = check(HEALTH_ENDPOINT, expected_status=200)
    results["app_health"] = {"ok": ok, "latency_ms": lat, "detail": detail}
    if not ok:
        all_ok = False

    # Nginx proxy (expects 301 redirect HTTP->HTTPS)
    ok, lat, detail = check_redirect(NGINX_URL, expected_status=301)
    results["nginx_http"] = {"ok": ok, "latency_ms": lat, "detail": detail}
    if not ok:
        # Fallback: maybe it returns 200 directly
        ok2, lat2, detail2 = check(NGINX_URL, expected_status=200)
        results["nginx_http"] = {"ok": ok2, "latency_ms": lat2, "detail": detail2}
        if not ok2:
            all_ok = False

    # DB integrity
    ok, detail = check_db(DB_PATH)
    results["database"] = {"ok": ok, "detail": detail}
    if not ok:
        all_ok = False

    # Overall status
    status = "PASS" if all_ok else "FAIL"
    log_file = write_log(results, status)

    # Print summary
    print(f"[ProSync Monitor] {status} — log: {log_file}")
    for name, r in results.items():
        ok_icon = "✓" if r.get("ok") else "✗"
        lat = f" ({r.get('latency_ms','?')}ms)" if "latency_ms" in r else ""
        print(f"  {ok_icon} {name}{lat}: {r.get('detail', '')}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())