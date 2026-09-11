## 2. Taban Çizgisinin Derinleştirilmesi ve Sistem İskeleti

*(ölçümün yeniden üretilebilirliği, başarısızlık türlerinin ayrıştırılması, hedef geometrisi ile recall ilişkisi, etiket kalitesi denetimi, sistem iskeleti, süreç dersleri)*

Bölüm 1'de hazır bir nesne tespit modelinin havadan çekilmiş arama-kurtarma
görüntülerinde ne kadarını bulduğunu ölçtüm. Bu bölümde iki iş birden yaptım. Birincisi,
o ölçümün içine girip **neyin neden kaçırıldığını** ayrıştırdım: kaçırmaların hepsi aynı
sebepten değil ve hangi sebebin hangi payı tuttuğu, bundan sonra nereye yatırım
yapılacağını belirliyor. İkincisi, ölçümün etrafına görüntülerin yüklendiği ve
saklandığı bir **sistem iskeleti** kurdum.

Bu bölümde de **hiç model eğitmedim**. Buradaki bütün sayılar, bölüm 1'de kurulan aynı
taban çizgisi koşusunun çıktılarından türetildi; yeni bir tarama yapılmadı. Tek istisna
2.1'de anlatılan tekrar koşusudur ve onun amacı yeni bir sonuç üretmek değil, eldeki
sonucun tekrar üretilebilir olduğunu göstermekti.

Kullandığım tüm sayılar ölçüm scriptlerinin ürettiği çıktı dosyalarından gelir. Hangi
sayının hangi dosyadan okunduğu bölüm 2.7'de listelidir.

---

### 2.1. Ölçümün yeniden üretilebilirliği

Bölüm 1'in ana tablosu, üç veri bölümünün birleştirilmesiyle elde edilen kaynak bazlı
taban çizgisiydi: 1.579 görüntü, 3.073 etiketli kutu, 17 kaynak, üç güven eşiği. Bu
koşu yalnızca CPU üzerinde **2 saat 42 dakika** sürmüştü.

Aynı koşuyu iki gün sonra, hiçbir parametresini değiştirmeden tekrarladım. Amacım yeni
bir bilgi elde etmek değildi; sonraki bütün karşılaştırmaların dayanacağı zeminin
sağlam olup olmadığını görmekti.

#### 2.1.1 Karşılaştırmanın kapsamı

İki koşunun ürettiği kaynak bazlı sonuç tablosu **57 satır ve 31 sütun** içeriyor. Bu
sütunlardan üçü tasarım gereği karşılaştırma dışında bırakıldı:

| Dışarıda bırakılan sütun | Neden |
|---|---|
| `sure_saniye_goruntu_basina` | İşlem süresi makinenin o anki yüküne göre değişir; deterministik değildir. |
| `kosu_tarih` | Koşunun ne zaman yapıldığı, sonucun kendisi değildir. |
| `kosu_komut` | Çalıştırılan komut satırının tam hali; çıktı yolu farklı verilebilir. |

*Bu tablo ne söylüyor:* Üç sütunun üçü de ölçümün **sonucunu** değil, ölçümün ne zaman
ve nasıl çalıştırıldığını kaydeden alanlar. Bunları karşılaştırmaya dahil etmek, saatin
ilerlemiş olmasını bir tutarsızlık gibi göstermek olurdu. Geriye kalan 28 sütunun
tamamı sonucun kendisidir: kutu sayıları, doğru bulunanlar, kaçırılanlar, recall,
yanlış pozitifler, precision ve koşu parametreleri.

Buna göre karşılaştırılan hücre sayısı **57 × 28 = 1.596**'dır.

#### 2.1.2 Sonuç

| Ölçüt | Sonuç |
|---|---|
| Satır anahtarı farkı (kaynak × güven eşiği) | yok |
| Sütun adı farkı | yok |
| Farklı çıkan hücre | **0 / 1.596** |
| İlk koşu süresi | 162,1 dakika |
| İkinci koşu süresi | 156,8 dakika |

*Bu tablo ne söylüyor:* Süre dışında hiçbir sayı oynamadı. 1.596 hücrenin tamamı
birebir aynı çıktı. İki koşu arasında kütüphane sürümleri de aynıydı: Python 3.13.1,
ultralytics 8.4.144, sahi 0.12.6, torch 2.14.0. Bu sürümler tahmin edilmedi, her iki
çıktı dosyasının `kosu_surum_` önekli sütunlarından okundu ve karşılaştırıldı.

**BULGU:** Taban çizgisi ölçümü bit düzeyinde tekrar üretilebilir. Tekrar
üretilebilirliği sağlayan üç tasarım kararı var: görüntü listesi dosya adına göre
sıralanıyor, çıkarım deterministik çalışıyor ve eşleştirmede skor eşitliği indeks
sırasıyla çözülüyor. Bunların üçü de bölüm 1'de bilinçli olarak konmuştu; bu koşu
onların işe yaradığını gösterdi.

#### 2.1.3 Bunun neden önemli olduğu

Bu, kendi başına ilginç bir sonuç değil. Önemi, bu bölümdeki ve sonraki bölümlerdeki
her karşılaştırmanın bu koşuya göre yapılacak olmasından geliyor.

Somut olarak: bundan sonra karo boyutunu değiştirdiğimde, modeli eğittiğimde veya
eşleştirme eşiğini oynattığımda, elde ettiğim recall'ı bu koşununkiyle
karşılaştıracağım. Eğer taban çizgisinin kendisi koşudan koşuya birkaç ondalık
oynasaydı, gözlediğim farkın müdahaleden mi yoksa gürültüden mi geldiğini
ayıramazdım. Küçük bir iyileştirme — diyelim recall'da 0,01'lik bir artış — ölçüm
gürültüsünün içinde kaybolurdu.

Şimdi gürültü tabanının **sıfır** olduğunu biliyorum. Bu, sonraki ölçümlerde
gördüğüm her farkın gerçek bir fark olduğu anlamına geliyor. Bir müdahale recall'ı
0,3160'tan 0,3170'e çıkarırsa, bu 0,001'lik artış gerçektir; rastlantı değildir.

Bunun bir maliyeti de var ve onu da yazmak gerekiyor: tekrar koşusu 2 saat 42 dakikalık
işlem süresinin ikinci kez harcanması demekti. Bu süreyi neden harcadığım bölüm
2.6'daki birinci derste anlatılıyor — koşuyu zaten tekrarlamak zorundaydım, çünkü ilk
koşu kutu bazındaki kaydı hiç üretmemişti. Tekrar üretilebilirlik kontrolü, mecburen
yapılan bir koşunun yan ürünü olarak elde edildi.

---

### 2.2. Başarısızlık türlerinin ayrıştırılması

Bölüm 1'de kaçırmaları iki türe ayırmıştım. **A türü** çözünürlük kaynaklıydı: hedef
küçüktü, model göremedi. **B türü** ise görünüm kaynaklı görünüyordu: BLI, GRO ve CAB
kaynaklarının kutuları küçük olmamasına rağmen recall'ları, boyutlarının öngördüğünden
belirgin biçimde düşüktü. B türünü bölüm 1'de **hipotez** olarak işaretlemiştim, çünkü
üç kaynakta toplam 101 kutu vardı ve bu, kaynak düzeyinde genelleme için ince bir
örneklem.

Bu bölümde B türünün doğasına dair somut bir soru sordum: bu kaynaklarda kutular
**bulunamıyor mu**, yoksa **bulunuyor ama düşük skorla sıralanıyor** mu?

