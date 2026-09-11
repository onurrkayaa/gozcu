"""Egitimsiz yolo11n'in SADECE test bolumu (157 goruntu) uzerindeki taban cizgisi.

Hafta 0'da olculen 0,2663 recall train+valid+test birlestirilmis kume uzerindeydi;
egitimden sonra sadece test olculecegi icin o sayi karsilastirma tabani olamaz.
Bu script ayni protokolu sadece test bolumune uygular ve egitim sonrasi
karsilastirilacak tabani uretir.

Olcum mantigi burada TEKRARLANMAZ: 01_taban_cizgisi.py oldugu gibi calistirilir.
Ayni protokolun iki kopyasi zamanla birbirinden kayar; tek kopya kalsin diye bu
dosya yalnizca protokol parametrelerini sabitleyen ince bir sarmalayicidir.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

SCRIPT_DIZIN = Path(__file__).resolve().parent
PROJE_KOK = SCRIPT_DIZIN.parent
OLCUM_SCRIPTI = SCRIPT_DIZIN / "01_taban_cizgisi.py"

# --- Hafta 0 olcum protokolu. Bu degerler taban cizgisinin egitim sonrasi
# --- olcumle karsilastirilabilir olmasinin TEK sarti; bu yuzden komut satirindan
# --- degistirilebilir yapilmadilar.
PROTOKOL = {
    "--bolum": "test",
    "--iou": "0.3",
}

# Taban cizgisi egitimsiz modelle olculur. Egitilmis bir agirlikla ayni protokolu
# kosmak icin --model verilir; protokolun geri kalani (bolum, karo, ortusme, IoU,
# esikler, cihaz) degismedigi icin iki olcum dogrudan karsilastirilabilir.
PROTOKOL_MODEL = "yolo11n.pt"

# Karo olcegi protokolun geri kalanindan ayri tutulur: "karo kucultmek TEK BASINA
# ne kazandiriyor" sorusu ancak olcegi degistirip geri kalan her seyi sabit
# tutarak yanitlanabilir. Varsayilan, taban cizgisinin olcegidir.
PROTOKOL_KARO = 512
PROTOKOL_ORTUSME = 0.20
# Tarama en dusuk esikle bir kez yapilir, digerleri sonradan filtrelenir.
CONF_ESIKLERI = ["0.05", "0.15", "0.30"]

TABAN_CIKTI = "test_taban_cizgisi"
KUTU_CIKTI = "test_kutu_bazinda"

# Alt kume uzerinde olculen hicbir sonuc taban cizgisi degildir. Dosya adina
# konan bu onek, deneme kosusunun gercek tabanla karismasini engeller --
# mevcut taban_cizgisi.csv'nin test satiri tam olarak boyle kullanilamaz hale
# geldi (limit 100, ada gore sirali dosya listesi yuzunden ZRI eksik temsil).
DENEME_ONEKI = "DENEME_"


def argumanlari_coz() -> argparse.Namespace:
    ayrastirici = argparse.ArgumentParser(
        description=(
            "Egitimsiz modelin test bolumu taban cizgisini olcer. Olcum protokolu "
            "(karo 512, ortusme 0,2, IoU 0,3, yolo11n, cpu) koda sabittir ve "
            "degistirilemez; degistirilebilirse taban cizgisi olma ozelligini kaybeder."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument(
        "--model", default=PROTOKOL_MODEL,
        help="Olculecek Ultralytics agirligi. Varsayilan, taban cizgisinin egitimsiz modelidir.",
    )
    ayrastirici.add_argument(
        "--etiket", default=None,
        help=(
            "Cikti dosyalarini test_<etiket>.csv ve test_kutu_bazinda_<etiket>.csv "
            "olarak adlandirir. Verilmezse taban cizgisi adlari kullanilir."
        ),
    )
    ayrastirici.add_argument(
        "--karo", type=int, default=PROTOKOL_KARO,
        help=(
            "Karo kenar uzunlugu. Varsayilan disinda bir deger verilirse cikti "
            "dosya adina _karo<N> soneki eklenir; taban cizgisi dosyalarinin "
            "uzerine YAZILMAZ. Boyle bir kosu taban cizgisi degil, olcek deneyidir."
        ),
    )
    ayrastirici.add_argument(
        "--ortusme", type=float, default=None,
        help=f"Ortusme orani. Verilmezse karo {PROTOKOL_KARO} icin {PROTOKOL_ORTUSME} kullanilir.",
    )
    ayrastirici.add_argument(
        "--limit", type=int, default=0,
        help=(
            "Deneme kosusu icin en fazla kac goruntu islensin (0 = 157'nin hepsi). "
            f"Sifirdan buyukse cikti dosyalari {DENEME_ONEKI} onekiyle yazilir."
        ),
    )
    return ayrastirici.parse_args()


def olcum_scriptini_calistir(argv: list[str]) -> None:
    """01_taban_cizgisi.py'yi verilen argumanlarla, bu surecin icinde calistirir.

    Dosya adi rakamla basladigi icin normal import edilemez; dosya yolundan
    yukluyoruz. scripts/ klasoru yola ekleniyor ki 01'in 'from ortak import ...'
    satiri calissin.
    """
    if not OLCUM_SCRIPTI.is_file():
        raise SystemExit(f"Olcum scripti bulunamadi: {OLCUM_SCRIPTI}")
    sys.path.insert(0, str(SCRIPT_DIZIN))

    # kosu_bilgisi() CSV'ye sys.argv'i yazar. Burada 01'in kendi komutunu
    # gecirmemiz, CSV'yi okuyan birinin kosuyu birebir tekrar edebilmesini saglar.
    sys.argv = argv

    spec = importlib.util.spec_from_file_location("olcum_01", OLCUM_SCRIPTI)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    modul.main()


def main() -> None:
    arg = argumanlari_coz()
    onek = DENEME_ONEKI if arg.limit else ""
    rapor_kok = PROJE_KOK / "reports"

    if arg.ortusme is None:
        if arg.karo != PROTOKOL_KARO:
            raise SystemExit(
                f"Karo {arg.karo} icin varsayilan ortusme yok. --ortusme ile acikca verin "
                f"(varsayilan yalnizca protokol karosu {PROTOKOL_KARO} icin tanimlidir)."
            )
        arg.ortusme = PROTOKOL_ORTUSME
    # Taban cizgisi dosya adi soneksizdir; her farkli olcek kendi dosyasina yazar.
    sonek = "" if arg.karo == PROTOKOL_KARO else f"_karo{arg.karo}"
    if arg.etiket:
        # Etiket verildiginde taban cizgisi adlari hic kullanilmaz; boylece
        # egitilmis modelin olcumu taban dosyalarinin uzerine yazamaz.
        taban_ad, kutu_ad = f"test_{arg.etiket}", f"test_kutu_bazinda_{arg.etiket}"
        sonek = ""
    else:
        taban_ad, kutu_ad = TABAN_CIKTI, KUTU_CIKTI

    argv = [str(OLCUM_SCRIPTI)]
    for ad, deger in PROTOKOL.items():
        argv += [ad, deger]
    argv += ["--model", arg.model]
    argv += ["--karo", str(arg.karo), "--ortusme", str(arg.ortusme)]
    argv += ["--conf", *CONF_ESIKLERI]
    # Onek bazinda cikti, test bolumunde hangi kaynaklarin bulundugunu ve her
    # birinden kac hedef geldigini ayni dosyaya yazar.
    argv += ["--onek-bazinda"]
    argv += ["--limit", str(arg.limit)]
    argv += ["--cikti", str(rapor_kok / f"{onek}{taban_ad}{sonek}.csv")]
    argv += ["--kutu-cikti", str(rapor_kok / f"{onek}{kutu_ad}{sonek}.csv")]

    if arg.model == PROTOKOL_MODEL:
        print("=== TEST BOLUMU TABAN CIZGISI (egitimsiz yolo11n) ===")
    else:
        print(f"=== TEST BOLUMU OLCUMU (model: {arg.model}) ===")
        print(f"Protokol taban cizgisiyle ayni; degisen tek sey agirlik. "
              f"Taban cizgisi modeli: {PROTOKOL_MODEL}")
    if arg.karo != PROTOKOL_KARO:
        print(f"OLCEK DENEYI: karo {arg.karo}, ortusme {arg.ortusme}. Taban cizgisi "
              f"karo {PROTOKOL_KARO}'dir; bu kosu onun yerine gecmez, yanina yazilir.")
    if arg.limit:
        print(f"DENEME KOSUSU: en fazla {arg.limit} goruntu. Bu cikti taban cizgisi "
              f"DEGILDIR, dosya adi {DENEME_ONEKI} onekiyle yazilir.")
    else:
        print("Tam kosu: test bolumunun tamami olculur.")
    print(f"Calistirilan: {' '.join(argv)}\n", flush=True)

    olcum_scriptini_calistir(argv)


if __name__ == "__main__":
    main()
