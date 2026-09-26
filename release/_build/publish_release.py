#!/usr/bin/env python
"""Publish the two release assets as a GitHub Release.

The repository itself carries the payload (`release/`), and `build_assets.py`
packs the two zips. This script is the last step: create the Release page for the
current setup version and upload both archives.

It never publishes unless asked to: the default is a dry run that verifies
everything it would send.

    # 1. see exactly what would be published (no network writes)
    python release/_build/publish_release.py

    # 2. publish (needs a token with `repo` scope; `gh auth login` is not required)
    set GITHUB_TOKEN=ghp_...
    python release/_build/publish_release.py --publish

    # or point it at the assets somewhere else (for example a fresh download)
    python release/_build/publish_release.py --publish --assets-dir D:\\build

What it does before touching the network:
  * reads the setup version from build_assets.py and derives the tag (v<version>);
  * checks that both zips exist and that their SHA256 values match the committed
    `release/_build/SHA256SUMS.txt` (so a stale asset can never be published);
  * checks that the release notes file exists and is not empty;
  * with `--publish`, first asks the API whether the tag already exists and
    refuses to overwrite an existing release.

Uploads use the documented uploads.github.com endpoint (the older
uploads.github.com host) and never delete anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RELEASE = HERE.parent
REPO_ROOT = RELEASE.parent
OWNER_REPO = "Clearmind777/Nanoamp_for_win"
API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"
NOTES = RELEASE / "RELEASE_NOTES-{version}.md"
OFFLINE_ZIP = "nanoamp-0.1.0-windows-offline-deps.zip"


def setup_version() -> str:
    text = (HERE / "build_assets.py").read_text(encoding="utf-8")
    match = re.search(r'^SETUP_VERSION\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("SETUP_VERSION not found in build_assets.py")
    return match.group(1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expected_hashes() -> dict[str, str]:
    path = HERE / "SHA256SUMS.txt"
    if not path.is_file():
        raise SystemExit(f"missing {path}; run build_assets.py first")
    out: dict[str, str] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        if not line.strip():
            continue
        digest, _, name = line.partition("  ")
        out[name.strip()] = digest.strip()
    return out


def request(method: str, url: str, token: str | None, data: bytes | None = None,
            content_type: str = "application/json") -> tuple[int, dict]:
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "nanoamp-release-script"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = resp.read().decode("utf-8", "replace")
            return resp.status, (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            payload = json.loads(body)
        except ValueError:
            payload = {"message": body[:400]}
        return exc.code, payload


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--publish", action="store_true",
                    help="actually create the release and upload the assets")
    ap.add_argument("--assets-dir", default=str(HERE),
                    help="where the two zips are (default: release/_build)")
    ap.add_argument("--tag", default=None, help="tag name (default: v<setup version>)")
    ap.add_argument("--name", default=None, help="release title")
    ap.add_argument("--token", default=None,
                    help="GitHub token (default: $GITHUB_TOKEN / $GH_TOKEN)")
    args = ap.parse_args()

    version = setup_version()
    tag = args.tag or f"v{version}"
    title = args.name or f"nanoamp {version} — Windows 版"
    notes = Path(str(NOTES).format(version=version))
    assets_dir = Path(args.assets_dir)
    setup_zip = assets_dir / f"nanoamp-{version}-windows-setup.zip"
    deps_zip = assets_dir / OFFLINE_ZIP
    token = args.token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    print(f"repository : {OWNER_REPO}")
    print(f"tag        : {tag}")
    print(f"title      : {title}")
    print(f"notes      : {notes}")
    print(f"assets dir : {assets_dir}")
    print()

    problems: list[str] = []
    if not notes.is_file():
        problems.append(f"release notes not found: {notes}")
    elif not notes.read_text(encoding="utf-8").strip():
        problems.append(f"release notes are empty: {notes}")

    wanted = expected_hashes()
    for path in (setup_zip, deps_zip):
        if not path.is_file():
            problems.append(f"asset not found: {path}")
            continue
        want = wanted.get(path.name)
        got = sha256(path)
        # MiB, the same unit the release notes and the previous releases use.
        size_mb = path.stat().st_size / (1024 ** 2)
        if want is None:
            problems.append(f"{path.name} is not listed in SHA256SUMS.txt")
        elif want != got:
            problems.append(f"{path.name} sha256 mismatch:\n"
                            f"    SHA256SUMS.txt {want}\n"
                            f"    on disk        {got}")
        else:
            print(f"  OK  {path.name}  {size_mb:.1f} MB  sha256 {got[:16]}…")

    if problems:
        print("\nCannot publish:")
        for p in problems:
            print("   -", p)
        return 1

    if not token:
        print("\nNo token: set GITHUB_TOKEN (or GH_TOKEN) with `repo` scope, then re-run "
              "with --publish.")
        print("Dry run only; nothing was sent to GitHub.")
        return 0

    status, existing = request("GET", f"{API}/repos/{OWNER_REPO}/releases/tags/{tag}", token)
    if status == 200:
        print(f"\nRelease {tag} already exists: {existing.get('html_url')}")
        print("Refusing to overwrite it. Delete it first, or pass a different --tag.")
        return 1
    if status not in (200, 404):
        print(f"\nCould not query the tag (HTTP {status}): {existing.get('message')}")
        return 1

    if not args.publish:
        total_mib = (setup_zip.stat().st_size + deps_zip.stat().st_size) / (1024 ** 2)
        print("\nDry run: would create the release and upload 2 assets "
              f"({total_mib:.1f} MB).")
        print("Re-run with --publish to do it.")
        return 0

    payload = json.dumps({
        "tag_name": tag,
        "name": title,
        "body": notes.read_text(encoding="utf-8"),
        "draft": False,
        "prerelease": False,
    }).encode("utf-8")
    status, release = request("POST", f"{API}/repos/{OWNER_REPO}/releases", token, payload)
    if status != 201:
        print(f"Creating the release failed (HTTP {status}): {release.get('message')}")
        return 1
    print(f"created release: {release.get('html_url')}")

    upload_url = release["upload_url"].split("{")[0]
    for path in (setup_zip, deps_zip):
        print(f"uploading {path.name} ({path.stat().st_size / (1024 ** 2):.1f} MB)…")
        status, asset = request("POST", f"{upload_url}?name={path.name}", token,
                               path.read_bytes(), "application/zip")
        if status != 201:
            print(f"   upload failed (HTTP {status}): {asset.get('message')}")
            print("   The release exists; upload the remaining file by hand if needed.")
            return 1
        print(f"   uploaded: {asset.get('browser_download_url')}")

    print(f"\nPublished {tag}: {release.get('html_url')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