Bu ayrım pratik bir sonuç doğuruyor. Eğer aday kutular üretiliyor ama skorları eşiğin
altında kalıyorsa, çözüm basit: eşiği düşür. Eğer aday hiç üretilmiyorsa, eşiği
düşürmenin hiçbir faydası olmaz — çünkü sıralanacak bir şey yok.

#### 2.2.1 Yöntem

Soruyu yanıtlamak için en düşük güven eşiğine, yani **0,05**'e baktım. Bu eşik, modelin
bildirdiği en zayıf adayları bile kapsıyor. Bir kutu bu eşikte bile hiçbir adayla
eşleşmiyorsa, o kutu için model hiçbir şey üretmemiş demektir.

Kutuları iki gruba ayırdım:

- **B türü:** BLI, GRO ve CAB kaynaklarının tamamı — 101 kutu.
- **Karşılaştırma grubu:** en az 100 kutusu olan diğer kaynaklar — BRA, BRK, BRS, GOR,
  MED, TRS, VRD ve ZRI; toplam 2.648 kutu.

Karşılaştırma grubuna 100 kutu alt sınırı koydum, çünkü altındaki kaynakların tek tek
oranları güvenilir değil ve karşılaştırmayı gürültüyle kirletirlerdi.

#### 2.2.2 Sonuç

| Grup | Kaynak sayısı | Kutu | Eşleşen | Hiç eşleşmeyen | Hiç eşleşmeyen oranı |
|---|---|---|---|---|---|
| B türü (BLI, GRO, CAB) | 3 | 101 | 37 | **64** | **%63,4** |
| Diğer (≥100 kutu) | 8 | 2.648 | 1.628 | 1.020 | %38,5 |

*Bu tablo ne söylüyor:* Güven eşiği 0,05'e, yani ölçtüğüm en düşük değere
indirildiğinde bile B türü kaynaklardaki kutuların **yaklaşık üçte ikisi** hiçbir
adayla eşleşmiyor. Karşılaştırma grubunda aynı oran %38,5. Aradaki fark 24,9 puan.
Model bu kutular için düşük skorlu bir tahmin bile üretmiyor; ortada sıralanacak bir
aday yok.

**BULGU:** B türü kaçırmaların çoğunluğu sıralama problemi değil, üretim problemidir.
"Güven eşiğini düşürerek bu kaynakları kurtarabiliriz" varsayımı, ölçülen veriyle
uyuşmuyor.

Burada bir örneklem uyarısı koymam gerekiyor. B türü grubu **101 kutu** içeriyor ve bu,
grup düzeyinde karşılaştırma için kabul edilebilir bir büyüklük. Ancak aşağıdaki skor
dağılımı yalnızca **eşleşen** kutular üzerinde hesaplanıyor ve B türünde eşleşen kutu
sayısı 37; bu, 50'lik alt sınırın altında kaldığı için **az örnek** olarak
işaretlenmiştir. Dağılımın kendisini bu uyarıyla birlikte okumak gerekiyor.

#### 2.2.3 Eşleşenlerin skor dağılımı

Eşleşen kutuların hangi güven skoruyla eşleştiğine de baktım. Eğer B türünde bulunan az
sayıdaki kutu eşiğin hemen üstünde toplanıyorsa, bu "eşik biraz daha düşse biraz daha
bulurduk" anlamına gelirdi.

| Skor bandı | B türü (n = 37, az örnek) | Diğer (n = 1.628) |
|---|---|---|
| 0,05 – 0,15 | 15 (%40,5) | 411 (%25,2) |
| 0,15 – 0,30 | 8 (%21,6) | 365 (%22,4) |
| 0,30 – 0,50 | 4 (%10,8) | 378 (%23,2) |
| 0,50 – 1,00 | 10 (%27,0) | 474 (%29,1) |

*Bu tablo ne söylüyor:* B türünde eşleşen kutuların %40,5'i en alt bantta, yani eşiğin
hemen üstünde. Karşılaştırma grubunda bu oran %25,2. B türünde bulunanların daha büyük
bir kısmı zar zor bulunuyor. Ancak bu dağılım yalnızca **37 kutuya** dayanıyor; alt
banttaki 15 kutuluk fark, birkaç kutunun yer değiştirmesiyle oynayabilecek bir
büyüklük. Bu yüzden dağılımı bir bulgu olarak değil, 2.2.2'deki asıl sonucu destekleyen
ikincil bir gözlem olarak sunuyorum.

**İLGİNÇ AMA KANITLANMAMIŞ:** B türünde bulunan kutuların eşiğe daha yakın toplanması,
modelin bu kaynaklardaki hedeflere genel olarak daha düşük güven atadığına işaret
ediyor olabilir. Ancak örneklem bunu bağımsız bir bulgu saymaya yetmiyor.

#### 2.2.4 Eşiği düşürmenin bedeli

Yukarıdaki analiz "eşiği düşürmek B türünü kurtarmaz" diyor. Peki eşiği düşürmek genel
olarak ne kadara mal oluyor?

| Güven eşiği | Recall | Toplam yanlış pozitif | FP/görüntü | Precision |
|---|---|---|---|---|
| 0,30 | 0,3160 | 1.407 | **0,89** | 0,4083 |
| 0,15 | 0,4520 | 5.380 | 3,41 | 0,2052 |
| 0,05 | 0,6066 | 21.387 | **13,54** | 0,0802 |

*Bu tablo ne söylüyor:* Eşiği 0,30'dan 0,05'e indirmek recall'ı 0,3160'tan 0,6066'ya
çıkarıyor — yani neredeyse iki katına. Ama görüntü başına yanlış alarm 0,89'dan 13,54'e
yükseliyor; bu **15 katlık** bir artış. Mutlak sayıyla: 1.407 yanlış tespit yerine
21.387 yanlış tespit. Operatörün elemesi gereken hacim, bulunan insan sayısından çok
daha hızlı büyüyor. Precision 0,4083'ten 0,0802'ye düşüyor; yani her 100 tespitin
yalnızca 8'i gerçek.

Bu tablo 2.2.2 ile birlikte okunduğunda tek bir sonuca varıyor: eşiği düşürmek hem
pahalı hem de B türü için etkisiz. Pahalı, çünkü yanlış alarm bütçesini 15 katına
çıkarıyor. Etkisiz, çünkü B türü kutuların %63,4'ü zaten en düşük eşikte bile
bulunmuyor.

Bu tablodaki üç satır da veri kümesinin **tamamına** aittir: 1.579 görüntü, 3.073 kutu.
Bölüm 1'de belirtildiği gibi, baskın kaynak (ZRI) hariç tutulduğunda sayılar farklıdır
ve bu bölümde de karışmaması için ayrı ayrı verilecektir.

---

### 2.3. Hedef geometrisi ile recall ilişkisi

Bu, bölümün ana bulgusu. Anlatımı üç aşamada kuruyorum: önce gözlediğim şey, sonra ilk
yorumum, sonra o yorumu nasıl sınadığım ve sınamanın onu nasıl elediği.

#### 2.3.1 Gözlem: en-boy oranına göre recall ayrışıyor

Her etiket kutusunun genişliğini yüksekliğine bölerek bir **en-boy oranı** hesapladım.
Oran 1'den büyükse kutu yatay uzanmış, 1'den küçükse dikey uzanmış demektir. Kutuları
üç gruba ayırdım: **yatay** (oran > 1,5), **kare benzeri** (0,8 – 1,5) ve **dikey**
(oran < 0,8). Sınırları veriye bakmadan, geometrik olarak simetrik seçtim.

