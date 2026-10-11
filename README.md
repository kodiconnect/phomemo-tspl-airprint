# phomemo-tspl-airprint

Print to a USB-connected Phomemo label printer from an iPhone, iPad or Mac
using the normal **Print** menu, no Labelife app needed.

The Phomemo PM64D (and similar Labelife printers) only print over Bluetooth
through the vendor's app, so they never show up in the iOS or macOS print
dialog. This project plugs the printer into a Linux box by USB and shares it
over your network as an AirPrint printer, using a small **open-source driver**
(`filter/rastertotspl`, ~250 lines of Python) instead of the vendor's
closed-source binary.

```
iPhone / Mac ──AirPrint (IPP)──▶ CUPS in Docker ──▶ rastertotspl ──USB──▶ printer
                                  (on your Linux box)   (TSPL commands)
```

## Do I need the vendor's driver or anything private?

No. Everything needed to print is in this repo. The vendor driver is only used
by an optional comparison script (see [Checking against the vendor driver](#checking-against-the-vendor-driver)),
and it is never included in this repository.

## Supported printers

| Printer | USB ID | Status |
|---|---|---|
| Phomemo PM64D | `2e3c:5760` (reports as "QIN LabelPrinter") | Verified: output is byte-identical to the vendor driver |

Other Phomemo / Labelife printers that speak TSPL may work. If you have one,
run the comparison script and open an issue or PR with the result.

## What you need

- A Linux machine that stays on (a NAS such as Unraid, or a home server),
  with Docker and Docker Compose. Tested on x86_64. The driver is plain
  Python on a Debian image, so arm64 (e.g. a Raspberry Pi) should work too,
  but is untested.
- `avahi-daemon` running on that machine, so iPhones and Macs can discover
  the printer. Most distros and Unraid run it already.
- Port 631 free on the host, so no other CUPS is running there.
- A **USB-A to USB-C** cable. A USB-C to USB-C cable from a computer's USB-C
  port may not work at all (see [Troubleshooting](#troubleshooting)).

## Setup

### 1. Connect the printer

Switch the printer on and connect it by USB. Then check that Linux sees it:

```sh
lsusb | grep -i 2e3c        # expect: ID 2e3c:5760 QIN LabelPrinter
ls -l /dev/usb/lp0          # the printer device
```

If `lsusb` shows the printer but `/dev/usb/lp0` is missing, load the kernel's
USB printer driver: `sudo modprobe usblp`.

### 2. Check the host

```sh
pgrep -a avahi-daemon       # should print a running avahi-daemon
ss -ltn | grep ':631 '      # should print nothing (port 631 free)
```

If a host CUPS already uses port 631, stop it (`sudo systemctl disable --now cups`)
or run this container on a different machine.

### 3. Start the print server

```sh
git clone https://github.com/kodiconnect/phomemo-tspl-airprint.git
cd phomemo-tspl-airprint
docker compose up -d --build
docker logs label-printer      # ends with: entrypoint: ready, queues: PM64D
```

Settings live in the `environment:` block of `compose.yaml`:

| Variable | Default | Meaning |
|---|---|---|
| `PRINTER_NAME` | `PM64D` | Queue name |
| `PRINTER_INFO` | `Phomemo PM64D label printer` | Name shown on iPhone/Mac |
| `PRINTER_LOCATION` | empty | Location text |
| `PAGE_SIZE` | `w288h432` (4 x 6 in) | Default label size, see the PPD for others |
| `CUPS_ALLOW` | empty | Extra networks allowed to print, e.g. `100.64.0.0/10` for Tailscale. The host's own subnets are always allowed. |

### 4. Print a test label

```sh
docker exec -i label-printer lp -d PM64D < tests/fixtures/test-label.pdf
```

You should get a 4 x 6 label with a border, "PM64D TEST" and a black square
in the lower left.

### 5. Add it on your devices

- **iPhone / iPad:** Share → Print → Printer → *Phomemo PM64D label printer*.
- **Mac:** System Settings → Printers & Scanners → Add Printer → pick it from
  the list. Use paper size 4 x 6.
- **Anything else, or if it isn't discovered:** add an IPP printer at
  `ipp://<host-ip>:631/printers/PM64D`.

### Unraid

Put the repo in `/mnt/user/appdata/phomemo-tspl-airprint` and run
`docker compose up -d --build` there (Unraid ships Docker Compose). Unraid's
own avahi-daemon handles discovery. `restart: unless-stopped` brings it back
after reboots.

## Printer options

Chosen per job in the print dialog, or as queue defaults with
`docker exec label-printer lpadmin -p PM64D -o Name=Value`:

| Option | Values | Default |
|---|---|---|
| Media Size (`PageSize`) | 4x6, 100x150 mm, 4x4, 4x3, 4x2, 3x2, 2x1 in | 4 x 6 in |
| Darkness | Printer Default, 1–15 | Printer Default (keeps the printer's own setting) |
| Print Speed | 2–6 in/s | 4 |
| Gap Between Labels | None (continuous), 2–6 mm | 3 mm |

Add sizes in `tools/gen-ppd.py` and regenerate the PPD:
`python3 tools/gen-ppd.py > ppd/phomemo-pm64d.ppd`.

## Troubleshooting

- **The printer isn't in `lsusb` at all.** It's a cable or port problem, not
  a driver one: Linux lists every USB device before any driver loads. Use a
  USB-A to USB-C cable in a USB-A port. Cheap devices often leave out the
  resistors a USB-C port needs to switch on, so they stay invisible on a
  USB-C to USB-C cable. Also check that the cable carries data, not just power.
- **Nothing appears on the iPhone.** Check `avahi-browse -rt _ipp._tcp` on the
  host lists the printer, and that the phone is on the same network.
- **Faint or blank labels.** These are direct-thermal labels; check they are
  loaded the right way up, then raise Darkness.
- **Labels drift across the gaps.** Set Gap Between Labels to match your
  labels, or calibrate the printer from its own menu.
- **Logs:** `docker logs label-printer` and
  `docker exec label-printer cat /var/log/cups/error_log`.

## Security

- The container gets the `/dev/usb` printer devices only (cgroup rule for
  character major 180), plus the host D-Bus socket for avahi. It uses host
  networking to listen on port 631.
- Printing is allowed from the host's own subnets plus `CUPS_ALLOW`. The CUPS
  web admin and all queue management are limited to inside the container.
- Don't expose port 631 to the internet.
- The PM64D presents a single USB interface of class 07 (printer), with no
  keyboard/HID or storage interfaces. Check yours with
  `lsusb -v -d 2e3c:5760 | grep bInterfaceClass`.

## How it works

CUPS receives the job (PDF, image or Apple raster from AirPrint), renders it
to a 203 dpi 1-bit bitmap at the label size, and runs `filter/rastertotspl`,
which turns each page into [TSPL](https://www.tscprinters.com/), the plain-text
command language of most thermal label printers:

```
SIZE 102 mm,152 mm
REFERENCE 0,0
DIRECTION 0,0
GAP 3.0 mm,0.0 mm
SET TEAR ON
OFFSET 0 mm
SPEED 4
CLS
BITMAP 0,0,102,1218,1,<1218 rows x 102 bytes>
PRINT 1,1
```

On the PM64D a **0 bit is a black dot and 1 is white**, even in BITMAP mode
1. The vendor driver's output was the reference for that and for the command
layout.

## Checking against the vendor driver

`tools/compare-with-vendor.sh [MODEL]` downloads the vendor's Linux driver
(the archived copy pinned by nixpkgs, sha256-verified) into the git-ignored
`vendor/` folder, then runs both filters inside the Docker image with
networking disabled and compares their output byte for byte. It needs an
x86_64 host. `MODEL` is a PPD name from the vendor driver, `PM64D` by default.

To keep the vendor filter as a hidden reference queue (`PM64D-vendor`) next
to the open one, uncomment the `./vendor:/opt/vendor:ro` volume in
`compose.yaml`.

## Development

```sh
python3 -m unittest discover -s tests -v   # filter tests, no CUPS needed
sh tests/smoke.sh                          # full CUPS pipeline in Docker, no printer needed
```

The tests check the filter's output against the vendor driver's hash for the
same input, in 1-bit, 8-bit, compressed and big-endian raster, plus option
handling and bad input.

## Not affiliated

Not affiliated with or endorsed by Phomemo or Labelife. Product names are
trademarks of their owners.

## License

MIT, see [LICENSE](LICENSE).
