# Gözcü — Hafta 0 Raporu

**Havadan çekilmiş arama-kurtarma görüntülerinde insan tespiti: taban çizgisi ölçümü**

Bu raporda, hazır bir nesne tespit modelinin havadan çekilmiş arama-kurtarma
görüntülerinde ne kadar başarılı olduğunu ölçtüm. Bu aşamada **hiç model
eğitmedim**. Amacım, projeye devam etmeden önce başlangıç noktasının nerede
olduğunu sayılarla görmekti. Buna *taban çizgisi* (baseline) diyorum: sonraki
çalışmaların kendisiyle karşılaştırılacağı, üzerine iyileştirme yapılacak ilk ölçüm.

Kullandığım tüm sayılar `reports/` klasöründeki CSV dosyalarından gelir. Hangi
sayının hangi dosyada olduğu `README_hafta0.md` bölüm 6'daki tabloda listelidir.

---

## 1. Problem

Veri kümesindeki görüntüler **4000×3000 piksel**. Aradığımız insanlar ise medyan
olarak **60×59 piksel** — yani tipik bir insan, görüntünün toplam alanının yalnızca
**%0,031**'ini kaplıyor. Bu, on binde üç demek. Ölçülen en küçük kutu genişliği 19, en küçük kutu yüksekliği 20 piksel.

Buradaki asıl zorluk şu: nesne tespit modelleri girdiyi sabit bir boyuta küçültür.
Kullandığım model varsayılan olarak görüntüyü **640 piksele** indiriyor. 4000 piksel
genişliğindeki bir görüntü 640'a inince ölçek 6,25 kat küçülür. 60 pikselik bir insan
bu işlemden sonra **yaklaşık 9 piksele** düşer.

9 piksellik bir lekede insan biçimini tanımak pratikte mümkün değil. Yani görüntüyü
olduğu gibi modele vermek, aradığımız şeyi model onu görmeden önce yok ediyor.

---

## 2. Yaklaşım: karolama

**Karolama** (tiling), büyük bir görüntüyü küçük parçalara bölüp her parçayı ayrı ayrı
modele vermek demek. Görüntü küçültülmediği için nesneler orijinal boyutlarında kalır.

Ben görüntüyü **512×512 piksellik** karolara böldüm. Bu seçimin nedeni şu: 512
piksellik bir karo modele verildiğinde 640'a *büyütülür*, küçültülmez. Yani 60
pikselik insan yaklaşık 75 piksele çıkar — kaybolmak yerine belirginleşir.

Karoları **%20 örtüşmeyle** kestim. Örtüşme olmasaydı, tam karo sınırına denk gelen
bir insan ikiye bölünür ve iki karonun hiçbirinde bütün olarak görünmezdi. %20
örtüşme, 512 pikselik karoda yaklaşık 102 piksellik bir bindirme demek; veri
kümesindeki en büyük kutunun (162×190 piksel) yarısından fazlası. Bu, sınıra denk
gelen nesnelerin en az bir karoda bütün olarak yakalanmasını sağlıyor.

Karolama işini SAHI kütüphanesiyle yaptım. SAHI, karolara ayırma ve sonuçları tekrar
birleştirme işini üstleniyor.

Bunun bedeli hız. Bir 4000×3000 görüntü %20 örtüşmeyle yaklaşık 90 karoya bölünüyor,
yani model 90 kez çalışıyor. Ölçümlerimde bu, görüntü başına **5,7–6,2 saniye**
sürdü (yalnızca CPU, GPU yok).

---

## 3. Ne ölçtüm ve neden

Bir tahminin doğru sayılması için gerçek etikete yeterince benzemesi gerekir. Bunu
**IoU** (Intersection over Union, kesişim/birleşim oranı) ile ölçtüm: iki kutunun
çakışan alanının, kapladıkları toplam alana bölümü. 1,0 tam üst üste, 0 hiç
çakışmıyor demek. Eşiği **0,3** aldım.

Her gerçek kutu en fazla bir tahminle eşleşir. Birden fazla aday varsa güven skoru
yüksek olan öncelikli işlenir.

Ölçtüğüm metrikler:

| Metrik | Anlamı |
|---|---|
| **Recall (duyarlılık)** | Gerçekte var olan insanların yüzde kaçını buldu. 100 kişiden 38'ini bulduysa recall 0,38. |
| **Yanlış pozitif (FP)** | Modelin "burada insan var" dediği ama aslında insan olmayan tespitler. |
| **FP/görüntü** | Görüntü başına ortalama kaç yanlış alarm. |
| **Precision (kesinlik)** | Modelin yaptığı tespitlerin yüzde kaçı doğruydu. |

