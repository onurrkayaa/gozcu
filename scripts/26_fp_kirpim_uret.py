#!/usr/bin/env python3
"""Kor etiketleme icin siki ve baglam kirpimlarini uretir, sonra dogrular.

Kirpimlar YALNIZCA kor kimlige gore adlandirilir. Dosya adi ne modeli ne de
adayin FP mi kontrol mu oldugunu ele verir; kaynak goruntunun adi da gecmez.

Kirpimlar Git'e girmez: kaynak goruntuden bu script ile yeniden uretilebilir
ve binlerce dosyadir. Depoda manifest, korleme anahtari ve bu script durur.

Kirpim uzerine kutu CIZILMEZ. Cizilseydi FP ile kontrol kirpimi arasindaki
fark (kutunun icerige oturma bicimi) etiketleyene ipucu verebilirdi.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ortak import RAPOR_KOK, VERI_KOK, bolum_yolu, iou_hesapla, Kutu, yolo_etiket_oku, etiket_yolu  # noqa: E402

GOSTERIM_EN_BOY = 640   # kirpimlar gosterim icin bu genislige kuculur
JPEG_KALITE = 88
YASAK_DIZGELER = ("Taban", "Model", "ZRI", "VRD", ".rf.", "_fp", "_kontrol", "_tp")


def argumanlari_al():
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--veri", type=Path, default=VERI_KOK)
    a.add_argument("--bolum", default="test")
    a.add_argument("--manifest", type=Path, default=RAPOR_KOK / "hafta7_fp_etiket_manifesti.csv")
    a.add_argument("--anahtar", type=Path, default=RAPOR_KOK / "hafta7_fp_korleme_anahtari.csv")
    a.add_argument("--kirpim-dizin", type=Path, default=RAPOR_KOK / "hafta7_kirpimlar")
    a.add_argument("--yalnizca-dogrula", action="store_true",
                   help="Kirpim uretmeden mevcut dosyalari dogrular.")
    return a.parse_args()


def csv_oku(yol: Path) -> list[dict]:
    with yol.open(encoding="utf-8") as dosya:
        return list(csv.DictReader(dosya))


def kirpimlari_uret(anahtar, goruntu_dizin: Path, hedef: Path):
    from PIL import Image

    hedef.mkdir(parents=True, exist_ok=True)
    # Ayni goruntuden birden cok aday cikabilir; dosyayi bir kez acip
    # hepsini kirpmak diskten tekrar tekrar okumayi onler.
    gruplu: dict[str, list[dict]] = {}
    for satir in anahtar:
        gruplu.setdefault(satir["goruntu_adi"], []).append(satir)

    uretilen = 0
    for sira, (goruntu_adi, satirlar) in enumerate(sorted(gruplu.items()), start=1):
        with Image.open(goruntu_dizin / goruntu_adi) as gorsel:
            gorsel = gorsel.convert("RGB")
            for satir in satirlar:
                for tur, onek in (("siki", "siki"), ("baglam", "baglam")):
                    kutu = tuple(int(float(satir[f"{onek}_{k}"]))
                                 for k in ("x1", "y1", "x2", "y2"))
                    kirpim = gorsel.crop(kutu)
                    if kirpim.width > GOSTERIM_EN_BOY:
                        oran = GOSTERIM_EN_BOY / kirpim.width
                        kirpim = kirpim.resize(
                            (GOSTERIM_EN_BOY, max(1, round(kirpim.height * oran))),
                            Image.LANCZOS)
                    kirpim.save(hedef / f"{satir['kor_kimlik']}_{tur}.jpg",
                                "JPEG", quality=JPEG_KALITE)
                    uretilen += 1
        if sira % 25 == 0:
            print(f"  {sira}/{len(gruplu)} goruntu islendi", flush=True)
    return uretilen


def dogrula(manifest, anahtar, kirpim_dizin: Path, veri_kok: Path, bolum: str) -> list[str]:
    from PIL import Image

    sorunlar: list[str] = []

    manifest_kimlikleri = [s["kor_kimlik"] for s in manifest]
    anahtar_kimlikleri = [s["kor_kimlik"] for s in anahtar]
    if len(set(manifest_kimlikleri)) != len(manifest_kimlikleri):
        sorunlar.append("Manifest'te tekrar eden kor kimlik var.")
    if set(manifest_kimlikleri) != set(anahtar_kimlikleri):
        sorunlar.append("Manifest ile korleme anahtari birebir eslesmiyor.")

    # Kor kimlik disinda hicbir sey dosya adina sizmamali.
    for satir in manifest:
        for alan in ("siki_kirpim", "baglam_kirpim"):
            ad = satir[alan]
            if not ad.startswith(satir["kor_kimlik"] + "_"):
                sorunlar.append(f"{ad}: dosya adi kor kimlikle baslamiyor.")
            if any(yasak in ad for yasak in YASAK_DIZGELER):
                sorunlar.append(f"{ad}: dosya adi gercek sinifi ele veriyor.")

    # Manifest degerlerinde de sizinti olmamali.
    for satir in manifest:
        for alan, deger in satir.items():
            if alan.startswith("kosu_"):
                continue
            if any(yasak in str(deger) for yasak in ("Taban-", "Model-", "ZRI", "VRD", ".rf.")):
                sorunlar.append(f"Manifest alani sizdiriyor: {alan}={deger}")

    # Iki gorsel, bozuk dosya yok.
    eksik = bozuk = 0
    for satir in manifest:
        for alan in ("siki_kirpim", "baglam_kirpim"):
            yol = kirpim_dizin / satir[alan]
            if not yol.is_file():
                eksik += 1
                continue
            try:
                with Image.open(yol) as gorsel:
                    gorsel.verify()
            except Exception:
                bozuk += 1
    if eksik:
        sorunlar.append(f"{eksik} kirpim dosyasi eksik.")
    if bozuk:
        sorunlar.append(f"{bozuk} kirpim dosyasi bozuk.")

    # Kontrol bolgeleri gercek insan kutulariyla cakismamali.
    goruntu_dizin, etiket_dizin = bolum_yolu(bolum, veri_kok)
    from PIL import Image as _Image
    onbellek: dict[str, list[Kutu]] = {}
    cakisan = 0
    for satir in anahtar:
        if satir["aday_turu"] != "kontrol":
            continue
        ad = satir["goruntu_adi"]
        if ad not in onbellek:
            with _Image.open(goruntu_dizin / ad) as gorsel:
                g, y = gorsel.size
            onbellek[ad] = yolo_etiket_oku(etiket_yolu(goruntu_dizin / ad, etiket_dizin), g, y)
        kutu = Kutu(float(satir["x1"]), float(satir["y1"]),
                    float(satir["x2"]), float(satir["y2"]))
        if any(iou_hesapla(kutu, gercek) > 0 for gercek in onbellek[ad]):
            cakisan += 1
    if cakisan:
        sorunlar.append(f"{cakisan} kontrol bolgesi gercek insan kutusuyla cakisiyor.")

    # Es kimlikler karsilikli olmali.
    kimlikten = {s["kor_kimlik"]: s for s in anahtar}
    for satir in anahtar:
        es = kimlikten.get(satir["es_kor_kimlik"])
        if es is None or es["es_kor_kimlik"] != satir["kor_kimlik"]:
            sorunlar.append(f"{satir['kor_kimlik']}: es kimlik karsilikli degil.")
        elif es["aday_turu"] == satir["aday_turu"]:
            sorunlar.append(f"{satir['kor_kimlik']}: es ayni turde.")
    return sorunlar


def main():
    arg = argumanlari_al()
    manifest = csv_oku(arg.manifest)
    anahtar = csv_oku(arg.anahtar)
    goruntu_dizin, _ = bolum_yolu(arg.bolum, arg.veri)

    if not arg.yalnizca_dogrula:
        print(f"Kirpim uretiliyor -> {arg.kirpim_dizin}")
        uretilen = kirpimlari_uret(anahtar, goruntu_dizin, arg.kirpim_dizin)
        print(f"  {uretilen} kirpim yazildi")

    print("\n=== MANIFEST VE KIRPIM DOGRULAMASI ===")
    sorunlar = dogrula(manifest, anahtar, arg.kirpim_dizin, arg.veri, arg.bolum)
    print(f"  manifest kaydi     : {len(manifest)}")
    print(f"  beklenen kirpim    : {len(manifest) * 2}")
    print(f"  diskteki kirpim    : {len(list(arg.kirpim_dizin.glob('*.jpg')))}")
    print(f"  kontrol bolgesi    : {sum(1 for s in anahtar if s['aday_turu'] == 'kontrol')}")
    print(f"  FP bolgesi         : {sum(1 for s in anahtar if s['aday_turu'] == 'fp')}")
    print(f"  kalite ornegi      : {sum(1 for s in manifest if s['tur'] == 'kalite')}")
    if sorunlar:
        for s in sorunlar:
            print(f"  SORUN: {s}")
        raise SystemExit("Dogrulama basarisiz; etiketlemeye baslanmaz.")
    print("  SONUC: dogrulama gecti.")


if __name__ == "__main__":
    main()
