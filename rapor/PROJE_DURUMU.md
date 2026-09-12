# Proje Durumu

Bu dosya rapor gövdesinin parçası değildir; nerede olduğumuzu ve sıradaki işin ne
olduğunu tek yerde tutar. Buradaki her sayı bir çıktı dosyasından okunur ve yanında
üreten CSV ile script yazar. Bir sayı ile bu dosya çelişirse **CSV kazanır**.

Son güncelleme: Hafta 6 kapanışı — görev üyeliği, inceleme, coğrafi bulgu ve harita.

---

## 1. Nerede duruyoruz

Hafta 0–3'te ölçüm altyapısı, taban çizgisi ve asenkron tarama hattı kuruldu.
Hafta 4'te kendi verimizle model eğitildi, ONNX'e aktarıldı ve gerçek Celery
hattına bağlandı; **Hafta 4 kapanmıştır** ve sonuçları `rapor/bolum_05.md`
dosyasında raporlanmıştır.

Hafta 5'te operatör arayüzü kuruldu ve gerçek backend'e bağlandı; **Hafta 5
kapanmıştır** (ayrıntı: bölüm 2.12–2.14) ve `rapor/bolum_06.md` dosyasında
raporlanmıştır.

Hafta 6'da erişim görev üyeliğine oturtuldu, operatör kararı ayrı bir kayda
alındı, coğrafi bulgu modeli PostGIS ile kuruldu, bulgular Union-Find ile
kümelendi ve harita eklendi. **Hafta 6 kapanmıştır** (ayrıntı: bölüm 2.15–2.19).
Sıradaki ana iş Hafta 7'dir.

## 2. Ölçülenler

### 2.1. Taban çizgisi ve Model-512 (Hafta 0–4)

Test bölümü: 157 görüntü, 970 hedef. Protokol: karo 512, örtüşme 0,20, IoU 0,30, CPU.

| conf | Taban recall | Taban FP/görüntü | Model-512 recall | Model-512 FP/görüntü |
|---|---|---|---|---|
| 0,05 | 0,7113 | 18,24 | 0,9299 | 13,59 |
| 0,15 | 0,5485 | 5,45 | 0,8856 | 7,07 |
| 0,30 | 0,3804 | 1,81 | 0,8124 | 3,93 |

Kaynak: `reports/test_taban_cizgisi.csv`, `reports/test_model512.csv`
(`scripts/01_taban_cizgisi.py`, aynı protokol).

Yükseklik bandına göre kazanım conf 0,30'da ölçülüdür: en büyük kazanım < 44 px
bandında (+0,5488), en küçüğü ≥ 80 px bandında (+0,2557) — `reports/yukseklik_kazanim.csv`
(`scripts/13_kutu_bazinda_karsilastir.py`).

### 2.2. Eğitim–test kaynak aşinalığı (BULGU + KISIT)

Tüm veride 17 kaynak öneki var; train–test'te ortak olan iki önek: **ZRI ve VRD**.
ZRI test bölümünde 87 görüntü / 939 hedefle bulunurken eğitimde de 34 görüntü /
319 hedefle var. Test bölümündeki 970 hedefin 939'u ZRI'dir.
Kaynak: `reports/egitim_test_onek_kesisimi.csv` (`scripts/14_egitim_test_asinalik.py`).

Bunun adı **kaynak aşinalığı kısıtıdır**, veri sızıntısı değildir.

### 2.3. Train–test dosya çakışması (BULGU)

1579 görüntünün tamamının SHA-256 özeti dosya baytlarından hesaplandı; 1579 benzersiz
hash çıktı. Train–test, train–valid ve valid–test ortak hash sayısı **0**.
Kaynak: `reports/egitim_test_hash_kontrolu.csv` (`scripts/14_egitim_test_asinalik.py`).

Yani aynı görüntü dosyası iki bölümde birden bulunmuyor: **veri sızıntısı yok.**

### 2.4. ≥ 80 px bandı ve %60 kenar kuralı (HİPOTEZ — eğitim verisi tarafı ölçüldü)

Karo 512, train+valid, min-görünür 0,60. ≥ 80 px bandındaki 409 hedefin 178'i en az bir
karoda kenar kuralından etkileniyor (oran 0,4352) ve hedef başına geçerli karo-etiket
1,5868. Bir önceki bant (65–80 px): 361 hedef, 113 etkilenen (oran 0,3130), hedef başına
1,6094. İki metrikte de ≥ 80 px daha olumsuz.
Kaynak: `reports/kenar_kurali_yukseklik.csv` (`scripts/15_kenar_kurali_yukseklik.py`).