Güven eşiği 0,30'da, veri kümesinin tamamında:

| Oran grubu | Aralık | Kutu | Bulunan | Recall | Medyan oran |
|---|---|---|---|---|---|
| Yatay | > 1,5 | 481 | 97 | **0,2017** | 1,738 |
| Kare benzeri | 0,8 – 1,5 | 1.737 | 445 | **0,2562** | 1,076 |
| Dikey | < 0,8 | 855 | 429 | **0,5018** | 0,655 |

*Bu tablo ne söylüyor:* Dikey uzanmış kutuların recall'ı, yatay uzanmışların iki
katından fazla (0,5018'e karşı 0,2017). Üç grubun üçü de 481 kutunun üzerinde, yani
hiçbiri az örnek değil. Ayrışma büyük ve örneklem sağlam.

Aynı hesabı baskın kaynak ZRI hariç tutarak tekrarladım, çünkü ZRI tek başına tüm
etiketlerin %42'sini taşıyor ve toplu sayıyı kendi başına belirleyebilir:

| Oran grubu | Kutu | Bulunan | Recall | Medyan oran |
|---|---|---|---|---|
| Yatay | 278 | 40 | 0,1439 | 1,774 |
| Kare benzeri | 947 | 167 | 0,1763 | 1,067 |
| Dikey | 551 | 266 | 0,4828 | 0,641 |

*Bu tablo ne söylüyor:* ZRI çıkarıldığında üç grubun da recall'ı düşüyor ama sıralama
korunuyor ve aradaki fark **büyüyor**: dikey ile yatay arasındaki uçurum 0,3001'den
0,3389'a çıkıyor. Yani gözlenen ayrışma ZRI'nin yarattığı bir yanılsama değil.

Bu iki tablodaki ZRI hariç satırlar, bölüm 1'deki 0,2663 recall ve 0,74 FP/görüntü
değerleriyle aynı kapsamdan gelir: 1.453 görüntü ve 1.776 kutu. Tablodaki üç grubun
kutu sayıları toplandığında (278 + 947 + 551) bu sayı elde edilir.

#### 2.3.2 İlk yorumum: "model ayakta duran insan önseline sahip"

Bu tabloları ilk gördüğümde şöyle düşündüm. Model COCO veri kümesiyle eğitilmiş. COCO'da
"person" sınıfının örneklerinin ezici çoğunluğu yerden çekilmiş fotoğraflarda ayakta
duran veya oturan insanlar. Ayakta duran bir insan görüntüde dikey bir dikdörtgen
kaplar: uzun ve dar.

Havadan bakıldığında ise durum değişir. Dik duran bir insan yukarıdan bakıldığında
kısalır; yere uzanmış bir insan ise yatay bir dikdörtgen olarak görünür. Dolayısıyla
model, kendi eğitim dağılımına benzeyen dikey kutuları buluyor, benzemeyen yatay
kutuları kaçırıyor olabilirdi.

Bu yorum bölüm 1'deki bir gözlemle de örtüşüyordu: BLI kaynağının örneklerine gözle
baktığımda bulunanların dik durduğunu, kaçırılanların neredeyse tamamının çimende
yattığını görmüştüm.

Yorum tutarlıydı, açıklayıcıydı ve elimdeki iki ayrı gözlemle uyumluydu. Tam da bu
yüzden şüphelendim.

#### 2.3.3 Karıştırıcı değişken: yükseklik

Yorumu ilan etmeden önce şunu sordum: en-boy oranı, tek başına bir şey mi ölçüyor,
yoksa başka bir şeyin gölgesi mi?

Buradaki sorun şu. En-boy oranı genişliğin yüksekliğe bölümü. **Dikey bir kutu, tanımı
gereği yüksekliği genişliğinden büyük olan kutudur.** Eğer recall'ı belirleyen şey
aslında kutunun piksel cinsinden yüksekliğiyse, dikey kutular otomatik olarak daha
yüksek recall gösterirdi — duruşla hiç ilgisi olmadan. Yükseklik burada bir
**karıştırıcı değişken** (confounder): hem oranı hem recall'ı aynı anda etkileyen ve
ikisi arasında sahte bir ilişki yaratabilen üçüncü bir etken.

Bunu sınamanın yolu **koşullama**: bir değişkeni sabitleyip diğerinin etkisine bakmak.
Ama tek yönlü koşullama yanıltıcı olabilir, çünkü hangi değişkeni sabitlediğinize göre
sonuç değişir. Bu yüzden testi **simetrik** kurdum: önce oranı sabitleyip yükseklik
etkisine, sonra yüksekliği sabitleyip oran etkisine baktım. Gerçek etken hangisiyse, o
diğeri sabitlendiğinde ayakta kalmalı.

Kutuları yüksekliğe göre üç tabakaya böldüm. Tabaka sınırlarını sabit bir sayı
uydurarak değil, verinin kendi yükseklik dağılımının üçlü çeyreklerinden hesapladım:
veri kümesinin tamamında **52,0** ve **70,0** piksel. Böylece her tabakaya yaklaşık eşit
sayıda kutu düşüyor.

#### 2.3.4 Birinci yön: oran sabit, yükseklik değişiyor

Her oran grubunun içinde, yükseklik tabakaları arasında recall nasıl değişiyor?

| Oran grubu | Kısa (< 52 px) | Orta (52 – 70 px) | Uzun (> 70 px) |
|---|---|---|---|
| Yatay | 0,1603 (n = 312) | 0,2190 (n = 137) | 0,5312 (n = 32, az örnek) |
| Kare benzeri | 0,1464 (n = 690) | 0,2729 (n = 667) | 0,4263 (n = 380) |
| Dikey | 0,2000 (n = 90, az örnek) | 0,4456 (n = 193) | 0,5682 (n = 572) |

*Bu tablo ne söylüyor:* Her satırda, soldan sağa gidildikçe recall artıyor. Bu üç oran
grubunun **üçünde de** geçerli. Yatay kutularda 0,1603'ten 0,5312'ye, kare benzerlerde
0,1464'ten 0,4263'e, dikeylerde 0,2000'den 0,5682'ye. Yani oran ne olursa olsun, kutu
uzadıkça bulunma olasılığı yükseliyor. İki hücre az örnek bayrağı taşıyor (32 ve 90
kutu) ve tek başlarına yorumlanmamalı; ancak kare benzeri satırı 690, 667 ve 380
kutuyla tamamen sağlam ve aynı eğilimi tek başına gösteriyor.

**Yükseklik etkisi, oran sabitlendiğinde ayakta kaldı.**

#### 2.3.5 İkinci yön: yükseklik sabit, oran değişiyor

Şimdi aynı tabloyu diğer yönden okuyorum. Her yükseklik tabakasının içinde, oran
grupları arasında recall nasıl değişiyor?

Koşulsuz halde dikey ile yatay arasındaki fark **+0,3001**'di (0,5018'e karşı 0,2017).
Yükseklik sabitlendiğinde bu fark ne oluyor?

| Yükseklik tabakası | Yatay | Kare benzeri | Dikey | Dikey − Yatay |
|---|---|---|---|---|
| Kısa (< 52 px) | 0,1603 (n = 312) | 0,1464 (n = 690) | 0,2000 (n = 90, az örnek) | **+0,0397** |
| Orta (52 – 70 px) | 0,2190 (n = 137) | 0,2729 (n = 667) | 0,4456 (n = 193) | **+0,2266** |
| Uzun (> 70 px) | 0,5312 (n = 32, az örnek) | 0,4263 (n = 380) | 0,5682 (n = 572) | **+0,0370** |

