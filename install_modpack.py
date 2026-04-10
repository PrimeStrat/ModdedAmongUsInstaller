import io
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

TOU_MIRA_REPOS = [
    "PrimeStrat/TOU-Mira",
    "AU-Avengers/TOU-Mira",
]
LEVEL_IMPOSTOR_REPO = "DigiWorm0/LevelImposter"

THUNDERSTORE_BASE = Path(
    os.environ.get("APPDATA", ""),
    "Thunderstore Mod Manager",
    "DataFolder",
    "AmongUs",
    "profiles",
)

GITHUB_API = "https://api.github.com"
REQUEST_HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "ModdedAmongUsInstaller/1.0"}

PROFILE_SUBDIRS = [
    "_state",
    "BepInEx/plugins",
    "BepInEx/config",
    "BepInEx/core",
    "BepInEx/patchers",
]

# Entry point for the installer.
#
# @return: None
def main():
    print("=" * 60)
    print("  Modded Among Us Installer")
    print("  TOU-Mira + LevelImposter -> Thunderstore Profile")
    print("=" * 60)

    profile_name = sys.argv[1] if len(sys.argv) > 1 else None

    print("\n[1/4] Finding latest releases...")
    tou_repo, tou_tag, tou_label, tou_url = _get_tou_mira_release()
    li_tag, li_label, li_url = _get_level_impostor_release()

    print(f"\n  TOU-Mira     : {tou_label}  (tag: {tou_tag}, repo: {tou_repo})")
    print(f"  LevelImposter: {li_label}  (tag: {li_tag})")

    if not profile_name:
        default_name = f"ModdedAmongUs_TOU-{tou_tag}_LI-{li_tag}"
        profile_name = input(f"\n  Profile name [{default_name}]: ").strip() or default_name

    print(f"\n  Profile will be created at:")
    print(f"    {THUNDERSTORE_BASE / profile_name}")

    print("\n[2/4] Downloading TOU-Mira...")
    tou_zip = _download_bytes(tou_url, "TOU-Mira")

    print("\n[3/4] Downloading LevelImposter...")
    li_zip = _download_bytes(li_url, "LevelImposter")

    print("\n[4/4] Creating Thunderstore profile...")
    profile_dir = _create_profile(profile_name, tou_zip, li_zip, tou_tag, li_tag)

    print("\n" + "=" * 60)
    print("  Installation complete!")
    print(f"  Profile: {profile_name}")
    print(f"  Path:    {profile_dir}")
    print()
    print("  To use:")
    print("  1. Open Thunderstore Mod Manager")
    print("  2. Select the Among Us game")
    print(f"  3. Switch to the '{profile_name}' profile")
    print("  4. Click 'Start Modded' to launch")
    print("=" * 60)

# Send a GET request to the GitHub API and return parsed JSON.
#
# @param url: Full GitHub API URL to request.
# @return: Parsed JSON as dict/list, or None if 404.
def _api_get(url: str) -> dict | list | None:
    req = urllib.request.Request(url, headers=REQUEST_HEADERS)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise

# Download a file from a URL with a progress indicator.
#
# @param url: Direct download URL.
# @param label: Display label for progress output.
# @return: Raw bytes of the downloaded file.
def _download_bytes(url: str, label: str) -> bytes:
    headers = {**REQUEST_HEADERS, "Accept": "application/octet-stream"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        data = bytearray()
        chunk_size = 1024 * 256
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            data.extend(chunk)
            downloaded_kb = len(data) // 1024
            if total:
                pct = len(data) * 100 // total
                total_kb = total // 1024
                print(f"\r  Downloading {label}: {pct:3d}%  ({downloaded_kb:,} KB / {total_kb:,} KB)", end="", flush=True)
            else:
                print(f"\r  Downloading {label}: {downloaded_kb:,} KB", end="", flush=True)
        print()
    return bytes(data)

# Extract a zip archive into a destination folder, merging with existing contents.
#
# @param zip_bytes: Raw bytes of the zip file.
# @param dest: Destination directory path.
# @param label: Display label for progress output.
# @return: None
def _safe_extract(zip_bytes: bytes, dest: Path, label: str):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        members = zf.namelist()
        strip_prefix = _detect_wrapping_folder(members)

        if strip_prefix:
            print(f"  Stripping top-level folder: {strip_prefix}")

        print(f"  Extracting {label} ({len(members)} entries) -> {dest}")
        for member in members:
            if member.startswith("/") or ".." in member:
                print(f"    SKIPPED (unsafe path): {member}")
                continue

            rel = member[len(strip_prefix):] if strip_prefix and member.startswith(strip_prefix) else member
            if not rel:
                continue

            target = dest / rel
            if member.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)

