"""Cografi bulgularin mesafeye gore kumelenmesi (Union-Find).

PROBLEM: Ortusen karolar ayni kisiyi birden fazla kez bulabilir, iki operator
ayni noktaya ayri bulgu acabilir. Haritada bunlar ayri isaretler olarak
gorunurse operator tek bir hedefi birden fazla hedef sanar.

COZUM: Birbirine belirli bir mesafeden yakin bulgulari ayni bagli bilesene
koymak. Bunun icin birlestir-bul (Union-Find) yapisini kullaniyorum.

GECISLILIK KASITLIDIR: A ile B esik icindeyse ve B ile C esik icindeyse,
A ile C arasindaki mesafe esikten BUYUK olsa bile ucu ayni kumeye girer.
Bu bir hata degil, bagli bilesen tanimidir: aralarinda yakinlik zinciri olan
noktalar tek bir bolgeyi isaret eder. Bedeli sudur -- uzun bir nokta zinciri
tek kume olarak gorunur. Bu davranis kullaniciya anlatilmali, cunku "esik 50
metre" ifadesi kume CAPININ 50 metre oldugunu DUSUNDURUR, oysa oyle degildir.

MESAFE METRE CINSINDENDIR. Finding.location alani `geography` tipinde
saklandigi icin PostGIS mesafeyi kuresel olarak, metre biriminde hesaplar.
Dereceler uzerinden Oklid mesafesi KULLANILMAZ: 1 derece boylam ekvatorda
~111 km, 60. enlemde ~55 km'dir, yani derece mesafesi enleme gore anlamini
degistirir.

ESIK BIR KARARDIR, OLCUM DEGILDIR. Asagidaki varsayilan, elimizde gercek GPS
bulunmadigi icin hicbir alan olcumunden turetilmemistir.
"""
from django.db import transaction
from django.utils import timezone

from .models import Finding

#: Varsayilan kumeleme esigi (metre). KARAR, olcum degil: insan boyu bir
#: hedefin cevresinde bu yaricapta ikinci bir isaret gorulurse operatorun bunu
#: ayri bir hedef degil ayni hedefin tekrari sayacagi varsayimina dayanir.
#: Gercek ucus verisi elde edilirse yeniden degerlendirilmelidir.
VARSAYILAN_ESIK_METRE = 50.0


class BirlestirBul:
    """Union-Find (disjoint set), yol sikistirma ve rutbe birlesimiyle.

    Deterministik olmasi icin kok secimi rutbeye, esitlikte KUCUK ANAHTARA
    baglidir; boylece ayni girdi her zaman ayni kokleri uretir.
    """

    def __init__(self, ogeler=()):
        self._ata = {oge: oge for oge in ogeler}
        self._rutbe = {oge: 0 for oge in self._ata}

    def ekle(self, oge):
        if oge not in self._ata:
            self._ata[oge] = oge
            self._rutbe[oge] = 0

    def bul(self, oge):
        self.ekle(oge)
        kok = oge
        while self._ata[kok] != kok:
            kok = self._ata[kok]
        # Yol sikistirma: zincirdeki her dugumu dogrudan koke bagla.
        while self._ata[oge] != kok:
            self._ata[oge], oge = kok, self._ata[oge]
        return kok

    def birlestir(self, a, b):
        kok_a, kok_b = self.bul(a), self.bul(b)
        if kok_a == kok_b:
            return False
        rutbe_a, rutbe_b = self._rutbe[kok_a], self._rutbe[kok_b]
        if rutbe_a < rutbe_b:
            kok_a, kok_b = kok_b, kok_a
        elif rutbe_a == rutbe_b:
            # Esit rutbede kucuk anahtar kok olur -> deterministik sonuc.
            if kok_b < kok_a:
                kok_a, kok_b = kok_b, kok_a
            self._rutbe[kok_a] += 1
        self._ata[kok_b] = kok_a
        return True

    def gruplar(self):
        """{kok: [uyeler...]} -- hem kokler hem uyeler sirali."""
        toplu = {}
        for oge in sorted(self._ata):
            toplu.setdefault(self.bul(oge), []).append(oge)
        return {kok: sorted(uyeler) for kok, uyeler in sorted(toplu.items())}


def _provenans_grubu(finding):
    """Bulgunun hangi kumeleme grubuna ait oldugu.

    Demo ve gercek konumlar AYNI KUMEYE KARISTIRILMAZ. Karisirlarsa sentetik
    bir nokta gercek bir bulguyu kendine ceker ve harita uzerinde uydurma bir
    yogunlasma olusur.
    """
    return "demo" if finding.is_demo else "gercek"


