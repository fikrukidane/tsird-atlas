FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
ENV MAPFILE=/mapfiles/tsird.map

RUN apt-get update && \
    apt-get install -y --no-install-recommends apache2 mapserver-bin cgi-mapserver ca-certificates curl && \
    a2enmod cgi && \
    rm -rf /var/lib/apt/lists/*

COPY apache.conf /etc/apache2/sites-available/000-default.conf
COPY mapfiles /mapfiles
RUN mkdir -p /var/www/html && echo "OK" > /var/www/html/health
EXPOSE 8000
CMD ["/usr/sbin/apache2ctl", "-D", "FOREGROUND"]