# Detect if all zip entries share a single top-level wrapping folder.
#
# @param members: List of zip entry paths.
# @return: The wrapping folder prefix to strip, or empty string if none.
def _detect_wrapping_folder(members: list[str]) -> str:
    top_dirs = {m.split("/")[0] for m in members if "/" in m}
    if len(top_dirs) != 1:
        return ""
    candidate = next(iter(top_dirs)) + "/"
    if all(m.startswith(candidate) or m == candidate.rstrip("/") for m in members):
        return candidate
    return ""

# Find the latest TOU-Mira release with a Steam zip asset.
#
# @return: Tuple of (repo, tag, version_label, steam_zip_url).
def _get_tou_mira_release() -> tuple[str, str, str, str]:
    for repo in TOU_MIRA_REPOS:
        print(f"  Checking {repo} for releases...")
        releases = _api_get(f"{GITHUB_API}/repos/{repo}/releases")
        if not releases:
            continue
        for rel in releases:
            if rel.get("draft"):
                continue
            tag = rel["tag_name"]
            for asset in rel.get("assets", []):
                name = asset["name"]
                if "steam" in name.lower() and name.endswith(".zip"):
                    print(f"  Found TOU-Mira {tag} from {repo}")
                    return repo, tag, rel.get("name", "???"), asset["browser_download_url"]

    print("ERROR: Could not find any TOU-Mira release with a Steam zip asset.")
    sys.exit(1)

# Find the latest LevelImposter release with a LevelImposter.zip asset.
#
# @return: Tuple of (tag, version_label, zip_url).
def _get_level_impostor_release() -> tuple[str, str, str]:
    print(f"  Checking {LEVEL_IMPOSTOR_REPO} for releases...")
    releases = _api_get(f"{GITHUB_API}/repos/{LEVEL_IMPOSTOR_REPO}/releases")
    if not releases:
        print("ERROR: Could not find any LevelImposter releases.")
        sys.exit(1)

    for rel in releases:
        if rel.get("draft"):
            continue
        tag = rel["tag_name"]
        for asset in rel.get("assets", []):
            if asset["name"].lower() == "levelimposter.zip":
                print(f"  Found LevelImposter {tag}")
                return tag, rel.get("name", "???"), asset["browser_download_url"]

    print("ERROR: Could not find a LevelImposter.zip asset in any release.")
    sys.exit(1)

# Parse a version tag into major, minor, patch integers.
#
# @param version_string: Version string like 'v1.5.9' or '0.21.2-beta'.
# @return: Tuple of (major, minor, patch).
def _parse_version(version_string: str) -> tuple[int, int, int]:
    cleaned = version_string.lstrip("v").split("-")[0]
    parts = cleaned.split(".")
    parts += ["0"] * (3 - len(parts))
    return int(parts[0]), int(parts[1]), int(parts[2])

