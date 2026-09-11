# egitim/ — Kaggle üzerinde Model-512 eğitimi

Bu klasör, karolanmış eğitim kümesi üzerinde yolo11n'i eğiten Kaggle
notebook'unu içerir. Eğitim yerelde değil Kaggle'da koşar; sebebi GPU.

| | |
|---|---|
| Notebook | `kaggle_egitim.ipynb` |
| Veri kümesi | `onurrkayaa/gozcu-karo-512` (Kaggle, **özel**) |
| Kaynak | `data/karo_512/` — `python scripts/11_karo_veri_hazirla.py --karo 512 --ortusme 0.20` |
| Çıktı | `best.pt` (~5 MB) |

## Notebook nasıl koşulur

1. Kaggle'da **Code → New Notebook**, sonra `kaggle_egitim.ipynb` dosyasını
   **File → Import Notebook** ile yükle.
2. Sağ paneldeki **Input** bölümünden **Add Input → Datasets** ile
   `gozcu-karo-512` kümesini ekle. Notebook `/kaggle/input/gozcu-karo-512`
   yolunu bekler; küme başka bir adla bağlanırsa 5. hücre hata verir.
3. Sağ panelde **Accelerator = GPU T4 x2** seç.
   Notebook `device=0` kullanır, yani iki GPU'dan yalnızca birini kullanır —
   notebook içinde çok GPU'lu DDP kırılgan olduğu için bu bilinçli bir karardır.
4. Sağ panelde **Internet = On** yap. Kapalıysa `pip install ultralytics`
   hücresi paketi indiremez ve `yolo11n.pt` ağırlıkları çekilemez.
5. **Save & Run All (Commit)** ile başlat. Bu yol tarayıcı kapansa bile koşuyu
   sürdürür; interaktif oturum ise sekme kapanınca düşer.

Koşu bitince notebook'un **Output** sekmesinde
`egitim/model512/weights/best.pt` dosyası bulunur.

## best.pt nasıl indirilir ve nereye konur

Notebook çıktısından `best.pt` dosyasını indir ve proje kökünde şu yola koy:

```
agirliklar/model512_best.pt
```

Klasör yoksa oluştur (`mkdir -p agirliklar`). Ölçüm script'leri modeli bu
yoldan `--model` argümanıyla alır.

**Ağırlıklar depoya girmez.** `.gitignore` içinde `*.pt` kuralı vardır; bu
hem indirilen `best.pt` hem de kökteki `yolo11n.pt` için geçerlidir. Ağırlığın
tek kalıcı kopyası Kaggle'daki koşu çıktısı ve senin yerel diskindir, o yüzden
indirdikten sonra yedeğini almayı unutma.

## Kaggle GPU kotası

Haftada **30 saat** GPU. Kota Cumartesi 00:00 UTC'de sıfırlanır.
`patience=20` sayesinde koşu 100 epoch'u doldurmadan erken durabilir, ama üst
sınır olarak birkaç saat hesaba katılmalı. Kotayı boşa harcamamak için
notebook'taki doğrulama hücresi (6. hücre) eğitimden önce koşar: veri yapısı
yanlışsa koşu ilk saniyede durur, saatler sonra değil.

## Bu notebook'un sayıları taban çizgisiyle karşılaştırılamaz

Notebook'un ürettiği mAP ve recall, 512×512 karolar üzerinde hesaplanır.
Bizim taban çizgimiz ise 4000×3000 tam görüntüler üzerinde SAHI ile ölçüldü
(`reports/test_taban_cizgisi.csv`, conf 0,30: recall 0,3804 / FP-görüntü 1,81).
İkisi farklı ölçüm birimidir ve doğrudan karşılaştırılamaz.

Kazanım kararını veren tek ölçüm, eğitilmiş ağırlıkla yerelde koşulan
`scripts/10_test_taban_cizgisi.py` ölçümüdür. Kapı iki eksenlidir: recall
0,3804'ün üstüne çıkmalı **ve** FP/görüntü 1,81'in üstüne çıkmamalı.
