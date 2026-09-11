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

"""Unit tests for the luna-init configuration files and generator scripts.

Run with:  tests/run-tests.sh   (or: python3 -m unittest tests.test_luna_init)

The configuration tests need only the standard library. The generator
tests additionally need pytz and a zoneinfo database and are skipped
when pytz is not importable.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src')
TESTS = os.path.join(ROOT, 'tests')
GENERATOR = os.path.join(SRC, 'gen-ext-timezones.py')
EXTRACTOR = os.path.join(SRC, 'extract-description.py')
VALIDATOR = os.path.join(TESTS, 'validate-configs.py')

try:
	import pytz  # noqa: F401
	HAVE_PYTZ = True
except ImportError:
	HAVE_PYTZ = False


def run(cmd, **kwargs):
	return subprocess.run(cmd, capture_output=True, **kwargs)


class ConfigValidationTest(unittest.TestCase):
	def test_all_config_files_valid(self):
		res = run([sys.executable, VALIDATOR, '--root', ROOT])
		self.assertEqual(res.returncode, 0, res.stderr.decode())


@unittest.skipUnless(HAVE_PYTZ, "pytz not available")
class GeneratorTest(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.tmpdir = tempfile.TemporaryDirectory()
		cls.output = os.path.join(cls.tmpdir.name, 'ext-timezones.json')
		cls.res = run([sys.executable, GENERATOR, '--white-list-only',
			'-s', SRC, '-o', cls.output])
		cls.data = None
		if cls.res.returncode == 0:
			with open(cls.output) as f:
				cls.data = json.load(f)

	@classmethod
	def tearDownClass(cls):
		cls.tmpdir.cleanup()

	def test_generator_succeeds(self):
		self.assertEqual(self.res.returncode, 0, self.res.stderr.decode())

	def test_output_passes_validator(self):
		res = run([sys.executable, VALIDATOR, '--root', ROOT, '--ext', self.output])
		self.assertEqual(res.returncode, 0, res.stderr.decode())

	def test_zones_sorted_by_offset(self):
		offsets = [z['offsetFromUTC'] for z in self.data['timeZone']]
		self.assertEqual(offsets, sorted(offsets))

	def test_renamed_zones(self):
		zones = {z['ZoneID']: z for z in self.data['timeZone']}
		# Godthab must be emitted under its modern name
		self.assertNotIn('America/Godthab', zones)
		self.assertEqual(zones['America/Nuuk']['City'], 'Nuuk')
		self.assertEqual(zones['Europe/Kyiv']['City'], 'Kyiv')
		self.assertNotIn('Europe/Kiev', zones)

	def test_syszones_offsets(self):
		by_desc = {}
		for z in self.data['syszones']:
			self.assertTrue(z['ZoneID'].startswith('Etc/'))
			self.assertEqual(z['supportsDST'], 0)
			by_desc.setdefault(z['Description'], z['offsetFromUTC'])
		self.assertEqual(by_desc['GMT'], 0)
		self.assertEqual(by_desc['GMT+14'], 14 * 60)
		self.assertEqual(by_desc['GMT-12'], -12 * 60)

	def test_deterministic_for_fixed_year(self):
		out2 = os.path.join(self.tmpdir.name, 'run2.json')
		out3 = os.path.join(self.tmpdir.name, 'run3.json')
		for out in (out2, out3):
			res = run([sys.executable, GENERATOR, '-w', '-y', '2026', '-s', SRC, '-o', out])
			self.assertEqual(res.returncode, 0, res.stderr.decode())
		with open(out2, 'rb') as a, open(out3, 'rb') as b:
			self.assertEqual(a.read(), b.read())

	def test_stdout_mode(self):
		res = run([sys.executable, GENERATOR, '-w', '-s', SRC])
		self.assertEqual(res.returncode, 0, res.stderr.decode())
		data = json.loads(res.stdout.decode('utf-8'))
		self.assertIn('timeZone', data)

	def test_short_w_takes_no_argument(self):
		# A regression here makes -w swallow the next argument
		out = os.path.join(self.tmpdir.name, 'short-w.json')
		res = run([sys.executable, GENERATOR, '-w', '-s', SRC, '-o', out])
		self.assertEqual(res.returncode, 0, res.stderr.decode())
		self.assertTrue(os.path.exists(out))

	def test_unknown_option_is_rejected(self):
		res = run([sys.executable, GENERATOR, '--bogus'])
		self.assertEqual(res.returncode, 2)
		self.assertIn(b'Usage', res.stderr)

	def test_extract_description_round_trip(self):
		gen = run([sys.executable, GENERATOR, '-w', '-s', SRC])
		self.assertEqual(gen.returncode, 0, gen.stderr.decode())
		res = run([sys.executable, EXTRACTOR], input=gen.stdout)
		self.assertEqual(res.returncode, 0, res.stderr.decode())
		extracted = json.loads(res.stdout.decode('utf-8'))
		with open(os.path.join(SRC, 'uiTzInfo.json')) as f:
			ui = json.load(f)
		# every extracted zone that exists in uiTzInfo must agree on Description
		for zone, info in extracted.items():
			if zone in ui:
				self.assertEqual(info['Description'], ui[zone]['Description'], zone)

	def test_corrupt_reference_file_fails_cleanly(self):
		baddir = os.path.join(self.tmpdir.name, 'bad')
		os.mkdir(baddir)
		with open(os.path.join(baddir, 'mccInfo.json'), 'w') as f:
			f.write('{ not json')
		with open(os.path.join(baddir, 'uiTzInfo.json'), 'w') as f:
			f.write('{}')
		out = os.path.join(baddir, 'out.json')
		res = run([sys.executable, GENERATOR, '-w', '-s', baddir, '-o', out])
		self.assertNotEqual(res.returncode, 0)
		self.assertNotIn(b'Traceback', res.stderr)
		self.assertFalse(os.path.exists(out), "no partial output may be left behind")


if __name__ == '__main__':
	unittest.main(verbosity=2)
