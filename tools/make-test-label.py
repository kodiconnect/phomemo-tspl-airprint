#!/usr/bin/env python3
"""Write the 4x6 in test label PDF used by the tests (no dependencies).

    python3 tools/make-test-label.py tests/fixtures/test-label.pdf

A border, two lines of text and a solid square in the lower left, so
inverted, mirrored or shifted output is obvious on paper.
"""
import sys

CONTENT = b"""4 w 6 6 276 420 re S
BT /F1 28 Tf 20 380 Td (PM64D TEST) Tj ET
BT /F1 14 Tf 20 350 Td (open TSPL filter) Tj ET
0 g 20 40 120 120 re f
"""


def main(path):
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 288 432] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(CONTENT) + CONTENT + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    with open(path, "wb") as f:
        f.write(out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "test-label.pdf")
