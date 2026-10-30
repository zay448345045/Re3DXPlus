#!/bin/sh
set -eu
SDK=$(xcrun --sdk iphoneos --show-sdk-path)
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUT=$(mktemp "${TMPDIR:-/tmp}/wmmt-hq-test.XXXXXX")
# Keep the uniquely-created temporary executable; do not delete unchecked paths.
clang -std=c11 -Wno-deprecated-declarations -F "$SDK/System/Library/Frameworks" -ffunction-sections -fdata-sections "$ROOT/test/ios_hq_mock_test.c" -Wl,-dead_strip -lm -o "$OUT"
"$OUT"
