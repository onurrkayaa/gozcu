# Gözcü — Hafta 0: Taban Çizgisi Ölçümü

Havadan (dron) çekilmiş arama-kurtarma görüntülerinde kayıp insan tespiti.
Bu aşamada **model eğitimi yoktur**. Amaç tek bir soruyu ölçmek:

> COCO ile önceden eğitilmiş hazır bir dedektör, karolamalı (tiling) çalıştırıldığında
> bu veri kümesindeki insanların ne kadarını buluyor?

Sonuç, projeye devam kararı için taban çizgisi (baseline) oluşturur.

---

## 1. Neden karolama?

Görüntüler 4000x3000 piksel, aranan insanlar ise medyan **60x59 piksel** —
yani görüntü alanının yalnızca **%0.031**'i. Görüntü doğrudan modele verilirse model
onu 640 piksele küçültür ve 60 piksellik bir insan ~9 piksele iner; bu boyutta tespit
pratikte imkânsızdır. Bu yüzden görüntü 512 piksellik karolara bölünüp her karo ayrı
taranır (SAHI kütüphanesi).

## 2. Ortam kurulumu

Kullanılan Python sürümü: **3.13.1**. (PyTorch 2.14.0 ve ultralytics 8.4.144
tekerlekleri 3.13 için sorunsuz kuruldu; 3.12'ye düşmeye gerek kalmadı.)
Donanım: macOS arm64, **yalnızca CPU**.

```bash
cd gozcu

# Sanal ortam
python3.13 -m venv .venv

# Paketler (sürümler sabitlenmiştir)
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Model dosyası `yolo11n.pt` ilk çalıştırmada ultralytics tarafından proje köküne
otomatik indirilir (~5.4 MB); ayrıca bir işlem gerekmez.

## 3. Veri düzeni

Veri kümesi `data/heridal/` altında YOLO formatındadır:

```
data/heridal/
├── data.yaml          # nc: 1, names: ['human']
├── train/images/  train/labels/     1106 görüntü
├── valid/images/  valid/labels/      316 görüntü
└── test/images/   test/labels/       157 görüntü
```

Not: Veri kümesindeki sınıf adı `human`, COCO modelindeki karşılığı `person`
(sınıf kimliği 0). İkisi aynı şeyi kasteder; tahminler yalnızca bu sınıfa filtrelenir.

## 4. Çalıştırma sırası

Tüm komutlar proje kökünden çalıştırılır. Her script `--help` ile ne yaptığını anlatır.

### 4.1 Testler (önce bunu çalıştır)

IoU hesabı ve tahmin-gerçek eşleştirme mantığının doğruluğunu doğrular.

```bash
.venv/bin/python -m pytest tests/ -v
```

### 4.2 Veriyi tanı

Görüntü ve kutu istatistiklerini hesaplar. Model çalıştırmaz, hızlıdır (~1 sn).

```bash
.venv/bin/python scripts/00_veri_incele.py
```

Çıktı: `reports/veri_istatistik.csv`

### 4.3 Taban çizgisi ölçümü

Önce küçük bir duman testi yapıp hızın makul olduğunu doğrula:

```bash
.venv/bin/python scripts/01_taban_cizgisi.py --limit 5
```

Sonra tam koşu (CPU'da ~6 sn/görüntü, 100 görüntü ≈ 10 dakika):

```bash
.venv/bin/python scripts/01_taban_cizgisi.py --bolum test --limit 100 --dogrula
```

Çıktı: `reports/taban_cizgisi.csv`

Kullanılabilir argümanlar:

| Argüman | Varsayılan | Açıklama |
|---|---|---|
| `--bolum` | `test` | Ölçülecek bölüm (train/valid/test), ya da `hepsi` |
| `--onek` | yok | Sadece bu kaynak öneklerini ölç (ör. `VRD MED`); verilmezse hepsi |
| `--onek-bazinda` | kapalı | Çıktıyı kaynak bazında üretir (bkz. 5.5) |
| `--limit` | `100` | En fazla kaç görüntü işlensin (0 = hepsi) |
| `--karo` | `512` | Karo kenar uzunluğu, piksel |
| `--ortusme` | `0.2` | Karolar arası örtüşme oranı |
| `--conf` | `0.05 0.15 0.30` | Güven eşikleri; her değer için bir satır üretilir |
| `--iou` | `0.3` | Eşleştirme için IoU eşiği |
| `--dogrula` | kapalı | Tek tarama + filtreleme optimizasyonunu doğrular (bkz. 5.2) |

### 4.4 Karolamalı / karolamasız karşılaştırma

Aynı görüntüleri iki modda ölçüp tek tabloda karşılaştırır (~11 dakika).

```bash
.venv/bin/python scripts/02_karolama_karsilastir.py --bolum test --limit 100
```

Çıktı: `reports/karolama_karsilastirma.csv`

### 4.5 Görsel kontrol

10 örnek görüntüyü küçültüp gerçek kutuları **yeşil**, tahminleri **kırmızı**
(güven skoruyla birlikte) çizer.

```bash
.venv/bin/python scripts/03_gorsellestir.py --bolum test
```

Çıktı: `reports/ornekler/` klasörü ve `reports/ornek_secim.csv`.

Örnekler rastgele ya da baştan sırayla değil, **tabakalı** seçilir:

| Tabaka | Adet | Ölçüt |
|---|---|---|
| `kalabalik` | 4 | En çok etiketi olan sahneler |
| `az_etiketli` | 4 | 1-2 kutulu seyrek sahneler |
| `negatif` | 2 | Hiç etiketi olmayan sahneler |

Negatif görüntüler **kasten** dahil edilir: modelin boş arazide ürettiği yanlış
pozitifler ancak böyle gözle görülebilir. Ölçümde görüntü başına 1.39 FP (conf=0.30)
çıkıyor; bunun neye benzediğini görmek, sayıyı okumaktan daha bilgilendiricidir.

Tabaka adetleri script'in başındaki `KALABALIK_ADET`, `AZ_ADET`, `NEGATIF_ADET`
sabitlerinde tanımlıdır. Seçilen görüntülerin listesi etiket sayılarıyla birlikte
`reports/ornek_secim.csv` dosyasına yazılır; böylece hangi görüntülere bakıldığı
kayda geçer ve seçim tekrar üretilebilir.

---

## 5. Ölçüm hakkında bilinmesi gerekenler

### 5.1 `perform_standard_pred=False`

SAHI'nin `get_sliced_prediction` fonksiyonunda bu parametre **varsayılan olarak
`True`**'dur ve karolara **ek olarak** tüm görüntüyü küçültüp bir kez daha tarar.
Açık bırakılsaydı "karolamalı" ölçüm, karolamasız ölçümü zaten içinde barındırırdı ve
4.4'teki karşılaştırma anlamsız olurdu. Bu yüzden kapatılmıştır; değer her CSV'ye
`kosu_perform_standard_pred` sütunu olarak yazılır.

### 5.2 Tek tarama + sonradan filtreleme

Birden fazla güven eşiği isteniyorsa her eşik için ayrı tarama yapmak, süreyi eşik
sayısı kadar katlar. Bunun yerine tarama **bir kez** en düşük eşikle yapılır, yüksek
eşikler sonuç üzerinde filtrelenir.

Bu optimizasyonun doğruluğu `--dogrula` bayrağıyla ölçülebilir: bir görüntü doğrudan
yüksek eşikle taranır ve sonucu, düşük eşikli taramanın filtrelenmiş haliyle
karşılaştırılır.

İlk denemede sonuçlar **farklı** çıktı. Sebep: SAHI, güven eşiği düşük olduğunda kutu
birleştirme yöntemini kendiliğinden `GREEDYNMM/IOS`'tan `NMS/IOU`'ya çeviriyor
(kendi uyarı mesajıyla birlikte). Böylece aynı görüntü, farklı eşiklerde farklı
birleştirme rejiminde işleniyordu. Çözüm olarak `postprocess_type="NMS"` ve
`postprocess_match_metric="IOU"` açıkça sabitlendi; doğrulama bundan sonra **aynı**
sonucu verdi.

### 5.3 Metriklerin tanımı

Bir tahmin, bir gerçek kutuyla **IoU ≥ 0.3** ise eşleşmiş sayılır. Her gerçek kutu en
fazla bir tahminle eşleşir; birden fazla aday varsa güven skoru yüksek olan öncelikli
işlenir.

| Metrik | Anlamı |
|---|---|
| `gercek_kutu` | Etiketlerdeki toplam kutu sayısı |
| `dogru_bulunan_tp` | Eşleşen tahmin sayısı (doğru pozitif) |
| `kacirilan_fn` | Hiçbir tahminle eşleşmeyen gerçek kutu (kaçırılan insan) |
| `recall` | TP / (TP + FN) — aranan insanların ne kadarının bulunduğu |
| `yanlis_pozitif_fp` | Hiçbir gerçek kutuyla eşleşmeyen tahmin |
| `fp_goruntu_basina` | FP / görüntü sayısı — operatörün eleyeceği yanlış alarm yükü |
| `precision` | TP / (TP + FP) |
| `sure_saniye_goruntu_basina` | Ortalama işlem süresi |

Arama-kurtarma bağlamında **recall, precision'dan önemlidir**: kaçırılan bir insan
geri alınamaz, yanlış alarmı ise operatör eler.

### 5.4 Kaynak (önek) bazında ölçüm

Veri kümesindeki dosya adları `train_ZRI_3035_...` biçimindedir; ikinci parça
görüntünün hangi çekim bölgesinden geldiğini söyler. Toplam **17 farklı kaynak**
vardır ve dağılımları çok dengesizdir — `reports/onek_dagilimi.csv` bunu belgeler.

En önemli sapma: **ZRI** (şehir parkı) 126 görüntüde 1297 kutu taşır, yani veri
kümesindeki etiketlerin %42'si. Diğer 16 kaynak dağlık/ormanlık arazidir ve görüntü
başına ortalama 1'in altında etiket içerir. Dahası bölünmeler kaynak bazında
ayrışmıştır: `test` bölümü 17 kaynaktan yalnızca 2'sini (ZRI ve VRD) içerir ve
ZRI'nin 126 görüntüsünün 87'si oradadır.

Bu yüzden tek bir birleşik recall sayısı yanıltıcıdır — pratikte "ZRI parkında
recall" anlamına gelir. `--onek-bazinda` bayrağı her kaynak için ayrı satır üretir,
ayrıca iki özet satırı ekler:

- `TOPLAM` — tüm kaynaklar birlikte
- `ZRI_HARIC` — baskın kaynak dışarıda bırakıldığında kalan tablo

Kaynak bazında tam ölçüm (üç bölüm birleşik, 1579 görüntü, ~2.5 saat):

```bash
.venv/bin/python scripts/01_taban_cizgisi.py \
    --bolum hepsi --limit 0 --onek-bazinda \
    --cikti reports/taban_cizgisi_onek.csv
```

**Bölümleri birleştirmek neden şu an geçerli:** `--bolum hepsi`, train/valid/test
ayrımını yok sayar. Bu normalde ciddi bir hata olurdu; ancak bu aşamada model
eğitilmemiştir ve COCO ağırlıklarıyla çalışır — yani üç bölümdeki hiçbir görüntüyü
görmemiştir. Ölçüm bu nedenle geçerlidir ve CSV'nin `kosu_gecerlilik_notu` sütununda
bu koşul açıkça yazılıdır. **Hafta 3'te eğitim yapıldıktan sonra bu koşu
tekrarlanamaz**; o noktadan itibaren yalnızca `test` bölümü kullanılmalıdır.

### 5.5 Tekrarlanabilirlik

Aynı komut ikinci kez çalıştırıldığında tespit sayıları birebir aynıdır: görüntü
listesi ada göre sıralanır, çıkarım deterministiktir, eşleştirmede skor eşitliği
indeks sırasıyla çözülür.

**Tek istisna `sure_saniye_goruntu_basina` sütunudur** — süre ölçümü doğası gereği
makinenin o anki yüküne göre birkaç yüzde oynar. Diğer tüm sayılar sabittir.

Her CSV, sonucun hangi koşullarda üretildiğini `kosu_` önekli sütunlarda taşır: model
adı, bölüm, görüntü sayısı, karo boyutu, örtüşme oranı, `perform_standard_pred`,
postprocess ayarı, IoU eşiği, Python/ultralytics/sahi/torch sürümleri, tarih ve
çalıştırılan komutun tam hali. Böylece tablo, rapora tek başına konulduğunda da
kendini açıklar.

---

## 6. Dosya düzeni

```
gozcu/
├── requirements.txt
├── README_hafta0.md
├── yolo11n.pt                       # ilk çalıştırmada otomatik iner
├── data/heridal/                    # veri kümesi (YOLO formatı)
├── scripts/
│   ├── ortak.py                     # IoU, eşleştirme, etiket okuma, tarama, CSV
│   ├── 00_veri_incele.py
│   ├── 01_taban_cizgisi.py
│   ├── 02_karolama_karsilastir.py
│   └── 03_gorsellestir.py
├── tests/
│   └── test_eslestirme.py           # IoU ve eşleştirme testleri
└── reports/                         # tüm çıktılar buraya yazılır
    ├── veri_istatistik.csv
    ├── taban_cizgisi.csv
    ├── karolama_karsilastirma.csv
    ├── ornek_secim.csv
    ├── onek_dagilimi.csv
    ├── taban_cizgisi_onek.csv
    └── ornekler/
```

`scripts/ortak.py` üç scriptin de kullandığı ortak mantığı barındırır; tarama
ayarları (karo rejimi, postprocess, person sınıf filtresi) orada tek yerde tanımlıdır,
böylece üç ölçüm birbiriyle karşılaştırılabilir kalır.