Eğitim verisi davranışı hipotezle aynı yönde. **Recall düşüşüyle nedensellik bu ölçümde
kurulmadı.** Hiçbir bantta tamamen kaybolan hedef yok (0).

### 2.5. Adım sabitken karo boyutu (BULGU — yalnızca veri hazırlama)

Adım iki koşulda da 240 px. Karo 320 / örtüşme 0,25: belirsiz karoya düşen benzersiz
hedef 974 (oran 0,4631), hedef başına geçerli karo-etiket 1,6928. Karo 512 /
örtüşme 0,53125: 851 (oran 0,4047) ve 4,1959. İki metrikte de karo 320 daha fazla
etkileniyor. İki koşulda da tamamen kaybolan hedef 0.
Kaynak: `reports/adim_sabit_karsilastirma.csv` (`scripts/16_adim_sabit_karo_sayimi.py`).

Karo 512 / örtüşme 0,53125 satırı **yeni bir sayımdır**; eğitimde kullanılan
karo 512 / örtüşme 0,20 kümesinin sonucu değildir. Recall ve model üstünlüğü ölçülmedi.

### 2.6. Model-512 ONNX kimliği (BULGU)

Kaynak `agirliklar/model512_best.pt` (5.463.834 bayt) Kaggle çıktısındaki özgün
`best.pt` ile aynı SHA-256'ya sahip (UYUŞTU). Dışa aktarılan ONNX 10.544.114 bayt,
opset 18, girdi `images: 1x3x512x512`, çıktı `output0: 1x5x5376`, sınıf `0:human`,
`onnx.checker` GEÇTİ. Export ayarları: imgsz 512, batch 1, dynamic False,
simplify True, half False, device cpu.
Kaynak: `reports/model512_onnx_bilgisi.csv` (`scripts/17_model512_onnx_export.py`).

### 2.7. PyTorch ↔ ONNX uyumluluğu (BULGU)

Aynı 157 görüntü, aynı SAHI protokolü, değişen tek şey çıkarım motoru. Üç ölçülmüş
eşikte de TP, FN, FP, recall, FP/görüntü ve precision **birebir aynı** (fark sütunlarının
tamamı 0). 3036 tahminin tamamı eşleşti; yalnız bir motorda bulunan tahmin yok.
En büyük skor farkı 2,29e-06, en büyük koordinat farkı 0,000244 piksel.
Kaynak: `reports/pytorch_onnx_metrik.csv`, `reports/pytorch_onnx_fark.csv`
(`scripts/18_pytorch_onnx_karsilastir.py`).

Ölçülen şey **metrik eşitliğidir**; bit düzeyinde aynılık değildir.

### 2.8. Gerçek Celery hattında süre (BULGU)

Görev `olcum-onnx-sure-20260912-142859` (koşu 5), 157 kare, 157 done / 0 failed /
0 takılı, toplam 2450 tespit, iki işçi süreci, 2 soğuk başlangıç, aynı ONNX oturumuyla
tek süreçte en çok 79 kare.

| Aşama (sn) | min | medyan | p95 | maks |
|---|---|---|---|---|
| Görüntü okuma | 7,2005 | 10,1187 | 15,1177 | 19,5873 |
| ONNX çıkarım | 6,3205 | 9,3633 | 12,5423 | 18,0256 |
| NMS + koordinat | 0,2946 | 0,3895 | 0,4907 | 0,5730 |
| Veritabanına yazma | 0,0054 | 0,0173 | 0,0402 | 0,0559 |
| Kare toplam | 14,8069 | 19,8840 | 28,2916 | 37,3691 |

Kaynak: `reports/gercek_onnx_celery_sure.csv` ve `..._ozet.csv`
(`scripts/19_gercek_onnx_celery_sure.py`).

Kuyruk bekleme süresi (medyan 845,4332 sn) ayrı tutulur: bu, karenin işçi sırasını
bekleme süresidir, kare çalışma süresi değildir.

### 2.9. Zaman aşımı kararı (KARAR — ölçüme dayalı)

