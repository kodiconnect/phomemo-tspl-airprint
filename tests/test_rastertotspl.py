"""Tests for filter/rastertotspl. Plain unittest, no CUPS needed.

    python3 -m unittest discover -s tests

The fixtures are tests/fixtures/test-label.pdf rendered by Debian bookworm's
CUPS into raster: 1-bit K (what our PPD asks for) and 8-bit W (what the
vendor PPD asks for). VENDOR_SHA256 is the vendor filter's output for the
8-bit raster on a PM64D setup; ours must match it byte for byte.
"""
import gzip
import hashlib
import os
import struct
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILTER = os.path.join(ROOT, "filter", "rastertotspl")
PPD = os.path.join(ROOT, "ppd", "phomemo-pm64d.ppd")
FIXTURES = os.path.join(ROOT, "tests", "fixtures")

VENDOR_SHA256 = "0360c7a30eeca54add2e72f91b3a7ce7c209fe08bae741c07c17320aca51df0a"

HEADER_LEN = 1796
# cups_page_header2_t fields the filter reads (offset of each uint32)
READ_FIELDS = (276, 280, 352, 356, 372, 376, 384, 388, 392, 396, 400)


def fixture(name):
    with gzip.open(os.path.join(FIXTURES, name), "rb") as f:
        return f.read()


def run_filter(raster, options="", ppd=PPD):
    env = dict(os.environ, PPD=ppd)
    return subprocess.run(
        [sys.executable, FILTER, "1", "user", "title", "1", options],
        input=raster, capture_output=True, env=env, check=False,
    )


def setup_commands(tspl):
    """The text commands before the BITMAP payload."""
    return tspl[: tspl.index(b"BITMAP")].decode("ascii").split("\r\n")[:-1]


def compress_v2(raster):
    """Re-encode an uncompressed little-endian v3 raster as compressed v2."""
    assert raster[:4] == b"3SaR"
    header = raster[4 : 4 + HEADER_LEN]
    bpl = struct.unpack_from("<I", header, 392)[0]
    height = struct.unpack_from("<I", header, 376)[0]
    body = raster[4 + HEADER_LEN :]
    lines = [body[i * bpl : (i + 1) * bpl] for i in range(height)]

    def encode_line(line):
        out, i = bytearray(), 0
        while i < len(line):
            j = i
            while j + 1 < len(line) and line[j + 1] == line[i] and j - i < 127:
                j += 1
            if j > i:  # run of identical bytes
                out += bytes([j - i]) + line[i : i + 1]
                i = j + 1
                continue
            k = i  # literal stretch, up to 128 bytes, until a run starts
            while k < len(line) and k - i < 128 and not (
                k + 1 < len(line) and line[k + 1] == line[k]
            ):
                k += 1
            n = max(1, k - i)
            if n == 1:
                out += bytes([0]) + line[i : i + 1]
            else:
                out += bytes([257 - n]) + line[i : i + n]
            i += n
        return out

    out, y = bytearray(b"2SaR" + header), 0
    while y < height:
        repeat = 1
        while y + repeat < height and lines[y + repeat] == lines[y] and repeat < 256:
            repeat += 1
        out += bytes([repeat - 1]) + encode_line(lines[y])
        y += repeat
    return bytes(out)


def to_big_endian(raster):
    """Swap the little-endian v3 raster to big-endian (RaS3)."""
    assert raster[:4] == b"3SaR"
    header = bytearray(raster[4 : 4 + HEADER_LEN])
    for off in READ_FIELDS:
        (value,) = struct.unpack_from("<I", header, off)
        struct.pack_into(">I", header, off, value)
    return b"RaS3" + bytes(header) + raster[4 + HEADER_LEN :]


class MatchesVendor(unittest.TestCase):
    def assertVendorOutput(self, raster):
        result = run_filter(raster)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(hashlib.sha256(result.stdout).hexdigest(), VENDOR_SHA256)

    def test_1bit_k_raster(self):
        self.assertVendorOutput(fixture("test-label-1bit-k.ras.gz"))

    def test_8bit_w_raster(self):
        self.assertVendorOutput(fixture("test-label-8bit-w.ras.gz"))

    def test_compressed_v2_raster(self):
        self.assertVendorOutput(compress_v2(fixture("test-label-1bit-k.ras.gz")))

    def test_big_endian_raster(self):
        self.assertVendorOutput(to_big_endian(fixture("test-label-1bit-k.ras.gz")))


class Commands(unittest.TestCase):
    raster = fixture("test-label-1bit-k.ras.gz")

    def test_default_setup_matches_vendor_layout(self):
        out = run_filter(self.raster).stdout
        self.assertEqual(
            setup_commands(out),
            [
                "SIZE 102 mm,152 mm",
                "REFERENCE 0,0",
                "DIRECTION 0,0",
                "GAP 3.0 mm,0.0 mm",
                "SET TEAR ON",
                "OFFSET 0 mm",
                "SPEED 4",
                "CLS",
            ],
        )
        self.assertIn(b"BITMAP 0,0,102,1218,1,", out)
        self.assertTrue(out.endswith(b"\r\nPRINT 1,1\r\n"))

    def test_darkness_sends_density(self):
        out = run_filter(self.raster, "Darkness=10").stdout
        self.assertIn("DENSITY 10", setup_commands(out))

    def test_options_are_clamped(self):
        cmds = setup_commands(
            run_filter(self.raster, "Darkness=99 PrintSpeed=1 GapHeight=-5").stdout
        )
        self.assertIn("DENSITY 15", cmds)
        self.assertIn("SPEED 1", cmds)
        self.assertIn("GAP 0.0 mm,0.0 mm", cmds)

    def test_non_numeric_options_fall_back(self):
        cmds = setup_commands(
            run_filter(self.raster, "Darkness=abc PrintSpeed=fast").stdout
        )
        self.assertFalse(any(c.startswith("DENSITY") for c in cmds))
        self.assertIn("SPEED 4", cmds)

    def test_option_text_cannot_inject_commands(self):
        out = run_filter(self.raster, "Darkness=8\r\nFORMFEED GapHeight=3;CUT").stdout
        self.assertNotIn(b"FORMFEED", out)
        self.assertNotIn(b"CUT", out)


class BadInput(unittest.TestCase):
    def test_rejects_non_raster(self):
        result = run_filter(b"%PDF-1.4 not a raster")
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"not CUPS raster", result.stderr)

    def test_rejects_truncated_raster(self):
        raster = fixture("test-label-1bit-k.ras.gz")
        result = run_filter(raster[: len(raster) // 2])
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"truncated", result.stderr)

    def test_rejects_empty_job(self):
        result = run_filter(b"3SaR")
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"no pages", result.stderr)


if __name__ == "__main__":
    unittest.main()