*Bu tablo ne söylüyor:* Kısa tabakada dikey ile yatay arasındaki fark 0,3001'den
0,0397'ye düşüyor — yani koşulsuz farkın yaklaşık sekizde biri. Uzun tabakada 0,0370;
benzer şekilde çökmüş durumda. Üstelik uzun tabakada sıralama da bozuluyor: yatay
kutuların recall'ı (0,5312) kare benzerlerinkinden (0,4263) **yüksek** çıkıyor, yani
"yatay olmak kötüdür" beklentisi tersine dönüyor. Yalnızca orta tabakada fark büyük
ölçüde korunuyor (+0,2266).

Aynı hesabı ZRI hariç tekrarladığımda tablo şu hale geliyor (tabaka sınırları bu kapsam
için yeniden hesaplandı: 49,0 ve 68,0 piksel):

| Yükseklik tabakası | Yatay | Kare benzeri | Dikey | Dikey − Yatay |
|---|---|---|---|---|
| Kısa (< 49 px) | 0,1011 (n = 178) | 0,0829 (n = 386) | 0,0444 (n = 45, az örnek) | **−0,0567** |
| Orta (49 – 68 px) | 0,0972 (n = 72, az örnek) | 0,1868 (n = 380) | 0,4122 (n = 131) | **+0,3150** |
| Uzun (> 68 px) | 0,5357 (n = 28, az örnek) | 0,3536 (n = 181) | 0,5600 (n = 375) | **+0,0243** |

*Bu tablo ne söylüyor:* ZRI hariç kapsamda kısa tabakada fark **işaret değiştiriyor**:
dikey kutuların recall'ı (0,0444) yatay kutularınkinden (0,1011) düşük. Uzun tabakada
fark yine çökmüş (+0,0243). Orta tabakada ise fark korunuyor, hatta koşulsuz farktan
(+0,3389) biraz küçük ama hâlâ büyük (+0,3150).

**Oran etkisi, yükseklik sabitlendiğinde üç tabakanın ikisinde çöküyor; ZRI hariç
kapsamda kısa tabakada ise tersine dönüyor. Yalnızca orta tabakada ayakta kalıyor.**

İki yönün sonucu asimetrik. Yükseklik, oran sabitlendiğinde üç oran grubunun üçünde de
etkisini koruyor. Oran ise, yükseklik sabitlendiğinde üç tabakanın yalnızca birinde
koruyor. Bu asimetri, hangisinin asıl etken olduğunu gösteriyor.

#### 2.3.6 Kontrol: aynı test alan üzerinden yapılınca

Yüksekliği sabitlemeden önce aynı testi **alan** üzerinden de yapmıştım: kutuları
alanlarına göre üç tabakaya bölüp her tabakanın içinde oran etkisine baktım. Sonucu
buraya koyuyorum, çünkü yükseklikle arasındaki fark öğreticidir.

| Alan tabakası | Yatay | Kare benzeri | Dikey | Dikey − Yatay |
|---|---|---|---|---|
| Küçük (< 2.860 px²) | 0,1172 (n = 128) | 0,1437 (n = 668) | 0,3493 (n = 229) | +0,2321 |
| Orta (2.860 – 4.779 px²) | 0,1890 (n = 164) | 0,2667 (n = 555) | 0,5049 (n = 305) | +0,3159 |
| Büyük (> 4.779 px²) | 0,2698 (n = 189) | 0,3911 (n = 514) | 0,6075 (n = 321) | +0,3377 |

*Bu tablo ne söylüyor:* Alan sabitlendiğinde oran etkisi **üç tabakanın üçünde de**
ayakta kalıyor; üstelik hiçbir hücre az örnek bayrağı taşımıyor. Eğer testi yalnızca
alan üzerinden yapıp bırakmış olsaydım, "oran bağımsız bir etkendir" sonucuna varır ve
2.3.2'deki duruş yorumunu doğrulanmış sayardım. Yüksekliği ayrı bir eksen olarak
sınamak, bu yanlış sonucu engelledi.

Bunun sebebi geometrik: alan genişlik ile yüksekliğin çarpımıdır ve aynı alanı çok
farklı yükseklik değerleriyle elde etmek mümkündür. Alanı sabitlemek yüksekliği
sabitlemez. Yüksekliği sabitlemek ise doğrudan sabitler.

#### 2.3.7 Altı ölçünün doğrudan karşılaştırması

Koşullama testleri "hangisi asıl etken" sorusuna yanıt veriyor ama bir de doğrudan
karşılaştırma yapmak istedim. Altı farklı geometrik ölçünün, kutunun bulunup
bulunmadığını gösteren ikili değişkenle **nokta-çift korelasyonunu** hesapladım. Bu
korelasyon, sürekli bir ölçü ile 0/1 değerli bir değişken arasındaki doğrusal ilişkinin
gücünü verir; değeri 0'a yakınsa ilişki yok, 1'e yakınsa güçlü ilişki var demektir.

| Ölçü | Nokta-çift korelasyon |
|---|---|
| Kutu yüksekliği (piksel) | **0,3258** |
| Yükseklik / genişlik oranı | 0,2809 |
| Maksimum kenar (piksel) | 0,2378 |
| Kutu alanı (piksel²) | 0,2150 |
| Minimum kenar (piksel) | 0,1872 |
| Kutu genişliği (piksel) | **0,0438** |

*Bu tablo ne söylüyor:* Altı ölçü arasında recall ile en güçlü ilişkiyi **yükseklik**
kuruyor (0,3258). Oranın kendisi ikinci sırada (0,2809) — yani oran gerçekten bir sinyal
taşıyor, ama yükseklikten zayıf bir sinyal; ve 2.3.5 bu sinyalin yükseklik sabitlendiğinde
büyük ölçüde kaybolduğunu gösteriyor. Alan (0,2150) yükseklikten belirgin biçimde
geride. En çarpıcısı **genişlik**: 0,0438 ile pratikte sıfır. Kutunun ne kadar geniş
olduğu, bulunup bulunmayacağı hakkında neredeyse hiçbir şey söylemiyor.

Bu farkı iki quintile eğrisi yan yana koyunca daha net görülüyor. Her ölçüyü kendi
dağılımının beşli çeyreklerine bölüp her grupta recall'ı ölçtüm:

| Grup (küçükten büyüğe) | Yükseklik: medyan → recall | Genişlik: medyan → recall |
|---|---|---|
| 1 | 39 px → 0,1123 | 39 px → 0,2730 |
| 2 | 51 px → 0,2088 | 50 px → 0,2982 |
| 3 | 60 px → 0,3023 | 61 px → 0,3434 |
| 4 | 72 px → 0,4173 | 73 px → 0,3361 |
| 5 | 95 px → 0,5584 | 95 px → 0,3317 |

*Bu tablo ne söylüyor:* İki ölçünün medyan değerleri neredeyse aynı aralıkta (39'dan
95 piksele) ama davranışları tamamen farklı. Yükseklik arttıkça recall tekdüze
yükseliyor: 0,1123'ten 0,5584'e, yani beş kattan fazla. Genişlik arttıkça recall önce
hafifçe yükselip sonra düzleşiyor: 0,2730'dan 0,3434'e çıkıp 0,3317'ye geri iniyor. En
geniş kutular, üçüncü gruptakilerden daha iyi bulunmuyor. Her grup 591 ile 637 kutu
arasında; hiçbiri az örnek değil.

#### 2.3.8 Sonuç