# Generate a mods.yml manifest for the Thunderstore profile.
#
# @param tou_version: TOU-Mira version tag string.
# @param li_version: LevelImposter version tag string.
# @return: YAML string for mods.yml.
def _build_mods_yml(tou_version: str, li_version: str) -> str:
    now_ms = int(time.time() * 1000)
    tou_maj, tou_min, tou_pat = _parse_version(tou_version)
    li_maj, li_min, li_pat = _parse_version(li_version)

    return (
        f"- manifestVersion: 1\n"
        f"  name: BepInEx-BepInExPack_AmongUs\n"
        f"  authorName: BepInEx\n"
        f"  websiteUrl: https://thunderstore.io/c/among-us/p/BepInEx/BepInExPack_AmongUs/\n"
        f"  displayName: BepInExPack_AmongUs\n"
        f"  description: BepInEx pack for Among Us. Preconfigured and ready to use.\n"
        f"  gameVersion: '0'\n"
        f"  networkMode: both\n"
        f"  packageType: other\n"
        f"  installMode: managed\n"
        f"  installedAtTime: {now_ms}\n"
        f"  loaders: []\n"
        f"  dependencies: []\n"
        f"  incompatibilities: []\n"
        f"  optionalDependencies: []\n"
        f"  versionNumber:\n"
        f"    major: 6\n"
        f"    minor: 0\n"
        f"    patch: 752\n"
        f"  enabled: true\n"
        f"- manifestVersion: 1\n"
        f"  name: TOU-Mira\n"
        f"  authorName: AU-Avengers\n"
        f"  websiteUrl: https://github.com/AU-Avengers/TOU-Mira\n"
        f"  displayName: Town of Us Mira\n"
        f"  description: Town of Us mod built on MiraAPI for Among Us.\n"
        f"  gameVersion: '0'\n"
        f"  networkMode: both\n"
        f"  packageType: other\n"
        f"  installMode: managed\n"
        f"  installedAtTime: {now_ms}\n"
        f"  loaders: []\n"
        f"  dependencies:\n"
        f"    - BepInEx-BepInExPack_AmongUs\n"
        f"  incompatibilities: []\n"
        f"  optionalDependencies: []\n"
        f"  versionNumber:\n"
        f"    major: {tou_maj}\n"
        f"    minor: {tou_min}\n"
        f"    patch: {tou_pat}\n"
        f"  enabled: true\n"
        f"- manifestVersion: 1\n"
        f"  name: LevelImposter\n"
        f"  authorName: DigiWorm0\n"
        f"  websiteUrl: https://github.com/DigiWorm0/LevelImposter\n"
        f"  displayName: LevelImposter\n"
        f"  description: Custom map loader for Among Us.\n"
        f"  gameVersion: '0'\n"
        f"  networkMode: both\n"
        f"  packageType: other\n"
        f"  installMode: managed\n"
        f"  installedAtTime: {now_ms}\n"
        f"  loaders: []\n"
        f"  dependencies:\n"
        f"    - BepInEx-BepInExPack_AmongUs\n"
        f"  incompatibilities: []\n"
        f"  optionalDependencies: []\n"
        f"  versionNumber:\n"
        f"    major: {li_maj}\n"
        f"    minor: {li_min}\n"
        f"    patch: {li_pat}\n"
        f"  enabled: true\n"
    )

# Create a Thunderstore profile folder with extracted mod contents.
#
# @param profile_name: Name for the Thunderstore profile folder.
# @param tou_zip: Raw bytes of the TOU-Mira zip archive.
# @param li_zip: Raw bytes of the LevelImposter zip archive.
# @param tou_version: TOU-Mira version tag string.
# @param li_version: LevelImposter version tag string.
# @return: Path to the created profile directory.
def _create_profile(profile_name: str, tou_zip: bytes, li_zip: bytes,
                    tou_version: str, li_version: str) -> Path:
    profile_dir = THUNDERSTORE_BASE / profile_name

    if profile_dir.exists():
        print(f"\n  Profile '{profile_name}' already exists at:\n    {profile_dir}")
        resp = input("  Overwrite? [y/N]: ").strip().lower()
        if resp != "y":
            print("  Aborted.")
            sys.exit(0)
        shutil.rmtree(profile_dir)

    profile_dir.mkdir(parents=True, exist_ok=True)

    _safe_extract(tou_zip, profile_dir, "TOU-Mira")
    _safe_extract(li_zip, profile_dir, "LevelImposter")

    for sub in PROFILE_SUBDIRS:
        (profile_dir / sub).mkdir(parents=True, exist_ok=True)

    mods_yml = _build_mods_yml(tou_version, li_version)
    (profile_dir / "mods.yml").write_text(mods_yml, encoding="utf-8")
    print("  Wrote mods.yml")

    return profile_dir


if __name__ == "__main__":
    main()
