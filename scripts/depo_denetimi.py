"""Depoya girmemesi gereken seyleri yakalar.

Bu bir olcum script'i DEGILDIR; bir kapidir. Yerelde ve surekli entegrasyonda
ayni komutla calisir:

    python scripts/depo_denetimi.py

Denetlenenler:
  - sir dosyalari (.env, kaggle.json, anahtar dosyalari)
  - model agirliklari (.pt, .onnx) ve veri kumesi
  - bagimlilik ve derleme ciktilari (node_modules, dist, __pycache__)
  - yerel mutlak yollar (/Users/..., /home/...)
  - sir gorunumlu satirlar (parola, token, API anahtari)
  - beklenmedik buyuk dosyalar
  - markdown belgelerindeki kirik depo ici baglantilar

Yalnizca GIT TARAFINDAN IZLENEN dosyalara bakar: yerelde duran veri kumesi ve
agirliklar zaten .gitignore icindedir ve denetimin konusu degildir.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROJE_KOK = Path(__file__).resolve().parent.parent

#: Hicbir kosulda izlenmemesi gereken yollar.
YASAK_DESENLER = (
    (r"(^|/)\.env$", "ortam dosyasi (sir icerir)"),
    (r"(^|/)\.env\.(?!example$)", "ortam dosyasi (sir icerir)"),
    (r"(^|/)kaggle\.json$", "Kaggle API kimligi"),
    (r"\.pt$", "PyTorch agirligi (buyuk ikili)"),
    (r"\.onnx$", "ONNX agirligi (buyuk ikili)"),
    (r"(^|/)node_modules/", "bagimlilik klasoru"),
    (r"(^|/)dist/", "derleme ciktisi"),
    (r"__pycache__/", "Python onbellegi"),
    (r"\.pyc$", "Python onbellegi"),
    (r"(^|/)\.DS_Store$", "macOS klasor meta dosyasi"),
    (r"(^|/)data/", "veri kumesi (lisansi ayri, boyutu buyuk)"),
    (r"\.sqlite3$", "yerel veritabani"),
    (r"\.(pem|key|p12|pfx)$", "anahtar/sertifika dosyasi"),
    (r"(^|/)\.playwright-mcp/", "tarayici otomasyonu gecici ciktisi"),
)

#: Metin icinde aranan sir gorunumlu desenler. Amac kesin teshis degil,
#: kazayla yapistirilmis bir degeri yakalamak.
SIR_DESENLERI = (
    (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
     "JWT gorunumlu deger"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "ozel anahtar"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS erisim anahtari"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "GitHub belirteci"),
    (re.compile(r"(?i)(password|parola|secret|api[_-]?key)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
     "gomulu sir gorunumlu atama"),
)

#: "Gomulu sir gorunumlu atama" kurali test ve olcum kodunda UYGULANMAZ.
#: Oralardaki degerler bilerek yazilmis, tek kullanimlik fixture parolalaridir:
#: bir test kullanicisinin parolasi olmadan kimlik dogrulama testi yazilamaz.
#: Geri kalan kurallar (JWT, ozel anahtar, bulut belirteci) HER YERDE gecerli
#: kalir -- asil yakalanmak istenen sey odur.
FIXTURE_YOLLARI = re.compile(
    r"(^|/)(tests?|conftest\.py)(/|$)|(^|/)test_[^/]+\.py$|(^|/)scripts/\d+_[^/]+\.py$"
)

#: Yerel mutlak yollar. Depodaki hicbir dosya belirli bir makinenin ev dizinine
#: atif yapmamali; /tmp ve /app gibi ortamdan bagimsiz yollar serbesttir.
YEREL_YOL = re.compile(r"/(Users|home)/[A-Za-z0-9._-]+/")

#: Metin olarak taranacak uzantilar.
METIN_UZANTILARI = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".yml", ".yaml",
    ".html", ".css", ".sh", ".cfg", ".ini", ".txt", ".conf", ".example",
}

#: Icerik taramasi disinda tutulan dosyalar. Ikisi de kendi kural listesi
#: yuzunden eslesiyor: biri kurallarin tanimlandigi dosya, digeri o kurallarin
#: CALISTIGINI kanitlamak icin ornek JWT ve ornek ozel anahtar metni tasiyan
#: test dosyasi. Ucuncusu, olcum kayitlarinin komut sutunlari.
TARAMA_DISI = {
    "scripts/depo_denetimi.py",
    "scripts/tests/test_depo_denetimi.py",
    "reports/README.md",
}

#: Tirnak icindeki deger bir degiskenden veya komut ciktisindan geliyorsa
#: ("$VAR", "$(komut)", "${VAR}") bu bir GOMULU sir degildir; okuma islemidir.
DEGISKENDEN_OKUMA = re.compile(r"[:=]\s*['\"]?\$")

#: Buyuk dosya siniri. Olcum CSV'leri ve rapor gorselleri bunun altinda.
BUYUK_DOSYA_BAYT = 6 * 1024 * 1024


def izlenen_dosyalar() -> list[str]:
    cikti = subprocess.run(
        ["git", "ls-files"], cwd=PROJE_KOK, capture_output=True, text=True, check=True
    )
    return [s for s in cikti.stdout.splitlines() if s]


def yasak_yollari_bul(dosyalar: list[str]) -> list[str]:
    bulgular = []
    for yol in dosyalar:
        for desen, aciklama in YASAK_DESENLER:
            if re.search(desen, yol):
                bulgular.append(f"{yol}: {aciklama} izlenmemeli")
    return bulgular


def icerik_denetle(dosyalar: list[str]) -> list[str]:
    bulgular = []
    for yol in dosyalar:
        if yol in TARAMA_DISI or Path(yol).suffix.lower() not in METIN_UZANTILARI:
            continue
        tam = PROJE_KOK / yol
        try:
            metin = tam.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        fixture_mi = bool(FIXTURE_YOLLARI.search(yol))
        for satir_no, satir in enumerate(metin.splitlines(), start=1):
            for desen, aciklama in SIR_DESENLERI:
                if aciklama == "gomulu sir gorunumlu atama" and (
                    fixture_mi or DEGISKENDEN_OKUMA.search(satir)
                ):
                    continue
                if desen.search(satir):
                    bulgular.append(f"{yol}:{satir_no}: {aciklama}")
            if YEREL_YOL.search(satir):
                bulgular.append(f"{yol}:{satir_no}: yerel mutlak yol")
    return bulgular


#: Markdown baglantisi: [metin](hedef). Yalnizca DEPO ICI goreli baglantilar
#: denetlenir; http(s), mailto ve yalnizca capa (#...) olanlar atlanir.
MD_BAGLANTI = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def baglantilari_denetle(dosyalar: list[str]) -> list[str]:
    """Markdown dosyalarindaki depo ici baglantilarin hedefi var mi.

    README GitHub'in vitrinidir; kirik bir baglanti orada en gorunur yerde
    durur. Dis adresler AGA CIKILMADAN dogrulanamayacagi icin denetlenmez."""
    bulgular = []
    for yol in dosyalar:
        if not yol.endswith(".md"):
            continue
        tam = PROJE_KOK / yol
        try:
            metin = tam.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        for satir_no, satir in enumerate(metin.splitlines(), start=1):
            for hedef in MD_BAGLANTI.findall(satir):
                if hedef.startswith(("http://", "https://", "mailto:", "#", "<")):
                    continue
                # Capa kismi dosya adinin parcasi degildir.
                dosya_kismi = hedef.split("#", 1)[0]
                if not dosya_kismi:
                    continue
                aday = (tam.parent / dosya_kismi).resolve()
                if not aday.exists():
                    bulgular.append(f"{yol}:{satir_no}: kirik baglanti -> {hedef}")
    return bulgular


def buyuk_dosyalari_bul(dosyalar: list[str], sinir=BUYUK_DOSYA_BAYT) -> list[str]:
    bulgular = []
    for yol in dosyalar:
        tam = PROJE_KOK / yol
        if not tam.is_file():
            continue
        boyut = tam.stat().st_size
        if boyut > sinir:
            bulgular.append(f"{yol}: {boyut / 1024 / 1024:.1f} MB — beklenmedik buyuklukte")
    return bulgular


def main() -> int:
    ayristirici = argparse.ArgumentParser(description=__doc__)
    ayristirici.add_argument(
        "--sinir-mb", type=float, default=BUYUK_DOSYA_BAYT / 1024 / 1024,
        help="Buyuk dosya esigi (MB).",
    )
    arg = ayristirici.parse_args()
    sinir = int(arg.sinir_mb * 1024 * 1024)

    dosyalar = izlenen_dosyalar()
    bulgular = (
        yasak_yollari_bul(dosyalar)
        + icerik_denetle(dosyalar)
        + baglantilari_denetle(dosyalar)
        + buyuk_dosyalari_bul(dosyalar, sinir)
    )

    print(f"Izlenen dosya: {len(dosyalar)}")
    if bulgular:
        print(f"\n{len(bulgular)} bulgu:\n")
        for bulgu in bulgular:
            print(f"  - {bulgu}")
        return 1

    print("Temiz: yasak yol, sir gorunumlu satir, yerel mutlak yol, kirik "
          "baglanti veya beklenmedik buyuk dosya bulunmadi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
