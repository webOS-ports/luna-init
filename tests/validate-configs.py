#!/usr/bin/env python3
# Copyright (c) 2026 LG Electronics, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""Validate the luna-init configuration files.

Standalone (stdlib-only) so it can run as a build gate from CMake, from
the unit tests, and by hand:

    validate-configs.py [--root REPO_ROOT] [--ext EXT_TIMEZONES_JSON]

Exits non-zero and prints one line per problem if anything is wrong.
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET

errors = []


def fail(path, msg):
	errors.append("%s: %s" % (path, msg))


def load_json_strict(path):
	"""Parse JSON, rejecting duplicate keys anywhere in the document."""
	def hook(pairs):
		seen = set()
		for key, _ in pairs:
			if key in seen:
				fail(path, "duplicate key %r" % key)
			seen.add(key)
		return dict(pairs)
	try:
		with open(path, 'r', encoding='utf-8') as f:
			return json.load(f, object_pairs_hook=hook)
	except (ValueError, OSError) as e:
		fail(path, str(e))
		return None


def check_str(path, obj, key, where):
	if not isinstance(obj.get(key), str) or not obj.get(key):
		fail(path, "%s: %r must be a non-empty string" % (where, key))


def validate_handlers(path):
	data = load_json_strict(path)
	if data is None:
		return
	for entry in data.get('resources', []):
		where = "resource %r" % entry.get('extn')
		check_str(path, entry, 'extn', where)
		check_str(path, entry, 'mime', where)
		check_str(path, entry, 'appId', where)
		if not isinstance(entry.get('streamable'), bool):
			fail(path, "%s: 'streamable' must be a boolean" % where)
	for section in ('redirects', 'commands'):
		for entry in data.get(section, []):
			where = "%s %r" % (section, entry.get('url'))
			check_str(path, entry, 'url', where)
			check_str(path, entry, 'appId', where)
			try:
				re.compile(entry.get('url') or '')
			except re.error as e:
				fail(path, "%s: url is not a valid regex: %s" % (where, e))


def validate_mcc_info(path):
	data = load_json_strict(path)
	if data is None:
		return
	entries = data.get('mccInfo')
	if not isinstance(entries, list) or not entries:
		fail(path, "top-level 'mccInfo' must be a non-empty list")
		return
	for entry in entries:
		where = "mcc %r" % entry.get('mcc')
		mcc = entry.get('mcc')
		if not isinstance(mcc, int) or not 200 <= mcc <= 799:
			fail(path, "%s: 'mcc' must be an integer in [200, 799]" % where)
		check_str(path, entry, 'Country', where)
		cc = entry.get('CountryCode')
		if not isinstance(cc, str) or not re.fullmatch(r'[A-Z]{2}', cc):
			fail(path, "%s: 'CountryCode' must be two uppercase letters" % where)
		validate_offset(path, entry, where)
		if 'ZoneID' in entry:
			check_str(path, entry, 'ZoneID', where)


def validate_offset(path, entry, where):
	off = entry.get('offsetFromUTC')
	# UTC offsets used by tzdata span -12:00 .. +14:00
	if not isinstance(off, int) or not -720 <= off <= 840:
		fail(path, "%s: 'offsetFromUTC' must be an integer number of minutes in [-720, 840]" % where)
	if entry.get('supportsDST') not in (0, 1):
		fail(path, "%s: 'supportsDST' must be 0 or 1" % where)


def validate_ui_tz_info(path):
	data = load_json_strict(path)
	if data is None:
		return
	if not isinstance(data, dict) or not data:
		fail(path, "must be a non-empty object keyed by ZoneID")
		return
	for zone, info in data.items():
		if not isinstance(info, dict):
			fail(path, "%s: value must be an object" % zone)
			continue
		if not isinstance(info.get('City'), str):
			fail(path, "%s: 'City' must be a string" % zone)
		check_str(path, info, 'Description', zone)
		if 'Country' in info:
			check_str(path, info, 'Country', zone)
		if 'preferred' in info and not isinstance(info['preferred'], bool):
			fail(path, "%s: 'preferred' must be a boolean" % zone)


def validate_ext_timezones(path):
	data = load_json_strict(path)
	if data is None:
		return
	zones = data.get('timeZone')
	if not isinstance(zones, list) or not zones:
		fail(path, "'timeZone' must be a non-empty list")
		return
	seen = set()
	for entry in zones:
		where = "zone %r/%r" % (entry.get('ZoneID'), entry.get('CountryCode'))
		check_str(path, entry, 'ZoneID', where)
		validate_offset(path, entry, where)
		key = (entry.get('ZoneID'), entry.get('CountryCode'))
		if key in seen:
			fail(path, "%s: duplicate (ZoneID, CountryCode)" % where)
		seen.add(key)
	syszones = data.get('syszones')
	# GMT-12 .. GMT+14 in whole and half hours, with GMT twice (GMT-0/GMT+0)
	if not isinstance(syszones, list) or len(syszones) != 54:
		fail(path, "'syszones' must list exactly 54 Etc/* zones (got %s)"
			% (len(syszones) if isinstance(syszones, list) else type(syszones).__name__))
	if 'mccInfo' not in data:
		fail(path, "'mccInfo' section is missing")


def validate_fonts_xml(path):
	try:
		ET.parse(path)
	except (ET.ParseError, OSError) as e:
		fail(path, str(e))


def main():
	root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	ext = None
	args = sys.argv[1:]
	while args:
		arg = args.pop(0)
		if arg == '--root' and args:
			root = args.pop(0)
		elif arg == '--ext' and args:
			ext = args.pop(0)
		else:
			sys.stderr.write("Usage: %s [--root REPO_ROOT] [--ext EXT_TIMEZONES_JSON]\n" % sys.argv[0])
			return 2

	conf = os.path.join(root, 'files', 'conf')
	src = os.path.join(root, 'src')

	validate_handlers(os.path.join(conf, 'command-resource-handlers.json'))
	validate_mcc_info(os.path.join(src, 'mccInfo.json'))
	validate_ui_tz_info(os.path.join(src, 'uiTzInfo.json'))
	for name in ('default-dock-positions.json', 'default-launcher-page-layout.json',
			'region.json', 'defaultPreferences.txt', 'cust-preferences.txt',
			'locale.txt', 'CustomerCareNumber.txt'):
		load_json_strict(os.path.join(conf, name))
	for name in ('webos-system-fonts.xml', 'webos-fallback-fonts.xml'):
		validate_fonts_xml(os.path.join(conf, 'fonts', name))
	if ext:
		validate_ext_timezones(ext)

	if errors:
		for e in errors:
			sys.stderr.write("ERROR: %s\n" % e)
		sys.stderr.write("validate-configs: %d problem(s) found\n" % len(errors))
		return 1
	print("validate-configs: all configuration files are valid")
	return 0


if __name__ == '__main__':
	sys.exit(main())
