## 4. Kendi Verimizle Model Eğitimi

*(Karolanmış eğitim kümesinin hazırlanması, 512 pikselik karolar üzerinde eğitilen modelin taban çizgisiyle aynı protokolde ölçülmesi, karşılaştırma kuralının eşikten yanlış pozitif bütçesine taşınması ve bu ölçümün sınırları.)*

### 4.1. Bu bölümün sorusu

Bu bölümün sorusu tek cümlelik: **kendi verimizle eğitmek ne kazandırıyor?**

Soruyu bu kadar dar tutmamın sebebi var. Hafta 0'da eğitimsiz bir modelle ölçüm yapmış
ve kaçırılan hedeflerin nereden geldiğini aramıştım. Kaynak bazındaki recall farkının
büyük kısmını hedefin piksel cinsinden boyutu açıklıyordu (bölüm 1, "Hedef boyutu
bulgusu"). Bölüm 2'de bu bulguyu daraltıp karıştırıcı değişkeni ayıkladım: recall'ı
yöneten şey en-boy oranı değil, kutunun **yüksekliğiydi** (bölüm 2, "Karıştırıcı
değişken: yükseklik").

Kendi verimizle eğitim, bu iki ölçümün sonucudur. Rastgele bir hiperparametre denemesi
değil. Eğitimsiz modelin zorlandığı yer küçük hedeflerse, elimizdeki en doğrudan
müdahale modele tam olarak o hedefleri göstermek. Bu bölümde yaptığım şey budur:
ölçtüm, ölçüme dayanan bir müdahale seçtim, sonra aynı protokolle tekrar ölçtüm.

İki şeyi baştan sınırlamak istiyorum. Birincisi, bu bölümde eğitilen model bir
**eğitim ve araştırma prototipidir**; operatörün kararının yerine geçmez, operatöre
bakılacak yer önerir. İkincisi, bölümün sonunda çıkacak kazanım sayısı tek bir test
bölümünde, tek bir kaynak dağılımında ölçülmüştür; genellenebilir bir ortalama değil,
bir üst sınırdır. Bunun neden böyle olduğunu 4.8'de tek tek açıyorum.

### 4.2. Ölçüm hatası tuzağı ve karşılaştırılabilir taban

Eğitim sonrası kazanımı ilan etmenin en kolay yolu, elimdeki en eski sayıyı alıp yeni
sayının yanına koymaktı. Hafta 0'ın recall'ı 0,2663 idi. Eğitim sonrası ölçüm 0,8124
verdi. İki sayıyı yan yana koymak üç kat kazanım gibi görünür ve **yanlıştır**.

Yanlış olmasının sebebi, iki sayının aynı şeyi ölçmemesi. 0,2663, güven eşiği 0,30'da,
ZRI kaynağı hariç tutularak, train + valid + test bölümlerinin **birleştirilmiş**
kümesinde ölçülmüştü. Eğitimden sonra train ve valid bölümleri modelin gördüğü veridir;
o bölümlerde ölçüm yapmak kazanım değil ezber ölçer. Geriye yalnızca test bölümü kalır.
Test bölümü ise ne aynı küme ne de aynı kaynak dağılımıdır: veri kümesinin tamamında
kutular 17 kaynağa yayılırken, test bölümünün 970 hedefinin 939'u tek bir kaynaktan
(ZRI) gelir.

Aynı eksene getirdiğimde, yani ZRI hariç bırakma kuralını iki kümede de uyguladığımda,
eğitimsiz modelin recall'ı tüm veride 0,2663, yalnızca test bölümünde ise **0,3548**
çıkıyor. Aradaki fark modelin değişmesinden değil, ölçülen kümenin değişmesinden
kaynaklanıyor. Bu tek gözlem, 0,2663'ü karşılaştırma tabanı olmaktan çıkarmaya yetti.

Bu yüzden eğitimden önce ayrı bir koşu yaptım ve **yalnızca test bölümü** üzerinde yeni
bir taban çizgisi ürettim. Ölçüm mantığını yeniden yazmadım: `10_test_taban_cizgisi.py`
yalnızca protokol parametrelerini (bölüm, IoU eşiği, karo boyutu, örtüşme, güven
eşikleri) sabitleyen ince bir sarmalayıcıdır ve asıl ölçümü Hafta 0'ın script'ine
yaptırır. Aynı protokolün iki kopyası zamanla birbirinden kayar; tek kopya kalsın diye
böyle yaptım.

Protokolün hangi parçalarının sabit tutulduğu da bu yüzden önemli. Bölüm ve eşleşme
IoU'su script'in içinde sabitlenmiş, komut satırından değiştirilemez yapılmıştır;
karo boyutu ve örtüşme ise ayrı tutulmuştur, çünkü "karo küçültmek tek başına ne
kazandırıyor" sorusu ancak ölçeği değiştirip geri kalan her şeyi sabit tutarak
yanıtlanabilir. Eşleşme eşiğini 0,30'da tuttum: 60 piksel civarındaki bir hedefte
birkaç piksellik kayma IoU'yu hızla düşürdüğü için daha yüksek bir eşik, bulunmuş
hedefleri kaçırılmış saymaya başlar.

Ana taban çizgisi bu koşudur: eğitimsiz yolo11n, test bölümü, 157 görüntü, 970 hedef,
karo 512, örtüşme 0,20, eşleşme için IoU 0,30.

| Güven eşiği | TP | FN | Recall | Yanlış pozitif | FP/görüntü | Precision |
|---|---|---|---|---|---|---|
| 0,05 | 690 | 280 | 0,7113 | 2.863 | 18,24 | 0,1942 |
| 0,15 | 532 | 438 | 0,5485 | 856 | 5,45 | 0,3833 |
| 0,30 | 369 | 601 | **0,3804** | 284 | **1,81** | 0,5651 |

*Bu tablo ne söylüyor:* Eğitimsiz model, eşik düşürüldüğünde daha çok hedef buluyor ama
bunun bedeli hızla büyüyor. 0,05'te recall 0,7113'e çıkıyor; aynı noktada görüntü başına
18,24 yanlış pozitif üretiyor ve doğru bulunan her tahmine karşılık dört katından fazla
yanlış tahmin düşüyor (precision 0,1942). 0,7113 ölçülmüş ve gerçek bir değerdir, ama
operatöre 157 görüntüde 2.863 yanlış kutu göstermek anlamına geldiği için çalışma noktası
değildir. Ana çalışma noktası olarak **conf 0,30**'u seçtim: recall 0,3804, FP/görüntü
1,81.

Bu tablodaki her satır, kendi koşu bilgisini de taşıyor. Ölçüm CSV'lerinde metrik
sütunlarının yanında `kosu_` önekli alanlar var: `kosu_model`, `kosu_bolum`,
`kosu_karo_boyutu`, `kosu_ortusme_orani`, `kosu_iou_esigi`, `kosu_cihaz`, paket sürümleri
(`kosu_surum_python`, `kosu_surum_ultralytics`, `kosu_surum_sahi`, `kosu_surum_torch`),
`kosu_tarih` ve çalıştırılan komutun tam metni (`kosu_komut`). Bunu eklememin sebebi
pratik: bir sayının hangi koşudan geldiğini aylar sonra hatırlamak mümkün değil, ama
satırın kendisi söylüyorsa hatırlamak gerekmiyor. Ayrıca `kosu_tarama_notu` ve
`kosu_gecerlilik_notu` alanları, o koşunun bilinen sınırını satırın yanında taşıyor —
örneğin taban çizgisi koşusunda "tek tarama conf=0.05, yüksek eşikler filtrelendi"
yazıyor, yani üç eşik ayrı taramalarla değil tek taramanın süzülmesiyle üretilmiştir.

Bu alanlar ölçümün hangi komutla üretildiğini kayıt altına alır. Aynı ölçümün iki kez
koşulduğunu ve iki koşunun birbirini doğruladığını göstermezler; CSV'lerde her ölçümün
tek koşu kaydı vardır.

### 4.3. Eğitim verisinin hazırlanması

Karolama mekaniğinin kendisini bölüm 3'te kurmuştum; burada tekrar anlatmıyorum. Bu alt
bölüm yalnızca **eğitim verisine özgü** kararları içeriyor.

**Tam görüntü yerine karolanmış eğitim.** Kaynak görüntüler 4000×3000 piksel, hedeflerin
medyan kutu kenarı ise 60 piksel. Tam görüntüyü 512 pikselik girdiye küçültmek hedefi
yaklaşık 8 piksele indirir; o boyutta öğrenilecek bir şey kalmaz. Bu yüzden eğitim
kümesini de karolara kestim.

**Eğitim karosu = çıkarım karosu.** Model 512 pikselik karolarda eğitildi ve ölçümde de
512 pikselik karolarla tarandı. Bu bilinçli bir kısıt: eğitim ile çıkarım arasında ölçek
farkı bırakmak, kazanımın ne kadarının eğitimden ne kadarının ölçek uyumundan geldiğini
ayırt edilemez hale getirirdi.

**%60 min-görünür kenar kuralı.** Karo sınırına denk gelen bir hedefin yalnızca bir
parçası karoya düşer. Kutunun karo içinde kalan alanı orijinalinin %60'ından azsa o
etiketi karoya yazmıyorum. Bu bir ölçüm değil, bir **karardır**: kesilmiş kutuyu tam
kutu gibi etiketlemek modele yanlış geometri öğretir, ama eşiği çok yükseltmek de kenara
düşen hedefleri tamamen kaybettirir. %60'ı bu iki riskin arasında seçtim; en iyi değer
olduğunu ölçmedim.

**Üç kategori: pozitif, belirsiz, negatif.** Kural şu: içinde en az bir hedef %60 eşiğini
geçen karo **pozitif**; içinde hedef var ama hiçbiri eşiği geçemeyen karo **belirsiz**;
içinde hiç hedef olmayan karo **negatif** adayı.

**Belirsiz karolar neden negatif havuzuna alınmadı.** Bu ayrımın tek sebebi bu. Belirsiz
bir karoda gerçekten insan var; sadece kutusu kırpılmış durumda. O karoyu negatif diye
eğitime koymak, modele "bu görüntüde insan yok" demek olurdu — yani doğrudan yanlış
etiket. Belirsiz karoları hiçbir yere koymadım: ne pozitif, ne negatif. Toplamdan
düşürülürler.

**Negatif oranı 3,00.** Negatif adayların hepsini kullanmak mümkün değil; 512 pikselik
karolamada 110.164 negatif aday çıkıyor, yani pozitiflerin kırk katı. Bu oranda bir küme
modele "hiçbir şey bulma" davranışını öğretir. Pozitif karo başına üç negatif karo
seçtim. Oranın kendisi de bir karardır, taranmış bir değer değil.

Negatif karoların neden hiç gerekli olduğu da buraya ait. Çıkarımda 4000×3000 pikselik
bir görüntü 512'lik karolara bölündüğünde seksen karo çıkıyor ve bunların büyük çoğunluğu
boş arazi. Model yalnızca içinde insan olan karolarla eğitilseydi, boş araziyi hiç
görmemiş olurdu; sahada karşılaşacağı karoların ezici çoğunluğu tam olarak o boş
arazidir. Negatif karolar bu yüzden kümenin içinde.

**Sabit tohum.** Negatif seçimi rastgeledir; tohumu 0'a sabitledim ki aynı komut aynı
kümeyi üretsin.

**train ve valid ayrı karolandı.** İki bölümün karoları hiçbir aşamada karışmaz; bir
kaynak görüntünün karoları tek bir bölümde kalır. Test bölümü ise eğitim için hiç
karolanmadı — o bölüm yalnızca ölçümde, tam görüntü + karolamalı tarama protokolüyle
kullanılır.

| Ölçüt | Karo 512 | Karo 320 |
|---|---|---|
| Kaynak görüntü (train + valid) | 1.422 | 1.422 |
| Pozitif karo | 2.771 | 3.128 |
| Negatif aday | 110.164 | 309.352 |
| Seçilen negatif karo | 8.313 | 9.384 |
| Belirsiz karo | 745 | 1.578 |
| Yazılan karo-etiket | 3.327 | 3.560 |
| Atlanan hedef örneği | 964 | 1.871 |
| Hiçbir karoda bütün kalmayan hedef | 0 | 0 |
| train / val karo | 7.924 / 3.160 | 8.872 / 3.640 |
| Toplam karo | 11.084 | 12.512 |
| Negatif oranı | 3,00 | 3,00 |
| Karo-etiket / benzersiz hedef | 1,58 | 1,69 |

*Bu tablo ne söylüyor:* İki küme aynı 1.422 kaynak görüntüden üretildi ve ikisinde de
negatif oranı tam 3,00. En önemli satır en alttaki iki satır değil, sondan üçüncüsü:
**hiçbir karoda bütün kalmayan hedef sayısı iki kümede de sıfır.** Yani %60 kuralı
hiçbir hedefi tamamen kaybetmedi; her hedef en az bir karoda tam olarak kaldı. Karo-etiket
sayısının benzersiz hedef sayısına oranı (1,58 ve 1,69) örtüşmenin doğal sonucudur: aynı
hedef birden fazla karoda tam kaldığında birden fazla kez etiketlenir. Bu oran train ve
valid bölümlerindeki 2.103 benzersiz hedefe göre hesaplandı.

"Atlanan hedef örneği" satırı sık yanlış okunan bir sayı. 964, kaybolan hedef değil;
%60 eşiğini geçemediği için **o karoya yazılmayan hedef örneği** sayısıdır. Aynı hedef
komşu karoda tam kalıp yazılmış olabilir, nitekim kaybolan benzersiz hedef sıfır.

Aynı dikkat "belirsiz karo" sayısı için de gerekli. 512'de 745, 320'de 1.578 belirsiz
karo var ve bu ikiye katlanma %60 kuralının bedelini gösteriyormuş gibi görünüyor. Ama
karonun birimi karodur: karoyu küçülttükçe aynı görüntüden daha çok karo çıkar ve kenara
denk gelen karo sayısı mekanik olarak artar. 745 ile 1.578'i doğrudan mekanizma kanıtı
olarak kullanmadım. Doğru birim, "kaç **benzersiz hedef** yalnızca belirsiz karolarda
göründü" sorusudur ve bu ölçülmedi.

Son olarak karolanmış kümeyi gözle kontrol ettim: seçilmiş karolar, diskteki YOLO etiket
dosyalarından okunan kutularla çizildi. Bunu otomatik bir test yerine yapmadım, otomatik
testin yanına yaptım. Otomatik test geometrinin kendi kendisiyle tutarlı olduğunu
gösterir; kutuları yeniden hesaplayıp çizmek aynı hatayı iki kez yapıp tutarlı görünmekten
ibaret olurdu. Gözle kontrol, üretilen **dosyaların** doğru olduğunu gösterir.

### 4.4. 2x2 deney tasarımı

İki değişken vardı: model (eğitimsiz / kendi verimizle eğitilmiş) ve karo boyutu
(512 / 320). Dört hücrelik bir matris çıkıyor. Bu bölümde dördünü de doldurmadım.

| Hücre | Model | Karo | Durum | conf 0,30'da sonuç |
|---|---|---|---|---|
| 1 | Eğitimsiz | 512 | **ÖLÇÜLDÜ** | recall 0,3804 · FP/görüntü 1,81 |
| 2 | Eğitimsiz | 320 | **ÖLÇÜLDÜ** | recall 0,4402 · FP/görüntü 3,36 · precision 0,4471 |
| 3 | Eğitilmiş | 512 | **EĞİTİLDİ VE ÖLÇÜLDÜ** | ana karşılaştırma, 4.6'da |
| 4 | Eğitilmiş | 320 | **YAPILMADI** | — |

*Bu tablo ne söylüyor:* Matris tamamlanmış değil. Dördüncü hücre için ne eğitim koşusu
yapıldı ne ölçüm; o satırda sayı yok çünkü sayı yok. Bu bölümün ana karşılaştırması
birinci ve üçüncü hücre arasındadır: karo boyutu sabit tutulup yalnızca model
değiştirilir.

Dördüncü hücreyi boş bırakmak bir eksiklik, ama geçme koşulunu şimdiden yazabiliyorum:
Model-320'nin kabul edilmesi için **FP/görüntü ≤ 3,36 bütçesinde recall > 0,4402**
vermesi gerekir. Yani kendi ölçek tabanını, kendi yanlış pozitif bütçesinde geçmeli.

Dördüncü hücrenin bu bölümde yapılmamasının sebebi sıralama. Üçüncü hücre ana soruyu
yanıtlıyor; dördüncüsü ise ancak üçüncüsünün sonucu bilindikten sonra anlamlı bir soru
haline geliyor, çünkü karo küçültmenin eğitilmiş bir modelde de aynı yönde çalışıp
çalışmadığı ancak eğitilmiş bir modele sahipken sorulabilir. Kümenin kendisi hazır
duruyor; eksik olan eğitim koşusu ve ölçüm.

İkinci hücre, karo küçültmenin tek başına ne yaptığını gösteriyor. Aynı eğitimsiz model,
aynı test bölümü, tek fark karo boyutu ve örtüşme oranı:

| Güven eşiği | Karo 512 recall | Karo 512 FP/görüntü | Karo 320 recall | Karo 320 FP/görüntü |
|---|---|---|---|---|
| 0,05 | 0,7113 | 18,24 | 0,7526 | 40,86 |
| 0,15 | 0,5485 | 5,45 | 0,6175 | 10,86 |
| 0,30 | 0,3804 | 1,81 | 0,4402 | 3,36 |
| Süre | — | 6,63 sn/görüntü | — | 16,57 sn/görüntü |

*Bu tablo ne söylüyor:* Karoyu küçültmek her eşikte recall'ı artırıyor — conf 0,30'da
0,3804'ten 0,4402'ye, yani +0,0598. Ama aynı noktada FP/görüntü 1,81'den 3,36'ya
çıkıyor ve görüntü başına tarama süresi 6,63 saniyeden 16,57 saniyeye, yani iki buçuk
katından fazlasına uzuyor. Üç eksenin ikisi kötüleşiyor.

Bu yüzden "karo 320 tek başına bir kazanımdır" demedim ve demiyorum. Recall'ın arttığı
doğru; kazanım olup olmadığı ancak yanlış pozitif ve süre bütçesi sabitlenerek
söylenebilir, bu da yapılmadı.

### 4.5. Model-512 eğitimi ve yakınsama

Eğitimi Kaggle'ın ücretsiz T4 GPU'sunda koştum. Sıfırdan değil, `yolo11n.pt` ağırlıklarından
başlayan bir transfer öğrenmesi. Önemli parametreler: girdi boyutu 512, yığın (batch) 16,
100 epoch, sabır (patience) 20, tohum 0, `deterministic` açık. Veri artırma tarafında
mozaik 1,0 (son 10 epoch'ta kapanıyor), yatay çevirme 0,5, **dikey çevirme 0,0**. Dikey
çevirmeyi kapalı tuttum çünkü havadan çekilmiş bir görüntüde insan figürünün baş-ayak
yönü bilgi taşır.

Başlangıç ağırlığı olarak yolo11n'i seçmemin sebebi de karşılaştırmanın kendisi. Taban
çizgisi eğitimsiz yolo11n ile ölçüldü; aynı aileden başlayıp aynı boyutta bir ağ
eğitince, iki ölçüm arasındaki farkın mimari değişikliğinden gelmediğini biliyorum.
Değişen tek şey modelin gördüğü veri. Daha büyük bir gövde seçmek muhtemelen daha
yüksek bir sayı verirdi, ama bölümün sorusunu — kendi verimizle eğitmek ne kazandırıyor
— bulanıklaştırırdı.

Koşu 100 epoch'un tamamını tamamladı; sabır penceresi devreye girmedi. Log'a göre
**100 epoch 2,025 saatte** tamamlandı. En iyi epoch 82 çıktı. Ölçümde `best.pt`
kullandım, `last.pt` kullanmadım: ikisi aynı boyutta ama farklı dosyalar, ve karşılaştırmanın
hangi ağırlıkla yapıldığı belirsiz kalmamalı. Kullanılan dosya 5.463.834 bayt, SHA-256
özeti `66a93278…f3b7` ile başlıyor, sınıf tablosu `{0: 'human'}`.

Kaggle'ın kendi doğrulama kümesinde, en iyi epoch'ta ölçülen değerler: mAP50 **0,7982**,
mAP50-95 **0,4914**, precision **0,8488**, recall **0,7347**.

Bu dört sayıyı taban çizgisinin yanına koyup kazanım iddiası kurmadım ve kurmuyorum. İki
ölçüm farklı şeyler üzerinde: Kaggle doğrulaması 512×512 karolar üzerinde, kutu başına
IoU 0,7 ile hesaplanan standart bir doğrulama koşusudur; taban çizgisi ise tam görüntü
üzerinde karolamalı tarama, NMS birleştirme ve IoU 0,30 eşleşmesiyle ölçülmüştür. Aynı
ada sahip iki metrik, aynı protokolde ölçülmedikçe yan yana konamaz. Kaggle sayıları
burada yalnızca eğitimin makul bir noktaya yakınsadığını göstermek için var.

| Ölçüt | En iyi değer (epoch) | Epoch 100 | Fark |
|---|---|---|---|
| val/box_loss | 1,3232 (57) | 1,3462 | +0,0230 |
| val/cls_loss | 0,9039 (81) | 0,9177 | +0,0139 |
| val/dfl_loss | 1,2039 (66) | 1,2256 | +0,0218 |
| mAP50-95 | 0,4914 (82) | 0,4845 | −0,0069 |

*Bu tablo ne söylüyor:* Üç doğrulama kaybı da eğitimin sonunda en düşük noktalarının
biraz üstünde kalıyor ve mAP50-95 tepe noktasından 0,0069 geriliyor. Bu bir **sınırlı
ayrışmadır**: eğitim kaybı düşmeye devam ederken doğrulama tarafı son epoch'larda
yükseliyor, ama farklar ikinci ondalıkta kalıyor ve doğrulama metriği çökmüyor.
Buradan "aşırı uydurma yok" gibi mutlak bir sonuç çıkarmıyorum; çıkardığım sonuç,
son epoch yerine en iyi epoch'un ağırlığını kullanma kararının bu tabloyla uyumlu
olduğudur.

### 4.6. Kapı ölçümü ve kapı kuralının düzeltilmesi

Eğitilmiş modeli taban çizgisiyle birebir aynı protokolde ölçtüm: aynı test bölümü, aynı
157 görüntü ve 970 hedef, aynı karo boyutu ve örtüşme, aynı IoU eşiği, aynı script. Tek
değişen şey model ağırlığı.

| conf 0,30 | TP | FN | Recall | Yanlış pozitif | FP/görüntü | Precision |
|---|---|---|---|---|---|---|
| Taban-512 | 369 | 601 | 0,3804 | 284 | 1,81 | 0,5651 |
| Model-512 | 788 | 182 | 0,8124 | 617 | 3,93 | 0,5609 |

*Bu tablo ne söylüyor:* Sabit eşikte recall iki kattan fazla artıyor, ama yanlış pozitif
yükü de artıyor: görüntü başına 1,81'den 3,93'e. Precision ise neredeyse aynı kalıyor
(0,5651 → 0,5609), çünkü hem doğru hem yanlış tahmin sayısı birlikte büyüyor. Model-512'nin
617 yanlış pozitifinin 592'si ZRI kaynağından geliyor; bu dağılımın ne anlama geldiğini
4.8'de ele alıyorum.

Eğitim öncesinde koyduğum kapı kuralı şuydu:

> "Model-512 sabit conf 0,30'da Taban-512'nin recall'ını (0,3804) geçmeli ve
> FP/görüntüyü (1,81) artırmamalı."

Yukarıdaki tabloya göre bu kural **karşılanmadı**: recall koşulu sağlandı, FP koşulu
sağlanmadı. Ama kuralın kendisini yeniden okuduğumda kusurlu olduğunu gördüm.

Kusur şurada: güven eşiği bir model özelliği değil, **çevrilebilir bir hiperparametredir**.
Aynı sayısal eşik iki farklı modelde iki farklı çalışma noktasına denk gelir; skor
dağılımları farklı olduğu için 0,30 birinde ihtiyatlı, diğerinde cömert davranır. Eşiği
sabitlemek, iki modeli aynı yerde karşılaştırmayı garanti etmez. Kullanıcıya yansıyan şey
de zaten eşiğin sayısı değil, **görüntü başına kaç yanlış kutuya bakmak zorunda kaldığı**.
Sabitlenmesi gereken şey budur.

Kuralı şöyle değiştirdim:

> "Model, taban ile aynı FP/görüntü bütçesinde (≤ 1,81) daha yüksek recall vermeli;
> karşılaştırma noktası eşik değil bütçedir."

Bu kuralı uygulayabilmek için Model-512'nin eşik eğrisini çıkardım: conf 0,05'ten
0,95'e 0,01 adımlarla recall ve FP/görüntü. Tabanın 1,81'lik bütçesine denk gelen
noktayı bu eğriden okudum.

| Koşu | conf | TP | FN | Recall | FP/görüntü | Bütçe (≤ 1,81) |
|---|---|---|---|---|---|---|
| Taban-512 | 0,30 | 369 | 601 | 0,3804 | 1,81 | referans |
| Model-512 | 0,52 | 667 | 303 | 0,6876 | 1,83 | bütçe üstü |
| Model-512 | **0,53** | 662 | 308 | **0,6825** | **1,75** | içinde |
| Model-512 | 0,73 | 384 | 586 | 0,3959 | 0,53 | içinde |
| Model-512 | 0,74 | 356 | 614 | 0,3670 | 0,49 | içinde |

*Bu tablo ne söylüyor:* Tabanın yanlış pozitif bütçesine sığan ilk nokta conf 0,53.
Orada Model-512, taban ile karşılaştırılabilir bir yanlış alarm yükü altında recall
0,6825 veriyor. Bir alt satır (0,52) bütçeyi 0,02 ile aşıyor ve bu yüzden geçerli
karşılaştırma noktası değil. Son iki satır ise eşiği yükseltmeye devam edince ne
olduğunu gösteriyor: conf 0,73'te model, tabanın recall'ını (0,3959 karşı 0,3804) hâlâ
geçiyor ama yanlış pozitif yükü 0,53'e, yani tabanın üçte birinin altına iniyor;
0,74'te recall tabanın altına düşüyor. Bu iki satır, 0,53'ün bir uç nokta değil eğri
üzerinde bir seçim olduğunu gösteriyor.

Ana sonuç budur: **tabanın yanlış pozitif bütçesinde recall 0,3804'ten 0,6825'e
çıkıyor.** Bu 1,79 kat ve 293 ek hedef demek. Üstelik bunu yaparken Model-512 tabandan
biraz daha **az** yanlış pozitif üretiyor: 1,75 karşı 1,81.

Bu sonucu okurken iki ayrı şeyi karıştırmamak gerekiyor. Recall'ın artması, aynı 157
görüntüde daha önce hiç işaretlenmemiş 293 hedefin işaretlenmesi demek. FP/görüntünün
1,81'den 1,75'e inmesi ise operatörün bakacağı yanlış kutu sayısının artmadığı anlamına
gelir. İkisi aynı çalışma noktasında birlikte gerçekleştiği için bu, bir eksende
kazanıp diğerinde kaybetme durumu değil. Ama bunun bir **takas eğrisi üzerinde seçilmiş
tek nokta** olduğunu da unutmamak gerekir: eşik 0,52'ye indirildiğinde recall 0,6876'ya
çıkıyor ve bütçe aşılıyor; 0,73'e çıkarıldığında yanlış alarm üçte bire iniyor ve recall
tabanın hemen üstüne düşüyor. Hangi noktanın doğru olduğu ölçümün değil, operasyonun
sorusudur.

conf 0,53 için precision ve mutlak yanlış pozitif sayısı **ölçülmedi**; eşik taraması
CSV'si yalnızca recall ve FP/görüntü sütunlarını taşır.

Bu karşılaştırmayı ilk denemede yapamadım. Sebebi, kutu bazında kaydın yalnızca
**gerçek** kutuları tutmasıydı: her hedefin boyutu ve onu bulan tahminin skoru
kaydediliyordu, ama hiçbir hedefle eşleşmeyen tahminler — yani yanlış pozitiflerin
kendisi — hiçbir dosyaya yazılmıyordu. Bu kayıttan recall(conf) eğrisi türetilebiliyor,
FP(conf) eğrisi türetilemiyordu. Eşit-FP kuralını uygulamak için tam olarak o eğri
gerekiyordu. Boşluğu, ölçüm script'ine NMS sonrası **tüm** tahminleri skor ve
koordinatlarıyla yazan bir tahmin kaydı ekleyerek kapattım; Model-512 koşusu bu kayıtla
tekrarlandı ve eğri oradan türetildi.

### 4.7. Yükseklik bandı kazanımı

Hafta 0'da recall'ı yöneten değişken kutunun piksel cinsinden yüksekliğiydi. Müdahale
kendi verimizle eğitim oldu. Şimdi aynı değişkeni tekrar ölçüyorum: kazanım hangi
yükseklik bandında ne kadar?

Bantlar Hafta 0'da ölçülen kutu yüksekliği beştebirlik sınırlarıdır (44 / 55 / 65 / 80
piksel), yani eğitim sonucuna göre seçilmiş sınırlar değil.

| Yükseklik bandı | Hedef | Taban recall | Model recall | Fark |
|---|---|---|---|---|
| < 44 px | 82 | 0,2073 | 0,7561 | +0,5488 |
| 44–55 px | 173 | 0,2601 | 0,8035 | +0,5434 |
| 55–65 px | 239 | 0,3347 | 0,8201 | +0,4854 |
| 65–80 px | 257 | 0,4397 | 0,8599 | +0,4202 |
| ≥ 80 px | 219 | 0,5205 | 0,7763 | +0,2557 |

*Bu tablo ne söylüyor:* Taban sütununda recall yükseklikle birlikte düzenli olarak
artıyor — 0,2073'ten 0,5205'e. Model sütununda bu düzen büyük ölçüde kayboluyor: beş
bandın dördü 0,75–0,86 aralığında toplanıyor. Kazanım en kısa kutularda en büyük
(+0,5488) ve en uzun kutularda en küçük (+0,2557). Yani müdahale, ölçümün işaret ettiği
yerde en çok işe yaradı ve recall'ın yüksekliğe bağımlılığı azaldı. En küçük bant 82
hedefe dayanıyor; 50'nin üzerinde olduğu için tabloda yorumlanabilir, ama en dar
örneklem odur.

Bantların pratik anlamı şu: 4000×3000 pikselik bir karede 44 pikselden kısa bir kutu,
uçuş yüksekliği arttıkça giderek daha sık karşılaşılacak duruma karşılık gelir. Tabanın
o bantta verdiği 0,2073, beş hedeften dördünün hiç işaretlenmemesi demekti. Aynı bantta
modelin verdiği 0,7561 hâlâ kusursuz değil, ama sıralama tersine dönmüş durumda.

Bu tablo conf 0,30'da üretildi ve şu şerhi taşır: **conf 0,53 için bant eğrisi
türetilmedi; bant kırılımı ile eşit-FP kararı aynı conf noktasında hizalanmış değildir.**
Yani 4.6'daki eşit-bütçe sonucu ile buradaki bant kazanımları iki farklı çalışma
noktasından okunmuştur.

En uzun bandın (≥ 80 px) neden diğerlerinin altında kaldığını da açıklamadım. Akla gelen
bir ihtimal, %60 kenar kuralının uzun kutuları orantısız etkilemesi: kutu büyüdükçe
karo sınırına taşma olasılığı artar, taşan kutu da eşiği geçemeyip o karoya
yazılmaz. Bu bir **HİPOTEZ**; mekanizma ölçülmedi. Bandın kendisi 219 hedefe dayandığı
için gözlemin kendisi sağlam, açıklaması değil.

### 4.8. Zorunlu kısıtlar

Bu bölümün sayıları sekiz kısıtla birlikte okunmalı.

**Bir — test bölümünün neredeyse tamamı tek kaynaktan geliyor.** 970 hedefin 939'u ZRI,
yalnızca 31'i VRD kaynağından. Yani test bölümünün %97'si tek bir veri kümesinin
görüntüleridir. ZRI aynı zamanda eğitim bölümünde de bulunuyor; bölümler görüntü
düzeyinde ayrı ama kaynak düzeyinde değil. Bu iki gerçek birlikte, conf 0,30'daki
0,8124'ün genellenebilir bir ortalama olmadığını söyler. O sayı bir **üst sınırdır**:
modelin eğitimde bolca gördüğü bir kaynağın görüntülerinde ulaştığı değer.

Aynı bölümün bir başka özelliği de görüntü başına hedef yoğunluğu: test bölümünde
görüntü başına ortalama 6,18 kutu var, oysa train bölümünde 1,36. Test bölümü bu
anlamda da veri kümesinin geri kalanını temsil etmiyor.

**İki — ZRI_HARIC satırı bir güvenlik kontrolü değildir.** Kaynak yanlılığını ölçmek
için CSV'lerde ZRI hariç satırı tutuyorum, ama test bölümünde bu satır 31 hedefe çöküyor.
Kendi koyduğum alt sınır 50 hedef; 31 onun altında. Bu satır ilgi çekici olabilir, tek
başına sonuç çıkarılacak bir ölçüm değildir.

**Üç — yanlış pozitiflerin kaynak dağılımı.** conf 0,30'da Model-512'nin 617 yanlış
pozitifinin 592'si ZRI görüntülerinden geliyor. ZRI hariç bakıldığında recall 0,3548'den
0,9032'ye çıkıyor ve FP/görüntü 0,79'dan 0,36'ya **düşüyor** — yani ZRI dışındaki
görüntülerde model hem daha çok buluyor hem daha az yanlış alarm veriyor. Bu **İLGİNÇ
AMA KANITLANMAMIŞ**: arkasında yalnızca 31 hedef ve 70 görüntü var.

**Dört — %60 kenar kuralının bedeli ölçülmedi.** Kural, 512'lik kümede 745, 320'lik
kümede 1.578 belirsiz karo üretti. Bu karolar eğitim kümesine hiç girmedi. Kuralın
≥ 80 px bandındaki düşüşle ilişkisi ölçülmedi; 4.7'deki açıklama hipotez olarak kalıyor.

**Beş — bazı erken ölçümler temsili olmayan alt kümede üretildi.** İlk taban çizgisi
dosyası ve karolamalı/karolamasız karşılaştırma dosyası `--limit 100` ile koşuldu.
Dosyalar ada göre sıralandığı için bu 100 görüntü kaynakları dengesiz temsil ediyor:
70 VRD görüntüsünün tamamı, ZRI'nin 87 görüntüsünden yalnızca 30'u. ZRI veri kümesinin
en kolay kaynağı olduğu için bu alt küme çarpık. O dosyalardan **yön** okunabilir,
mutlak değer okunamaz. Bu bölümdeki taban çizgisi bu dosyalardan hiçbiri değil, test
bölümünün tamamı üzerinde koşulan ayrı ölçümdür.

**Altı — eşik taraması tek taraflı.** Tarama, Model-512 için tam: 273 hücrenin hepsinde
FP/görüntü dolu, çünkü o koşuda tahmin kaydı alındı. Taban-512 için taramanın yalnızca
9 hücresinde FP ölçülü, **264 hücrede `olculmedi` yazıyor**, çünkü taban koşusunda
tahmin kaydı alınmamıştı. Buna rağmen eşit-FP kararı geçerli: karar tabanın **tek** bir
noktasına dayanıyor ve o nokta (conf 0,30 → 1,81 FP/görüntü) ölçülmüş üç noktadan biri.
Tabanın kendi eğrisi bilinmediği için "taban da eşik çevrilerek ne kadar iyileşirdi"
sorusu bu bölümde yanıtsız.

**Yedi — konum alanları boş.** Görüntülerin EXIF/GPS alanları null; gerçek koordinat
verisi yok. Bu yüzden bu bölümde hiçbir yerde "GPS gerçek" denmez, ölçümler yalnızca
görüntü düzlemindedir.

**Sekiz — hız farkının mekanizması ölçülmedi.** Görüntü başına tarama süresi taban
koşusunda 6,63 saniye, Model-512 koşusunda 3,85 saniye. Bu bir **gözlemdir**. Neden
böyle olduğunu ölçmedim: NMS öncesi aday tahmin sayısı kaydedilmedi, iki koşu farklı
zamanlarda aynı CPU'da koştu ve makine yükü kontrol edilmedi. Süre farkını "model daha
az aday üretiyor" gibi bir mekanizmaya bağlamak için elimde ölçüm yok.

### 4.9. Çürütülen varsayımlar ve süreç dersleri

**Aynı eşikte karşılaştırma.** Eğitim öncesinde iki modeli aynı conf değerinde
karşılaştırmanın adil olduğunu varsaymıştım. Kapı kuralını da öyle yazmıştım. Sınamak
için Model-512'nin eşik eğrisini çıkardım ve tabanın FP noktasına denk gelen eşiği
aradım. Çıkan sonuç, aynı yanlış pozitif yükünün iki modelde farklı eşiklere denk
geldiğiydi: tabanda 0,30, modelde 0,53. Varsayım **ÇÜRÜTÜLDÜ**; sabitlenmesi gereken
şeyin eşik değil bütçe olduğuna karar verdim.

**Kutu bazında kaydın yeterli olduğu.** Kutu bazında CSV'nin her iki eğriyi de türetmeye
yeteceğini düşünmüştüm. Sınamak için eşik taramasını yazmaya oturduğumda, dosyanın
yalnızca gerçek kutuları ve onları bulan tahminlerin skorlarını tuttuğunu gördüm;
eşleşmeyen tahminler hiçbir yere yazılmıyordu. recall(conf) türetilebiliyor, FP(conf)
türetilemiyordu. Varsayım **ÇÜRÜTÜLDÜ**; ölçüm script'ine tüm tahminleri yazan bir
kayıt ekledim ve Model-512 koşusunu bu kayıtla tekrarladım.

**Kaggle veri yolunun sabit yazılabileceği.** Veri kümesinin `/kaggle/input/<slug>`
altına bağlanacağını varsayıp yolu doğrudan yazmıştım. Sınama kendiliğinden oldu: eğitim
başladı ve saniyeler içinde `IndexError` ile durdu, çünkü gerçek bağlanma yolu farklıydı
— Kaggle özel kümeleri başka bir dizin altına bağlıyor. Varsayım **ÇÜRÜTÜLDÜ**. Yolu
sabit yazmak yerine `glob` ile `data.yaml` aramaya geçtim ve tek aday bulunduğunu
doğrulayan bir `assert` koydum; birden fazla küme bağlıysa sessizce yanlış kümeyle eğitmek
mümkün olurdu. Ayrıca eğitimden önce koşan ucuz bir yapı kontrolü ekledim: görüntü listesi
boşsa önce anlaşılır bir hata veriyor, çünkü boş liste kontrolü olmadan asıl sebep
`IndexError`'ın arkasında gizleniyordu.

**Sınıf adının önemsiz olduğu.** Notebook'ta sınıf adını `insan`, karolama script'i ise
`human` yazıyordu. Tek sınıflı bir modelde adın sonucu değiştirmediğini düşünmüştüm, ama
iki farklı `data.yaml` üreticisinin farklı ad yazması, script bir daha koşulduğunda
çatışmanın geri gelmesi demekti. Notebook'u üretecin değerine uydurdum; elle yazılmış
değer değil, üretecin değeri esas alındı.

**Dört basamak yuvarlamanın etkisiz olduğu.** Tahmin kaydındaki skorlar dört ondalık
basamağa yuvarlı. Bunun sayımları etkilemeyeceğini varsaymıştım. Sınamak için türetilen
eğriyi ölçülmüş noktalarla karşılaştırdım: conf 0,30'da türetilen FP/görüntü 3,94,
ölçülen 3,93. Varsayım kısmen **ÇÜRÜTÜLDÜ** — etki sıfır değil. Etkisi ikinci ondalık
basamakta kalıyor ve eşik tam bir skor değerine denk geldiğinde bir-iki tahmin fazladan
sayılmasından kaynaklanıyor; eşit-FP kararını değiştirecek büyüklükte değil, ama
türetilmiş sayıları ölçülmüş sayı gibi sunmamak gerektiğini gösteriyor.

**Görüntü sayısını kutu bazında kayıttan saymak.** Test bölümünün görüntü sayısını
doğrulamak için kutu bazında CSV'deki benzersiz görüntü adlarını saydım ve 112 buldum;
oysa bölümde 157 görüntü var. Sebep basit ve kayıt tasarımının doğrudan sonucu: dosya
gerçek kutuları listeliyor, hedefi olmayan 45 görüntü hiç satır üretmiyor. Varsayım
**ÇÜRÜTÜLDÜ**; görüntü sayısı özet CSV'den okunmalı. Bu, dördüncü dersin tersinden
tekrarı: bir dosyadan ancak içine yazılan şey sayılabilir.

**"Karo 320 tek başına bir kazanımdır."** Karo küçültmenin recall'ı artırdığını
görünce bunu kazanım saymıştım. Aynı koşunun diğer sütunlarına baktığımda recall
+0,0598 artarken FP/görüntünün 1,81'den 3,36'ya, sürenin 6,63'ten 16,57 saniyeye
çıktığını gördüm. Varsayım **ÇÜRÜTÜLDÜ**: üç eksenin birinde iyileşip ikisinde
kötüleşen bir değişiklik, bütçe sabitlenmeden kazanım olarak adlandırılamaz.

**Karo boyutu ile adımın aynı şey olduğu.** 512 ile 320 karşılaştırmasının yalnızca karo
boyutunu değiştirdiğini varsaymıştım. Kayıtlara baktığımda iki koşunun örtüşme
oranlarının da farklı olduğunu gördüm: 512'de örtüşme 102 piksel, yani kaydırma adımı
410; 320'de örtüşme 80 piksel, adım 240. Adım oranı 1,71. Yani o deneyde iki değişken
birden değişti ve gözlenen farkın ne kadarının karo boyutundan, ne kadarının adımdan
geldiği **ayrıştırılamaz**. Varsayım **ÇÜRÜTÜLDÜ**. Doğru deney, adımı sabit tutup
yalnızca karo boyutunu değiştirmektir: 512'yi 0,53125 örtüşmeyle, 320'yi 0,25 örtüşmeyle
koşmak ikisinde de 240 pikselik adım verir. Bu deney yapılmadı.

### 4.10. Sonraki adım

#### 4.10.1 Ölçüm ve analiz tarafında açık kalanlar

Model-320 hiç eğitilmedi ve ölçülmedi; 2x2 matrisin dördüncü hücresi boş. Eğitim ve test
bölümlerinin kaynak öneki kesişimi sayısal olarak çıkarılmadı; ZRI'nin iki bölümde birden
bulunduğunu biliyorum ama bunun etkisini ölçmedim. ≥ 80 px bandındaki düşüşün %60 kenar
kuralıyla ilişkisi hipotez halinde. Adım sabitlenerek yapılacak karo boyutu deneyi
yapılmadı. "Belirsiz karolar kaç **benzersiz hedefi** etkiliyor" sorusunun doğru metriği
tanımlandı ama ölçülmedi. Taban çizgisinin tam eşik eğrisi çıkarılmadı; tabanın FP
tarafı yalnızca üç noktada ölçülü. conf 0,53 için yükseklik bandı kırılımı türetilmedi.
NMS öncesi aday tahmin sayısı hiçbir koşuda kaydedilmedi, bu yüzden hız farkının
mekanizması açık.

#### 4.10.2 Bir sonraki adımda fiilen yapılacak iş

Birincisi, hazır bekleyen karo 320 kümesini bu bölümdeki akışın aynısıyla eğitmek:
aynı transfer başlangıcı, aynı tohum, aynı epoch sayısı, aynı kayıt düzeni. Kümenin
kendisi zaten üretildi.

İkincisi, çıkan Model-320'yi kendi ölçek tabanına karşı değerlendirmek. Kapı şimdiden
yazılı: FP/görüntü ≤ 3,36 bütçesinde recall > 0,4402. Kapının eşik değil bütçe üzerinden
tanımlanmış olması, bu bölümde öğrenilen şeyin doğrudan uygulanmasıdır.

Üçüncüsü, modeli ONNX biçimine çevirmek ve gerçek çıkarım süresini ölçmek. Bu bölümdeki
süre sayıları CPU üzerinde, ölçüm script'inin içinden alınmış gözlemlerdir; dağıtılacak
biçimdeki gerçek gecikme ayrıca ölçülmelidir.
