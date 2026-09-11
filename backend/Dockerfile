FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# GeoDjango'nun PostGIS backend'i icin zorunlu sistem kutuphaneleri.
RUN apt-get update && apt-get install -y --no-install-recommends \
        binutils \
        libproj-dev \
        gdal-bin \
        libgdal-dev \
        libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

# Duman testi: GDAL kurulmadiysa imaj burada patlasin, calisma aninda degil.
RUN gdalinfo --version && geos-config --version

WORKDIR /app

# Once bagimliliklar, sonra kod: kod degisince pip katmani yeniden calismasin.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
CMD ["/app/entrypoint.sh"]