**BULGU:** Recall'ı yöneten şey kutunun alanı veya en-boy oranı değil, kutunun piksel
cinsinden **yüksekliğidir**. Genişliğin katkısı ölçülebilir düzeyde değildir
(korelasyon 0,0438; quintile eğrisi düz).

**ÇÜRÜTÜLDÜ — "model ayakta duran insan önseline sahip":**

- *Ne tahmin ettim:* Model COCO'daki dikey insan şekline alışkın olduğu için dikey
  kutuları buluyor, yatay kutuları kaçırıyor. Yani asıl etken hedefin duruşu.
- *Nasıl ölçtüm:* Simetrik koşullama. Önce oranı sabitleyip yükseklik etkisine, sonra
  yüksekliği sabitleyip oran etkisine baktım. Tabaka sınırlarını verinin kendi
  dağılımının üçlü çeyreklerinden hesapladım. Aynı hesabı ZRI dahil ve hariç olmak
  üzere iki kapsamda tekrarladım. Ayrıca altı geometrik ölçünün recall ile
  korelasyonunu karşılaştırdım.
- *Ne çıktı:* Yükseklik etkisi, oran sabitlendiğinde üç oran grubunun üçünde de ayakta
  kaldı. Oran etkisi ise yükseklik sabitlendiğinde üç tabakanın ikisinde çöktü ve ZRI
  hariç kapsamda kısa tabakada işaret değiştirdi. Korelasyon sıralamasında yükseklik
  (0,3258) oranın (0,2809) önünde. Gözlenen oran ayrışması büyük ölçüde yükseklik
  farkının gölgesi.

Duruş yorumunun tamamen yanlış olduğunu iddia etmiyorum; iddia ettiğim şey, elimdeki
veriyle **oran etkisinin yükseklikten bağımsız bir etken olduğunu gösteremediğim**.
Yatay uzanmış bir insan aynı zamanda kısa bir kutu üretir; bu iki özellik veri kümesinde
birbirine gömülü ve mevcut ölçüm onları ayıramıyor.

**AÇIK SORU:** Orta yükseklik tabakasında oran farkı neden ayakta kalıyor? Bu tabakada
dikey ile yatay arasındaki fark veri kümesinin tamamında +0,2266, ZRI hariç kapsamda
+0,3150 — her ikisi de koşulsuz farkın büyük kısmını koruyor. Kısa ve uzun tabakalarda
fark çökerken orta tabakada durması, açıklayamadığım bir düzensizlik. Orta tabakanın
hücreleri örneklem bakımından da zayıf değil (137, 667 ve 193 kutu), yani bunu
gürültüye bağlayamıyorum. Bu soru bu bölümde cevaplanmadı.

---

### 2.4. Etiket kalitesi denetimi

Yukarıdaki analizlerin tamamı bir varsayıma dayanıyor: etiketlerin doğru olduğuna. Eğer
veri kümesindeki bazı kutular aslında insan değilse, modelin onları "kaçırması" hata
sayılmaz ve düşük recall'ın bir kısmı veri hatasından geliyor olurdu.

Bu varsayımı en çok şüphelendiğim yerde sınadım: **CAB** kaynağında. CAB, bölüm 1'de B
türü olarak işaretlenen üç kaynaktan biri ve recall'ı 0,088 ile veri kümesinin en
düşüklerinden. Ayrıca bölüm 1'de görsel incelemede CAB'in arazisinin kayalık olduğunu ve
insanların açık gri kayaların arasında neredeyse kontrastsız durduğunu not etmiştim.

CAB'in örnek görsellerinden birinde, modelin hiçbir adayla eşleştirmediği bir etiket
kutusuna yakınlaştırıp gözle inceledim. Kutunun içindeki nesne insan değildi.

**Sonuç:** Bu tek gözlem, bu kaynaktaki düşük recall'ın veri hatasından kaynaklandığı
anlamına gelmiyor. Tam tersi bir okuma da mümkün değil. Yapabildiğim tek çıkarım şu: bu
kaynakta en azından bir hatalı etiket var ve ölçtüğüm recall değerleri, etiketlerin
tamamının doğru olduğu varsayımıyla hesaplanmış durumda.

**SINIR — bu denetim tek görselde tek nesneyle sınırlıdır.** Bir görseldeki bir kutuya
bakıp bir kaynağın etiket kalitesi hakkında konuşamam. CAB'de 34 etiketli kutu var;
denetlenen oran %3'ün altında. Bu denetim sistematik değil, tesadüfi bir gözlem. Etiket
kalitesinin recall'a katkısını ölçmek için, en az bir kaynağın kutularının tamamının
bağımsız olarak yeniden etiketlenmesi ve iki etiket kümesinin karşılaştırılması
gerekirdi. Böyle bir çalışma yapılmadı.

Bu gözlemi rapora koymamın sebebi, sonraki ölçümlerde etiket kalitesinin akılda
tutulması gereken bir değişken olduğunu işaretlemek. Şu an elimde bu değişkenin
büyüklüğüne dair hiçbir sayı yok.

---

### 2.5. Sistem iskeleti

Bölüm 1'in sonunda, ölçümlerin tek seferlik script koşuları olarak sürdürülemeyeceğini
yazmıştım. Bu adımda ölçümün etrafına bir sistem kurdum. Bu adımda **hiçbir tespit
çalıştırılmadı**; kurulan şey, görüntülerin yüklendiği, doğrulandığı ve saklandığı
boru hattının ilk halkası.

#### 2.5.1 Yığın

| Bileşen | Sürüm | Rolü |
|---|---|---|
| Docker Compose | — | Çalışma ortamının tekrar üretilebilir paketlenmesi |
| Python | 3.13 (slim-bookworm) | Çalışma zamanı |
| Django | 5.2.17 (LTS) | Web çerçevesi |
| Django REST Framework | 3.18.1 | API katmanı |
| SimpleJWT | 5.5.1 | Token tabanlı kimlik doğrulama |
| PostgreSQL + PostGIS | 16 + 3.5 | Veritabanı ve coğrafi veri desteği |
| psycopg | 3.3.5 | Veritabanı sürücüsü |

*Bu tablo ne söylüyor:* Seçimlerin ortak paydası uzun ömürlülük. Django'nun LTS sürümü
seçildi, çünkü proje dokuz adım boyunca sürecek ve ara sürüm yükseltmeleriyle uğraşmak
ölçüm zamanından çalar. PostGIS, veritabanına coğrafi sorgu yeteneği ekler; şu an
kullanılmıyor ama tespit koordinatlarının haritaya bağlanması planlandığı için baştan
kuruldu. Kimlik doğrulamanın token tabanlı olması, ileride bir web arayüzünün aynı API
ile konuşabilmesi içindir.

Gizli anahtarların hiçbiri koda gömülü değil; hepsi ortam değişkeninden okunuyor.
Django'nun gizli anahtarı boş bırakılırsa uygulama açılmıyor — kodda sessiz bir
varsayılan yok. Bu, yanlışlıkla varsayılan anahtarla çalışan bir kurulumun fark
edilmeden ayakta kalmasını engelliyor.

#### 2.5.2 Veri modeli

Beş tablo kurdum:

| Tablo | Ne tutuyor |
|---|---|
| **Mission** | Bir arama görevi: ad, açıklama, oluşturan kullanıcı, tarih |
| **Frame** | Göreve ait tek bir görüntü: dosya, özgün ad, sha256 özeti, genişlik, yükseklik, çekim zamanı, enlem/boylam/irtifa, durum |
| **ModelVersion** | Kullanılan model sürümü: ad, ağırlık dosyası, çerçeve, giriş boyutu, karo boyutu, örtüşme oranı |
| **InferenceRun** | Bir görev üzerinde bir model sürümüyle yapılan koşu: eşikler, karo ayarları, durum, ilerleme sayaçları |
| **Detection** | Tek bir tespit: hangi koşu, hangi kare, skor, kutu koordinatları, karo satır/sütunu |