**Recall'ı birincil metrik seçtim.** Sebebi arama-kurtarma bağlamının kendisi:
kaçırılan bir kişi geri gelmez, ama yanlış alarm sadece operatörün birkaç saniyesini
alır. Bu iki hatanın maliyeti eşit değil, dolayısıyla onları eşit ağırlıkta ölçen
metrikler (precision, F1) burada yanıltıcı olur.

FP/görüntü'yü ikincil metrik olarak tuttum, çünkü sınırsız değil. Görüntü başına 20
yanlış alarm üreten bir sistem teknik olarak yüksek recall'a ulaşabilir ama pratikte
operatörü boğar. Yani recall'ı FP bütçesiyle birlikte okumak gerekiyor.

---

## 4. Taban çizgisi sonuçları

Modelin bir tespiti bildirmesi için gereken en düşük güven skoruna **güven eşiği**
diyorum. Eşik düştükçe model daha çok şey bildirir: recall artar, yanlış alarm da
artar. Bu yüzden tek bir eşik yerine üçünü birden ölçtüm.

### 4.1 Karolamalı ölçüm — tüm veri kümesi

1.579 görüntü, 3.073 etiketlenmiş insan:

| Güven eşiği | Bulunan | Kaçırılan | Recall | FP/görüntü | Precision |
|---|---|---|---|---|---|
| 0,05 | 1.864 | 1.209 | **0,607** | 13,54 | 0,080 |
| 0,15 | 1.389 | 1.684 | **0,452** | 3,41 | 0,205 |
| 0,30 | 971 | 2.102 | **0,316** | 0,89 | 0,408 |

*Bu tablo ne söylüyor:* Hiç eğitilmemiş, COCO veri kümesiyle gelen hazır bir model,
makul bir yanlış alarm seviyesinde (görüntü başına 0,89) aranan insanların yaklaşık
**üçte birini** buluyor. Eşiği düşürüp recall'ı %61'e çıkarmak mümkün, ama o zaman
görüntü başına 13,5 yanlış alarm oluşuyor — 1.579 görüntüde 21.387 yanlış tespit
demek. Bu, operatörün elemesi gereken hacim olarak gerçekçi değil.

### 4.2 Karolama gerçekten gerekli mi?

