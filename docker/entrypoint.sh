#!/bin/sh
# Render cupsd.conf, start cupsd, (re)create the queue(s), then keep cupsd in
# the foreground. Queues are rebuilt on every start, so the container holds
# no state that a rebuild would lose.
#
#   PRINTER_NAME      queue name, shared over IPP/AirPrint   (PM64D)
#   PRINTER_URI       where jobs go                          (file:///dev/usb/lp0)
#   PRINTER_INFO      name shown to iOS/macOS                (Phomemo PM64D label printer)
#   PRINTER_LOCATION  location text                          (empty)
#   PAGE_SIZE         default PPD page size                  (w288h432 = 4x6 in)
#   CUPS_ALLOW        extra networks allowed to print, space separated,
#                     e.g. "100.64.0.0/10" for a Tailscale tailnet
#
# Optional vendor reference queue: if /opt/vendor/rastertolabeltspl and
# /opt/vendor/PM64D.ppd exist (you supply them, see tools/compare-with-vendor.sh),
# an unshared "<PRINTER_NAME>-vendor" queue is added for comparing output.
set -e

PRINTER_NAME=${PRINTER_NAME:-PM64D}
PRINTER_URI=${PRINTER_URI:-file:///dev/usb/lp0}
PRINTER_INFO=${PRINTER_INFO:-Phomemo PM64D label printer}
PRINTER_LOCATION=${PRINTER_LOCATION:-}
PAGE_SIZE=${PAGE_SIZE:-w288h432}

nets=""
for net in ${CUPS_ALLOW:-}; do
  case "$net" in
    *[!0-9A-Fa-f:./]*) echo "entrypoint: ignoring invalid CUPS_ALLOW entry: $net" >&2 ;;
    *) nets="$nets $net" ;;
  esac
done
while IFS= read -r line; do
  if [ "$line" = "@EXTRA_ALLOW@" ]; then
    for net in $nets; do
      printf '  Allow from %s\n' "$net"
    done
  else
    printf '%s\n' "$line"
  fi
done < /etc/cups/cupsd.conf.in > /etc/cups/cupsd.conf

cupsd -f &
pid=$!

for _ in $(seq 1 30); do
  lpstat -r >/dev/null 2>&1 && break
  sleep 1
done

lpadmin -p "$PRINTER_NAME" -E \
  -v "$PRINTER_URI" \
  -P /usr/share/cups/model/label/phomemo-pm64d.ppd \
  -D "$PRINTER_INFO" \
  -L "$PRINTER_LOCATION" \
  -o printer-is-shared=true \
  -o PageSize="$PAGE_SIZE"
lpadmin -d "$PRINTER_NAME"
queues="$PRINTER_NAME"

if [ -f /opt/vendor/rastertolabeltspl ] && [ -f /opt/vendor/PM64D.ppd ]; then
  install -m 755 /opt/vendor/rastertolabeltspl /usr/lib/cups/filter/rastertolabeltspl
  lpadmin -p "${PRINTER_NAME}-vendor" -E \
    -v "$PRINTER_URI" \
    -P /opt/vendor/PM64D.ppd \
    -D "$PRINTER_INFO (vendor filter, reference)" \
    -o printer-is-shared=false \
    -o PageSize="$PAGE_SIZE"
  queues="$queues ${PRINTER_NAME}-vendor"
fi

for q in $queues; do
  cupsenable "$q"
  cupsaccept "$q"
done
echo "entrypoint: ready, queues: $queues" >&2

wait "$pid"
