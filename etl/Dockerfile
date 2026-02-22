FROM ghcr.io/osgeo/gdal:ubuntu-small-3.10.1
# Using GHCR official OSGeo GDAL image (Docker Hub deprecated/migrated)
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /work
RUN apt-get update && apt-get install -y python3-pip python3-venv ca-certificates curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /work/requirements.txt
RUN python3 -m venv /opt/venv && \
	/opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
	/opt/venv/bin/pip install --no-cache-dir -r /work/requirements.txt
ENV PATH="/opt/venv/bin:$PATH"
COPY etl_healthcheck.sh /usr/local/bin/etl_healthcheck.sh
RUN chmod +x /usr/local/bin/etl_healthcheck.sh
CMD ["sleep", "infinity"]
