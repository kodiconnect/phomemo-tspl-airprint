# CUPS + AirPrint print server for Phomemo / Labelife TSPL label printers,
# using the open filter in filter/rastertotspl. No vendor code is included;
# libcupsimage2 is only for the optional vendor reference queue.
FROM debian:bookworm-slim

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      cups cups-filters cups-client libavahi-client3 python3 \
      libcupsimage2 \
 && rm -rf /var/lib/apt/lists/* \
 && echo "FileDevice Yes" >> /etc/cups/cups-files.conf

COPY filter/rastertotspl /usr/lib/cups/filter/rastertotspl
COPY ppd/phomemo-pm64d.ppd /usr/share/cups/model/label/phomemo-pm64d.ppd
COPY docker/cupsd.conf.in /etc/cups/cupsd.conf.in
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod 755 /usr/lib/cups/filter/rastertotspl /entrypoint.sh \
 && chmod 644 /usr/share/cups/model/label/phomemo-pm64d.ppd

EXPOSE 631
ENTRYPOINT ["/entrypoint.sh"]
