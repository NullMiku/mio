#!/usr/bin/env python3
"""Safely overlay the GF1-GF5 autonomous spec onto an existing Mio checkout.

Only copies files bundled in specs/001-go-free-single-binary; it does not touch
.git, gf0, source files, worktrees, or remote repositories. Existing destination
files are backed up before replacement. Run from the unpacked archive folder.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent
PACKAGE = ROOT / "specs" / "001-go-free-single-binary"
RELPATH = pathlib.Path("specs/001-go-free-single-binary")

def sha256(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def run():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=pathlib.Path, required=True, help="Mio repository root")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    repo = args.repo.expanduser().resolve(strict=True)
    if not (repo / ".git").exists():
        raise SystemExit("Refusing target without a .git entry: " + str(repo))
    if not (repo / "specs" / "001-go-free-single-binary").is_dir():
        raise SystemExit("Existing GF0 spec directory not found; verify target repo")
    if not PACKAGE.is_dir():
        raise SystemExit("Bundle source directory missing")
    # Deliberately do not visit files outside the package root or follow symlinks.
    paths = sorted(f for f in PACKAGE.rglob("*") if f.is_file())
    if any(f.is_symlink() for f in paths):
        raise SystemExit("Refusing package containing symlinks")
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = repo / "build" / ("gofree-spec-backup-" + timestamp)
    if backup.exists():
        raise SystemExit("Backup path already exists: " + str(backup))
    manifest = []
    for src in paths:
        rel = src.relative_to(PACKAGE)
        dest = repo / RELPATH / rel
        # No symlink traversal through pre-existing destination directories.
        cur = repo / "specs"
        for part in ("001-go-free-single-binary", *rel.parts[:-1]):
            cur = cur / part
            if cur.is_symlink():
                raise SystemExit("Refusing symlink component: " + str(cur))
        if dest.is_symlink():
            raise SystemExit("Refusing destination symlink: " + str(dest))
        if dest.exists() and not dest.is_file():
            raise SystemExit("Destination not a file: " + str(dest))
        old = sha256(dest) if dest.exists() else None
        new = sha256(src)
        manifest.append({"path": (RELPATH / rel).as_posix(), "before_sha256": old, "after_sha256": new, "action": "skip_identical" if old == new else ("back_up_and_replace" if old else "new")})
    if args.dry_run:
        print(json.dumps({"dry_run": True, "files": manifest}, ensure_ascii=False, indent=2))
        return
    backup.mkdir(parents=True, exist_ok=False)
    # Pre-copy everything requiring backup, so no destination change precedes backup.
    for item in manifest:
        if item["action"] != "back_up_and_replace":
            continue
        rel = pathlib.Path(item["path"])
        dest = repo / rel
        saved = backup / rel
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dest, saved)
        if sha256(saved) != item["before_sha256"]:
            raise SystemExit("Backup validation failure: " + str(rel))
    for item in manifest:
        if item["action"] == "skip_identical":
            continue
        rel = pathlib.Path(item["path"])
        src = ROOT / rel
        dest = repo / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        if sha256(dest) != item["after_sha256"]:
            raise SystemExit("Install validation failure: " + str(rel))
    result = {"backup_dir": str(backup), "installed": manifest}
    (backup / "install-manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    run()
