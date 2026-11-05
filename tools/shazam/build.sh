#!/bin/bash
# Build and sign cb-shazam, the little Mac tool scripts/shazam_tag.py uses to ask
# Shazam which song is in each clip.
#
#   tools/shazam/build.sh com.yourname.concertbuddy.shazam
#
# Shazam only answers apps whose bundle ID has ShazamKit turned on, so first create
# that bundle ID in your Apple developer account (README › Song tagging with Shazam).
# The ID is remembered in tools/shazam/bundle-id, so later builds need no argument.
# Signing uses your first "Apple Development" (or "Developer ID Application")
# certificate; set CB_SHAZAM_SIGN_IDENTITY to pick another.
set -euo pipefail
cd "$(dirname "$0")"

BUNDLE_ID="${1:-${CB_SHAZAM_BUNDLE_ID:-$(cat bundle-id 2>/dev/null || true)}}"
if [ -z "$BUNDLE_ID" ]; then
  echo "Usage: tools/shazam/build.sh com.yourname.concertbuddy.shazam" >&2
  echo "  (a bundle ID you've registered with ShazamKit turned on; see README › Song tagging with Shazam)" >&2
  exit 2
fi
echo "$BUNDLE_ID" > bundle-id

IDENTITY="${CB_SHAZAM_SIGN_IDENTITY:-$(security find-identity -v -p codesigning | awk -F'"' '/Apple Development|Developer ID Application/ {print $2; exit}')}"
if [ -z "$IDENTITY" ]; then
  echo "No code-signing certificate found. Open Xcode › Settings › Accounts, sign in, and create an Apple Development certificate." >&2
  exit 1
fi

cat > Info.plist <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>${BUNDLE_ID}</string>
  <key>CFBundleName</key><string>cb-shazam</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>1</string>
</dict>
</plist>
PLIST

echo "Compiling…"
xcrun swiftc -O -swift-version 5 -target "$(uname -m)-apple-macos14" main.swift -o cb-shazam \
  -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker Info.plist

echo "Signing as $IDENTITY ($BUNDLE_ID)…"
codesign --force --sign "$IDENTITY" --identifier "$BUNDLE_ID" cb-shazam

echo "Built tools/shazam/cb-shazam. Try it on one clip:"
echo "  tools/shazam/cb-shazam media/<show-id>/IMG_1234.MOV"
