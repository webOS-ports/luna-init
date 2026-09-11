#!/bin/sh
# Copyright (c) 2026 LG Electronics, Inc.
# SPDX-License-Identifier: Apache-2.0
#
# Host-side driver: pushes the timezone stress test to a LuneOS device over
# adb and runs it against the ext-timezones.json installed on the device.
#
#   adb-stress.sh [-s SERIAL] [-r ROUNDS] [-c READERS] [-e EXT_TIMEZONES_JSON]
#
# Without -e, the zone list is pulled from /usr/palm/ext-timezones.json on
# the device itself, so the test exercises exactly what is installed.
set -eu

SERIAL=""
ROUNDS=1
READERS=2
EXT=""
while getopts "s:r:c:e:" opt; do
	case "$opt" in
		s) SERIAL="$OPTARG" ;;
		r) ROUNDS="$OPTARG" ;;
		c) READERS="$OPTARG" ;;
		e) EXT="$OPTARG" ;;
		*) echo "usage: $0 [-s SERIAL] [-r ROUNDS] [-c READERS] [-e EXT_TIMEZONES_JSON]" >&2; exit 2 ;;
	esac
done

ADB="adb"
[ -n "$SERIAL" ] && ADB="adb -s $SERIAL"

TESTS_DIR=$(cd "$(dirname "$0")" && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

if [ -z "$EXT" ]; then
	$ADB pull /usr/palm/ext-timezones.json "$TMP/ext-timezones.json" >/dev/null
	EXT="$TMP/ext-timezones.json"
fi

python3 - "$EXT" > "$TMP/zonelist" <<'EOF'
import json, sys
with open(sys.argv[1]) as f:
	data = json.load(f)
for entry in data['timeZone'] + data['syszones']:
	print(json.dumps(entry, ensure_ascii=False, separators=(',', ':')))
EOF

echo "Zones to cycle: $(wc -l < "$TMP/zonelist")"
$ADB push "$TESTS_DIR/stress-timezones.sh" "$TMP/zonelist" /tmp/ >/dev/null
$ADB shell "sh /tmp/stress-timezones.sh /tmp/zonelist $ROUNDS $READERS; echo EXIT:\$?" | tee "$TMP/out"
grep -q '^EXIT:0' "$TMP/out"
