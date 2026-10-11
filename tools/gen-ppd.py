#!/usr/bin/env python3
"""Generate ppd/phomemo-pm64d.ppd.

The PPD asks CUPS for 203 dpi, 1-bit black (cupsColorSpace 3) raster and
hands it to filter/rastertotspl. Edit SIZES or the option lists here and
re-run; don't edit the .ppd by hand.

    python3 tools/gen-ppd.py > ppd/phomemo-pm64d.ppd
"""

SIZES = [  # (PPD key, label, width pt, height pt); 72 pt = 1 inch
    ("w288h432", "4 x 6 in", 288, 432),
    ("w283h425", "100 x 150 mm", 283, 425),
    ("w288h288", "4 x 4 in", 288, 288),
    ("w288h216", "4 x 3 in", 288, 216),
    ("w288h144", "4 x 2 in", 288, 144),
    ("w216h144", "3 x 2 in", 216, 144),
    ("w144h72", "2 x 1 in", 144, 72),
]
DEFAULT_SIZE = "w288h432"

HEADER = [
    '*PPD-Adobe: "4.3"',
    '*FormatVersion: "4.3"',
    '*FileVersion: "1.0"',
    "*LanguageVersion: English",
    "*LanguageEncoding: ISOLatin1",
    '*PCFileName: "PM64DTSP.PPD"',
    '*Manufacturer: "Phomemo"',
    '*Product: "(PM64D)"',
    '*ModelName: "Phomemo PM64D open TSPL"',
    '*ShortNickName: "Phomemo PM64D TSPL"',
    '*NickName: "Phomemo PM64D, open TSPL filter"',
    '*PSVersion: "(3010.000) 0"',
    '*LanguageLevel: "3"',
    "*ColorDevice: False",
    "*DefaultColorSpace: Gray",
    "*FileSystem: False",
    '*Throughput: "1"',
    "*LandscapeOrientation: Plus90",
    "*TTRasterizer: Type42",
    '*1284DeviceID: "MFG:;CMD:XPP,XL;MDL:PM64D;CLS:PRINTER;"',
    "*cupsVersion: 2.4",
    "*cupsModelNumber: 0",
    "*cupsManualCopies: True",
    '*cupsFilter: "application/vnd.cups-raster 0 rastertotspl"',
]


def pick_one(lines, key, label, default, choices, order=20):
    """choices: list of (value, label, PostScript code)."""
    lines += [
        f"*OpenUI *{key}/{label}: PickOne",
        f"*OrderDependency: {order} AnySetup *{key}",
        f"*Default{key}: {default}",
    ]
    lines += [f'*{key} {value}/{text}: "{code}"' for value, text, code in choices]
    lines += [f"*CloseUI: *{key}", ""]


def main():
    lines = HEADER + [""]
    size_code = '<</PageSize[{} {}]/ImagingBBox null>>setpagedevice'
    for key in ("PageSize", "PageRegion"):
        pick_one(
            lines, key, "Media Size", DEFAULT_SIZE,
            [(k, label, size_code.format(w, h)) for k, label, w, h in SIZES],
            order=10,
        )
    lines.append(f"*DefaultImageableArea: {DEFAULT_SIZE}")
    lines += [f'*ImageableArea {k}/{label}: "0 0 {w} {h}"' for k, label, w, h in SIZES]
    lines.append(f"*DefaultPaperDimension: {DEFAULT_SIZE}")
    lines += [f'*PaperDimension {k}/{label}: "{w} {h}"' for k, label, w, h in SIZES]
    lines.append("")

    pick_one(
        lines, "Resolution", "Resolution", "203dpi",
        [("203dpi", "203 DPI",
          "<</HWResolution[203 203]/cupsBitsPerColor 1/cupsColorOrder 0"
          "/cupsColorSpace 3>>setpagedevice")],
        order=10,
    )
    # Option values are read by the filter, not by PostScript, so the code is
    # empty. "Default" sends no DENSITY and keeps the printer's own setting.
    pick_one(
        lines, "Darkness", "Darkness", "Default",
        [("Default", "Printer Default", "")]
        + [(str(i), str(i), "") for i in range(1, 16)],
    )
    pick_one(
        lines, "PrintSpeed", "Print Speed", "4",
        [(str(i), f"{i} in/s", "") for i in range(2, 7)],
    )
    pick_one(
        lines, "GapHeight", "Gap Between Labels", "3",
        [("0", "None (continuous)", "")]
        + [(str(i), f"{i} mm", "") for i in (2, 3, 4, 5, 6)],
    )
    print("\n".join(lines))


if __name__ == "__main__":
    main()