Ölçülen en yavaş görev 37,3692 sn. Karar kuralı (10× pay + 60 sn temiz kapanma payı +
1,5× visibility) en az soft 374 / hard 434 / visibility 651 gerektiriyor; mevcut
600 / 660 / 900 bunların hepsini aşıyor ve soft < hard < visibility sıralaması
sağlanıyor. **Karar: KORUNDU**, hiçbir ayar değiştirilmedi.
Kaynak: `reports/gercek_onnx_celery_sure_ozet.csv`.

Güvenlik payı bir ölçüm değildir; CSV'de `guvenlik_payi_notu` sütununda
"KARAR (olcum degil)" olarak işaretlidir.

### 2.10. SIGKILL dayanıklılığı (BULGU)

Görev `sigkill-dayaniklilik-20260912-151442`, 4 kare. Tarama sürerken işçi konteyneri
`docker kill --signal=KILL` ile öldürüldü; kanıt çıkış kodu 137 ve konteynerin durması
(graceful stop kullanılmadı). Öldürme anındaki kare 338, durumu `processing`.

Ölçülenler: öldürülen kare yeniden teslim edildi ve `done` oldu (kill'den 1017,5 sn
sonra; visibility timeout 900 sn), 4/4 kare son duruma ulaştı, kayıp kare 0, takılı
kare 0, kontrolsüz yinelenen Detection 0, toplam 44 tespit, koşu `done`.
Kaynak: `reports/onnx_sigkill_dayaniklilik.csv` (`scripts/20_onnx_sigkill_dayaniklilik.py`).

**Ölçülemeyen:** karenin kaç kez işlenmeye başlandığı. SIGKILL ile ölen girişim iş
ortasında öldüğü için zamanlama kaydına satır yazamadı; bu yüzden "deneme sayısı" bir
ölçüm olarak verilemez. `acks_late=True` ile idempotanslığın birlikte çalıştığı,
yukarıdaki kayıp/takılı/yinelenen sonuçlarıyla gösterilmiştir.

### 2.11. Görüntüyü kare başına tek kez okuma (BULGU + açık kısıt)

Eskiden `OnnxDedektor.detect` her karo için görüntüyü diskten yeniden açıyordu; artık
kare başına bir kez okunuyor. Aynı 157 görüntü, aynı protokol, aynı model SHA-256 ile
tekrar ölçüldü: görev `olcum-onnx-tek-okuma-20260912-153715` (koşu 8), 157/157 done,
toplam 2450 tespit — **tespit davranışı değişmedi**.

| Aşama | medyan önce → sonra | p95 önce → sonra |
|---|---|---|
| Görüntü okuma | 10,1187 → 0,2774 (−%97,26) | 15,1177 → 0,5107 (−%96,62) |
| ONNX çıkarım | 9,3633 → 15,3550 (+%63,99) | 12,5423 → 30,5586 (+%143,64) |
| Kare toplam | 19,8840 → 16,0092 (−%19,49) | 28,2916 → 31,6530 (+%11,88) |

Kaynak: `reports/tek_okuma_karsilastirma.csv` (`scripts/21_tek_okuma_karsilastir.py`),
ham koşular `reports/gercek_onnx_celery_sure.csv` ve
`reports/gercek_onnx_celery_sure_tek_okuma.csv`.

Doğru okuma: **medyan kare süresi düştü, kuyruk sonu (p95) yükseldi.** Kare toplam
medyanı 19,8840 → 16,0092 sn (−%19,49) inerken p95 28,2916 → 31,6530 sn (+%11,88)
yükseldi. ONNX çıkarım süresi de arttı (medyan +%63,99, p95 +%143,64); artışın
**sebebi bu deneyde ölçülmedi** ve görüntü okuma kazanımı olarak yazılamaz. Kuyruk bekleme farkı (medyan 845,4332 → 614,4650 sn) işçi zamanlamasına
bağlıdır, kod kazanımı sayılmaz.

### 2.12. Konum kaynağı taraması (BULGU — Hafta 5)

Hafta 5'in ilk sorusu şuydu: arayüz bir göreve veya kareye konum yazabilir mi?
Soru sayımla cevaplandı. Tarama çıkarım gerektirmediği için veri kümesinin
tamamı tek koşuda incelendi.

| Kaynak | İncelenen | EXIF bulunan | GPS bulunan | Enlem/boylam bulunan |
|---|---|---|---|---|
| HERIDAL train | 1106 | 0 | 0 | 0 |
| HERIDAL valid | 316 | 0 | 0 | 0 |
| HERIDAL test | 157 | 0 | 0 | 0 |
| **HERIDAL toplam** | **1579** | **0** | **0** | **0** |
| Veritabanı Frame kaydı | 494 | 0 | — | 0 |

