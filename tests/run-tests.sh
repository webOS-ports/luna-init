#!/bin/sh
# Copyright (c) 2026 LG Electronics, Inc.
# SPDX-License-Identifier: Apache-2.0
#
# Host-side test entry point for luna-init. Usage: tests/run-tests.sh [python3]
set -eu

PYTHON="${1:-${PYTHON:-python3}}"
TESTS_DIR="$(cd "$(dirname "$0")" && pwd)"

exec "$PYTHON" "$TESTS_DIR/test_luna_init.py"
