#!/bin/sh
# End-to-end check without a printer: build the image, start cupsd with the
# queue pointed at a file, print tests/fixtures/test-label.pdf through the
# whole CUPS pipeline, and check the TSPL that lands in the file.
#
#   sh tests/smoke.sh
set -eu

cd "$(dirname "$0")/.."
image=phomemo-tspl-airprint:smoke
name=phomemo-tspl-smoke-$$
out=$(mktemp -d)
chmod 777 "$out"
tspl=$(mktemp)
trap 'docker rm -f "$name" >/dev/null 2>&1 || true; rm -rf "$out" "$tspl"' EXIT

docker build -q -t "$image" . >/dev/null
docker run -d --name "$name" --network none \
  -e PRINTER_URI=file:///out/label.tspl \
  -v "$out":/out \
  "$image" >/dev/null

for _ in $(seq 1 30); do
  docker logs "$name" 2>&1 | grep -q "entrypoint: ready" && break
  sleep 1
done
docker exec -i "$name" lp -d PM64D -t smoke < tests/fixtures/test-label.pdf

for _ in $(seq 1 60); do
  docker exec "$name" test -s /out/label.tspl \
    && ! docker exec "$name" lpstat -o | grep -q . && break
  sleep 1
done

# cupsd writes the file as root with private permissions, so read it from
# inside the container rather than from the (possibly non-root) host.
docker exec "$name" cat /out/label.tspl > "$tspl"
head=$(head -c 300 "$tspl" | tr -d '\r' | sed -n '1,9p')
printf '%s\n' "$head"
printf '%s\n' "$head" | grep -qx 'SIZE 102 mm,152 mm'
printf '%s\n' "$head" | grep -q '^BITMAP 0,0,102,1218,1,'
tail -c 12 "$tspl" | grep -q 'PRINT 1,1'
echo "sha256: $(sha256sum "$tspl" | cut -d' ' -f1)"
echo "smoke: OK"
