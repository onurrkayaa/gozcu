# Proje Durumu

Bu dosya rapor gövdesinin parçası değildir; nerede olduğumuzu ve sıradaki işin ne
olduğunu tek yerde tutar. Buradaki her sayı bir çıktı dosyasından okunur ve yanında
üreten CSV ile script yazar. Bir sayı ile bu dosya çelişirse **CSV kazanır**.

Son güncelleme: Hafta 4 kapanış denetimi.

---

## 1. Nerede duruyoruz

Hafta 0–3'te ölçüm altyapısı, taban çizgisi ve asenkron tarama hattı kuruldu.
Hafta 4'te kendi verimizle model eğitildi, ONNX'e aktarıldı ve gerçek Celery
hattına bağlandı. **Hafta 4 kapanmıştır**; sıradaki ana iş Hafta 5'tir.

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

Doğru okuma: **medyan kare süresi düştü, kuyruk sonu (p95) yükseldi.** ONNX çıkarım
süresi arttı; artışın sebebi bu deneyde ölçülmedi ve görüntü okuma kazanımı olarak
yazılamaz. Kuyruk bekleme farkı (medyan 845,4332 → 614,4650 sn) işçi zamanlamasına
bağlıdır, kod kazanımı sayılmaz.

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

## 4. Yapılmayanlar (yapılmış gibi gösterilmez)

- Model-320 eğitilmedi, ölçülmedi; `agirliklar/` altında yalnızca Model-512 dosyaları var.
- ONNX üzerinde doğruluk kaybı dışında bir hız optimizasyonu (batch, paralellik, quantize)
  denenmedi.
- Operatöre dönük arayüz yok; hat şu an yalnızca API ve kuyruk seviyesinde çalışıyor.

## 5. Sıradaki işler

### 5.1. Ölçüm/analiz tarafında açık kalanlar

1. ONNX çıkarım süresindeki artışın mekanizması (tek işçiyle ve iki işçiyle ayrı ölçüm).
2. Kare toplam p95'teki yükselmenin hangi karelerden geldiği.
3. Model-320 eğitimi ve kendi ölçek tabanına karşı değerlendirilmesi.
4. ≥ 80 px bandındaki düşüşün kenar kuralıyla nedensel bağı (eğitim verisi tarafı ölçüldü,
   model tarafı ölçülmedi).

### 5.2. Bir sonraki adımda fiilen yapılacak iş (Hafta 5)

Operatörün sistemi fiilen kullanabildiği yüzü kurmak: görüntü yükleme, tarama başlatma,
ilerleme takibi ve tespitlerin görüntü üzerinde eşik kaydırılarak incelenmesi. Arka uçta
gereken her şey hazır — tespitler sabit bir depolama tabanıyla saklanıyor ve eşik okuma
anında uygulanıyor, yani arayüzün eşik değiştirmesi yeni bir tarama gerektirmiyor.

Bunun yanında Bölüm 5'in yazımı: Hafta 4'ün dışa aktarım, motor eşdeğerliği, gerçek süre
ve dayanıklılık sonuçları bölüm için yeterli kanıta sahiptir.
