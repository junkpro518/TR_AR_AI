#!/usr/bin/env python3
"""
Load YouTube channel videos into a NotebookLM notebook.

Commands:
  scrape  --channel URL [--output FILE]         Fetch video URLs via yt-dlp
  load    --notebook ID [--input FILE]           Add videos to NotebookLM via nlm
          [--count N] [--concurrency N]
"""
import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


# ─── Scrape ───────────────────────────────────────────────────────────────────

def scrape(channel_url: str, output: str | None) -> list[dict]:
    """Use yt-dlp to list all videos in a channel (no download)."""
    print(f"Fetching video list from: {channel_url}")
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(id)s\t%(title)s",
        "--no-warnings",
        channel_url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"yt-dlp error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)

    videos = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2:
            vid_id, title = parts
            videos.append({"id": vid_id, "title": title, "url": f"https://www.youtube.com/watch?v={vid_id}"})

    print(f"Found {len(videos)} videos.")

    dest = output or "videos.json"
    Path(dest).write_text(json.dumps(videos, ensure_ascii=False, indent=2))
    print(f"Saved to: {dest}")
    return videos


# ─── Load ─────────────────────────────────────────────────────────────────────

def _add_video(nlm_path: str, notebook_id: str, video: dict) -> tuple[bool, str]:
    """Add a single YouTube video to NotebookLM. Returns (success, title)."""
    cmd = [nlm_path, "source", "add", notebook_id, "--youtube", video["url"]]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.returncode == 0, video["title"]


def load(notebook_id: str, input_file: str, count: int, concurrency: int, nlm_path: str) -> None:
    videos: list[dict] = json.loads(Path(input_file).read_text())
    videos = videos[:count]
    print(f"Loading {len(videos)} videos into notebook {notebook_id} (concurrency={concurrency})…")

    ok = fail = 0
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(_add_video, nlm_path, notebook_id, v): v for v in videos}
        for fut in as_completed(futures):
            success, title = fut.result()
            if success:
                ok += 1
                print(f"  ✓ {title}")
            else:
                fail += 1
                print(f"  ✗ {title}", file=sys.stderr)

    print(f"\nDone: {ok} loaded, {fail} failed.")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Load YouTube channel into NotebookLM")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scrape = sub.add_parser("scrape", help="Fetch video list from a YouTube channel")
    p_scrape.add_argument("--channel", required=True, help="YouTube channel URL")
    p_scrape.add_argument("--output", default="videos.json", help="Output JSON file (default: videos.json)")

    p_load = sub.add_parser("load", help="Add videos to NotebookLM")
    p_load.add_argument("--notebook", required=True, help="NotebookLM notebook ID")
    p_load.add_argument("--input", default="videos.json", help="Input JSON file (default: videos.json)")
    p_load.add_argument("--count", type=int, default=50, help="Max videos to load (default: 50)")
    p_load.add_argument("--concurrency", type=int, default=5, help="Parallel uploads (default: 5)")
    p_load.add_argument("--nlm", default="nlm", help="Path to nlm binary (default: nlm)")

    args = parser.parse_args()

    if args.cmd == "scrape":
        scrape(args.channel, args.output)
    elif args.cmd == "load":
        load(args.notebook, args.input, args.count, args.concurrency, args.nlm)


if __name__ == "__main__":
    main()
