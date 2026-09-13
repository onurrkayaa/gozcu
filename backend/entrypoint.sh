#!/bin/sh
# Uretim benzeri baslangic.
#
# runserver BURADA KULLANILMAZ: Django'nun gelistirme sunucusu tek is parcacikli
# calisir, statik dosya servisi gelistirme icindir ve Django belgeleri onu
# uretimde kullanmamayi acikca soyler. Gelistirme kosumu icin
# docker-compose.dev.yml override'i runserver'a doner.
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Isci sayisi ortamdan ayarlanabilir. Varsayilan 3: tek CPU'lu bir dizustunde
# bile istek sirasinda bekleme yaratmayacak kadar, bellegi sismeyecek kadar az.
exec gunicorn gozcu_api.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_ISCI:-3}" \
    --timeout "${GUNICORN_ZAMAN_ASIMI:-120}" \
    --access-logfile - \
    --error-logfile -
