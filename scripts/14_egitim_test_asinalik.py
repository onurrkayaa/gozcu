"""Egitim-test kaynak asinaligi ve dosya icerigi kesisimi olcumu.

IKI AYRI SEY olculur ve BIRBIRINE KARISTIRILMAZ:

1. Kaynak oneki kirilimi (train/valid/test). Ayni kaynak onegi ayni goruntu
   demek DEGILDIR; onek kesisimi veri sizintisi kaniti degildir. Onek kesisimi
   cikarsa bunun adi KAYNAK ASINALIGI KISITI'dir.
2. Goruntu dosyalarinin BAYTLARINDAN hesaplanan SHA-256 kesisimi. Ayni SHA-256
   dosya iceriginin ayni oldugunu gosterir; ayni hash hem train hem testte
   bulunuyorsa bu VERI SIZINTISIDIR.

Hash dosya adindan veya yol metninden degil, dosya baytlarindan hesaplanir.
Goruntuler acilmaz, model calistirilmaz, ag kullanilmaz; standart kutuphane
disinda bagimlilik yoktur.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIZIN = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIZIN))

from ortak import (  # noqa: E402
    GECERLI_UZANTILAR,
    RAPOR_KOK,
    VERI_KOK,
    bolum_yolu,
    csv_yaz,
    etiket_yolu,
    goruntuleri_listele,
    kosu_bilgisi,
    sayi_bicimle,
    tablo_bas,
)

BOLUMLER = ("train", "valid", "test")

# Hash okumasi parca parca yapilir; 4000x3000 goruntuler tek seferde belege
# yuklenmesin diye.
PARCA_BOYUTU = 1 << 20

# Bilinen toplamlar. Bu degerler daha onceki olcumlerden gelir ve onek
# ayristiricisinin ya da etiket eslestirmesinin sessizce yanlis calismasini
# yakalamak icindir. Uyusmazlik cikarsa olcum YAYIMLANMAZ.
BEKLENEN = {
    "test_goruntu": 157,
    "test_hedef": 970,
    "train_goruntu": 1106,
    "valid_goruntu": 316,
    "train_valid_hedef": 2103,
    "onek_sayisi": 17,
}

# Bolum 4'te kullanilacak iki kaynak; ozet ciktida ayrica basilirlar.
IZLENEN_ONEKLER = ("ZRI", "VRD")

EVET = "evet"
HAYIR = "hayir"


def argumanlari_coz() -> argparse.Namespace:
    ayrastirici = argparse.ArgumentParser(
        description=(
            "train/valid/test bolumlerinin kaynak oneki kirilimini ve goruntu "
            "dosyalarinin SHA-256 kesisimini olcer. Model calistirmaz."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ayrastirici.add_argument(
        "--veri", type=Path, default=VERI_KOK, help="Veri kumesinin kok klasoru",
    )
    ayrastirici.add_argument(
        "--onek-cikti", type=Path, default=RAPOR_KOK / "egitim_test_onek_kesisimi.csv",
        help="Kaynak oneki kirilimi CSV'sinin yolu",
    )
    ayrastirici.add_argument(
        "--hash-cikti", type=Path, default=RAPOR_KOK / "egitim_test_hash_kontrolu.csv",
        help="SHA-256 kontrolu CSV'sinin yolu",
    )
    return ayrastirici.parse_args()


def onek_cikar(goruntu: Path) -> str:
    """Dosya adindan kaynak onegini cikarir: train_ZRI_3035_... -> ZRI"""
    parcalar = goruntu.stem.split("_")
    return parcalar[1] if len(parcalar) > 1 else "?"


def dosya_sha256(yol: Path) -> str:
    """Dosyanin BAYTLARININ SHA-256 ozeti. Dosya adi veya yol metni hesaba girmez."""
    ozet = hashlib.sha256()
    with yol.open("rb") as dosya:
        for parca in iter(lambda: dosya.read(PARCA_BOYUTU), b""):
            ozet.update(parca)
    return ozet.hexdigest()


def hedef_say(etiket_dosya: Path) -> int:
    """YOLO etiket dosyasindaki hedef sayisi. Bos dosya sifir hedeftir.

    Eksik veya bozuk etiket sessizce gecilmez: dosya yoksa ya da bir satir YOLO
    formatina uymuyorsa hata firlatilir ve islem durur."""
    if not etiket_dosya.is_file():
        raise FileNotFoundError(f"Etiket dosyasi yok: {etiket_dosya}")
    sayi = 0
    for no, satir in enumerate(
        etiket_dosya.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not satir.strip():
            continue
        parcalar = satir.split()
        if len(parcalar) < 5:
            raise ValueError(
                f"Bozuk etiket satiri ({len(parcalar)} alan, en az 5 bekleniyor): "
                f"{etiket_dosya} satir {no}"
            )
        try:
            [float(p) for p in parcalar[:5]]
        except ValueError as hata:
            raise ValueError(
                f"Bozuk etiket satiri (sayiya cevrilemedi): {etiket_dosya} satir {no}"
            ) from hata
        sayi += 1
    return sayi


def bolum_kayitlari(bolum: str, veri_kok: Path) -> list[dict]:
    """Bir bolumdeki her goruntu icin bolum, goreli yol, onek, hedef sayisi ve
    dosya baytlarinin SHA-256 ozetini toplar. Siralama dosya adina gore sabittir."""
    goruntu_dizin, etiket_dizin = bolum_yolu(bolum, veri_kok)
    kayitlar = []
    for yol in goruntuleri_listele(goruntu_dizin):
        kayitlar.append({
            "bolum": bolum,
            "goreli_yol": yol.relative_to(veri_kok).as_posix(),
            "onek": onek_cikar(yol),
            "hedef_sayisi": hedef_say(etiket_yolu(yol, etiket_dizin)),
            "sha256": dosya_sha256(yol),
        })
    return kayitlar


def tum_kayitlar(veri_kok: Path, bolumler=BOLUMLER) -> list[dict]:
    """Butun bolumlerin kayitlari; bolum sirasi ve dosya sirasi sabittir."""
    kayitlar: list[dict] = []
    for bolum in bolumler:
        kayitlar += bolum_kayitlari(bolum, veri_kok)
    return kayitlar


def bolum_ozeti(kayitlar: list[dict]) -> dict[str, dict[str, int]]:
    """Bolum basina goruntu sayisi, hedef sayisi ve onek sayisi."""
    ozet: dict[str, dict[str, int]] = {}
    for bolum in BOLUMLER:
        bolum_kayit = [k for k in kayitlar if k["bolum"] == bolum]
        ozet[bolum] = {
            "goruntu": len(bolum_kayit),
            "hedef": sum(k["hedef_sayisi"] for k in bolum_kayit),
            "onek": len({k["onek"] for k in bolum_kayit}),
        }
    return ozet


def onek_satirlari(kayitlar: list[dict]) -> list[dict]:
    """Kaynak oneki basina bolum kirilimi ve onek kesisimi. Kesisim burada
    'bu onek iki bolumde de geciyor' demektir; ayni goruntu demek DEGILDIR."""
    sayim: dict[str, dict[str, int]] = defaultdict(
        lambda: {f"{b}_{alan}": 0 for b in BOLUMLER for alan in ("goruntu", "hedef")}
    )
    for kayit in kayitlar:
        grup = sayim[kayit["onek"]]
        grup[f"{kayit['bolum']}_goruntu"] += 1
        grup[f"{kayit['bolum']}_hedef"] += kayit["hedef_sayisi"]

    satirlar = []
    for onek in sorted(sayim):
        g = sayim[onek]
        satirlar.append({
            "kaynak_oneki": onek,
            "train_goruntu_sayisi": g["train_goruntu"],
            "train_hedef_sayisi": g["train_hedef"],
            "valid_goruntu_sayisi": g["valid_goruntu"],
            "valid_hedef_sayisi": g["valid_hedef"],
            "test_goruntu_sayisi": g["test_goruntu"],
            "test_hedef_sayisi": g["test_hedef"],
            "train_valid_kesisimi": EVET if g["train_goruntu"] and g["valid_goruntu"] else HAYIR,
            "train_test_kesisimi": EVET if g["train_goruntu"] and g["test_goruntu"] else HAYIR,
            "valid_test_kesisimi": EVET if g["valid_goruntu"] and g["test_goruntu"] else HAYIR,
        })
    return satirlar


def hash_satirlari(kayitlar: list[dict]) -> list[dict]:
    """Her benzersiz SHA-256 icin hangi bolumde hangi dosyalarda gectigi.

    Kesisim cikmasa da butun benzersiz hash'ler yazilir; sonuc boylece yeniden
    denetlenebilir. Bir hash birden fazla dosyada gecerse tum goreli yollar
    ';' ile ayrilarak korunur."""
    yollar: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: {b: [] for b in BOLUMLER}
    )
    for kayit in kayitlar:
        yollar[kayit["sha256"]][kayit["bolum"]].append(kayit["goreli_yol"])

    satirlar = []
    for ozet in sorted(yollar):
        b = yollar[ozet]
        train_test = bool(b["train"]) and bool(b["test"])
        satirlar.append({
            "sha256": ozet,
            "train_dosyalari": ";".join(sorted(b["train"])),
            "valid_dosyalari": ";".join(sorted(b["valid"])),
            "test_dosyalari": ";".join(sorted(b["test"])),
            "train_valid_eslesmesi": EVET if b["train"] and b["valid"] else HAYIR,
            "train_test_eslesmesi": EVET if train_test else HAYIR,
            "valid_test_eslesmesi": EVET if b["valid"] and b["test"] else HAYIR,
            # Sizinti TANIMI: ayni dosya icerigi hem egitimde hem testte.
            "veri_sizintisi": EVET if train_test else HAYIR,
        })
    return satirlar


def capraz_dogrula(kayitlar: list[dict], beklenen: dict[str, int] = BEKLENEN) -> list[str]:
    """Olcumu daha once bilinen toplamlarla karsilastirir; uyusmazliklari
    fark sayisiyla birlikte metin listesi olarak dondurur."""
    ozet = bolum_ozeti(kayitlar)
    olculen = {
        "test_goruntu": ozet["test"]["goruntu"],
        "test_hedef": ozet["test"]["hedef"],
        "train_goruntu": ozet["train"]["goruntu"],
        "valid_goruntu": ozet["valid"]["goruntu"],
        "train_valid_hedef": ozet["train"]["hedef"] + ozet["valid"]["hedef"],
        "onek_sayisi": len({k["onek"] for k in kayitlar}),
    }
    uyusmazlik = []
    for ad, deger in beklenen.items():
        if olculen[ad] != deger:
            uyusmazlik.append(
                f"{ad}: beklenen {deger}, olculen {olculen[ad]}, fark {olculen[ad] - deger}"
            )
    return uyusmazlik


def izlenen_onek_satiri(satirlar: list[dict], onek: str, train_valid_hedef: int) -> str:
    """Bolum 4'te kullanilacak tek satirlik onek ozeti."""
    satir = next((s for s in satirlar if s["kaynak_oneki"] == onek), None)
    if satir is None:
        return f"{onek} oneki: veri kumesinde yok"
    pay = satir["train_hedef_sayisi"] + satir["valid_hedef_sayisi"]
    yuzde = sayi_bicimle(100 * pay / train_valid_hedef, 1) if train_valid_hedef else 0.0
    return (
        f"{onek} oneki: train {satir['train_goruntu_sayisi']} goruntu / "
        f"{satir['train_hedef_sayisi']} hedef, valid {satir['valid_goruntu_sayisi']} goruntu / "
        f"{satir['valid_hedef_sayisi']} hedef, test {satir['test_goruntu_sayisi']} goruntu / "
        f"{satir['test_hedef_sayisi']} hedef; train+valid hedef toplamindaki payi %{yuzde}"
    )


