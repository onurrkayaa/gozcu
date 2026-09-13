"""rapor/MULAKAT_NOTLARI.md dosyasindan PDF uretir.

Olcum yapmaz, yeni metin uretmez: yalnizca mevcut markdown'i bicimlendirir.
Bicimlendirme mantigi 06_rapor_uret.py icindedir ve BURADA KOPYALANMAZ --
font kaydi, markdown ayristirma ve sayfa duzeni oradan cagrilir. Boylece iki
PDF (rapor ve mulakat notlari) ayni bicime sahip olur ve bir duzeltme tek
yerde yapilir.

Kosu:
    python scripts/28_mulakat_pdf.py
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

PROJE_KOK = Path(__file__).resolve().parent.parent
SCRIPT_DIZIN = PROJE_KOK / "scripts"
sys.path.insert(0, str(SCRIPT_DIZIN))

# Dosya adi rakamla basladigi icin normal import edilemez; yoldan yukluyoruz.
_spec = importlib.util.spec_from_file_location(
    "rapor_uret", SCRIPT_DIZIN / "06_rapor_uret.py"
)
rapor_uret = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rapor_uret)

VARSAYILAN_KAYNAK = PROJE_KOK / "rapor" / "MULAKAT_NOTLARI.md"
VARSAYILAN_HEDEF = PROJE_KOK / "rapor" / "MULAKAT_NOTLARI.pdf"


def main() -> None:
    ayristirici = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayristirici.add_argument("--kaynak", type=Path, default=VARSAYILAN_KAYNAK)
    ayristirici.add_argument("--cikti", type=Path, default=VARSAYILAN_HEDEF)
    arg = ayristirici.parse_args()

    if not arg.kaynak.is_file():
        raise SystemExit(f"Kaynak bulunamadi: {arg.kaynak}")

    if not rapor_uret.fontlari_kaydet():
        raise SystemExit(
            "Sistemde gomulebilir TrueType font bulunamadi; Turkce karakterler "
            "bozuk cikacagi icin PDF uretilmedi."
        )

    metin = arg.kaynak.read_text(encoding="utf-8")
    hedef = rapor_uret.pdf_uret(metin, arg.cikti, [arg.kaynak.parent, PROJE_KOK])
    print(f"PDF: {hedef}  ({len(metin.split())} kelime)")


if __name__ == "__main__":
    main()