Kaynak: `reports/hafta5_gps_kaynak_karari.csv` (`scripts/22_konum_kaynagi_tara.py`)

Veri kümesi Roboflow üzerinden yeniden dışa aktarıldığı için EXIF blokları
kaynağında silinmiş. Dosya adları kaynak önekini taşır, konum taşımaz; depoda
uçuş günlüğü veya koordinat tablosu da yok. Alım hattındaki EXIF okuma kodu
(`core/services.extract_exif`) çalışıyor, okuyacak veri yok.

### 2.13. Konum politikası (KARAR)

Doğrulanabilir hiçbir koordinat kaynağı bulunmadığı için:

- Arayüz **"Konum bilgisi mevcut değil"** gösterir ve nedenini yazar.
- Kayıtta gerçek koordinat varsa gösterilir, kaynağı da belirtilir.
- Dosya sırasından, karo satır/sütunundan veya görüntü pikselinden enlem/boylam
  **türetilmez**. Böyle bir değer ölçüm değil uydurma olur.
- Hafta 6'da demo haritası gerekirse koordinat hem veride hem arayüzde
  **"Demo konumu — gerçek GPS değildir"** olarak etiketlenir.
- Koordinat saklanmaya başlandığında değerin yanında **kaynağı** da saklanmalıdır
  (exif / uçuş günlüğü / operatör beyanı / demo). Bu alan Hafta 5'te
  **eklenmedi**, yalnızca not edildi.

Gelecekteki kaynak önceliği: doğrulanmış EXIF GPS → uçuş günlüğü + zaman damgası
eşleştirmesi → operatörün açıkça verdiği konum → açıkça etiketlenmiş demo →
konum yok.

### 2.14. Operatör arayüzü (Hafta 5)