def main() -> None:
    arg = argumanlari_coz()

    kayitlar = tum_kayitlar(arg.veri)
    ozet = bolum_ozeti(kayitlar)

    print("=== BOLUM OZETI ===")
    tablo_bas([
        {"bolum": b, "goruntu": ozet[b]["goruntu"], "hedef": ozet[b]["hedef"],
         "onek": ozet[b]["onek"]}
        for b in BOLUMLER
    ])

    uyusmazlik = capraz_dogrula(kayitlar)
    if uyusmazlik:
        print("\n=== BILINEN TOPLAMLARLA CAPRAZ DOGRULAMA: UYUSMAZLIK ===")
        for satir in uyusmazlik:
            print(f"  {satir}")
        print("\nOlcum yayimlanmadi; CSV yazilmadi.")
        sys.exit(1)
    print("\nBilinen toplamlarla capraz dogrulama: uyustu.")

    onekler = onek_satirlari(kayitlar)
    hashler = hash_satirlari(kayitlar)

    kosu = kosu_bilgisi(
        veri_kok=str(arg.veri),
        bolumler=",".join(BOLUMLER),
        ozet_yontemi="sha256, dosya baytlari uzerinden",
        onek_yontemi="dosya adinin '_' ile ayrilmis ikinci parcasi",
        uzantilar=",".join(sorted(GECERLI_UZANTILAR)),
        kesisim_notu=(
            "onek kesisimi kaynak asinaligidir, veri sizintisi degildir; "
            "sizinti yalnizca ayni sha256'nin train ve testte bulunmasidir"
        ),
    )
    onek_csv = csv_yaz(arg.onek_cikti, onekler, kosu)
    hash_csv = csv_yaz(arg.hash_cikti, hashler, kosu)

    print("\n=== KAYNAK ONEKI KIRILIMI ===")
    tablo_bas(onekler, [
        "kaynak_oneki", "train_goruntu_sayisi", "train_hedef_sayisi",
        "valid_goruntu_sayisi", "valid_hedef_sayisi",
        "test_goruntu_sayisi", "test_hedef_sayisi",
        "train_valid_kesisimi", "train_test_kesisimi", "valid_test_kesisimi",
    ])

    train_valid_hedef = ozet["train"]["hedef"] + ozet["valid"]["hedef"]
    print()
    for onek in IZLENEN_ONEKLER:
        print(izlenen_onek_satiri(onekler, onek, train_valid_hedef))

    ortak_onek = [s["kaynak_oneki"] for s in onekler if s["train_test_kesisimi"] == EVET]
    print(f"\nTrain-test ortak onekleri ({len(ortak_onek)}): {', '.join(ortak_onek) or '(yok)'}")
    print("Onek kesisimi KAYNAK ASINALIGI KISITI'dir, veri sizintisi degildir.")

    print(f"\nOnek CSV : {onek_csv}  ({len(onekler)} satir)")
    print(f"Hash CSV : {hash_csv}  ({len(hashler)} benzersiz sha256)")

    train_valid = [s for s in hashler if s["train_valid_eslesmesi"] == EVET]
    train_test = [s for s in hashler if s["train_test_eslesmesi"] == EVET]
    valid_test = [s for s in hashler if s["valid_test_eslesmesi"] == EVET]

    print("\n=== SHA-256 KONTROLU ===")
    print(f"Train-valid ortak hash: {len(train_valid)}")
    print(f"Train-test ortak hash : {len(train_test)}")
    print(f"Valid-test ortak hash : {len(valid_test)}")
    for etiket, kume in (
        ("TRAIN-VALID", train_valid), ("VALID-TEST", valid_test), ("TRAIN-TEST", train_test)
    ):
        for s in kume:
            print(f"  {etiket} {s['sha256']}: "
                  f"train[{s['train_dosyalari']}] valid[{s['valid_dosyalari']}] "
                  f"test[{s['test_dosyalari']}]")

    if train_test:
        print("\nKAPI GECMEDI — VERI SIZINTISI: ayni sha256 hem train hem testte.")
        sys.exit(1)
    print("\nKAPI GECTI: ayni sha256 train ve testte birlikte bulunmuyor.")


if __name__ == "__main__":
    main()