*Bu tablo ne söylüyor:* Şemanın ayrım noktası **ModelVersion** ve **InferenceRun**'ın
ayrı tablolar olması. Aynı görüntü kümesi üzerinde farklı model sürümleriyle veya
farklı eşiklerle birden çok koşu yapılacak; her koşunun sonucu kendi kaydında durursa
koşular birbirinin üzerine yazmadan karşılaştırılabilir. Bölüm 1'de bu bilgi CSV
dosyalarında duruyordu ve tek koşu için yeterliydi; üst üste binen koşular için değil.

Tespit kutularının koordinatları **orijinal görüntü düzleminde** saklanıyor, karo
düzleminde değil. Karo koordinatları ayrı sütunlarda ayrıca tutuluyor. Bunun sebebi,
bir tespitin hangi karodan geldiğini bilmenin hata ayıklama için gerekli olması, ama
tespiti operatöre gösterirken orijinal görüntü üzerinde konumlandırmak zorunda olmam.

#### 2.5.3 Kısıtlar ve indeksler: neden bu üçü

Şemaya üç kısıt ve indeks koydum. Her biri belirli bir sorguyu veya belirli bir hatayı
hedefliyor.

**(mission, sha256) üzerinde tekillik kısıtı.** Her yüklenen görüntünün içeriğinden bir
sha256 özeti hesaplanıyor ve aynı görev içinde aynı özete sahip ikinci bir kayıt
açılamıyor. Bunun amacı **yeniden yükleme güvenliği**. Saha koşullarında bir yükleme
yarıda kesilip tekrar denenebilir; operatör aynı klasörü ikinci kez seçebilir. Kısıt
olmasaydı aynı fotoğraf iki kayıt olarak girer ve o görüntüdeki insanlar iki kez
sayılırdı — yani metrikler sessizce bozulurdu. Kısıt görev bazında tanımlı, çünkü aynı
fotoğrafın iki farklı görevde bulunması meşru bir durum.

**(mission, status) üzerinde bileşik indeks.** Sistem, bir görevdeki işlenmeyi bekleyen
kareleri bulmak zorunda: "şu görevin durumu *bekliyor* olan kareleri getir". Bu, iş
kuyruğunun her turda çalıştıracağı sorgu. İki sütun birlikte indekslendiğinde
veritabanı bu sorguyu tablonun tamamını taramadan yanıtlıyor.

**(inference_run, -score) üzerinde indeks.** Operatöre tespitler rastgele sırayla
gösterilmez; en yüksek skorlu olanlar önce gösterilir. Bu, "şu koşunun tespitlerini
skora göre azalan sırada getir" sorgusu demek. İndeks skora göre **azalan** yönde
tanımlı, çünkü sorgu her zaman o yönde çalışacak.

Üç kısıtın ortak özelliği, hiçbirinin genel amaçlı olmaması. Her biri, sistemin fiilen
çalıştıracağı belirli bir sorgudan veya fiilen karşılaşılacak belirli bir hatadan
türetildi.

#### 2.5.4 Kapı testi

İskeletin çalıştığını göstermek için uçtan uca bir test yaptım. Buna kapı testi diyorum:
amacı başarımı ölçmek değil, boru hattının her halkasının bağlı olduğunu doğrulamak.

| Adım | Sonuç |
|---|---|
| Gerçek fotoğraf yükleme | 5 fotoğraf yüklendi |
| Çözünürlük doğrulaması | Beşinin de 4000×3000 olduğu kaydedildi |
| Aynı dosyaların ikinci kez yüklenmesi | Yeni kayıt açılmadı, yinelenen olarak bildirildi |
| Otomatik testler | 10 test geçti |

*Bu tablo ne söylüyor:* Boru hattının ilk halkası çalışıyor. Özellikle ikinci satır
önemli: görüntü boyutu varsayılmıyor, yüklenen dosyadan okunup kaydediliyor. Bölüm
1'de veri kümesinin çözünürlüğünün sessizce değiştirilmiş olması tüm projenin
gerekçesini tehdit etmişti; sistem artık her görüntünün boyutunu kendi kaydında
tutuyor. Üçüncü satır, 2.5.3'teki tekillik kısıtının işlediğini gösteriyor.

Testlerin 10 tanesi otomatik ve her değişiklikten sonra çalıştırılabiliyor. Bu sayı
iskeletin kapsamına göre küçük; ölçüm tarafındaki eşleştirme mantığı için bölüm 1'de
yazılan 14 birim testiyle birlikte okunmalı.

#### 2.5.5 Kısıt: konum verisi yok

**KISIT — veri kümesindeki görüntülerde EXIF/GPS alanları boş geliyor.**

Frame tablosunda enlem, boylam, irtifa ve çekim zamanı için sütunlar var. Bu sütunlar
şu anda dolmuyor. Sebebi, veri kümesini bir dağıtım platformu üzerinden almış olmam:
platform dışa aktarım sırasında görüntüleri yeniden kodluyor ve EXIF üstverisi bu işlem
sırasında düşüyor. Bölüm 1'de aynı platformun çözünürlüğü de sessizce değiştirdiğini
anlatmıştım; bu, aynı kaynaktan gelen ikinci üstveri kaybı.

Bunun pratik sonucu şu: bir tespitin görüntü üzerindeki piksel konumunu biliyorum ama
yeryüzündeki konumunu bilmiyorum. Arama-kurtarma bağlamında operatöre "şu fotoğrafın şu
köşesinde bir şey var" demek ile "şu koordinatta bir şey var" demek arasında büyük fark
var.

Koordinat kaynağı **henüz karara bağlanmadı**. Önümde birden fazla yol var: özgün
HERIDAL dağıtımından üstveriyi almak, uçuş kaydı dosyalarıyla eşleştirmek veya konumu
sistemin girdisi olarak dışarıdan almak. Hangisinin seçileceği bu bölümde
belirlenmedi ve bu yüzden PostGIS yetenekleri kurulu ama kullanılmıyor. Sütunları
şimdiden şemaya koydum, çünkü sonradan sütun eklemek, sonradan veri toplamaktan çok
daha kolay.

---

### 2.6. Süreç dersleri

Bu bölümü kısa tutuyorum ama kısaltmak için sansürlemiyorum. Üç dersin üçü de bu
adımda bana zaman kaybettirdi.

#### 2.6.1 Ders 1 — Bir özelliği, ona ihtiyaç duyan koşudan sonra yazmak

Bölüm 1'de, pahalı bir koşunun ara sonuçlarını saklamamanın maliyetini anlatmıştım:
kaynak bazlı tam ölçüm 2 saat 42 dakika sürmüş, koşu bittikten sonra kaçırılan
kutuların dağılımına bakmak istediğimde veri elimde olmamıştı. Çözüm olarak kutu
bazında kayıt üreten bir özellik yazmıştım.

Bu bölüme başlarken o kaydı kullanmak istedim ve dosya yoktu.

Sebebi şuydu: kaynak bazlı tam koşu saat 14.42'de bitmişti; kutu bazında kayıt özelliği
ise saat 15.05'te, yani **23 dakika sonra** yazılmıştı. Özellik, ona ihtiyaç duyan
koşudan sonra hayata geçmişti. Kod doğruydu, test edilmişti, varsayılan olarak
çalışıyordu — ama üretmesi gereken veriyi üretecek koşu çoktan bitmişti.

