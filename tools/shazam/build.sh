#!/bin/bash
# Build and sign cb-shazam, the little Mac tool scripts/shazam_tag.py uses to ask
# Shazam which song is in each clip.
#
#   tools/shazam/build.sh com.yourname.concertbuddy.shazam                 # first time
#   tools/shazam/build.sh com.yourname.concertbuddy.shazam --sign "Your Name"
#   tools/shazam/build.sh                                                  # later: remembers both
#
# Shazam only answers when the signing certificate and the bundle ID belong to the
# SAME developer team, and that bundle ID has ShazamKit turned on (README › Song
# tagging with Shazam). If your Mac has certificates for more than one team (say,
# a work account too), pick yours with --sign and part of its name or team ID.
# The bundle ID and certificate are remembered in tools/shazam/bundle-id and
# tools/shazam/sign-identity (neither is committed).
set -euo pipefail
cd "$(dirname "$0")"

BUNDLE_ID="" PICK=""
while [ $# -gt 0 ]; do
  case "$1" in
    --sign) PICK="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) BUNDLE_ID="$1"; shift ;;
  esac
done
BUNDLE_ID="${BUNDLE_ID:-${CB_SHAZAM_BUNDLE_ID:-$(cat bundle-id 2>/dev/null || true)}}"
if [ -z "$BUNDLE_ID" ]; then
  echo "Usage: tools/shazam/build.sh com.yourname.concertbuddy.shazam [--sign \"Your Name\"]" >&2
  echo "  (a bundle ID you've registered with ShazamKit turned on; see README › Song tagging with Shazam)" >&2
  exit 2
fi

# ---------- which certificate ----------
# "team" = the OU of the certificate's subject, which is the developer team ID.
team_of() { security find-certificate -c "$1" -p 2>/dev/null | openssl x509 -noout -subject 2>/dev/null \
            | sed -n 's/.*OU *= *\([A-Z0-9]*\).*/\1/p' | head -1; }
org_of()  { security find-certificate -c "$1" -p 2>/dev/null | openssl x509 -noout -subject 2>/dev/null \
            | sed -n 's/.*[/,] *O *= *\([^/,]*\).*/\1/p' | head -1; }
CANDIDATES="$(security find-identity -v -p codesigning | awk -F'"' '/Apple Development|Developer ID Application/ {print $2}' | sort -u)"
if [ -z "$CANDIDATES" ]; then
  echo "No code-signing certificate found. Open Xcode › Settings › Accounts, select your own Apple ID," >&2
  echo "click Manage Certificates › + › Apple Development, then run this again." >&2
  exit 1
fi

PICK="${PICK:-${CB_SHAZAM_SIGN_IDENTITY:-$(cat sign-identity 2>/dev/null || true)}}"
IDENTITY=""
if [ -n "$PICK" ]; then
  while IFS= read -r c; do
    if [[ "$c" == *"$PICK"* ]] || [ "$(team_of "$c")" = "$PICK" ]; then IDENTITY="$c"; break; fi
  done <<< "$CANDIDATES"
  if [ -z "$IDENTITY" ]; then echo "No signing certificate matches \"$PICK\"." >&2; fi
elif [ "$(printf '%s\n' "$CANDIDATES" | grep -c .)" = 1 ]; then
  IDENTITY="$CANDIDATES"
fi
if [ -z "$IDENTITY" ]; then
  echo "This Mac has more than one signing certificate. Pick the one from the developer account" >&2
  echo "where you registered $BUNDLE_ID (its team ID is on developer.apple.com › Membership details):" >&2
  echo >&2
  while IFS= read -r c; do printf '  %-60s team %-12s %s\n' "$c" "$(team_of "$c")" "$(org_of "$c")" >&2; done <<< "$CANDIDATES"
  echo >&2
  echo "Then:  tools/shazam/build.sh $BUNDLE_ID --sign \"<part of its name, or its team ID>\"" >&2
  exit 2
fi
echo "$BUNDLE_ID" > bundle-id
echo "$IDENTITY" > sign-identity

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

echo "Compiling..."
xcrun swiftc -O -swift-version 5 -target "$(uname -m)-apple-macos14" main.swift -o cb-shazam \
  -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker Info.plist

echo "Signing as ${IDENTITY} (team $(team_of "$IDENTITY")) for ${BUNDLE_ID}..."
codesign --force --sign "$IDENTITY" --identifier "$BUNDLE_ID" cb-shazam
# Shazam goes by these two: the identifier must be the bundle ID, the team the one that owns it
SIGNED="$(codesign -dv cb-shazam 2>&1)"
grep -E '^(Identifier|TeamIdentifier)=' <<< "$SIGNED" | sed 's/^/  /' || true
if ! grep -qx "Identifier=${BUNDLE_ID}" <<< "$SIGNED"; then
  echo "Signing didn't take (identifier isn't ${BUNDLE_ID}); Shazam will refuse it." >&2
  exit 1
fi

echo "Built tools/shazam/cb-shazam. Try it on one clip:"
echo "  tools/shazam/cb-shazam media/<show-id>/IMG_1234.MOV"
