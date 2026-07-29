#!/usr/bin/env bash
# Download the latest built fonts and install them into ~/Library/Fonts.
# Same end state as opening every TTF in Font Book and clicking Install,
# minus the duplicate-resolution dialogs on every upgrade.
set -euo pipefail

REPO="heiskr/iosevka-heiskr"
DEST="$HOME/Library/Fonts"

command -v gh >/dev/null || { echo "gh is required: brew install gh" >&2; exit 1; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

tag=$(gh release view --repo "$REPO" --json tagName --jq .tagName)
echo "Latest build: $tag"

gh release download "$tag" --repo "$REPO" --pattern '*.zip' --dir "$tmp"

mkdir -p "$DEST"
for zipfile in "$tmp"/*.zip; do
  unzip -q -o -j "$zipfile" '*.ttf' -d "$DEST"
done

count=$(find "$DEST" -name 'IosevkaHeiskr*.ttf' | wc -l | tr -d ' ')
echo "Installed $count TTFs into $DEST"
echo "Restart your apps to pick up the new version."
