#!/usr/bin/env python3
"""Fetch public reels for one or more Instagram authors via instagram-cli.

Usage:
  fetch_author_reels.py --account-id <user_own_fbid> \
      --usernames name1,name2 [--limit 30] --outdir <dir>

Writes reels.jsonl and reels.csv into outdir. One record per reel:
username, date (user_local), url, post_id, likes, comments, caption.
Stops immediately on a 429 / rate-limit response and reports it.
"""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path


def run_posts(account_id, username, limit, after=None):
    cmd = [
        "instagram-cli", "posts",
        "--account-id", str(account_id),
        "--username", username,
        "--post-types", "REEL",
        "--limit", str(limit),
    ]
    if after:
        cmd += ["--after", after]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    out = proc.stdout or ""
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        low = (out + proc.stderr).lower()
        if "429" in out or "too many requests" in low or "rate limit" in low:
            raise RuntimeError(f"rate limited while fetching {username}")
        raise RuntimeError(f"bad JSON from instagram-cli for {username}: {out[:200]!r} {proc.stderr[:200]!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-id", required=True)
    ap.add_argument("--usernames", required=True, help="comma-separated author usernames")
    ap.add_argument("--limit", type=int, default=30, help="max reels per author")
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    outdir = Path(args.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)

    records = []
    seen = set()
    report = {}
    for username in [u.strip() for u in args.usernames.split(",") if u.strip()]:
        got, cursor, pages = 0, None, 0
        while got < args.limit and pages < 10:
            page = run_posts(args.account_id, username, min(25, args.limit - got), cursor)
            pages += 1
            posts = page.get("posts", [])
            new = 0
            for p in posts:
                pid = p.get("post_id")
                if not pid or pid in seen:
                    continue
                seen.add(pid)
                created = p.get("post_created_at") or {}
                records.append({
                    "username": p.get("username", username),
                    "date": created.get("user_local") or p.get("created_at"),
                    "url": p.get("url"),
                    "post_id": pid,
                    "likes": p.get("likes"),
                    "comments": p.get("comments"),
                    "caption": p.get("post_caption"),
                })
                got += 1
                new += 1
            cursor = page.get("next_cursor")
            if not page.get("has_next_page") or not cursor or new == 0:
                break
        report[username] = got

    jsonl = outdir / "reels.jsonl"
    with jsonl.open("w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    csvp = outdir / "reels.csv"
    with csvp.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["username", "date", "url", "post_id", "likes", "comments", "caption"])
        w.writeheader()
        for r in records:
            w.writerow(r)

    print(json.dumps({"ok": True, "total": len(records), "per_author": report,
                      "jsonl": str(jsonl), "csv": str(csvp)}))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)