Sonuç: 2 saat 42 dakikalık koşuyu ikinci kez çalıştırmak zorunda kaldım.

Bu, aynı hatanın **ikinci kez** yapılması. Birincisinde ara sonuçları hiç saklamamıştım;
ikincisinde saklama kodunu yazmıştım ama zamanlaması yanlıştı. İki durumun ortak yanı,
pahalı hesabın ne üreteceğine hesap **başlamadan önce** karar verilmemiş olması.

**Ders:** Pahalı bir koşuyu başlatmadan önce, o koşudan sonra sorulabilecek soruların
listesi çıkarılmalı ve koşunun çıktısı o listeyi karşılayacak şekilde tasarlanmalı.
Koşu başladıktan sonra yazılan hiçbir kayıt özelliği o koşuya yetişmez.

Bu olayın tek olumlu tarafı, mecburi tekrar koşusunun 2.1'deki tekrar üretilebilirlik
kontrolünü bedavaya getirmesi oldu.

#### 2.6.2 Ders 2 — Negatif sonuç veren bir kontrol, bilinen bir pozitifle sınanmadan güvenilmez

Depoyu herkese açık hale getirmeden önce, geçmişteki hiçbir commit'te parola veya gizli
anahtar kalmadığından emin olmak için bir arama yaptım. Arama hiçbir eşleşme
döndürmedi. İlk tepkim bunu "temiz" olarak okumaktı.

Sonra bir şey dikkatimi çekti: depoda, içinde şablon amaçlı bir parola satırı bulunan
bir örnek yapılandırma dosyası olduğunu biliyordum. Arama onu da bulmalıydı. Bulmamıştı.

Sebep, kullandığım arama deseninin boşluk karakteri için kısayol bir gösterim
içermesiydi; kullandığım arama aracı varsayılan olarak bu kısayolu desteklemeyen bir
düzenli ifade motoruyla çalışıyor. Desen hiçbir zaman eşleşmiyordu — deponun içeriğinden
tamamen bağımsız olarak. Yani arama "sır yok" demiyordu; arama hiçbir şey söylemiyordu.

Deseni destekleyen bir motorla tekrar çalıştırdığımda üç eşleşme çıktı. Üçünü de tek tek
inceledim; üçü de zararsızdı. Sonuç aynıydı ama artık dayanağı vardı.

**Ders:** Bir kontrol negatif sonuç verdiğinde, kontrolün kendisinin çalıştığı ayrıca
gösterilmelidir. Bunun yolu, kontrolün **bulması gerektiğini bildiğim** bir örnekle
sınanması. Sessizlik ile temizlik aynı şey değil; bozuk bir kontrol de sessiz kalır.

Bu ders yalnızca güvenlik taramasına özgü değil. Aynı mantık boş dönen bir veritabanı
sorgusu, hiç uyarı üretmeyen bir doğrulama adımı veya hiç hata yakalamayan bir test
için de geçerli.

#### 2.6.3 Ders 3 — Bir bulguyu ilan etmeden önce karıştırıcı değişken aranmalı

2.3'te anlatılan süreç bu dersin kendisi. Elimde büyük örneklemli, tutarlı ve iki ayrı
gözlemle desteklenen bir ayrışma vardı: dikey kutuların recall'ı yatay kutuların iki
katından fazlaydı. Buna bir açıklama da bulmuştum ve açıklama makuldü.

Eğer bu noktada durup bulguyu ilan etseydim, raporda yanlış bir nedensellik iddiası
bulunacaktı. Üstelik bu iddia sonraki adımları da yönlendirirdi: model eğitimi
tasarlanırken "yatay duruşlu örnekleri artır" gibi bir karar alınabilirdi.

Bulguyu kurtaran şey şu soruydu: *bu iki değişken birbirinden bağımsız mı?* En-boy oranı
ile yükseklik bağımsız değil; dikey kutu tanımı gereği yüksek kutudur. Simetrik
koşullama testi, ayrışmanın büyük kısmının yükseklikten geldiğini gösterdi.

**Ders:** İki değişken arasında güçlü bir ilişki gözlendiğinde, ilişkiyi ilan etmeden
önce "ikisini birden etkileyen üçüncü bir değişken var mı" sorusu sorulmalı. Varsa test
simetrik kurulmalı: her iki değişken sırayla sabitlenip diğerinin etkisine bakılmalı.
Tek yönlü koşullama yanıltıcıdır — 2.3.6'da gösterildiği gibi, testi yalnızca alan
üzerinden yapmış olsaydım yanlış sonuca varırdım.

Bu dersin maliyeti düşük oldu, çünkü gerekli veri zaten kutu bazındaki kayıtta duruyordu
ve ek tarama gerekmedi. Maliyeti düşüren şey, 2.6.1'de anlatılan hatanın telafisi olarak
üretilmiş olan o kayıttı.

---

### 2.7. Ek — Bu bölümde kullanılan ölçüm çıktıları

Bu bölümdeki her sayı aşağıdaki dosyalardan okunmuştur; hiçbiri elle girilmemiş veya
yeniden hesaplanmamıştır. Dosyaların tamamı bölüm 1'in taban çizgisi koşusundan veya
o koşunun ürettiği kutu bazındaki kayıttan türetilmiştir; bu bölümde yeni bir model
taraması yapılmamıştır.

| Dosya | Bu bölümde hangi sayılar | Üreten |
|---|---|---|
| `taban_cizgisi_onek.csv` | 2.1'deki tekrar üretilebilirlik karşılaştırmasının iki tarafı; 2.2.4'teki güven eşiği / yanlış pozitif tablosu | `01_taban_cizgisi.py` |
| `kutu_bazinda_sonuc.csv` | 2.2 ve 2.3'teki bütün analizlerin ham girdisi: her gerçek kutu için boyut, kaynak, eşleşme durumu ve eşleşen tahminin skoru | `01_taban_cizgisi.py` |
| `eslesme_skor_dagilimi.csv` | 2.2.2'deki hiç eşleşmeyen oranları; 2.2.3'teki skor bandı dağılımı | `07_gozlem_analiz.py` |
| `enboy_orani_recall.csv` | 2.3.1'deki koşulsuz oran grubu recall'ları, iki kapsam için | `07_gozlem_analiz.py` |
| `oran_boyut_tabakali.csv` | 2.3.6'daki alan tabakası kontrolü | `08_oran_boyut_kontrol.py` |
| `olcu_karsilastirma.csv` | 2.3.7'deki genişlik ve yükseklik quintile eğrileri | `08_oran_boyut_kontrol.py` |
| `oran_yukseklik_tabakali.csv` | 2.3.4 ve 2.3.5'teki yükseklik tabakası tabloları, iki kapsam için | `09_yukseklik_kontrol.py` |
| `olcu_karsilastirma_genis.csv` | 2.3.7'deki altı ölçünün nokta-çift korelasyonları | `09_yukseklik_kontrol.py` |

*Bu tablo ne söylüyor:* Bu bölümün analitik kısmı tek bir pahalı koşunun üzerine
kuruldu. Kutu bazındaki kayıt bir kez üretildikten sonra, 2.2 ve 2.3'teki bütün
tablolar model çalıştırılmadan, saniyeler içinde türetildi. Tabaka ve çeyrek sınırları
sabit sayılar değil; her biri ilgili kapsamın kendi dağılımından hesaplanıp çıktı
dosyasına yazıldı, böylece bir başkası aynı bölmeyi tekrar kurabilir. Her CSV, sonucun
hangi koşullarda üretildiğini `kosu_` önekli sütunlarda taşır.