Aynı 100 görüntüyü iki şekilde taradım: karolamalı (512 piksellik karolar) ve
karolamasız (tüm görüntü doğrudan modele, model 640'a küçültüyor).

| Yöntem | Güven eşiği | Recall | FP/görüntü | Süre (sn/görüntü) |
|---|---|---|---|---|
| Karolamalı | 0,05 | **0,762** | 16,74 | 5,91 |
| Karolamalı | 0,15 | **0,595** | 4,46 | 5,91 |
| Karolamalı | 0,30 | **0,437** | 1,39 | 5,91 |
| Karolamasız | 0,05 | **0,171** | 0,80 | 0,17 |
| Karolamasız | 0,15 | **0,071** | 0,09 | 0,17 |
| Karolamasız | 0,30 | **0,000** | 0,01 | 0,17 |

*Bu tablo ne söylüyor:* Karolama olmadan sistem çalışmıyor. En düşük eşikte bile
karolamasız yöntem 252 insandan yalnızca 43'ünü buluyor. Güven eşiği 0,30'a
çıkarıldığında **252 kişinin sıfırını** buluyor — tek bir doğru tespit bile yok.

Yanlış alarm bütçesi açısından bakınca: karolamasız yöntemin ulaşabildiği en yüksek
recall 0,171 ve bunu 0,80 FP/görüntü ile yapıyor. Karolamalı yöntem, bütçeyi 1,39
FP/görüntü'ye çıkardığımızda 0,437 recall veriyor — yani yaklaşık 1,7 katı yanlış
alarma karşılık **2,6 katı insan**. İki yöntemi tam olarak aynı FP seviyesinde
karşılaştıramıyorum, çünkü yalnızca üç güven eşiği ölçtüm; aradaki değerler
ölçülmedi.

Bedeli 35 kat işlem süresi (0,17 → 5,91 saniye). Bu ölçüm `--limit 100` ile test
bölümünün ilk 100 görüntüsü üzerinde yapıldı.

**BULGU:** Karolama bu problemde isteğe bağlı bir iyileştirme değil, sistemin
çalışması için ön koşul.

---

## 5. Veri kümesinin yapısı — tek sayı neden yanıltıcı

Dosya adları `train_ZRI_3035_...` biçiminde. İkinci parça, görüntünün hangi çekim
bölgesinden geldiğini gösteriyor. Bunlara **kaynak** diyorum. Veri kümesinde
**17 farklı kaynak** var ve dağılımları çok dengesiz.

En çarpıcı olan **ZRI**: 126 görüntüde 1.297 kutu taşıyor, yani veri kümesindeki tüm
etiketlerin **%42'si**. Görüntülerinin yalnızca %5,6'sı boş. Görsel olarak
bakıldığında ZRI bir şehir parkı — çimende oturan ve yatan insanlar. Geri kalan 16
kaynak dağlık ve ormanlık arazi; çoğunda görüntü başına ortalama bir insandan az
etiket var ve boş görüntü oranı %27–67 arasında.

Daha önemlisi, bölünmeler kaynak bazında ayrışmış. `test` bölümü 17 kaynaktan
yalnızca **2'sini** içeriyor (ZRI ve VRD) ve ZRI'nin 126 görüntüsünün 87'si orada.

Bunun sonucu şu: yalnızca test bölümünde ölçüm yapıp "recall 0,38" demek, aslında
"şehir parkında recall 0,38" demek oluyor. Kalan 15 kaynağın hiçbiri o sayının içinde
değil.

Bu yüzden ölçümü tüm veri kümesi üzerinde tekrarladım ve baskın kaynağı dışarıda
bırakan bir özet satırı da ekledim:

| Kapsam | Görüntü | Kutu | Recall (0,30) | FP/görüntü |
|---|---|---|---|---|
| Tüm veri kümesi | 1.579 | 3.073 | 0,316 | 0,89 |
| ZRI hariç | 1.453 | 1.776 | **0,266** | 0,74 |

*Bu tablo ne söylüyor:* Şehir parkı görüntüleri çıkarıldığında recall 0,316'dan
**0,266**'ya iniyor. Yani gerçek arazi koşullarında hazır model, aranan insanların
yaklaşık **dörtte birini** buluyor.

**Raporlanabilir dürüst taban çizgisi %26,6'dır.** Test bölümünden okunan %38'lik
değer, veri kümesinin yapısı nedeniyle iyimserdir.

Not: Bu ölçüm train, valid ve test bölümlerini birleştiriyor. Normalde bu ciddi bir
hata olurdu. Burada geçerli, çünkü model henüz eğitilmedi ve bu görüntülerin hiçbirini
görmedi. **Hafta 3'te eğitim yapıldıktan sonra bu koşu tekrarlanamaz**; o noktadan
sonra yalnızca test bölümü kullanılmalıdır. Bu koşul CSV dosyasına
`kosu_gecerlilik_notu` sütunu olarak da yazılıdır.

---

## 6. Hedef boyutu bulgusu

Kaynak bazında recall'lara baktığımda çok geniş bir aralık gördüm: aynı model, aynı
ayarlarla, kaynağa göre recall **0,05 ile 0,61 arasında** değişiyordu. Bunun sebebini
aradım.

Her kaynak için etiket kutularının medyan boyutunu hesapladım ve recall ile
karşılaştırdım. Kutu genişliği ile yüksekliğini tek bir sayıda birleştirmek için
**kutu kenarı** ölçüsünü kullandım: kutu alanının karekökü.

Sonuç, kutu boyutu ile recall arasında güçlü bir ilişki:

| Ölçüm | Pearson r | Spearman ρ |
|---|---|---|
| 17 kaynağın tamamı | **+0,820** | +0,667 |
| En büyük değer (CAP) hariç | +0,759 | +0,600 |
| En az 50 kutusu olan 11 kaynak | **+0,911** | +0,664 |
| En az 100 kutusu olan 8 kaynak | +0,902 | +0,595 |

Pearson r, iki değişken arasındaki doğrusal ilişkinin gücünü ölçer; +1 mükemmel
pozitif ilişki, 0 ilişki yok demektir.

*Bu tablo ne söylüyor:* İlişki tek bir uç değere dayanmıyor. En önemlisi, **örneklemi
küçük kaynakları çıkardıkça ilişki zayıflamıyor, güçleniyor** (+0,82'den +0,91'e).
Eğer bu sadece gürültü olsaydı tersinin olmasını beklerdik — az veriye dayanan
kaynaklar çıkarıldığında rastgele örüntüler kaybolur. Burada tam tersi oluyor, yani
ilişki gerçek.

**BULGU:** Kaynaklar arası recall farkının büyük kısmını hedef boyutu açıklıyor.
3.073 kutu üzerinden, ≥50 kutulu kaynaklarda r = +0,911.

Ana görsel: `reports/recall_vs_kutu_boyutu.png` — her nokta bir kaynak, yatay eksen
medyan kutu kenarı, dikey eksen recall, nokta büyüklüğü o kaynaktaki kutu sayısı.

---

## 7. Hata taksonomisi: iki farklı hata türü

Kutu boyutu modelinden sapmaya bakarak hataları iki gruba ayırdım. Burada **artık**
(residual) terimini kullanıyorum: bir kaynağın gerçek recall'ı ile, yalnızca kutu
boyutuna bakarak tahmin edilen recall'ı arasındaki fark. Artık sıfıra yakınsa o
kaynağın performansı tamamen boyutuyla açıklanıyor demektir.

### A türü — çözünürlük kaynaklı

| Kaynak | Medyan kutu kenarı | Recall (0,30) | Artık |
|---|---|---|---|
| BRA | 43,8 px | 0,050 | −0,011 |
| BRS | 44,9 px | 0,069 | −0,008 |
| SB | 46,6 px | 0,094 | −0,008 |
| TRS | 42,5 px | 0,123 | +0,081 |

*Bu tablo ne söylüyor:* Bu dört kaynak veri kümesindeki en küçük kutulara sahip.
Artık değerleri neredeyse sıfır — yani düşük recall'ları tamamen kutu boyutlarıyla
açıklanıyor, başka bir sebep aramaya gerek yok. TRS ise boyutunun öngördüğünden daha
iyi performans veriyor.

Bu hata türü **çözünürlük problemi**. Çözümü de oradan geçiyor: daha küçük karo
boyutu kullanmak, hedefi modele daha büyük göstermek demek.

### B türü — görünüm kaynaklı

| Kaynak | Medyan kutu kenarı | Recall (0,30) | Artık |
|---|---|---|---|
| BLI | 66,9 px | 0,196 | **−0,200** |
| GRO | 55,7 px | 0,095 | **−0,138** |
| CAB | 53,0 px | 0,088 | **−0,106** |

*Bu tablo ne söylüyor:* Bu üç kaynağın kutuları küçük değil. BLI'nin kutuları 66,9
piksel — veri kümesindeki en büyük kutulardan. Karşılaştırma için: ZRI'nin kutuları
64,9 piksel ve recall'ı 0,384, RAK'ınki 65,0 piksel ve recall'ı 0,392. BLI aynı kutu
boyutuyla bunların yarısından az recall veriyor.

Burada sorun çözünürlük değil, hedefin **görünümü**. Bu, daha küçük karoyla
çözülmez; veri kümesine özgü eğitim gerektirir.

Bu iki türün ayrılması pratik bir sonuç doğuruyor: karolama parametrelerini
iyileştirmek A türü hatalara yarar, B türüne yaramaz.

---

## 8. Çürütülen hipotezler

Bu bölümü kısaltmadım, çünkü yanlış çıkan tahminler doğru çıkanlar kadar bilgi verdi.

### 8.1 "VRD zor arazidir" — ÇÜRÜTÜLDÜ

**Ne tahmin ettim:** Test bölümünde iki kaynak vardı: ZRI (şehir parkı) ve VRD
(dağlık orman). VRD'nin gerçek arama-kurtarma senaryosunu temsil ettiğini ve bu
yüzden zor olacağını düşündüm.

**Nasıl ölçtüm:** Kaynak bazında recall ölçümü, tüm veri kümesi.

**Ne çıktı:** VRD, 205 kutuyla en iyi performans gösterenlerden biri — recall 0,410
(güven eşiği 0,30). Ayrıca boyut modelinden **+0,130** artıkla, boyutunun
öngördüğünden *daha iyi* sonuç veriyor. Tahminim yanlıştı. Zorluk, arazinin ormanlık
olmasından gelmiyor.

### 8.2 "BRA'nın düşük recall'ı arazi zorluğundan" — ÇÜRÜTÜLDÜ

**Ne tahmin ettim:** BRA, BRS, SB ve TRS'nin düşük recall'ının arazi karakterinden
kaynaklandığını düşündüm.

**Nasıl ölçtüm:** Kaynak başına medyan kutu boyutunu hesaplayıp recall ile
karşılaştırdım (`04_kutu_boyutu_analiz.py`).

**Ne çıktı:** Sebep arazi değil, hedef boyutu. Bu dört kaynak veri kümesindeki en
küçük dört kutuya sahip ve artık değerleri sıfıra çok yakın (bölüm 7, A türü).
Tahminimin yönü yanlıştı ama ölçüm daha basit ve daha güçlü bir açıklama verdi.

### 8.3 "BLI/GRO/CAB'in sapması düşük kontrasttan" — ÇÜRÜTÜLDÜ

**Ne tahmin ettim:** B türü kaynaklara gözle baktığımda insanların arka plandan zor
ayırt edildiğini gördüm ve bunu düşük kontrasta bağladım.

**Nasıl ölçtüm:** Her kutunun içindeki piksellerin ortalama parlaklığı ile kutuyu
çevreleyen halkanın (kutunun 3 katına genişletilmiş alanından kutunun kendisi
çıkarılmış bölge) ortalama parlaklığı arasındaki farkı hesapladım. 3.073 kutunun
tamamı ölçüldü (`05_kontrast_analiz.py`).

**Ne çıktı:** İlişki yok. Kontrast ile boyut modelinden artık arasında Pearson
r = **−0,068**, Spearman ρ = −0,037 — sıfıra yakın.

Dahası, tahminimin tam tersi bir örnek var: **CAB'in medyan kontrastı 20,5 ile
listedeki en yüksek ikinci değer**, ama artığı −0,106 ile en kötülerden. Buna karşılık
BRA'nın kontrastı listedeki en düşük değer (5,5) ama artığı sıfıra yakın, yani
recall'ı zaten boyutuyla açıklanıyor.

Gözlemim yanlış değildi ama sebebini yanlış adlandırmışım. Görselde gördüğüm şey
ortalama parlaklık farkı değildi.

### 8.4 "Kaçırılanlar yerde yatan insanlar" — HİPOTEZ, ZRI ile çelişiyor

**Ne tahmin ettim:** BLI görsellerinde bulunan kişilerin ayakta, kaçırılanların
çimende yatıyor olduğunu fark ettim. COCO veri kümesinin ağırlıklı olarak ayakta ve
oturan insanlarla eğitildiğini düşünürsek, havadan bakışta yatay uzanmış bir gövdenin
modele tanıdık gelmemesi mantıklı görünüyordu.

**Nasıl ölçtüm:** Ölçmedim. Yalnızca birkaç görsele baktım.

**Ne çıktı:** Hipotez, elimizdeki en büyük kaynakla çelişiyor. ZRI de çimende yatan
ve oturan insanlardan oluşuyor, ancak recall'ı 0,384 ile ortalamanın üstünde. Eğer
yatay duruş tek başına belirleyici olsaydı ZRI'nin de düşük performans göstermesi
gerekirdi.

Bu yüzden duruş hipotezini **doğrulanmamış** sayıyorum. Veri kümesinde duruş etiketi
olmadığı için ölçmek de kolay değil; her kutunun en-boy oranından dolaylı bir gösterge
türetilebilir ama bunu yapmadım.

### 8.5 İşaretli kontrast — İLGİNÇ AMA KANITLANMAMIŞ

Kontrast farkının işaretine (insanın arka plandan koyu mu açık mı olduğuna) baktığımda
recall ile bir ilişki gördüm: Pearson r = −0,581. İnsanların arka plandan koyu olduğu
12 kaynağın ortalama recall'ı 0,311, açık olduğu 5 kaynağınki 0,152.

Ancak bu ilişki, kutu boyutunun açıklamadığı kısmı açıklamıyor: artıkla korelasyon
r = +0,012 (en az 50 kutulu kaynaklarda). Yani insanların arka plandan açık olduğu
kaynaklar aynı zamanda küçük kutulu kaynaklar; iki değişken birbirine karışmış
durumda. Bağımsız bir açıklama olarak kullanılamaz.

---

## 9. Açık kalan soru

B türü kaynakların (BLI, GRO, CAB) sapması **açıklanamadı**. Kutu boyutu bu üç
kaynağı açıklamıyor, kontrast da elendi.

En güçlü adayım **arka planın doku karmaşıklığı**. CAB görsellerinde arazi, insan
boyutunda ve insan şeklinde açık renkli kaya parçalarıyla dolu. Ortalama parlaklık
farkı bu durumu ölçmüyor: kaya ile insan arasında belirgin parlaklık farkı olabilir,
ama arka plan aynı ölçekte bol miktarda benzer leke içerdiği için hedef yine de
ayırt edilemez hale geliyor.

Bunu ölçmek için uygun görünen iki gösterge var: kutu çevresindeki bölgenin **yerel
piksel varyansı** ve **kenar yoğunluğu**. İkisi de hesaplanabilir ve mevcut altyapıya
eklenmesi zor değil.

**Bu ölçüm yapılmadı.** Doku karmaşıklığı şu an bir hipotez; raporda bulgu olarak
sunulmamalıdır.

---

## 10. Ölçüm metodolojisi dersleri

### 10.1 Alt küme yanlılığı

İlk taban çizgisini test bölümünün ilk 100 görüntüsüyle ölçtüm. Sonra tüm bölümle
(157 görüntü) tekrarladım:

| Kapsam | Kutu | Recall (0,30) | Precision (0,30) |
|---|---|---|---|
| İlk 100 görüntü | 252 | 0,437 | 0,442 |
| Tam bölüm (157) | 970 | 0,380 | 0,565 |

İlk 100 görüntüde görüntü başına 2,52 kutu düşüyordu; kalan 57 görüntüde ise 12,60.
Sebep şu: görüntüleri tekrar üretilebilirlik için dosya adına göre sıralıyorum ve
listenin başındaki grup tek bir kaynaktan geliyordu.

Sonuç: alt küme **recall'ı yaklaşık 5,6 puan iyimser**, **precision'ı yaklaşık 12,3
puan kötümser** gösterdi. Yani yanlılık tek yönlü değil; iki metriği zıt yönlerde
bozdu.

**Ders:** Bir ölçümü hızlandırmak için ilk N örneği almak, dosya adları rastgele
dağılmıyorsa yanlı bir örneklem yaratır. Alt küme sonucunu kullanmadan önce, alt
kümenin temel özelliklerini (burada görüntü başına nesne sayısı) bölümün tamamıyla
karşılaştırmak gerekiyor.

### 10.2 SAHI'nin iki varsayılanı

**Birincisi:** `get_sliced_prediction` fonksiyonunda `perform_standard_pred`
parametresi varsayılan olarak açık. Bu, karolara **ek olarak** tüm görüntüyü de
küçültüp bir kez daha tarıyor. Açık bıraksaydım "karolamalı" ölçümüm karolamasız
ölçümü zaten içinde barındıracaktı ve bölüm 4.2'deki karşılaştırma anlamsız olacaktı.
Kapattım.

**İkincisi:** SAHI, güven eşiği düşük olduğunda kutu birleştirme yöntemini
kendiliğinden değiştiriyor. Birden fazla eşik ölçerken süreyi üçe katlamamak için
taramayı bir kez en düşük eşikle yapıp yüksek eşikleri sonradan filtreliyorum. Bu
optimizasyonun doğruluğunu tek bir görüntüde kontrol ettiğimde sonuçlar **farklı**
çıktı — çünkü iki tarama farklı birleştirme rejiminde çalışıyordu. Birleştirme tipini
açıkça sabitledikten sonra doğrulama aynı sonucu verdi.

**Ders:** Kütüphane varsayılanları ölçümün ne anlama geldiğini sessizce değiştirebilir.
Ölçüme giren her parametreyi açıkça yazmak ve CSV'ye kaydetmek gerekiyor. Her çıktı
dosyam `kosu_` önekli sütunlarda bu ayarları taşıyor.

### 10.3 Ara sonuçları saklamamanın maliyeti

Kaynak bazında tam ölçüm **2 saat 42 dakika** sürdü. Koşu bittikten sonra kaçırılan
kutuların boyut dağılımına bakmak istedim ve veriyi bulamadım: toplu metrikler *kaç*
kutunun kaçırıldığını söylüyordu ama *hangi* kutunun kaçırıldığını söylemiyordu.
Tahminler bellekteydi ve koşuyla birlikte silinmişti. Aynı soruyu yanıtlamak,
taramayı baştan yapmak anlamına geliyordu.

Kalıcı çözüm olarak `01_taban_cizgisi.py` artık her koşuda `kutu_bazinda_sonuc.csv`
üretiyor: her gerçek kutu için görüntü, kaynak, kutu boyutu, güven eşiği, eşleşip
eşleşmediği, eşleştiyse eşleşen tahminin skoru ve IoU'su. Bu dosya bir seçenek değil,
varsayılan davranış — çünkü veriyi atmanın maliyeti saatlerle ölçülüyor.

**Ders:** Pahalı bir hesabın ara sonuçlarını saklamak neredeyse bedava; saklamamak
ise sonradan akla gelen her soruyu hesabın kendisi kadar pahalı hale getiriyor.

### 10.4 Tekrar üretilemeyen çıktı

Kaynak dağılımı tablosunu ilk kez tek seferlik geçici bir betikle üretmiştim. Çıktı
dosyası duruyordu ama onu üreten kod hiçbir yerde kayıtlı değildi — yani tablo tekrar
üretilemiyordu. Hesabı `00_veri_incele.py` içine taşıdım.

**Ders:** Rapora girecek her sayının, sürüm kontrolündeki bir betikten yeniden
üretilebilmesi gerekiyor.

---

## 11. Kararlar ve gerekçeleri

| Karar | Alternatif | Neden bu |
|---|---|---|
| Karolama için SAHI | Kendi karolama kodumu yazmak | Karolara bölme, koordinat dönüşümü ve sonuçları birleştirme işini hazır ve test edilmiş halde veriyor. Kendi kodum aynı işi yapana kadar geçecek süre ölçüme harcanabilirdi. |
| 512 piksel karo | 640 (küçültme yok) veya 1024 | 512'lik karo modelin 640'lık girdisine *büyütülerek* verilir, yani hedef büyür. 1024 kullansaydım küçültme başlayacaktı. |
| %20 örtüşme | %0 veya %50 | %0'da karo sınırına denk gelen kişi ikiye bölünür. %50 karo sayısını yaklaşık iki katına çıkarıp süreyi de iki katına çıkarırdı. |
| IoU eşiği 0,3 | 0,5 (yaygın standart) | Hedefler 60 piksel civarında; bu boyutta birkaç piksellik kayma IoU'yu hızla düşürür. 0,5 eşiği, insanı doğru bulmuş ama kutusu biraz kaymış tespitleri hata sayardı. |
| Greedy (açgözlü) eşleştirme | Macar algoritması ile en iyi eşleştirme | Yüksek güven skorlu tahmini önceliklendirmek, tespit değerlendirmesinde yaygın davranış. Optimal eşleştirme daha karmaşık ve bu ölçekte sonucu anlamlı ölçüde değiştirmesi beklenmiyor. |
| yolo11n (en küçük model) | Daha büyük YOLO varyantları | Taban çizgisinin amacı en iyi sonucu almak değil, başlangıç noktasını ölçmek. CPU'da tam koşu zaten 2 saat 42 dakika sürdü; daha büyük model bunu katlardı. |
| Yalnızca CPU | GPU kiralamak | Elimdeki donanım. Süre kısıtı ölçüm tasarımını etkiledi (tek tarama + sonradan filtreleme) ama sonuçları etkilemedi. |
| Güven eşiği 0,05 / 0,15 / 0,30 | Tek eşik | Recall ile yanlış alarm arasındaki değiş tokuşu tek sayı göstermiyor. Üç nokta, eğrinin şeklini görmeye yetiyor. |

---

## 12. Sonraki adım

Bu ölçümler Hafta 1'in içeriğini doğrudan belirledi.

**1. Karo boyutunu optimize etmek (A türü hatalara yönelik).** Hedef boyutu ile recall
arasındaki ilişki (r = +0,911) net olduğuna göre, karoyu küçültmek hedefi modele daha
büyük gösterir. 512'nin yanı sıra 320 ve 256 piksellik karolar denenmeli. Beklenen
sonuç: BRA, BRS, SB, TRS gibi küçük hedefli kaynaklarda recall artışı. Bedeli karo
sayısının ve dolayısıyla sürenin artması; bu değiş tokuş ölçülmeli.

**2. Doku karmaşıklığını ölçmek (bölüm 9'daki açık soru).** Kutu çevresindeki yerel
varyans ve kenar yoğunluğu hesaplanıp B türü kaynakların artığıyla karşılaştırılmalı.
İlişki çıkarsa hata taksonomisi tamamlanmış olur; çıkmazsa başka aday aranmalı.

**3. Güven eşiği eğrisini sıklaştırmak.** Şu an elimde üç nokta var. Karolamalı ve
karolamasız yöntemleri eşit yanlış alarm bütçesinde karşılaştıramamamın sebebi bu.
Daha sık eşik örneklemesi bu karşılaştırmayı mümkün kılar.

**4. Eğitim öncesi son ölçüm.** Hafta 3'te eğitime geçilecekse, bölüm 5'teki birleşik
ölçüm o noktadan sonra geçersiz hale gelir. Eğitim başlamadan önce yapılacak tüm
eğitimsiz ölçümlerin tamamlanmış olması gerekiyor.

B türü hatalar (BLI, GRO, CAB) karolama parametreleriyle çözülmeyecek. Onlar için
veri kümesine özgü eğitim gerekiyor — yani Hafta 3'ün asıl gerekçesi bu bulgu.

---

## 13. Veri ve lisanslar

**Veri kümesi:** HERIDAL insan tespit veri kümesi, Roboflow Universe üzerinden
YOLOv8 formatında dışa aktarılmış sürüm.

- Kaynak: `https://universe.roboflow.com/onur-kaya/heridal-human-detection-jvf9b/dataset/1`
- Lisans: **CC BY 4.0** (Creative Commons Atıf 4.0). Bu lisans kullanım ve
  değiştirmeye izin verir, atıf zorunludur.
- İçerik: 1.579 görüntü, tek sınıf, 3.073 etiketli kutu. Roboflow dışa aktarımında
  görüntülere ön işleme veya veri artırma uygulanmamış; görüntüler 4000×3000
  orijinal çözünürlüğünde.
- Veri kümesindeki sınıf adı `human`, kullandığım COCO modelindeki karşılığı `person`.

> **Kontrol edilmesi gereken:** HERIDAL veri kümesinin orijinal akademik yayını
> vardır ve tez metninde ona atıf verilmesi uygun olur. Roboflow dışa aktarımı bu
> künyeyi içermediği için buraya yazmadım — uydurmamak adına boş bıraktım. Orijinal
> yayın künyesini teyit edip bu bölüme eklemek gerekiyor.

**Model:** `yolo11n.pt`, Ultralytics tarafından COCO veri kümesiyle önceden
eğitilmiş ağırlıklar. Ultralytics **AGPL-3.0** lisanslıdır. Bu lisans, yazılımın ağ
üzerinden hizmet olarak sunulması durumunda kaynak kodun paylaşılmasını zorunlu kılar.
Akademik ve kişisel kullanım için sorun yok; ileride bu çalışma bir servise
dönüştürülecekse lisans koşulları yeniden değerlendirilmelidir.

**Ortam:** Python 3.13.1, PyTorch 2.14.0, Ultralytics 8.4.144, SAHI 0.12.6, macOS
(arm64), yalnızca CPU. Sürümler `requirements.txt` içinde sabitlenmiştir ve her
çıktı CSV'sinin `kosu_surum_*` sütunlarında da kayıtlıdır.

---

## 14. Araçlar ve yöntem

Bu çalışmanın kodunu yazarken yapay zeka destekli bir geliştirme asistanı kullandım.

Şeffaflık adına neyin bana ait olduğunu netleştirmek isterim: problemin tanımı, ölçüm
tasarımı, hangi metriğin birincil olacağı, kabul kriterleri, hipotezlerin
formülasyonu ve sonuçların yorumu bana aittir. Asistanı kod yazımı, tekrarlayan
analizlerin uygulanması ve dokümantasyon işlerinde kullandım.

Üretilen her çıktıyı doğruladım:

- IoU hesabı ve eşleştirme mantığı için **14 birim testi** yazıldı (tam örtüşme, hiç
  örtüşmeme, kısmi örtüşme, eşik sınırı, bir gerçek kutunun en fazla bir tahminle
  eşleşmesi, tekrarlanabilirlik).
- Kutu bazındaki kayıt ile toplu metriklerin tutarlılığı üç güven eşiğinde ayrı ayrı
  karşılaştırıldı ve birebir aynı çıktı.
- Kaynak bazlı özet satırlarının doğruluğu, sonucu elle hesaplanabilen yapay veriyle
  test edildi.
- Tek tarama + sonradan filtreleme optimizasyonu, doğrudan tarama ile karşılaştırılarak
  doğrulandı (bölüm 10.2).
- Bütün ölçümler tekrar üretilebilir: görüntü listesi sıralı, çıkarım deterministik,
  parametreler CSV'ye kayıtlı. Tek istisna işlem süresi sütunudur; o makinenin anlık
  yüküne göre değişir.

Kodun tamamı ve çıktıların nasıl üretileceği `README_hafta0.md` içinde adım adım
yazılıdır.
