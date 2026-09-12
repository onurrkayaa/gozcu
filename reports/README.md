# reports/ — ölçüm çıktıları

Bu klasördeki CSV'ler `scripts/` altındaki ölçüm script'lerinin ürünüdür. Her
CSV, satırlarının yanında `kosu_` önekli sütunlarda kendi koşu bilgisini
taşır: model, karo boyutu, örtüşme, IoU eşiği, cihaz, paket sürümleri, tarih ve
çalıştırılan komut. Aşağıdaki "üretim komutu" sütunu tahmin değil, doğrudan o
dosyanın `kosu_komut` alanından okunmuştur (yalnızca depo kökü yolu kısaltıldı).

## Depoda olmayanlar

`.gitignore` yalnızca bu klasörün kökündeki CSV'leri izler. Aşağıdakiler
depoda **yoktur**, yerelde yeniden üretilmeleri gerekir:

| Ne | Neden yok | Nasıl üretilir |
|---|---|---|
| `karo_veri_manifest_320.csv`, `karo_veri_manifest_512.csv` | ~5 MB, üretimi 3 dakika | `python scripts/11_karo_veri_hazirla.py --karo 320` / `--karo 512 --ortusme 0.20` |
| `*.log` (koşu günlükleri) | Terminal çıktısının kopyası, CSV'de olmayan bilgi taşımaz | İlgili script'i `> reports/<ad>.log 2>&1` ile çalıştırarak |
| `ornekler/`, `ornekler_BLI/`, `ornekler_CAB/`, `ornekler_GRO/` | Görselleştirme PNG'leri, büyük | `python scripts/03_gorsellestir.py --bolum <bolum> [--onek <ONEK>]` |
| `gozle_kontrol_320/` | Karolanmış eğitim kümesinin gözle kontrol PNG'leri | `python scripts/12_gozle_kontrol.py --karo 320` |
| `recall_vs_kutu_boyutu.png` | Grafik | `python scripts/06_rapor_uret.py` |

Karolanmış eğitim kümelerinin kendisi (`data/karo_320/`, `data/karo_512/`;
573 MB ve 1,4 GB) da depoda değildir; yukarıdaki 11 numaralı komutla üretilir.

## Önce okunması gereken iki uyarı

**`taban_cizgisi.csv` — KARŞILAŞTIRMA TABANI OLARAK KULLANILMAZ.**
`--limit 100` ile üretilmiştir, yani test bölümünün 157 görüntüsünün yalnızca
100'ünü kapsar. Dosyalar ada göre sıralandığı için bu 100 görüntü kaynakları
dengesiz temsil eder: 70 VRD görüntüsünün tamamı ama ZRI'nin 87'sinden yalnızca
30'u. ZRI veri kümesinin en kolay kaynağı olduğundan bu alt küme çarpıktır.
Taban çizgisi için `test_taban_cizgisi.csv` kullanılmalıdır.

