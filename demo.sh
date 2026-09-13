#!/usr/bin/env bash
#
# Gozcu -- tek komutluk demo.
#
#   ./demo.sh              tum yigini kurar, demo verisini yukler, adresi yazar
#   ./demo.sh --sentetik   veri kumesi/model olsa bile sentetik modu zorlar (hizli)
#   ./demo.sh --sil        demo verisini siler (gercek veriye dokunmaz)
#   ./demo.sh --durdur     servisleri durdurur (veri kalir)
#
# Bu betik GERCEK BIR INTERNET DAGITIMI YAPMAZ. Her sey yerel makinede, duz
# HTTP uzerinde, 127.0.0.1'e bagli olarak calisir.

set -euo pipefail

KOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$KOK"

ADRES="http://localhost:8080"
KAYNAK="auto"
EYLEM="kur"

for arg in "$@"; do
  case "$arg" in
    --sentetik) KAYNAK="sentetik" ;;
    --gercek)   KAYNAK="gercek" ;;
    --sil)      EYLEM="sil" ;;
    --durdur)   EYLEM="durdur" ;;
    -h|--help)  sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Bilinmeyen secenek: $arg" >&2; exit 2 ;;
  esac
done

bilgi() { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
uyari() { printf '\033[1;33m!!\033[0m %s\n' "$1"; }
hata()  { printf '\033[1;31mHATA\033[0m %s\n' "$1" >&2; exit 1; }

# .env icindeki bir anahtari gunceller, yoksa ekler. Anahtar ve deger ortam
# degiskeni olarak gelir; boylece kabuk tirnaklamasi degeri bozamaz.
ENV_YAZ='
import os
from pathlib import Path
anahtar = "DEMO_PAROLA"
deger = os.environ["DEMO_PAROLA"]
yol = Path(".env")
satirlar = yol.read_text(encoding="utf-8").splitlines()
bulundu = False
for i, satir in enumerate(satirlar):
    if satir.startswith(anahtar + "="):
        satirlar[i] = anahtar + "=" + deger
        bulundu = True
if not bulundu:
    satirlar.append(anahtar + "=" + deger)
yol.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
'

command -v docker >/dev/null || hata "docker bulunamadi. Docker Desktop kurulu ve acik olmali."
docker info >/dev/null 2>&1 || hata "Docker calismiyor. Docker Desktop'i acin."

# --- .env: yoksa ORNEKTEN uretilir, sir DEPOYA GIRMEZ -----------------------
if [ ! -f .env ]; then
  bilgi ".env yok; .env.example'dan uretiliyor."
  cp .env.example .env
  GIZLI="$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')"
  DB_PAROLA="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"
  # BSD ve GNU sed farkli -i sozdizimi istiyor; gecici dosyayla ikisinde de calisir.
  python3 - "$GIZLI" "$DB_PAROLA" <<'PY'
import sys
from pathlib import Path
gizli, db_parola = sys.argv[1], sys.argv[2]
yol = Path(".env")
satirlar = []
for satir in yol.read_text(encoding="utf-8").splitlines():
    if satir.startswith("DJANGO_SECRET_KEY="):
        satir = f"DJANGO_SECRET_KEY={gizli}"
    elif satir.startswith("POSTGRES_PASSWORD="):
        satir = f"POSTGRES_PASSWORD={db_parola}"
    satirlar.append(satir)
yol.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
PY
  bilgi "Yeni DJANGO_SECRET_KEY ve POSTGRES_PASSWORD uretildi (.env dosyasi Git'e girmez)."
fi

# --- Demo parolasi: .env'de yoksa URETILIR ve oraya yazilir ------------------
# Depoya sabit bir demo parolasi KOYULMAZ. Uretilen deger .env icinde kalir,
# .env de Git'e girmez; ikinci kosuda ayni parola yeniden kullanilir.
if ! grep -qE '^DEMO_PAROLA=.+' .env 2>/dev/null; then
  YENI_PAROLA="demo-$(python3 -c 'import secrets; print(secrets.token_urlsafe(9))')"
  DEMO_PAROLA="$YENI_PAROLA" python3 -c "$ENV_YAZ"
  bilgi "Demo parolasi uretildi ve .env dosyasina yazildi."
fi
DEMO_PAROLA="$(grep -E '^DEMO_PAROLA=' .env | head -1 | cut -d= -f2-)"

if [ "$EYLEM" = "durdur" ]; then
  bilgi "Servisler durduruluyor."
  docker compose down
  echo "Veritabani ve yuklenen kareler duruyor. Tamamen silmek icin: docker compose down -v"
  exit 0
fi

if [ "$EYLEM" = "sil" ]; then
  bilgi "Demo verisi siliniyor (yalnizca demo gorevleri)."
  docker compose exec -T web python manage.py demo_kur --sil
  docker compose exec -T web python manage.py demo_konum_uret --sil || true
  exit 0
fi

# --- kurulum ----------------------------------------------------------------
bilgi "Imajlar derleniyor (ilk kosuda birkac dakika surebilir)."
docker compose build

bilgi "Servisler baslatiliyor."
docker compose up -d

bilgi "Saglik kontrolu bekleniyor."
for _ in $(seq 1 60); do
  DURUM="$(docker compose ps --format '{{.Service}} {{.Health}}' 2>/dev/null || true)"
  if echo "$DURUM" | grep -q '^web healthy'; then
    break
  fi
  sleep 3
done
echo "$DURUM" | grep -q '^web healthy' || {
  docker compose logs --tail 40 web
  hata "web servisi saglikli duruma gelmedi."
}

bilgi "Demo verisi kuruluyor (kaynak: $KAYNAK)."
docker compose exec -T web python manage.py demo_kur --kaynak "$KAYNAK"

echo
bilgi "Hazir. Tarayicida acin: $ADRES"
echo
echo "  Kullanici adi : demo            (operator -- inceleyebilir, tarama baslatabilir)"
echo "  Izleyici      : demo_izleyici   (salt okunur)"
echo "  Parola        : $DEMO_PAROLA"
echo
uyari "Demo verisidir. Koordinatlar sentetiktir, gercek GPS degildir."
uyari "Tespitler operator kararinin yerine gecmez. Egitim ve arastirma prototipidir."
echo
echo "Kapatmak icin : ./demo.sh --durdur"
echo "Demoyu silmek : ./demo.sh --sil"
