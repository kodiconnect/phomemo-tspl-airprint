#!/bin/sh
# Compare filter/rastertotspl with the vendor's closed filter, for checking
# the open driver against another Phomemo/Labelife model.
#
#   sh tools/compare-with-vendor.sh [PPD model name, default PM64D]
#
# Downloads the vendor's Linux driver (the archived copy nixpkgs pins),
# verifies its sha256, and unpacks the x86_64 filter and the model's PPD into
# ./vendor/ (git-ignored: the vendor files are proprietary and must not be
# committed). Both filters then run inside the Docker image with no network,
# on the test rasters, and their outputs are compared byte for byte.
#
# The vendor filter expects the raster its own PPD asks for (8-bit W for the
# PM64D), so the vendor run uses that; ours runs on the same raster.
set -eu

model=${1:-PM64D}
url=https://web.archive.org/web/20260804054912id_/https://oss.qu-in.ltd/Labelife/Label_Printer_Driver_Linux.zip
sha256=509db01d0965be3d6763faf0ac8370073c8240ffcac304d2ae5cae35782eab9a
image=phomemo-tspl-airprint:compare

cd "$(dirname "$0")/.."
mkdir -p vendor
if [ ! -f vendor/rastertolabeltspl ] || [ ! -f "vendor/$model.ppd" ]; then
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  curl -fsSL -o "$tmp/driver.zip" "$url"
  echo "$sha256  $tmp/driver.zip" | sha256sum -c -
  unzip -qj "$tmp/driver.zip" -d "$tmp"
  tar -xzf "$tmp"/LabelPrinter-*.tar.gz -C "$tmp"
  cp "$tmp"/LabelPrinter-*/x86_64/rastertolabeltspl vendor/
  if ! cp "$tmp/LabelPrinter-"*"/ppds/$model.ppd" vendor/; then
    echo "no $model.ppd in the vendor driver; available:" >&2
    ls "$tmp"/LabelPrinter-*/ppds/ | sed 's/\.ppd$//' >&2
    exit 1
  fi
fi

docker build -q -t "$image" . >/dev/null
docker run --rm --network none \
  -v "$PWD/vendor:/opt/vendor:ro" \
  -v "$PWD/tests/fixtures:/fixtures:ro" \
  -e MODEL="$model" \
  --entrypoint sh "$image" -c '
    set -eu
    install -m 755 /opt/vendor/rastertolabeltspl /usr/lib/cups/filter/
    cd /tmp
    cupsfilter -p "/opt/vendor/$MODEL.ppd" -m application/vnd.cups-raster \
      /fixtures/test-label.pdf > vendor.ras 2>/dev/null
    PPD="/opt/vendor/$MODEL.ppd" /usr/lib/cups/filter/rastertolabeltspl \
      1 u t 1 "" vendor.ras > vendor.tspl 2>/dev/null
    PPD=/usr/share/cups/model/label/phomemo-pm64d.ppd \
      /usr/lib/cups/filter/rastertotspl 1 u t 1 "" vendor.ras > open.tspl
    sha256sum vendor.tspl open.tspl
    if cmp -s vendor.tspl open.tspl; then
      echo "MATCH: open filter output is identical to the vendor filter for $MODEL"
    else
      echo "DIFFERENT for $MODEL. Setup commands:"
      for f in vendor open; do
        printf "  %-6s " "$f:"; head -c 300 "$f.tspl" | tr "\r\n" " |" | sed "s/BITMAP.*/BITMAP .../"; echo
      done
      exit 1
    fi
  '