**`taban_cizgisi_tam.csv` — adındaki "tam" tüm veri kümesi demek DEĞİLDİR.**
Dosya `--bolum test --limit 157` ile üretilmiştir; "tam" burada *test bölümünün
tamamı* anlamına gelir, train+valid+test birleşimi değil.
`test_taban_cizgisi.csv` ile aynı ölçümdür ve sayıları birebir aynıdır (970
hedef, conf 0,30'da recall 0,3804); tek fark `test_taban_cizgisi.csv`'nin kaynak
önekine göre kırılım da içermesidir.

## Taban çizgisi hangisi

Raporda "taban çizgisi" diye anılan tek sayı, `test_taban_cizgisi.csv`
dosyasındaki **`TOPLAM` / `conf_esigi = 0.3`** satırıdır: eğitimsiz yolo11n,
test bölümü (157 görüntü, 970 hedef), karo 512, **recall 0,3804**,
**FP/görüntü 1,81**. Eğitim sonrası kazanım bu iki eksende birden ölçülür.

`test_taban_cizgisi_karo320.csv` bir ölçek deneyidir, taban çizgisi değildir:
eğitim yine yok, yalnızca karo 512 yerine 320 kullanılmıştır.

## İzlenen dosyalar

| Dosya | Ne içerir | Üretim komutu (`kosu_komut`) | Güvenilir mi |
|---|---|---|---|
| `veri_istatistik.csv` | Bölüm başına görüntü/kutu sayıları, görüntü ve kutu ölçülerinin min/medyan/maks değerleri | `scripts/00_veri_incele.py` | Evet |
| `onek_dagilimi.csv` | Bölüm × kaynak öneki kırılımında görüntü, kutu ve boş görüntü sayıları | `scripts/00_veri_incele.py` | Evet |
| `taban_cizgisi.csv` | Eğitimsiz modelin üç güven eşiğindeki metrikleri | `scripts/01_taban_cizgisi.py --bolum test --limit 100 --dogrula` | **HAYIR** — çarpık alt küme, yukarıdaki uyarıya bakın |
| `taban_cizgisi_tam.csv` | Eğitimsiz modelin test bölümünün tamamındaki metrikleri | `scripts/01_taban_cizgisi.py --bolum test --limit 157 --cikti reports/taban_cizgisi_tam.csv` | Evet, ancak adı yanıltıcı — yukarıdaki uyarıya bakın |
| `taban_cizgisi_onek.csv` | Tüm veri kümesinde (train+valid+test) kaynak öneki × güven eşiği kırılımı, TOPLAM ve ZRI_HARIC özet satırlarıyla | `scripts/01_taban_cizgisi.py --bolum hepsi --limit 0 --onek-bazinda --cikti reports/taban_cizgisi_onek.csv` | Evet — eğitim öncesi olduğu için üç bölümü birleştirmek geçerliydi; eğitimden sonra tekrarlanamaz |
| `kutu_bazinda_sonuc.csv` | `taban_cizgisi_onek.csv` koşusunun kutu bazında kaydı: her hedefin boyutu ve her eşikte eşleşip eşleşmediği | `scripts/01_taban_cizgisi.py --bolum hepsi --limit 0 --onek-bazinda --cikti reports/taban_cizgisi_onek.csv` | Evet |
| `test_taban_cizgisi.csv` | **Taban çizgisi.** Eğitimsiz model, test bölümü, karo 512; kaynak öneki × güven eşiği kırılımı | `scripts/01_taban_cizgisi.py --bolum test --karo 512 --ortusme 0.2 --iou 0.3 --model yolo11n.pt --conf 0.05 0.15 0.30 --onek-bazinda --limit 0` | Evet |
| `test_kutu_bazinda.csv` | Taban çizgisi koşusunun kutu bazında kaydı | Yukarıdakiyle aynı koşu, `--kutu-cikti reports/test_kutu_bazinda.csv` | Evet |
| `test_taban_cizgisi_karo320.csv` | Ölçek deneyi: aynı ölçüm, karo 320 / örtüşme 0,25 | `scripts/01_taban_cizgisi.py --bolum test --iou 0.3 --model yolo11n.pt --karo 320 --ortusme 0.25 --conf 0.05 0.15 0.30 --onek-bazinda --limit 0` | Evet — taban çizgisi değil, ölçek deneyi |
| `test_kutu_bazinda_karo320.csv` | Ölçek deneyinin kutu bazında kaydı | Yukarıdakiyle aynı koşu, `--kutu-cikti reports/test_kutu_bazinda_karo320.csv` | Evet |
| `model512_egitim.csv` | Kaggle eğitim koşusunun epoch başına metrikleri: train/val kayıpları, precision, recall, mAP50, mAP50-95, öğrenme oranları. 100 epoch | Kaggle notebook `egitim/kaggle_egitim.ipynb` çıktısındaki `results.csv` kopyası; `kosu_komut` alanı yoktur | Evet — 512×512 karolar üzerinde; taban çizgisiyle karşılaştırılamaz |
| `test_model512.csv` | Eğitilmiş Model-512'nin test bölümü ölçümü, kaynak öneki × güven eşiği kırılımı | `scripts/01_taban_cizgisi.py --bolum test --iou 0.3 --model agirliklar/model512_best.pt --karo 512 --ortusme 0.2 --conf 0.05 0.15 0.30 --onek-bazinda --limit 0` | Evet — protokol taban çizgisiyle birebir aynı, doğrudan karşılaştırılabilir |
| `test_kutu_bazinda_model512.csv` | Model-512 ölçümünün kutu bazında kaydı | Yukarıdakiyle aynı koşu, `--kutu-cikti` | Evet |
| `tahminler_model512.csv` | Model-512'nin NMS sonrası TÜM tahminleri (TP + FP), skor ve koordinatlarıyla. FP/görüntü eğrisi ancak bu dosyadan türetilebilir | Yukarıdakiyle aynı koşu, `--tahmin-kaydi` | Evet — skorlar 4 basamağa yuvarlıdır; eşik tam bir skor değerine denk gelirse sayım 1-2 tahmin şişebilir |
| `esik_taramasi.csv` | conf 0,05-0,95 arası 0,01 adımla recall ve FP/görüntü; TOPLAM, ZRI, ZRI_HARIC ayrı | `scripts/13_kutu_bazinda_karsilastir.py` | Kısmen — Model-512 satırlarında FP tamamen dolu; Taban-512'de yalnızca ölçülmüş üç eşikte dolu, geri kalanı `olculmedi` (taban için tahmin kaydı alınmadı). `fp_durumu` sütunu hangisinin hangisi olduğunu söyler |
| `yukseklik_kazanim.csv` | conf 0,30'da kutu yüksekliği beştebirliklerine (44/55/65/80 px) göre taban ve model recall'ı ve farkı | `scripts/13_kutu_bazinda_karsilastir.py` | Evet — `az_ornek` sütunu n<50 grupları işaretler; ZRI_HARIC'in beş bandı da az örnek |
| `karolama_karsilastirma.csv` | Karolamalı ve karolamasız taramanın metrik karşılaştırması | `scripts/02_karolama_karsilastir.py --bolum test --limit 100` | Kısmen — `--limit 100` ile üretildi, `taban_cizgisi.csv` ile aynı çarpık alt küme; karolamanın yönü güvenilir, mutlak sayıları değil |
| `ornek_secim.csv` | Görselleştirilen örnek görüntülerin seçim kaydı (etiket/tahmin/eşleşme sayıları) | `scripts/03_gorsellestir.py --bolum test` | Evet — ölçüm değil, seçim kaydı |
| `ornek_secim_BLI.csv` | BLI kaynağı için aynı seçim kaydı | `scripts/03_gorsellestir.py --bolum valid --onek BLI --cikti reports/ornekler_BLI --secim-csv reports/ornek_secim_BLI.csv` | Evet — ölçüm değil, seçim kaydı |
| `ornek_secim_CAB.csv` | CAB kaynağı için aynı seçim kaydı | `scripts/03_gorsellestir.py --bolum valid --onek CAB --cikti reports/ornekler_CAB --secim-csv reports/ornek_secim_CAB.csv` | Evet — ölçüm değil, seçim kaydı |
| `ornek_secim_GRO.csv` | GRO kaynağı için aynı seçim kaydı | `scripts/03_gorsellestir.py --bolum valid --onek GRO --cikti reports/ornekler_GRO --secim-csv reports/ornek_secim_GRO.csv` | Evet — ölçüm değil, seçim kaydı |
| `onek_kutu_boyutu.csv` | Kaynak öneki başına medyan kutu ölçüleri ve üç eşikteki recall | `scripts/04_kutu_boyutu_analiz.py` | Evet |
| `onek_kontrast.csv` | Kaynak öneki başına hedef-arka plan kontrastı ve boyut modelinden artık | `scripts/05_kontrast_analiz.py` | Evet |
| `enboy_orani_recall.csv` | En-boy oranı gruplarına göre recall | `scripts/07_gozlem_analiz.py` | Evet — `ornek_durumu` sütunu az örneklemli grupları işaretler |
| `eslesme_skor_dagilimi.csv` | Eşleşen tahminlerin güven skoru bantlarına dağılımı | `scripts/07_gozlem_analiz.py` | Evet — `ornek_durumu_*` sütunları az örneklemli grupları işaretler |
| `olcu_karsilastirma.csv` | Kutu genişliği ve yüksekliğinin recall ile ilişkisi, gruplu karşılaştırma | `scripts/08_oran_boyut_kontrol.py` | Evet |
| `oran_boyut_tabakali.csv` | Alan tabakası × en-boy oranı grubu kırılımında recall | `scripts/08_oran_boyut_kontrol.py` | Evet — `ornek_durumu` sütunu az örneklemli grupları işaretler |
| `olcu_karsilastirma_genis.csv` | Aynı karşılaştırmanın daha çok grupla genişletilmiş hali | `scripts/09_yukseklik_kontrol.py` | Evet |
| `oran_yukseklik_tabakali.csv` | Yükseklik tabakası × en-boy oranı grubu kırılımında recall | `scripts/09_yukseklik_kontrol.py` | Evet — `ornek_durumu` sütunu az örneklemli grupları işaretler |
