#!/bin/sh
# Copyright (c) 2026 Herman van Hazendonk <github.com@herrie.org>
# SPDX-License-Identifier: Apache-2.0
#
# On-device stress test for the luna-init timezone data. Cycles the system
# timezone through every zone shipped in ext-timezones.json via
# com.webos.service.systemservice while concurrent readers hammer the
# preference and time queries, then restores the original timezone.
#
# Runs on the device (BusyBox sh):
#   stress-timezones.sh ZONELIST_FILE [ROUNDS] [READERS]
#
# ZONELIST_FILE holds one compact JSON timeZone entry per line (see
# adb-stress.sh, which generates it from ext-timezones.json).
set -u

ZONELIST="${1:?usage: stress-timezones.sh ZONELIST_FILE [ROUNDS] [READERS]}"
ROUNDS="${2:-1}"
READERS="${3:-2}"
SERVICE="luna://com.webos.service.systemservice"
WORK="/tmp/luna-init-stress.$$"

[ -r "$ZONELIST" ] || { echo "FATAL: cannot read $ZONELIST"; exit 2; }
mkdir -p "$WORK"

set_fail=0
verify_fail=0
set_ok=0
reader_stop="$WORK/stop"

# remember the current timezone so we can put it back
orig=$(luna-send -n 1 "$SERVICE/getPreferences" '{"keys":["timeZone"]}' 2>/dev/null \
	| sed -n 's/.*"timeZone":\({[^}]*}\).*/\1/p')
[ -n "$orig" ] || { echo "FATAL: cannot read current timeZone preference"; exit 2; }
echo "Original timezone: $orig"

restore() {
	touch "$reader_stop"
	wait 2>/dev/null
	luna-send -n 1 "$SERVICE/setPreferences" "{\"timeZone\":$orig}" >/dev/null 2>&1
	rm -rf "$WORK"
}
trap restore EXIT INT TERM

# concurrent readers: poll preferences and system time until told to stop,
# recording any call that does not report returnValue true
reader() {
	n=0
	errs=0
	while [ ! -e "$reader_stop" ]; do
		for call in "getPreferences {\"keys\":[\"timeZone\"]}" "time/getSystemTime {}"; do
			method=${call%% *}
			args=${call#* }
			out=$(luna-send -n 1 "$SERVICE/$method" "$args" 2>&1)
			case "$out" in
				*'"returnValue":true'*) ;;
				*) errs=$((errs+1)); printf '%s\n' "$out" >> "$WORK/reader.$1.log" ;;
			esac
			n=$((n+1))
		done
	done
	echo "$n $errs" > "$WORK/reader.$1.count"
}

i=1
while [ "$i" -le "$READERS" ]; do
	reader "$i" &
	i=$((i+1))
done

total_zones=$(grep -c . "$ZONELIST")
start=$(date +%s)
round=1
while [ "$round" -le "$ROUNDS" ]; do
	echo "=== Round $round/$ROUNDS: cycling $total_zones zones"
	while IFS= read -r entry; do
		[ -n "$entry" ] || continue
		zone=$(printf '%s' "$entry" | sed -n 's/.*"ZoneID":"\([^"]*\)".*/\1/p')
		out=$(luna-send -n 1 "$SERVICE/setPreferences" "{\"timeZone\":$entry}" 2>&1)
		case "$out" in
			*'"returnValue":true'*) set_ok=$((set_ok+1)) ;;
			*) set_fail=$((set_fail+1)); echo "SET FAIL $zone: $out" ;;
		esac
		back=$(luna-send -n 1 "$SERVICE/getPreferences" '{"keys":["timeZone"]}' 2>&1)
		case "$back" in
			*"\"ZoneID\":\"$zone\""*) ;;
			*) verify_fail=$((verify_fail+1)); echo "VERIFY FAIL $zone: $back" ;;
		esac
	done < "$ZONELIST"
	round=$((round+1))
done
elapsed=$(( $(date +%s) - start ))

touch "$reader_stop"
wait 2>/dev/null

reader_calls=0
reader_errs=0
for f in "$WORK"/reader.*.count; do
	[ -e "$f" ] || continue
	read -r calls errs < "$f"
	reader_calls=$((reader_calls+calls))
	reader_errs=$((reader_errs+errs))
done

echo "=== Stress summary"
echo "setPreferences: $set_ok ok, $set_fail failed"
echo "read-back verify: $verify_fail failed"
echo "concurrent reader calls: $reader_calls, $reader_errs failed"
echo "elapsed: ${elapsed}s"

if [ "$set_fail" -ne 0 ] || [ "$verify_fail" -ne 0 ] || [ "$reader_errs" -ne 0 ]; then
	echo "RESULT: FAIL"
	exit 1
fi
echo "RESULT: PASS"
exit 0