`frontend/` altında React + Vite + TypeScript arayüzü kuruldu; sunucu durumunu
TanStack Query tutuyor, sayfa geçişi react-router ile. Arayüz dili Türkçe.
Kapsam ifadesi ("Eğitim ve araştırma prototipidir. Tespitler operatör kararının
yerine geçmez.") her sayfada görünür.

Kurulan akış: giriş → görev listesi → görev oluşturma → kare ekleme → model
seçimi ve tarama başlatma → ilerleme izleme → tespitlerin gerçek görüntü
üzerinde incelenmesi → çıkış.

**Gerçek API entegrasyonu.** Arayüzün kullandığı her uç koddan okunarak ve
çalışan yerel API'ye kimlik doğrulamalı istek atılarak doğrulandı
(`reports/hafta5_api_sozlesmesi.csv`, 14 uç). Frontend'in zorunlu akışı mevcut
uçlarla tamamlanamadığı için üç uç eklendi; yeni veri modeli ve migration yok:

- `GET /api/missions/{id}/` — görev ayrıntısına doğrudan gidilebilmesi için
  (önceden 404'tü).
- `GET /api/missions/{id}/runs/` — sayfa yenilendikten sonra görevin son/aktif
  koşusunun bulunabilmesi için (önceden yalnızca POST kabul ediyordu).
- `GET /api/frames/{id}/image/` — görüntünün kimlik doğrulamasıyla okunması
  için. Gerekçe: `/media/` adresi DEBUG'ta kimlik doğrulamasız servis ediliyor,
  üretimde hiç servis edilmiyor. Dosya yolu istemciden gelmez, yalnızca Frame
  birincil anahtarı alınır.

Görev serializer'ına kare sayımları ve son koşu özeti salt okunur alan olarak
eklendi; mevcut alanların anlamı değişmedi.

**Doğrulama.** Operatör akışı gerçek backend ve gerçek tarayıcı üzerinde uçtan
uca yürütüldü: 34 kontrolün tamamı geçti
(`reports/hafta5_frontend_dogrulama.csv`). Entegrasyon koşusu Model-512 ONNX ile
2 karelik bir görevde yapıldı; koşu `done`, 2 kare tamamlandı, 0 başarısız.
**Bu bir performans ölçümü değildir** — Hafta 4'ün 157 karelik süre koşusu
tekrarlanmadı ve buradan hiçbir hız veya doğruluk sayısı türetilmedi.

Test ve derleme sonuçları:

| Kapı | Sonuç |
|---|---|
| Frontend testleri (Vitest) | 63 test, 7 dosya — geçti |
| Frontend lint (ESLint) | 0 hata (5 react-refresh uyarısı) |
| TypeScript denetimi | geçti |
| Frontend üretim derlemesi | geçti |
| Backend testleri (pytest) | 97 test — geçti (Hafta 4 sonunda 80 idi; 17'si yeni uçlar için) |
| Script testleri (pytest) | 145 test — geçti |
| Tarayıcı konsolu / ağ | uygulama kaynaklı hata yok |

Ekran görüntüleri: `rapor/gorseller/hafta5/`

**Arayüzün konum gösterme politikası** bölüm 2.13'teki karardır ve testle
korunuyor: GPS yokken arayüz koordinat üretmiyor, tespitler "kesin insan" diye
adlandırılmıyor.

**Görüntüleme eşiği.** Tespit inceleme ekranındaki kaydırıcı yalnızca ekranda
çizilen kutuları süzer; modeli yeniden çalıştırmaz ve **bir değerlendirme
metriği değildir**. Başlangıç değeri sabit yazılmaz, koşunun kendi
`conf_threshold` değerinden gelir. Kutular 0,05 tabanıyla saklandığı için tek
bir taramadan farklı eşikler yeniden tarama olmadan sorulabilir.

### 2.15. Görev üyeliği ve erişim denetimi (Hafta 6)

Hafta 5'e kadar erişim tek ölçüte bağlıydı: görevi kim oluşturduysa onu
görüyordu. Bu, ekip işi bir bağlamda yetersiz. `MissionMember` kaydı görev ile
kullanıcı arasına üç rol koyuyor: sahip (üyelik ve rol yönetir), operatör (kare
ekler, tarama başlatır, inceleme ve bulgu yazar), izleyici (yalnızca okur).

`Mission.created_by` silinmedi — geçmiş kayıtların kim tarafından açıldığını
açıklamaya devam ediyor — ama **yetki taşımıyor**. Mevcut on görevin sahibi
migration ile owner üyeliğine taşındı; veri kaybı olmadı (10 görev, 496 kare,
6622 tespit korundu).

Görev oluşturulunca owner üyeliğini bir `post_save` sinyali yazıyor. Kural
yalnızca API view'ında dursaydı yönetim komutundan, fixture'dan veya testten
açılan her görev sahipsiz kalırdı.

Üye olmayan kullanıcı **403 değil 404** alır: 403, kaydın varlığını sızdırır ve
kimlik deneyerek başkasının kaç görevi olduğunu saymayı mümkün kılar.

| İşlem | owner | operator | viewer | üye değil |
|---|---|---|---|---|
| Görev görüntüleme | 200 | 200 | 200 | 404 |
| Kare ekleme | 201 | 201 | 403 | 404 |
| Tarama başlatma | 202 | 202 | 403 | 404 |
| İnceleme yazma | 201 | 201 | 403 | 404 |
| Bulgu yazma | 201 | 201 | 403 | 404 |
| Kümeleme çalıştırma | 200 | 200 | 403 | 404 |
| Üye ekleme | 201 | 403 | 403 | 404 |
| Denetim okuma | 200 | 200 | 200 | 404 |
| Denetim yazma girişimi | 405 | 405 | 405 | 405 |

Kaynak: `reports/hafta6_yetki_matrisi.csv` (`scripts/24_yetki_matrisi.py`)

*Bu tablo ne söylüyor: Yirmi işlemin dördü ayrı kullanıcı sınıfıyla gerçekten
çağrıldı ve dönen kodlar kaydedildi; matris bir niyet beyanı değil ölçüm.
Denetim satırındaki 405 her rolde aynı, çünkü denetim kaydına API'den yazma ucu
hiç yok — owner bile yazamıyor.*

### 2.16. /media/ açığının kapatılması (Hafta 6)

Hafta 5 raporunda açık kısıt olarak kaydettiğim davranış kapatıldı. DEBUG
açıkken Django `/media/` altını kimlik doğrulaması olmadan sunuyordu; üyelik
devreye girince bu, denetimi tamamen dolaşan bir açık haline geldi.

Yol tamamen kaldırıldı. Görüntüye tek erişim `/api/frames/{id}/image/` ucu:
`Authorization` başlığını okuyor, karenin görevine üyeliği doğruluyor ve dosya
adını istemciden değil veritabanından alıyor. Ölçüm: kimliksiz istek 404,
kimlikli üyenin isteği de 404 (yol kapalı), güvenli uçtan üye 200 / üye olmayan
404.

### 2.17. Operatör incelemesi ve denetim kaydı (Hafta 6)

`Review`, bir tespit için operatörün kararını (doğrulandı / reddedildi /
belirsiz) ayrı bir tabloda tutuyor ve `Detection` kaydına dokunmuyor. Model
çıktısı ile insan yargısı aynı alana yazılsaydı ikisi geri dönülmez biçimde
karışır ve geçmiş ölçümler yeniden üretilemezdi.

Tekillik `(tespit, inceleyen)` çiftinde: her operatör kendi kararını günceller,
başkasınınkini ezmez. İki operatörün anlaşamadığı bilgisi korunuyor.

`AuditLog` eklemeli: `save()` yalnızca ilk yazmaya izin veriyor, `delete()` her
zaman hata veriyor, API'de yazma ucu yok. Kayıt işlemi yapan kodla **aynı
transaction içinde** yazılıyor — işlem geri alınırsa kayıt da geri alınıyor,
yani başarısız bir işlem sahte bir geçmiş üretmiyor. Hassas anahtarlar (parola,
token, e-posta, oturum) kayda hiç girmiyor ve uzun değerler kırpılıyor.

### 2.18. Coğrafi bulgu ve konum kaynağı (Hafta 6)

`Finding`, haritada gösterilebilen bulguyu tutuyor. Konum `geography(Point,
4326)` tipinde saklanıyor ve GiST indeksi kuruldu (PostGIS 3.5.3); bu sayede
mesafe sorguları doğrudan **metre** cinsinden çalışıyor.

Modelin en kritik alanı koordinat değil **kaynağı**. Beş değer ayırt ediliyor:
konum yok, EXIF GPS, uçuş günlüğü, operatör girişi, demo/sentetik. İlk ikisi
ölçülmüş sayılıyor ve **arayüzden seçilemiyor** — elle girilen bir koordinatın
"EXIF'ten geldi" diye kaydedilmesi haritaya bakan kişiyi yanıltırdı.

Bir veritabanı kısıtı, konum yokluğu ile koordinatın karışmasını engelliyor:
konum boşsa kaynak `none` olmak zorunda, konum doluysa `none` olamaz. Böylece
**null konum ile "0,0" birbirine karışmıyor** — 0,0 Gine Körfezi'nde gerçek bir
noktadır.

Detection kutusundan otomatik koordinat **üretilmiyor**. Piksel ile dünya
arasında dönüşüm için kameranın konumu, irtifası, yönelimi ve görüş açısı
gerekir; hiçbiri kayıtlarda yok.

### 2.19. Union-Find kümelemesi ve harita (Hafta 6)

Aynı görevdeki konumlu bulgular, metre cinsinden bir mesafe kuralıyla bağlı
bileşenlere ayrılıyor. Aday çiftleri PostGIS buluyor; her çift Python'da
karşılaştırılmıyor.

**Eşik bir KARARDIR, ölçüm değildir.** Varsayılan 50 metre ve hiçbir alan
ölçümünden türetilmedi.

**Geçişlilik kasıtlı:** A–B ve B–C eşik içindeyse, A–C arası eşikten büyük olsa
bile üçü aynı kümeye girer. Sonucu şu: eşik, kümenin çapı değildir.

| Senaryo | Beklenen küme | Gerçek küme |
|---|---|---|
| Tek nokta | 1 | 1 |
| İki yakın nokta (10 m) | 1 | 1 |
| İki uzak nokta (500 m) | 2 | 2 |
| Geçişli üçlü (40 + 40 m, uçlar 80 m) | 1 | 1 |
| Aynı koordinat (üç kayıt) | 1 | 1 |
| Eşik sınırının içinde (49 m) | 1 | 1 |
| Eşik sınırının dışında (51 m) | 2 | 2 |
| Demo ve gerçek yan yana (5 m) | 2 | 2 |
| Konumsuz kayıt dâhil | 1 | 1 |
| Farklı görevler | 2 | 2 |

Kaynak: `reports/hafta6_kumeleme_dogrulama.csv` (`scripts/23_kumeleme_dogrula.py`)

*Bu tablo ne söylüyor: On senaryonun onunda da beklenen ve gerçek küme sayısı
uyuştu; hepsi deterministik ve idempotent çıktı. Geçişli üçlü satırı kasıtlı
davranışın kanıtı: uçları eşikten uzak olduğu hâlde zincir tek küme üretiyor.
Eşik sınırının iki yanı (49 ve 51 metre) mesafenin gerçekten metre cinsinden
ölçüldüğünü gösteriyor.*

Harita Leaflet ile eklendi ve bölüm 2.13'teki konum kararına tabi: **konumlu
bulgu yoksa harita hiç açılmıyor**, çünkü boş bir dünya haritası "konum verisi
var ama işaret yok" izlenimi verir. Demo koordinatlar kesikli çerçeveli
işaretle çiziliyor, balonda kaynak görünüyor ve harita üstünde kapatılamayan bir
uyarı duruyor.

Demo verisi ayrı ve açık adlı bir görevde duruyor ("DEMO — sentetik konumlar
(gerçek GPS değildir)"), `demo_konum_uret` yönetim komutuyla üretiliyor ve
gerçek görüntülerden **türetilmiyor**.

### 2.20. Hafta 6 test ve doğrulama sonuçları

| Denetim | Sonuç |
|---|---|
| Backend testleri | 215 test, tamamı geçti (Hafta 5 sonunda 97 idi) |
| Ölçüm script'i testleri | 145 test, tamamı geçti |
| Arayüz testleri | 9 dosyada 105 test, tamamı geçti (Hafta 5 sonunda 63 idi) |
| Arayüz lint | 0 hata |
| TypeScript denetimi | Geçti |
| Arayüz üretim derlemesi | Geçti |
| Migration tutarlılığı | Bekleyen migration yok |
| PostGIS uzamsal indeks | `gist (location)` doğrulandı |
| Rol/işlem matrisi | 20 işlem, tamamı beklenen kodu döndü |
| Kümeleme senaryoları | 10 senaryo, tamamı geçti |
| Uçtan uca doğrulama | 26 kontrol, tamamı geçti |
| Tarayıcı konsolu / ağ | Uygulama kaynaklı hata yok |

*Bu tablo ne söylüyor: Üç test paketi de geçiyor ve backend testleri 97'den
215'e çıktı — artış üyelik, inceleme, bulgu, denetim ve kümeleme için yazılan
testlerden geliyor. Uçtan uca doğrulama dört ayrı kullanıcı sınıfıyla gerçek
tarayıcıda yürütüldü; ayrıntısı `reports/hafta6_harita_dogrulama.csv`.*

Ekran görüntüleri: `rapor/gorseller/hafta6/`

**Bu doğrulama bir performans ölçümü değildir.** Kullanılan koşu Hafta 5'ten
kalan iki karelik koşudur; model doğruluğu veya hız hakkında yeni bir iddia
kurulmadı ve 157 karelik süre koşusu tekrarlanmadı.

## 3. Açık kısıtlar

- **Kaynak aşinalığı:** Test hedeflerinin 939/970'i ZRI kaynağından ve ZRI eğitimde de
  var (`reports/egitim_test_onek_kesisimi.csv`). Sonuçlar bu kaynağa aşina bir model
  için geçerlidir.
- **ONNX çıkarım süresi değişkenliği:** Tek okuma koşusunda çıkarım medyanı +%63,99,
  p95 +%143,64 arttı. Sebep ölçülmedi; iki işçinin aynı CPU'yu paylaşması dâhil hiçbir
  açıklama doğrulanmadı.
- **Kuyruk sonu davranışı:** Kare toplam p95 28,2916 → 31,6530 sn'ye çıktı. Medyandaki
  iyileşme p95'i kapsamıyor.
- **≥ 80 px bandı:** Kenar kuralı etkisi yalnızca eğitim verisinde ölçüldü; recall ile
  nedensellik kurulmadı.
- **Model-320 yok:** 2x2 deney matrisinin dördüncü hücresi hâlâ boş.
- **Taban çizgisinin FP eğrisi** yalnızca üç eşikte ölçülü (`reports/esik_taramasi.csv`
  içinde `fp_durumu` sütunu hangi noktanın ölçülü olduğunu söyler).
- **Konum verisi yok:** Elimizdeki 1579 görüntünün hiçbirinde EXIF GPS yok, bu
  yüzden arayüz konum gösteremiyor ve harita kurulamıyor (bölüm 2.12–2.13).
- **JWT localStorage'da:** Backend HTTP-only çerez desteklemediği için token
  tarayıcı deposunda duruyor. Bir XSS açığı oturumun çalınması demektir; kabul
  edilen prototip sınırı budur ve `frontend/README.md` içinde yazılıdır.
  Yenileme ucu rotasyon yapmıyor: çalınan bir refresh token ömrü boyunca
  geçerli kalıyor.
- **Kümeleme eşiği ölçülmedi:** 50 metre bir karardır. Gerçek uçuş verisi
  olmadığı için hangi eşiğin doğru olduğu ölçülemedi.
- **Küme merkezi ölçülmüş konum değildir:** üyelerin aritmetik ortalamasıdır.
- **Kümeleme elle tetikleniyor:** yeni bulgu eklendiğinde kümeler kendiliğinden
  yeniden hesaplanmıyor.
- **Denetim kaydı ORM seviyesinde korunuyor:** veritabanına doğrudan erişimi
  olan biri yine de geçmişi değiştirebilir. Amaç, uygulama kodunun veya bir API
  ucunun kazara ya da kötü niyetle geçmişi bozmasını engellemek.
- **Tarama iptali/yeniden başlatma yok:** Backend'de böyle bir uç yok, arayüz de
  uydurma düğme göstermiyor.
- **Arayüzde listeler ilk sayfayla sınırlı:** Kare listesi ve bir karedeki tespit
  listesi 20 kayıtla gösteriliyor; toplam sayı ayrıca yazılıyor.

## 4. Yapılmayanlar (yapılmış gibi gösterilmez)

- Model-320 eğitilmedi, ölçülmedi; `agirliklar/` altında yalnızca Model-512 dosyaları var.
- ONNX üzerinde doğruluk kaybı dışında bir hız optimizasyonu (batch, paralellik, quantize)
  denenmedi.
- Uçtan uca (Playwright vb.) otomatik tarayıcı test paketi kurulmadı; tarayıcı
  doğrulaması elle yürütüldü ve ölçüm kayıtlarına yazıldı.
- Gerçek GPS'li veri hâlâ yok; haritada yalnızca elle girilen veya demo
  koordinatlar görünebiliyor.
- Arayüzde kullanıcı arama yok; üye eklerken kullanıcı adı elle yazılıyor.
- Bulgu durumu ve başlığı API'den düzenlenebiliyor ama arayüze bağlanmadı.

## 5. Sıradaki işler

### 5.1. Ölçüm/analiz tarafında açık kalanlar

1. ONNX çıkarım süresindeki artışın mekanizması (tek işçiyle ve iki işçiyle ayrı ölçüm).
2. Kare toplam p95'teki yükselmenin hangi karelerden geldiği.
3. Model-320 eğitimi ve kendi ölçek tabanına karşı değerlendirilmesi.
4. ≥ 80 px bandındaki düşüşün kenar kuralıyla nedensel bağı (eğitim verisi tarafı ölçüldü,
   model tarafı ölçülmedi).

### 5.2. Bir sonraki adımda fiilen yapılacak iş (Hafta 7)

Hafta 6 kapandı: üyelik, inceleme, coğrafi bulgu, denetim kaydı, kümeleme ve
harita kuruldu; yedi kapının tamamı geçildi (bölüm 2.15–2.20).

Hafta 7'nin işi **yanlış pozitif analizidir**. Elimizde artık iki şey birden
var: modelin ürettiği tespitler ve operatörün bunlar hakkındaki kararı. Bu
ikisini yan yana koymak, Hafta 4'ten beri yalnızca etiketlere karşı ölçülen
yanlış pozitiflerin gerçekte neye benzediğini incelemeyi mümkün kılıyor —
reddedilen adaylar hangi arazi, boyut ve kontrast koşullarında yoğunlaşıyor.

Bu analiz yapılırken dikkat edilecek nokta şu: operatör kararı bir **etiket
değildir**. Reddedilen bir aday gerçekten yanlış pozitif olabilir, ama operatör
de yanılmış olabilir. İki kaynağı aynı sayıya karıştırmamak gerekiyor.

Bölüm 6 yazıldı (`rapor/bolum_06.md`): Hafta 5'in API sözleşmesi, arayüz
mimarisi, oturum güvenlik sınırı, tespit geometrisi ve konum kaynağı kararını
kaynak CSV'leriyle birlikte sunuyor.
