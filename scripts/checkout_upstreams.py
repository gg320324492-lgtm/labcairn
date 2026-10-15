#!/usr/bin/env python3
"""Optional developer-only upstream reference checkout (does not execute upstream code)."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_VERSION = 1
CATALOG = {
    "pydantic-ai": ("https://github.com/pydantic/pydantic-ai.git", "MIT", "essential"),
    "openhands-sdk": ("https://github.com/OpenHands/software-agent-sdk.git", "MIT", "essential"),
    "deepagents": ("https://github.com/langchain-ai/deepagents.git", "MIT", "essential"),
    "paper-qa": ("https://github.com/Future-House/paper-qa.git", "Apache-2.0", "essential"),
    "paperspine": ("https://github.com/WUBING2023/PaperSpine.git", "MIT", "essential"),
    "opencode": ("https://github.com/anomalyco/opencode.git", "MIT", "targeted"),
    "gpt-researcher": ("https://github.com/assafelovic/gpt-researcher.git", "Apache-2.0", "optional"),
    "storm": ("https://github.com/stanford-oval/storm.git", "MIT", "optional"),
    "ai-scientist-v2": ("https://github.com/SakanaAI/AI-Scientist-v2.git", "custom; inspect LICENSE", "research-only"),
}


def cmd(*args: str) -> str:
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_snapshot(out: Path) -> dict:
    """Return the previous manifest so a narrow run never erases earlier records.

    Study clones arrive in batches (``--group essential``, then ``--repo opencode``).
    Starting from the file on disk keeps the recorded SHAs of every earlier batch.
    An unreadable or foreign-versioned snapshot is never silently replaced: the user
    moves it aside deliberately instead of losing pinned commits.
    """
    if not out.exists():
        return {"manifest_version": MANIFEST_VERSION, "created_at": now_iso(), "repos": {}}
    try:
        previous = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: {out} exists but cannot be parsed ({exc}). Move it aside; do not delete it.")
    if not isinstance(previous, dict) or previous.get("manifest_version") != MANIFEST_VERSION:
        raise SystemExit(
            f"ERROR: {out} declares manifest_version {previous.get('manifest_version')!r} but this script "
            f"writes {MANIFEST_VERSION}. Refusing to overwrite; move it aside or migrate it first."
        )
    if not isinstance(previous.get("repos"), dict):
        raise SystemExit(f"ERROR: {out} has no usable 'repos' object; move it aside before retrying.")
    return previous


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="show reference catalog without cloning")
    parser.add_argument("--group", choices=["essential", "all"], help="clone must-study or all candidates")
    parser.add_argument("--repo", action="append", choices=list(CATALOG), help="clone selected repository; repeatable")
    parser.add_argument("--dest", type=Path, default=ROOT.parent / "labcairn-upstreams", help="default sibling reference directory")
    args = parser.parse_args()
    if args.list:
        for k, (url, license_hint, group) in CATALOG.items():
            print(f"{k:20s} {group:13s} {license_hint:24s} {url}")
        return 0
    chosen = set(args.repo or [])
    if args.group:
        chosen.update(k for k, (_, _, group) in CATALOG.items() if args.group == "all" or group == "essential")
    if not chosen:
        parser.error("choose --group essential or one or more --repo NAME; see --list")
    dest = args.dest.resolve()
    # Guard common mistakes: no checkouts inside the tracked public source tree.
    if dest == ROOT or ROOT in dest.parents:
        parser.error("reference checkout destination must be outside the LabCairn repository")
    dest.mkdir(parents=True, exist_ok=True)
    # Merge into any existing snapshot: a partial run must not drop earlier batches.
    out = dest / "snapshot.json"
    previous = load_snapshot(out)
    records = dict(previous["repos"])
    before = set(records)
    for key in sorted(chosen):
        url, license_hint, group = CATALOG[key]
        path = dest / key
        if not path.exists():
            print(f"Cloning {key} (study only)...", flush=True)
            try:
                subprocess.run(["git", "clone", "--depth", "1", "--filter=blob:none", "--single-branch", url, str(path)], check=True)
            except subprocess.CalledProcessError:
                print(f"ERROR: clone failed for {key}. Inspect and retry manually; partial directory may remain.")
                return 1
        else:
            print(f"Keeping existing checkout {path} unchanged")
        try:
            sha = cmd("git", "-C", str(path), "rev-parse", "HEAD")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"ERROR: {path} is not a valid Git checkout")
            return 1
        records[key] = {
            **records.get(key, {}),
            "url": url,
            "path": str(path),
            "commit": sha,
            "license_hint_not_verified": license_hint,
            "priority": group,
            "recorded_at": now_iso(),
        }
        print(f"  {key}: {sha}")
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "created_at": previous.get("created_at") or now_iso(),
        "updated_at": now_iso(),
        "repos": records,
    }
    # Local-only snapshot for exactly the selected repos. Never add to public Git.
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    kept = sorted(before - set(chosen))
    print(f"Local snapshot written: {out}")
    if kept:
        print(f"Preserved earlier entries not selected this run: {', '.join(kept)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