---

### 2.8. Sonraki adım

Bu bölümü ikiye ayırıyorum, ama bölüm 1'dekinden farklı bir eksende. Orada ayrım
"açık kalan ölçümler" ile "fiilen kurulacak iş" arasındaydı. Burada ayrım
**gerekçenin nereden geldiği** üzerine: bazı adımların dayanağı bu bölümde ölçüldü,
bazılarının dayanağı ise henüz ölçülmedi. İkisini aynı listede tutmak, ölçülmüş bir
gerekçeyle ölçülmemiş bir sezgiyi eşit ağırlıkta göstermek olurdu.

Ayrım pratik bir işe yarıyor: zaman kısıtlı olduğunda önce (a) listesindeki adımlar
yapılır, çünkü onların ne işe yarayacağı hakkında elimde sayı var.

#### 2.8.1 Ölçüme dayanan adımlar

Aşağıdaki üç adımın gerekçesi bu bölümde ölçüldü.

**1. Karo boyutunu küçültme denemesi (320 ve 256 piksel).** Bölüm 2.3.8'de recall'ı
yöneten değişkenin kutunun piksel cinsinden yüksekliği olduğunu ölçtüm. Karo boyutunu
küçültmek, karonun modelin 640 piksellik girdisine daha büyük oranda büyütülmesi
demek; yani hedefin modelin gördüğü düzlemdeki **etkin yüksekliğini** artırıyor. Şu
anda 512 piksellik karo 640'a büyütülüyor. 320 piksellik karo iki kat, 256 piksellik
karo iki buçuk kat büyütülür. Bu, ölçülen açığa doğrudan müdahale: yüksekliği kutunun
kendisinde değiştiremem ama modelin gördüğü ölçekte değiştirebilirim. Bedeli karo
sayısının ve dolayısıyla koşu süresinin artması; bu değiş tokuş ölçülmeli.

**2. Recall'ın yükseklik beştebirlerine göre raporlanması.** Bölüm 2.3.7'deki quintile
eğrisi, yükseklik beştebirleri arasında recall'ın 0,1123'ten 0,5584'e çıktığını
gösteriyor. Tek bir toplam recall sayısı (veri kümesinin tamamında 0,3160) bu
dağılımın ortalamasıdır ve açığın nerede olduğunu gizler. En kısa beştebirde her on
kişiden yaklaşık birini buluyorum; bu sayı toplam içinde görünmüyor. Bundan sonraki
değerlendirmelerde recall tek bir sayı olarak değil, yükseklik beştebirleri kırılımıyla
raporlanmalı. Aksi halde bir müdahalenin hangi hedef boyutunda işe yaradığı
anlaşılamaz.

**3. B türü kaynaklar için eşik ayarı değil, eğitim.** Bölüm 2.2.2'de, güven eşiği
ölçtüğüm en düşük değere (0,05) indirildiğinde bile B türü kaynaklardaki 101 kutunun
**64'ünün** hiçbir adayla eşleşmediğini ölçtüm. Bu, eşik ayarıyla kapatılabilecek bir
açık değil: sıralanacak aday üretilmiyor. Bölüm 2.2.4 aynı eşik indirimi için
görüntü başına yanlış alarmın 0,89'dan 13,54'e çıktığını gösteriyor; yani eşik ayarı
hem etkisiz hem pahalı. Bu kaynaklar için yol, veri kümesine özgü eğitimden geçiyor.

#### 2.8.2 Gerekçesi henüz ölçülmemiş adımlar

Aşağıdaki üç adım denenebilir, ancak **bu bölümdeki ölçümler onları desteklemiyor**.
Buraya koymamın sebebi, akla gelmiş olmaları ve ileride ölçülebilir hale
gelebilecekleri; şu an gerekçeleri yok.

**1. Döndürme artırımı (rotation augmentation).** Bölüm 2.3.2'de en-boy oranı
ayrışmasını "model ayakta duran insan önseline sahip" diye yorumlamıştım; bu yorum
doğru olsaydı, eğitim verisini döndürerek çoğaltmak makul bir müdahale olurdu. Ancak
bölüm 2.3.5'teki koşullu analizde bu gerekçe zayıfladı: yükseklik sabitlendiğinde oran
etkisi tabakaların çoğunda çöktü. Üstelik uzun yükseklik tabakasında yatay kutuların
recall'ı 0,5312 ile kare benzerlerinkinin (0,4263) üzerinde; yani yatay kutular o
tabakada zaten bulunuyor. Döndürme artırımının çözeceği varsayılan problem, ölçtüğüm
yerde görünmüyor.

**2. Yanlış pozitiflerin insan yapısı nesnelere yakınlığının ölçülmesi.** Yanlış
alarmların bir kısmının bina, araç veya yol gibi insan yapısı nesnelerin çevresinde
yoğunlaştığına dair bir izlenimim var. Bu izlenim şu anda **iki görsellik bir
gözleme** dayanıyor; sayısı yok, sistematik değil ve bu bölümde ölçülmedi. Ölçülebilir
hale gelmesi için yanlış pozitif konumlarının bu tür nesnelere uzaklığının
hesaplanması gerekir, bu da o nesnelerin etiketlenmiş olmasını gerektirir. Elimde
böyle bir etiket yok.

**3. Arka plan doku karmaşıklığının ölçülmesi.** Bölüm 1'de B türü sapmanın düşük
kontrasttan gelebileceği hipotezi ölçülüp çürütülmüştü. Geriye kalan adaylardan biri
arka planın doku karmaşıklığı: kutunun çevresindeki yerel varyans ve kenar yoğunluğu.
Bu ölçüm bu bölümde yapılmadı. B türü kaçırmaların üretim problemi olduğunu 2.2.2'de
ölçtüm, ancak **neden** üretilmediğine dair bir ölçüm hâlâ yok; doku karmaşıklığı bu
sorunun aday cevaplarından yalnızca biri ve şu an diğerlerinden daha güçlü bir
dayanağı yok.

#### 2.8.3 Bu bölümde kapatılmayan sorular

Aşağıdaki üç soru bu bölümde açıldı veya açık kaldı; hiçbiri cevaplanmadı.

**1. Orta yükseklik tabakasındaki oran farkı.** Bölüm 2.3.8'de açık soru olarak
yazıldı. Oran etkisi kısa ve uzun yükseklik tabakalarında çökerken orta tabakada
korunuyor: veri kümesinin tamamında +0,2266, ZRI hariç kapsamda +0,3150. Bu
tabakanın hücreleri örneklem bakımından zayıf değil, yani düzensizliği gürültüye
bağlayamıyorum. Açıklaması yok.

**2. Koordinat kaynağı kararı.** Bölüm 2.5.5'te kısıt olarak yazıldı. Veri
kümesindeki görüntülerde EXIF/GPS alanları boş geldiği için tespitlerin yeryüzü
konumu bilinmiyor. Veritabanı şemasında sütunlar hazır ve PostGIS kurulu, ancak
konumun nereden geleceği bu bölümde karara bağlanmadı.

**3. CAB etiket denetiminin kapsamı.** Bölüm 2.4'te sınır olarak yazıldı. Denetim tek
görselde tek nesneyle sınırlı kaldı; CAB'deki 34 kutunun %3'ünden azı incelendi.
Etiket kalitesinin recall'a katkısı ölçülmedi ve bu katkının büyüklüğüne dair elimde
hiçbir sayı yok.