@transaction.atomic
def gorevi_kumele(mission, *, esik_metre=VARSAYILAN_ESIK_METRE, aktor=None):
    """Gorevin konumlu bulgularini bagli bilesenlere ayirir.

    Konumu olmayan bulgular kumelenmez: `location_source == none` olan kayitta
    kumelenecek bir sey yoktur ve bunlari tek bir "konumsuzlar" kumesine
    toplamak, aralarinda cografi bir iliski varmis izlenimi verirdi. Onlarin
    kume alanlari temizlenir.

    Ayni girdide tekrar calistirmak ayni sonucu uretir (idempotent): kume
    kimlikleri her kosuda sifirdan, sirali bir kuraldan turetilir; onceki
    kosunun kimliklerine bakilmaz.
    """
    if esik_metre <= 0:
        raise ValueError("Kumeleme esigi pozitif olmali.")

    bulgular = list(
        Finding.objects.filter(mission=mission).order_by("id")
    )
    konumlu = [b for b in bulgular if b.location is not None]
    konumsuz = [b for b in bulgular if b.location is None]

    # Konumsuzlarin kume bilgisi temizlenir.
    for bulgu in konumsuz:
        bulgu.cluster_id = None
        bulgu.cluster_key = ""
        bulgu.clustered_at = None

    guncellenecek = list(konumsuz)
    kume_sayisi = 0

    # Demo ve gercek AYRI kumelenir.
    for grup_adi in ("gercek", "demo"):
        grubun_bulgulari = [b for b in konumlu if _provenans_grubu(b) == grup_adi]
        if not grubun_bulgulari:
            continue

        kimlikler = [b.id for b in grubun_bulgulari]
        birlestir_bul = BirlestirBul(kimlikler)
        grup_kumesi = set(kimlikler)

        # Aday ciftleri PostGIS bulur: her bulgu icin yalnizca esik icindeki
        # komsular sorgulanir. Python'da her cifti karsilastirmak N^2 olurdu;
        # burada GiST indeksi aday sayisini bastan daraltiyor.
        for bulgu in grubun_bulgulari:
            komsular = (
                Finding.objects.filter(mission=mission, location__isnull=False)
                .exclude(pk=bulgu.pk)
                .filter(location__dwithin=(bulgu.location, esik_metre))
                .order_by("id")
                .values_list("id", flat=True)
            )
            for komsu_id in komsular:
                # dwithin gorev icindeki TUM konumlu kayitlari dondurur;
                # grup disindakileri burada eliyoruz.
                if komsu_id in grup_kumesi:
                    birlestir_bul.birlestir(bulgu.id, komsu_id)

        # Kume kimlikleri: gruplar en kucuk uye kimligine gore siralanir ve
        # 1'den baslayarak numaralanir. Girdi sirasi degisse bile ayni
        # numaralandirma cikar.
        gruplar = birlestir_bul.gruplar()
        sirali = sorted(gruplar.values(), key=lambda uyeler: uyeler[0])
        kimlikten_bulguya = {b.id: b for b in grubun_bulgulari}
        simdi = timezone.now()

        for sira, uyeler in enumerate(sirali, start=1):
            for uye_id in uyeler:
                bulgu = kimlikten_bulguya[uye_id]
                bulgu.cluster_id = sira
                bulgu.cluster_key = grup_adi
                bulgu.clustered_at = simdi
                guncellenecek.append(bulgu)
        kume_sayisi += len(sirali)

    Finding.objects.bulk_update(
        guncellenecek, ["cluster_id", "cluster_key", "clustered_at"], batch_size=500
    )

    return {
        "mission_id": mission.id,
        "esik_metre": esik_metre,
        "toplam_bulgu": len(bulgular),
        "kumelenen_bulgu": len(konumlu),
        "konumsuz_bulgu": len(konumsuz),
        "kume_sayisi": kume_sayisi,
    }


def kume_ozeti(mission):
    """Gorevin kumelerini uye sayisi ve merkeziyle ozetler.

    MERKEZ OLCULMUS BIR KONUM DEGILDIR: kumedeki noktalarin aritmetik
    ortalamasidir ve gercekte orada bir sey bulundugu anlamina gelmez.
    Haritada merkez gosterilecekse bu ayrim kullaniciya soylenmelidir.
    """
    ozet = {}
    sorgu = (
        Finding.objects.filter(mission=mission, location__isnull=False)
        .exclude(cluster_id=None)
        .order_by("cluster_key", "cluster_id", "id")
    )
    for bulgu in sorgu:
        anahtar = (bulgu.cluster_key, bulgu.cluster_id)
        kayit = ozet.setdefault(
            anahtar,
            {
                "cluster_key": bulgu.cluster_key,
                "cluster_id": bulgu.cluster_id,
                "uye_sayisi": 0,
                "finding_ids": [],
                "enlem_toplam": 0.0,
                "boylam_toplam": 0.0,
                "is_demo": bulgu.is_demo,
            },
        )
        kayit["uye_sayisi"] += 1
        kayit["finding_ids"].append(bulgu.id)
        kayit["enlem_toplam"] += bulgu.location.y
        kayit["boylam_toplam"] += bulgu.location.x

    sonuc = []
    for kayit in ozet.values():
        adet = kayit["uye_sayisi"]
        sonuc.append(
            {
                "cluster_key": kayit["cluster_key"],
                "cluster_id": kayit["cluster_id"],
                "uye_sayisi": adet,
                "finding_ids": kayit["finding_ids"],
                "is_demo": kayit["is_demo"],
                # GeoJSON sirasi: [boylam, enlem]
                "merkez": [
                    kayit["boylam_toplam"] / adet,
                    kayit["enlem_toplam"] / adet,
                ],
                "merkez_notu": "Kume uyelerinin ortalamasi; olculmus konum degildir.",
            }
        )
    return sonuc


__all__ = [
    "BirlestirBul",
    "VARSAYILAN_ESIK_METRE",
    "gorevi_kumele",
    "kume_ozeti",
]
