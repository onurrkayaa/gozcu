## 5. ONNX Dağıtımı ve Gerçek Hat Doğrulaması

*(bu bölümde önceki bölümden kalan üç veri sorusunu ölçüyor, eğitilmiş modeli ONNX biçimine aktarıp iki motorun eşdeğerliğini sınıyor, modeli gerçek görev hattında çalıştırıp süresini ve hata dayanıklılığını ölçüyor ve bulduğum bir kod kusurunu tek değişkenli bir deneyle düzeltiyorum)*

### 5.1. Bu bölümün sorusu

Önceki bölümün sonunda elimde eğitilmiş bir ağırlık vardı. Model-512, tabanla aynı yanlış
pozitif bütçesinde (görüntü başına ≤ 1,81) conf 0,53'te recall 0,6825 ve FP/görüntü 1,75
veriyordu; taban aynı bütçede recall 0,3804'te kalıyordu. Bu sayılar `scripts/13`'ün
ürettiği eşik taramasından okunur.

O bölüm bir soruyu cevapladı: model, kendi verimizle eğitildiğinde eşit yanlış alarm
yükünde daha çok hedef buluyor mu? Cevap evetti. Ama o cevabın verildiği yer bir ölçüm
script'iydi. Modelin bir dosya olarak var olması ile bir sistemin içinde çalışması aynı
şey değildir.

Bu bölümde yeni bir doğruluk kazanımı aramıyorum. Model ağırlığı değişmiyor, eğitim
tekrarlanmıyor, eşikler oynatılmıyor. Sorduğum soru şu:

> Kendi verimizle eğitilen model, dağıtılabilir bir biçimde, gerçek görev hattında,
> ölçülebilir ve hata karşısında dayanıklı biçimde çalışıyor mu?

Bu soru tek parça değil. Dört ayrı kapıya ayrılır ve her kapı ayrı ölçülür:

- **Dışa aktarım kapısı.** Ağırlık, çalışma zamanında PyTorch gerektirmeyen bir biçime
  çevrilebiliyor mu ve çıkan dosyanın kimliği kayıt altında mı?
- **Eşdeğerlik kapısı.** Aynı görüntülerde, aynı protokolde, yalnızca çıkarım motorunu
  değiştirdiğimde ölçülen metrikler aynı kalıyor mu?
- **Hat kapısı.** Model, sahte dedektörün yerine gerçek görev kuyruğuna takıldığında
  bütün kareler sonuçlanıyor mu ve süresi ne?
- **Dayanıklılık kapısı.** İşçi süreci iş ortasında öldürüldüğünde kare kayboluyor mu,
  iş yeniden teslim ediliyor mu, tespitler ikiye katlanıyor mu?

Bir noktayı baştan söylemek gerekir: **ONNX dosyasının oluşması tek başına hiçbir şeyin
kanıtı değildir.** Dosya oluşur, açılır, hatta bir şeyler de üretir; ama ürettiğinin
eğitilen modelin ürettiğiyle aynı olduğunu göstermek ayrı bir ölçümdür. Bu bölümün
ağırlığı o ölçümdedir.

Bölüme, önceki bölüm kapanırken açık bıraktığım üç veri sorusuyla başlıyorum; onlar
modelin değil, verinin ve eğitim kümesinin sorularıdır.

### 5.2. Önceki bölümden kalan veri soruları

#### 5.2.1. Kaynak öneki kesişimi ve dosya çakışması

Önceki bölümde şunu yazmıştım: test bölümünün neredeyse tamamı ZRI kaynağından geliyor ve
ZRI eğitim verisinde de var; ama bunun sayısal dökümünü çıkarmamıştım. `scripts/14` bu
dökümü iki ayrı ölçüm olarak üretir ve sonuçları `egitim_test_onek_kesisimi.csv` ile
`egitim_test_hash_kontrolu.csv` dosyalarına yazar.

Kaynak öneki, dosya adının ikinci parçasıdır (`train_ZRI_3035_...` → ZRI) ve görüntünün
hangi çekim kümesinden geldiğini söyler. Tüm veride 17 önek var.

| Önek | Train görüntü | Train hedef | Valid görüntü | Valid hedef | Test görüntü | Test hedef |
|---|---|---|---|---|---|---|
| ZRI | 34 | 319 | 5 | 39 | 87 | 939 |
| VRD | 253 | 164 | 17 | 10 | 70 | 31 |

*Bu tablo ne söylüyor:* Test bölümünde yalnızca iki kaynak var ve ikisi de eğitim
verisinde bulunuyor. Testteki 970 hedefin 939'u, yani neredeyse tamamı ZRI'dir. ZRI
eğitim tarafında da 34 görüntü ve 319 hedefle temsil edilmiştir. Diğer 15 önek test
bölümünde hiç geçmez. Sayılar `scripts/14`'ün ürettiği `egitim_test_onek_kesisimi.csv`
dosyasından okunur.

Bunun adı **KISIT**'tır: model, test ettiğim araziye eğitim sırasında da bakmıştır. Buna
kaynak aşinalığı diyorum. Kaynak aşinalığı, ölçülen recall'ın "hiç görülmemiş bir arazide"
geçerli olduğunu söylememi engeller.

Ama bu, aynı görüntünün iki bölümde birden bulunduğu anlamına **gelmez**. Ortak önek
"aynı kamera, aynı arazi, benzer koşullar" demektir; "aynı dosya" demek değildir. Bu ikisi
karıştırıldığında ortaya asılsız bir sızıntı iddiası ya da asılsız bir temizlik iddiası
çıkar. Ayırmanın tek yolu dosyaların kendisine bakmaktır.

Bunun için her görüntünün **baytlarından** SHA-256 özetini hesapladım. Dosya adından ya da
yolundan değil; içerikten. Aynı görüntü farklı adla iki bölümde bulunuyorsa bu yöntem onu
yakalar.

| Ölçüm | Sonuç |
|---|---|
| Toplam görüntü (train + valid + test) | 1579 |
| Benzersiz SHA-256 | 1579 |
| Train–test ortak hash | 0 |
| Train–valid ortak hash | 0 |
| Valid–test ortak hash | 0 |

*Bu tablo ne söylüyor:* 1579 görüntünün 1579'u birbirinden farklı; hiçbir bölüm çifti
ortak bir dosya paylaşmıyor. `egitim_test_hash_kontrolu.csv` bütün benzersiz hash'leri
satır satır tutar, yalnızca çakışanları değil — böylece sonuç sonradan denetlenebilir.
Bu bir **BULGU**'dur: incelenen dosyalarda birebir görüntü kopyası yok.

İddianın sınırı burada biter. Hash kontrolü yalnızca **birebir aynı dosyayı** yakalar.
Yeniden sıkıştırılmış, kırpılmış, döndürülmüş veya aynı sahnenin bir saniye sonra çekilmiş
karesi olan bir görüntü farklı bir hash verir ve bu ölçümde görünmez. Dolayısıyla
"her tür veri sızıntısı imkânsızdır" diyemem; diyebileceğim şey, aynı dosyanın iki
bölümde birden bulunmadığıdır.

İki ölçümü bir arada okumak gerekir: **dosya düzeyinde sızıntı yok, kaynak düzeyinde
aşinalık var.** Recall sayıları bu ikinci cümlenin gölgesinde okunmalıdır.

#### 5.2.2. ≥ 80 px bandı ve %60 kenar kuralı

Önceki bölümde bir gözlem vardı: eğitim, en büyük kazancı küçük hedeflerde veriyor ve
kazanım hedef büyüdükçe azalıyordu; ≥ 80 px bandı en düşük kazanımı gösteriyordu. Bunu
açıklamak için bir hipotez kurmuştum: eğitim verisini hazırlarken kullandığım %60
min-görünür kuralı büyük hedefleri daha çok eziyor olabilir.

Kural şu: bir hedef bir karonun içine alanının en az %60'ıyla giriyorsa o karoda etiket
olarak yazılır; girmiyorsa o karoda atlanır. Hedef silinmiş olmaz — başka bir karoda bütün
kalabilir. Büyük bir kutu karo sınırına daha kolay taşar, dolayısıyla kuraldan daha çok
etkilenmesi beklenir.

`scripts/15` bunu eğitim verisi tarafında ölçer. Karolama geometrisi yeniden yazılmaz;
karo koordinatları çıkarım tarafındaki `karolari_hesapla` işlevinden, %60 kararı ise
eğitim kümesini üreten script'in kendi hesabından gelir. Ölçüm yalnızca train ve valid
bölümlerini kapsar, karo 512'dir ve hiçbir karo diske yazılmaz. Bant sınırları
`yukseklik_kazanim.csv` dosyasındaki mevcut sınırlardan okunur, ikinci kez tanımlanmaz.

| Yükseklik bandı | Benzersiz hedef | En az bir kez etkilenen | Etkilenen oranı | Hedef başına geçerli karo-etiket | Tamamen kaybolan |
|---|---|---|---|---|---|
| < 44 px | 505 | 105 | 0,2079 | 1,5307 | 0 |
| 44–55 px | 465 | 119 | 0,2559 | 1,5914 | 0 |
| 55–65 px | 363 | 122 | 0,3361 | 1,6088 | 0 |
| 65–80 px | 361 | 113 | 0,3130 | 1,6094 | 0 |
| ≥ 80 px | 409 | 178 | 0,4352 | 1,5868 | 0 |
| TOPLAM | 2103 | 637 | 0,3029 | 1,5820 | 0 |

*Bu tablo ne söylüyor:* ≥ 80 px bandı iki metrikte birden en olumsuz durumda. Etkilenen
hedef oranı 0,4352 ile bütün bantların en yükseği ve bir önceki bandın (65–80 px, 0,3130)
belirgin biçimde üzerinde. Hedef başına geçerli karo-etiket sayısı ise 1,5868 ile bir
önceki bandın altında (1,6094). Yani ≥ 80 px hedefleri hem daha sık kenar kuralına
takılıyor hem de eğitim kümesine daha az örnekle giriyor. Son sütun da önemli: hiçbir
bantta bir hedef bütün karolarda birden elenmiş değil — örtüşme payı bu işi yapıyor.
Sayılar `scripts/15`'in ürettiği `kenar_kurali_yukseklik.csv` dosyasından okunur.

Bu sonuç **HİPOTEZ** etiketiyle kalır. Ölçtüğüm şey eğitim verisinin davranışıdır: ≥ 80 px
hedefleri kenar kuralından daha çok etkileniyor ve bu, recall düşüşüyle aynı yöndedir.
Ölçmediğim şey nedenselliktir. Eğitim örneği azaldığı için mi recall düşüyor, yoksa büyük
hedeflerde başka bir şey mi oluyor — bunu ayırmak için kuralı değiştirip modeli yeniden
eğitmek ve test recall'ını yeniden ölçmek gerekir. O deney yapılmadı. Eğitimdeki etkilenme
ile testteki recall arasında doğrudan sebep-sonuç kurmuyorum.

Bir ayrıntı da ölçümün kendi doğrulamasındadır: `scripts/15`, ürettiği toplamları eğitim
kümesini gerçekten üreten koşunun kaydıyla karşılaştırır — benzersiz hedef 2103, geçerli
karo-etiket 3327, atlanan hedef örneği 964, tamamen kaybolan hedef 0. Dördü de uyuşmasaydı
script CSV yazmadan duracaktı.

#### 5.2.3. Adım sabitlenerek karo boyutu deneyi

Önceki bölümde karo 320 ve karo 512 kümelerini karşılaştırırken bir sorun vardı: bu iki
koşulda yalnızca karo boyutu değil, karolar arası adım da farklıydı. Adım değişince
görüntü başına düşen karo sayısı ve kenar yoğunluğu da değişir; iki değişken birbirine
karışır.

`scripts/16` bu karışıklığı kaldırır. Karo 320 / örtüşme 0,25 ile karo 512 /
örtüşme 0,53125 seçilir; iki koşulda da adım aynı çıkar. Adım, mevcut karolama kodunun
ürettiği ardışık karolar arasındaki mesafeden geri okunur, ayrı bir formülle
hesaplanmaz — ikisi de **240 piksel**.

| Ölçü | Karo 320 / 0,25 | Karo 512 / 0,53125 |
|---|---|---|
| Adım | 240 px | 240 px |
| Benzersiz hedef | 2103 | 2103 |
| Planlanan toplam karo | 314.058 | 272.832 |
| Belirsiz karo | 1578 | 2032 |
| En az bir belirsiz karoya düşen benzersiz hedef | 974 | 851 |
| Belirsize düşen hedef oranı | 0,4631 | 0,4047 |
| Hedef başına geçerli karo-etiket | 1,6928 | 4,1959 |
| Tamamen kaybolan hedef | 0 | 0 |

*Bu tablo ne söylüyor:* Karo 512 koşulunda ham belirsiz karo sayısı daha yüksek (2032'ye
karşı 1578), ama benzersiz hedef düzeyinde tablo tersine dönüyor: belirsiz karoya düşen
hedef oranı karo 320'de 0,4631, karo 512'de 0,4047. Hedef başına geçerli karo-etiket de
karo 512'de belirgin biçimde daha yüksek (4,1959'a karşı 1,6928), çünkü büyük karo aynı
hedefi daha çok karoda bütün görüyor. İki metrikte de karo 320 daha fazla etkileniyor.
Sayılar `scripts/16`'nın ürettiği `adim_sabit_karsilastirma.csv` dosyasından okunur.

Burada bir metrik dersi var. Ham belirsiz karo sayısı tek başına mekanizma kanıtı
değildir: karo sayısı karo boyutuyla mekanik olarak değişir, iki koşulda planlanan toplam
karo zaten 314.058'e karşı 272.832'dir. Doğru soru "kaç karo belirsiz" değil, "kaç
**benzersiz hedef** belirsiz karoya düşüyor"dur. Bu metriği önceki bölümde tanımlamış ama
ölçmemiştim; burada ölçtüm.

Sonucun kapsamı dardır ve bunu açıkça yazmak gerekir. Ölçülen şey **eğitim verisi üretme
davranışıdır**: hangi koşul kaç hedefi belirsiz karoya düşürüyor, hedef başına kaç etiket
üretiyor. Ölçülmeyen şey model başarısıdır. Bu deneyde hiçbir model eğitilmedi, hiçbir
recall hesaplanmadı. "Hangi karo boyutu daha iyi model verir?" sorusu bu tabloyla
cevaplanamaz; cevaplamak için iki koşulda da eğitim yapıp aynı protokolde ölçmek gerekir.
Karo 512 / örtüşme 0,53125 satırı da yeni bir sayımdır — eğitimde kullanılan karo 512 /
örtüşme 0,20 kümesinin sonucu değildir.

### 5.3. Model-512'nin ONNX'e aktarılması

ONNX, model grafiğini çerçeveden bağımsız bir dosyada tutan bir değişim biçimidir. Amaç
şuydu: çalışma zamanında PyTorch ve Ultralytics kurulu olmasın, servis yalnızca bir
çalıştırıcıyla modeli çalıştırabilsin.

Dışa aktarımı `scripts/17` yapar ve tek satırlık bir kimlik kaydı üretir. Script önce
kaynağı doğrular: `agirliklar/model512_best.pt` dosyasının boyutunu ve SHA-256 özetini
diskten hesaplar, sonra Kaggle eğitim çıktısındaki özgün `best.pt` ile karşılaştırır.
İkisi **UYUŞTU**; yani dışa aktarılan ağırlık, eğitim koşusunun ürettiği dosyanın ta
kendisidir. Uyuşmasaydı export hiç çalışmayacaktı.

Giriş boyutu da tahmin edilmez: eğitim koşusunun `args.yaml` kaydından okunur ve 512
çıkar. Bu, rapordan veya hatırlanan bir değerden değil, eğitimin kendi kaydından gelir.

| Alan | Değer |
|---|---|
| Kaynak ağırlık | 5.463.834 bayt, SHA-256 `66a93278a16e1cf7…` |
| Özgün `best.pt` ile eşleşme | UYUŞTU |
| ONNX dosyası | 10.544.114 bayt, SHA-256 `361731351703f458…` |
| Opset | 18 |
| Girdi | `images`, 1x3x512x512, FLOAT |
| Çıktı | `output0`, 1x5x5376, FLOAT |
| Sınıf eşlemesi | `0: human` |
| `onnx.checker` | GEÇTİ |
| Export ayarları | imgsz 512, batch 1, dynamic False, simplify True, half False, device cpu |

*Bu tablo ne söylüyor:* Dosya oluştu, boş değil, açıldı ve yapısal denetimden geçti.
Girdi şekli sabit: model tek bir 512×512 karo bekliyor. Çıktı 5376 aday kutu taşıyor ve
her aday için 5 değer var (dört koordinat ve bir skor) — tek sınıflı bir model olduğu için
sınıf olasılığı tek sütundur. Sınıf eşlemesi `human`; yani dosyanın içindeki etiket, eğitim
verisindeki etiketle aynı. Bütün bu alanlar `scripts/17`'nin ürettiği
`model512_onnx_bilgisi.csv` dosyasından okunur.

Şekil kararı bilinçlidir. `dynamic False` verildiği için grafik sabit 1x3x512x512 girdiyle
üretildi. Dinamik şekil, değişken boyutlu görüntüleri tek grafikle işlemeyi sağlar; ama bu
projede çıkarım zaten sabit boyutlu karolar üzerinde yapılıyor ve sabit şekil, çalışma
zamanında hangi girdinin beklendiğini belirsiz bırakmıyor. Opset değeri de tahmin edilmez:
kurulu kütüphanenin bu Torch sürümü için seçtiği değer koda sorularak alınır, dışa
aktarımdan sonra da oluşan grafikten geri okunur.

Doğrulama bilinçli olarak **yapısaldır**: dosya var mı, boş mu, açılıyor mu, denetleyici
geçiyor mu, opset okunuyor mu, girdi-çıktı adları ve türleri okunuyor mu. Bu adımda ONNX
üzerinde hiçbir tahmin çalıştırılmadı. Sebebi basit: "dosya çalışıyor" ile "dosya doğru
sonucu veriyor" farklı iddialardır ve ikincisi bir sonraki başlığın konusudur.

ONNX dosyası depoya girmez. Sebebi boyutu (10,5 MB) ve ikili bir yapı olması; ağırlık
dosyaları zaten depo dışında tutuluyor. Bunun bedeli, dosyanın kaybolması hâlinde geri
getirilebilmesidir; onu da üç kayıt birlikte sağlar: dışa aktarımı yapan script, çıkan
dosyanın CSV'ye yazılmış SHA-256 özeti ve kaynak ağırlığın kendi özeti. Aynı script aynı
kaynakla çalıştırıldığında üretilen dosyanın kimliği bu kayıtla karşılaştırılabilir.
Nitekim sonraki bütün ölçümler işe bu karşılaştırmayla başlar: özet uyuşmazsa ölçüm hiç
başlamaz.

Son bir uyarı: bu başlıktaki hiçbir sayı hız ya da doğruluk kanıtı değildir. Dosya
boyutunun `.pt` dosyasının iki katı olması da bir performans bilgisi taşımaz.

### 5.4. PyTorch ile ONNX eşdeğerliği

Asıl soru şuydu: aynı görüntülerde, aynı protokolde, yalnızca çıkarım motorunu
değiştirirsem sonuç değişiyor mu?

Bu deneyin tek değişkenli olması için geri kalan her şeyin aynı kalması gerekiyordu:
görüntü kümesi ve sırası, karo boyutu ve örtüşme, karolar arası birleştirme, koordinat
taşıma, IoU eşiği, gerçek kutu eşleştirmesi ve metrik hesabı. `scripts/18` bunu şöyle
sağlar: PyTorch tarafı mevcut ölçüm yolunu olduğu gibi kullanır, ONNX tarafı ise karolamayı
ve karolar arası son işlemi aynı kütüphaneye bırakır, yalnızca karo başına çıkarımı
değiştirir. Protokol değerleri de script'e yazılmaz; eğitilmiş modelin mevcut ölçüm
CSV'sinin koşu sütunlarından okunur — karo 512, örtüşme 0,20, IoU 0,30, cihaz CPU,
eşikler 0,05 / 0,15 / 0,30.

Bir tasarım kararı burada önemlidir. ONNX tarafında hazır bir sarmalayıcı yerine servisin
kendi çalıştırıcısını ölçtüm. Sebebi, bir sonraki başlıkta kuyruğa bağlanacak motorun tam
olarak bu olmasıdır; ölçümde başka, üretimde başka bir yol kullanmak eşdeğerlik iddiasını
boşa çıkarırdı.

Doğrulama iki katmanlıdır. Birinci katman operasyonel metriklerdir.

| conf | Motor | TP | FN | FP | Recall | FP/görüntü | Precision |
|---|---|---|---|---|---|---|---|
| 0,05 | PyTorch | 902 | 68 | 2134 | 0,9299 | 13,59 | 0,2971 |
| 0,05 | ONNX | 902 | 68 | 2134 | 0,9299 | 13,59 | 0,2971 |
| 0,15 | PyTorch | 859 | 111 | 1110 | 0,8856 | 7,07 | 0,4363 |
| 0,15 | ONNX | 859 | 111 | 1110 | 0,8856 | 7,07 | 0,4363 |
| 0,30 | PyTorch | 788 | 182 | 617 | 0,8124 | 3,93 | 0,5609 |
| 0,30 | ONNX | 788 | 182 | 617 | 0,8124 | 3,93 | 0,5609 |

*Bu tablo ne söylüyor:* Ölçülen üç eşiğin hepsinde iki motorun bütün metrikleri birebir
aynı. `scripts/18`'in ürettiği `pytorch_onnx_metrik.csv` dosyasında ayrıca fark sütunları
da tutulur ve hepsi sıfırdır. Yani eşik nereye konursa konsun, iki motor aynı sayıda hedefi
buluyor, aynı sayıda hedefi kaçırıyor ve aynı sayıda yanlış kutu üretiyor.

İkinci katman tahmin düzeyidir. Metrikler eşit çıksa bile alttaki kutular kaymış olabilir;
bunu görmek için iki motorun tahminlerini görüntü görüntü eşleştirdim.

| Ölçü | Değer |
|---|---|
| Eşleşen tahmin | 3036 |
| Yalnız PyTorch'ta bulunan | 0 |
| Yalnız ONNX'te bulunan | 0 |
| En büyük skor farkı | 2,29e-06 |
| En büyük koordinat farkı | 0,000244 piksel |

*Bu tablo ne söylüyor:* Taban eşikte üretilen 3036 tahminin tamamı karşı tarafta bir
eşleşme buluyor; tek bir motorda görülüp diğerinde görülmeyen tahmin yok. Skorlar
milyonda iki mertebesinde, koordinatlar ise pikselin on binde ikisi mertebesinde farklı.
Sayılar `pytorch_onnx_fark.csv` dosyasından okunur.

Doğru sonuç şudur: **ölçülen metriklerde eşdeğerlik var, sayısal farklar ise küçük ama
sıfır değil.** Bu yüzden "iki motor bit düzeyinde aynı sonucu veriyor" demiyorum; öyle bir
şey ölçülmedi ve yukarıdaki iki fark değeri zaten bunun aksini gösteriyor. Söylenebilecek
olan, bu farkların üç ölçülmüş eşikte hiçbir metriği değiştirmediğidir.

Bir denetim noktası daha var. Böyle bir karşılaştırmada en kolay hata, sonucu gördükten
sonra toleransı gevşetip "yeterince yakın" demektir. Burada gevşetilecek bir tolerans
yoktur: karşılaştırma tam eşitlik üzerinden yapılır, fark sütunları CSV'ye ham hâliyle
yazılır ve tek bir metrik bile ayrılsaydı script kapıyı kapatıp duracaktı. Deneyin ayrıca
bir ön koşulu vardır: PyTorch tarafının yeni koşusu, eğitilmiş modelin mevcut ölçüm
CSV'sindeki sayıları yeniden üretmelidir. 24 alanın hepsi uyuştu; uyuşmasaydı ONNX sonucu
hiç yorumlanmayacaktı.

### 5.5. Modelin gerçek görev hattına alınması

İkinci haftada kurduğum hat şuydu: görüntü yüklenir, kare kaydı oluşur, tarama başlatılır,
görev kuyruğa girer, işçi süreci kareyi karolar ve tespitleri veritabanına yazar. O
haftada gerçek model yoktu; hattın doğruluğunu sahte bir dedektörle sınamıştım.

Bu bölümde sahte dedektörün yerini gerçek model aldı. Seçim açık bir veriye dayanır: model
sürümü kaydındaki çerçeve alanı. Alan `onnx` ise gerçek dedektör kurulur, `fake` ise sahte
dedektör kullanılmaya devam eder. Sahte dedektör silinmedi; testlerde hâlâ kullanılıyor.

Üç davranış kuralını baştan koydum:

- **Model yolu koda gömülmez.** Yol ayardan, ayar da ortam değişkeninden gelir; ağırlık
  dosyası depoda olmadığı için konteyner içindeki yeri host'takinden farklıdır.
- **Oturum karo başına yeniden kurulmaz.** Çalıştırıcı oturumu süreç başına bir kez
  açılır ve kareler arasında yeniden kullanılır.
- **Model yüklenemezse sessizce sahte dedektöre düşülmez.** Hata yükselir ve kare, mevcut
  durum makinesine göre başarısız işaretlenir. Bunun tersi, model bozukken sistemin
  çalışıyor görünmesi olurdu.

Ölçüm koşusunda 157 test görüntüsü yeni ve ayrı bir göreve alındı; görev adı
`olcum-onnx-sure-20260912-142859`. Görev fonksiyonu doğrudan çağrılmadı: kayıtlar arayüzün
kullandığı yolun aynısıyla oluşturuldu, koşu gerçek kuyruğa bırakıldı ve işi çalışan işçi
yaptı. Ölçülen şey bu yüzden gerçek kuyruk davranışıdır.

| Kontrol | Sonuç |
|---|---|
| Test görüntüsü = Frame sayısı | 157 = 157 |
| Frame son durumları | 157 done, 0 failed, 0 takılı |
| Kullanılan çerçeve | `onnx` (sahte dedektör çalışmadı) |
| Model SHA-256 | dışa aktarım kaydıyla aynı |
| Toplam Detection (veritabanı = CSV) | 2450 = 2450 |
| İşçi süreci | 2 |
| Soğuk başlangıç | 2 kare |
| Aynı oturumla işlenen en çok kare | 79 |

*Bu tablo ne söylüyor:* Bütün kareler sonuçlandı, hiçbiri yarıda kalmadı ve tespit sayısı
veritabanıyla ölçüm dosyası arasında birebir tutuyor. Soğuk başlangıç sayısının 2 olması,
çalıştırıcı oturumunun süreç başına yalnızca bir kez kurulduğunu gösterir: iki işçi süreci
var, iki oturum açıldı ve bir süreç aynı oturumla 79 kareyi işledi. Kontroller
`scripts/19` tarafından yapılır; biri bile geçmeseydi script CSV yazmadan dururdu.

Aşama sürelerini ölçebilmek için görevin içine zamanlama noktaları ekledim. Bu ölçüm bir
ayarla açılıp kapanır ve kapalıyken tek bir ayar okumasına iner; açıkken kare başına tek
bir satır yazılır, karo başına değil. Ölçtüğü aşamalar: kuyrukta bekleme, görüntü okuma,
karo planlama, çıkarım, karolar arası birleştirme ve koordinat taşıma, veritabanına yazma,
karenin toplam işlenme süresi ve görevin uçtan uca süresi.

Bir ayrımı baştan yapmak gerekir: **kuyrukta bekleme, karenin çalışma süresi değildir.**
Bütün kareler tek seferde kuyruğa girdiği için sondaki kareler sırasını uzun süre bekler;
bu süre işçinin meşguliyetini gösterir, modelin hızını değil. Aşağıdaki tabloda bu yüzden
ayrı tutuluyor ve zaman aşımı kararında hiç kullanılmıyor.

### 5.6. Gerçek süre ve zaman aşımı kararı

| Aşama (saniye) | min | medyan | p95 | maks |
|---|---|---|---|---|
| Görüntü okuma | 7,2005 | 10,1187 | 15,1177 | 19,5873 |
| Karo planlama | 0,0000 | 0,0001 | 0,0001 | 0,1640 |
| ONNX çıkarım | 6,3205 | 9,3633 | 12,5423 | 18,0256 |
| NMS ve koordinat | 0,2946 | 0,3895 | 0,4907 | 0,5730 |
| Veritabanına yazma | 0,0054 | 0,0173 | 0,0402 | 0,0559 |
| Kare toplam | 14,8069 | 19,8840 | 28,2916 | 37,3691 |
| Uçtan uca görev | 14,8069 | 19,8840 | 28,2917 | 37,3692 |

*Bu tablo ne söylüyor:* Bir karenin işlenmesi medyanda 19,88 saniye sürüyor ve bu sürenin
neredeyse tamamı iki aşamadan geliyor: görüntü okuma (medyan 10,12 sn) ve çıkarım
(medyan 9,36 sn). Karo planlama, birleştirme ve veritabanı yazma toplamda yarım saniyenin
altında kalıyor; yani veritabanı bu hatta darboğaz değil. Görüntü okumanın çıkarımla aynı
büyüklük sınıfında çıkması beklediğim bir sonuç değildi ve 5.8'in konusu oldu. Sayılar
`scripts/19`'un ürettiği `gercek_onnx_celery_sure_ozet.csv` dosyasından okunur; ham kare
kayıtları `gercek_onnx_celery_sure.csv` dosyasındadır.

| Ayrı tutulan ölçü (saniye) | min | medyan | p95 | maks |
|---|---|---|---|---|
| Kuyrukta bekleme | 0,2179 | 845,4332 | 1545,7425 | 1620,7126 |

*Bu tablo ne söylüyor:* Kuyrukta bekleme medyanda 845 saniye, yani kare toplam süresinin
kırk katından fazla. Bu sayı modelin yavaşlığını değil, 157 karenin iki işçiyle sırayla
işlenmesini anlatır: sıranın sonundaki kare, kendinden öncekiler bitene kadar bekler.
Bu yüzden aşağıdaki zaman aşımı hesabına katılmıyor.

Zaman aşımı tarafında üç ayar var: görevin nazikçe sonlandırılmasını isteyen yumuşak
sınır, süreci kesen sert sınır ve onaylanmamış bir mesajın yeniden dağıtılması için
beklenen süre. İkinci haftada bu değerleri makul tahminlerle koymuştum; artık gerçek
ölçüm var.

Kararın dayandığı ölçüm, **soğuk başlangıç dâhil en yavaş görev**: 37,3692 saniye.
Buradan sonrası ölçüm değil **KARAR**'dır ve ayrımı korumak gerekir. Seçtiğim kural şu:
ölçülen en yavaş göreve on kat pay, yumuşak sınırın üstüne temiz kapanma için 60 saniye,
yeniden dağıtım süresine de sert sınırın 1,5 katı. Bu çarpanlar ölçülmedi; geçici makine
yükü, daha yavaş bir kare ve kapanma payı düşünülerek seçildi. Ölçüm dosyasında da bu
alan "karar (ölçüm değil)" olarak işaretlidir.

| Ayar | Kuralın gerektirdiği en az | Mevcut değer | Sonuç |
|---|---|---|---|
| Yumuşak sınır | 374 sn | 600 sn | yeterli |
| Sert sınır | 434 sn | 660 sn | yeterli |
| Yeniden dağıtım süresi | 651 sn | 900 sn | yeterli |

*Bu tablo ne söylüyor:* Mevcut değerlerin üçü de kuralın gerektirdiği alt sınırların
üzerinde ve aralarındaki sıralama korunuyor: yumuşak sınır (600) < sert sınır (660) <
yeniden dağıtım süresi (900). Sıralama önemlidir; yeniden dağıtım süresi sert sınırdan
kısa olsaydı, hâlâ çalışan bir görev "ölmüş" sayılıp ikinci kez dağıtılabilirdi. Karar
bu yüzden **KORUNDU**: hiçbir ayar değiştirilmedi. Sayılar `gercek_onnx_celery_sure_ozet.csv`
dosyasından okunur.

Ayarları düşürmemek bilinçli bir tercihtir. Ölçülen en yavaş görev 37 saniyeyken 600
saniyelik bir sınır cömert görünür; ama sınırı ölçüme yaklaştırmanın tek kazancı hatalı
bir görevi daha erken kesmektir, bedeli ise yoğun bir makinede sağlıklı bir görevi yarıda
kesmektir. Ölçüm, sınırların daraltılmasını gerektiren bir durum göstermedi.

Bu değerlerin her donanımda yeterli olduğunu iddia etmiyorum. Ölçüm tek bir makinede, iki
işçiyle ve o anki yük altında yapıldı; daha yavaş bir makinede kural yeniden çalıştırılıp
karar yeniden verilmelidir.

### 5.7. İşçi öldürüldüğünde ne oluyor

İkinci haftada iki ayarı bilerek birlikte seçmiştim: mesaj, görev bittikten sonra
onaylanır ve görev yeniden çalıştırılabilir olacak şekilde yazılır. İlki işçi ölürse
mesajın kaybolmamasını sağlar, ikincisi aynı görevin iki kez çalışması hâlinde tespitlerin
ikiye katlanmamasını. O hafta bu sözleşme sahte dedektörle sınanmıştı. Burada gerçek
modelle tekrarladım.

Deney için ayrı bir görev oluşturdum (`sigkill-dayaniklilik-20260912-151442`, 4 kare); süre
ölçümünün görevini yeniden kullanmadım. Akış şöyle ilerledi:

1. İşçi ve mesaj aracısının çalıştığı doğrulandı, koşu gerçek kuyruğa bırakıldı.
2. En az bir kare işlenmeye başlayana kadar beklendi; 338 numaralı kare "işleniyor"
   durumundaydı ve o anda kayıtlı tespit sayısı 0'dı.
3. İşçi konteyneri **gerçek SIGKILL** ile öldürüldü. Nazik kapatma kullanılmadı; kanıt
   konteynerin 137 çıkış koduyla durmasıdır (128 + 9, yani öldürme sinyali). Öldüğü
   doğrulanmadan test devam etmedi.
4. Aynı işçi hizmeti yeniden başlatıldı.
5. Bütün kareler sonuçlanana kadar kontrollü aralıklarla veritabanı sorgulandı. Bekleme
   üst sınırı sonsuz değil; yeniden dağıtım süresi ve sert sınır kararından türetildi.

| Ölçü | Sonuç |
|---|---|
| Toplam kare | 4 |
| SIGKILL anındaki kare / durumu | 338 / işleniyor |
| Öldürme kanıtı | çıkış kodu 137, konteyner durmuş |
| Öldürülen karenin son durumu | done |
| Yeniden teslim süresi | 1017,5 sn |
| Son durumlar | 4 done, 0 failed |
| Takılı kare (bekleyen / kuyrukta / işleniyor) | 0 |
| Kayıp kare | 0 |
| Kontrolsüz yinelenen Detection | 0 |
| Toplam Detection | 44 |
| Koşunun son durumu | done |
| Toplam test süresi | 1026,72 sn |

*Bu tablo ne söylüyor:* İşçi iş ortasında öldürüldüğü hâlde hiçbir kare kaybolmadı ve
hiçbiri yarı durumda asılı kalmadı. Öldürülen kare, öldürme anından 1017,5 saniye sonra
tamamlandı; bu süre yeniden dağıtım ayarıyla (900 sn) uyumludur, çünkü onaylanmamış mesaj
ancak o süre dolduktan sonra yeniden dağıtılır. Aynı tespitin iki kez yazılması anlamına
gelecek kontrolsüz yineleme sayısı sıfır. Sayılar `scripts/20`'nin ürettiği
`onnx_sigkill_dayaniklilik.csv` dosyasından okunur.

Ölçümün bir sınırını açıkça yazmak gerekir. Bir karenin **kaç kez işlenmeye başlandığı**
doğrudan ölçülmedi. Sebebi şu: zamanlama kaydı kare bittiğinde yazılır, SIGKILL ile ölen
girişim ise iş ortasında durduğu için hiç satır yazamadı. Bu yüzden "tekrar işlenen kare
sıfırdı" demiyorum; öyle bir ölçüm yok. Ölçülen şeyler şunlardır: öldürülen karenin
yeniden teslim edilip tamamlanması, bütün karelerin son duruma ulaşması, kayıp kare
bulunmaması ve kontrolsüz yinelenen tespit bulunmaması.

Bu tek senaryonun kapsamı da dardır. Sınanan şey, işçi sürecinin ani ölümüdür. Mesaj
aracısının çökmesi, veritabanı bağlantısının kopması, ağ bölünmesi, disk dolması veya aynı
anda birden çok işçinin ölmesi sınanmadı. Bir dağıtık sistemin bütün hata türleri için
kanıt sunmuyorum; sunduğum kanıt, işçi ölümü karşısında bu hattın kare kaybetmediğidir.

### 5.8. Görüntüyü kare başına bir kez okumak

Süre tablosunda beklemediğim bir şey vardı: görüntü okuma, çıkarımla aynı büyüklük
sınıfındaydı (medyan 10,12 sn karşı 9,36 sn). Kodu okuyunca sebebi göründü. Dedektörün
karo başına çağrılan işlevi, her çağrıda kaynak görüntüyü diskten yeniden açıp çözüyordu.
Test görüntüleri 4000×3000 ve bu protokolde bir görüntü 80 karoya bölünüyor; yani bir kare
işlenirken aynı JPEG dosyası 80 kez açılıp 80 kez çözülüyordu.

Bu bir kusurdur ve düzeltmesi tek değişkenlidir: kaynak görüntüyü kare başına bir kez
okumak, karoları o bellekteki görüntüden kesmek. Model, oturum, karo protokolü, eşikler,
işçi sayısı ve kuyruk ayarları değişmedi.

Düzeltmeden önce davranışı sabitleyen testleri yazdım; ikisi kırmızı başladı ve düzeltmeden
sonra yeşile döndü. Testlerin doğruladıkları:

- Bir karede kaç karo işlenirse işlensin kaynak görüntü yalnızca bir kez açılıyor; yeni bir
  kare geldiğinde yeniden okunuyor.
- Bellekten kesilen karonun pikselleri, diskten kesilenle birebir aynı.
- Modele verilen tensörün şekli ve veri türü değişmiyor.
- Karo koordinatları ve tespitlerin tam görüntü düzlemine taşınması değişmiyor.
- Aynı sahte model çıktısı için eski ve yeni akış aynı kutuları üretiyor.
- Çıkarım hata verse bile açılan dosya kaynağı açık kalmıyor.
- Çalıştırıcı oturumunun kareler arasında yeniden kullanılması sürüyor.

Sonra aynı 157 görüntüyle, aynı protokolde ve aynı model özetiyle ölçümü tekrarladım; yeni
görev adı `olcum-onnx-tek-okuma-20260912-153715`. Karşılaştırmadaki bütün yüzdeler iki
ölçülmüş değerden `scripts/21` tarafından hesaplanır.

| Aşama | Medyan önce → sonra | Değişim | p95 önce → sonra | Değişim |
|---|---|---|---|---|
| Görüntü okuma | 10,1187 → 0,2774 | −%97,26 | 15,1177 → 0,5107 | −%96,62 |
| ONNX çıkarım | 9,3633 → 15,3550 | +%63,99 | 12,5423 → 30,5586 | +%143,64 |
| NMS ve koordinat | 0,3895 → 0,2245 | −%42,36 | 0,4907 → 0,3724 | −%24,11 |
| Veritabanına yazma | 0,0173 → 0,0260 | +%50,29 | 0,0402 → 0,0590 | +%46,77 |
| Kare toplam | 19,8840 → 16,0092 | −%19,49 | 28,2916 → 31,6530 | +%11,88 |

*Bu tablo ne söylüyor:* Hedeflenen yer düzeldi — görüntü okuma medyanı 10,12 saniyeden
0,28 saniyeye indi. Karenin toplam süresi medyanda 19,88'den 16,01 saniyeye düştü. Ama
tablo tek yönlü değil: aynı karenin kuyruk sonu davranışı kötüleşti, kare toplam p95
28,29'dan 31,65 saniyeye çıktı. Çıkarım süresi de arttı; medyanda +%63,99, p95'te
+%143,64. Sayılar `scripts/21`'in ürettiği `tek_okuma_karsilastirma.csv` dosyasından
okunur; ham kayıtlar iki koşunun kare CSV'lerindedir.

| Kontrol | Önce | Sonra |
|---|---|---|
| Kare sayısı | 157 | 157 |
| Toplam Detection | 2450 | 2450 |
| Tespit sayısı farklı görüntü | — | 0 |
| Soğuk başlangıç | 2 | 2 |
| Aynı oturumla en çok kare | 79 | 79 |
| done / hatalı kare | 157 / 0 | 157 / 0 |

*Bu tablo ne söylüyor:* Düzeltme tespit davranışını değiştirmedi. Yalnızca toplam tespit
sayısı değil, görüntü bazında tespit sayısı da aynı: 157 görüntünün hiçbirinde sayı
farklı çıkmadı. Oturum paylaşımı da bozulmadı.

Bu sonucun nasıl yazılacağı önemlidir. Yazılabilecek olan: **medyan görev süresi azaldı ve
tespit davranışı değişmedi.** Yazılamayacak olan: "sistem bütün yüzdeliklerde hızlandı" ya
da "genel performans kesin olarak iyileşti". Kare toplam p95 yükseldi; bu, en yavaş
karelerin daha da yavaşladığı anlamına gelir ve medyandaki iyileşme onu kapsamaz.

Çıkarım süresindeki artışın **sebebi ölçülmedi**. Akla gelen açıklamalar var — örneğin
görüntü çözme işi ortadan kalkınca iki işçinin aynı işlemciyi daha yoğun paylaşması — ama
bu deneyde hiçbiri sınanmadı ve tahmini sonuç diye yazmıyorum. Mekanizmayı ayırmak için
işçi sayısını tek değişken yapan ayrı bir ölçüm gerekir; o ölçüm yapılmadı.

Kuyrukta bekleme süresi de değişti (medyan 845,4332 → 614,4650 sn), ama bunu kod kazanımı
saymıyorum: kuyruk beklemesi işçi zamanlamasına ve görev sırasına bağlıdır, karenin
çalışma süresini ölçmez.

### 5.9. Süreçte bulunan ve düzeltilen kusurlar

Bu bölümdeki işlerin çoğu ölçüm yaparken ortaya çıkan kusurları düzeltmekle geçti. Dördü
kayda değer.

**Test paketi ölçüm kaydını kirletiyordu.** Aşama sürelerini toplayan ayar ortamdan
geliyor; ölçüm sırasında açık olduğu için backend testlerini çalıştırdığımda testlerin
kendi görevleri de aynı dosyaya satır yazdı. Test veritabanının koşu numaraları gerçek
koşununkilerle çakışabildiği için ölçüm satırları karıştı. Bunu, kayıtta beklenmeyen
sayıda satır görünce fark ettim. Düzeltme testlerin ortak hazırlık dosyasına eklendi:
testler bu kaydı kapatır, ihtiyacı olan test ayarı kendisi doldurur. Kirlenmiş koşuyu
kullanmadım; kuyruk temizlenip ölçüm baştan alındı. Ders: ölçüm açıkken test çalıştırmak
da bir müdahaledir.

**Dedektör görüntüyü karo başına açıyordu.** 5.8'in konusu. Bunu koddan değil ölçümden
fark ettim: görüntü okumanın çıkarımla aynı büyüklükte çıkması kodu okumamı sağladı.
Düzeltme tek değişkenli tutuldu ve önce/sonra aynı protokolde ölçüldü. Ders: aşamaları
ayrı ölçmek, yalnızca raporlamaya değil, kusur bulmaya da yarıyor.

**Ölçüm script'i mevcut çıktının üzerine yazabiliyordu.** Süre ölçümünün çıktı yolları
sabit varsayılanlara bağlıydı; argümansız ikinci bir koşu, saatler süren bir ölçümün
dosyasını sessizce değiştirebilirdi. Kusuru, ikinci koşuyu farklı bir dosyaya yazmak için
elle yol vermek zorunda kalınca gördüm. Artık yol verilmezse görev adından çakışmayan bir
ad üretiliyor, var olan bir dosyanın üzerine ise ancak açık bir bayrakla yazılabiliyor.
Ders: pahalı çıktıları koruyan varsayılan, dikkatli kullanıcıdan daha güvenilirdir.

**Görev adını sohbetten aktarmak.** Süre ölçümünün görev adını bir ara yanlış aktardım:
iptal ettiğim kirli denemenin adını kullandım. Kapanış denetiminde adları CSV'den okuyunca
fark ettim. Kural netleşti: ad, sayı ve komut hatırlanan yerden değil, üretilen dosyadan
okunur; metinle CSV çeliştiğinde CSV kazanır.

İki ayrım da bu bölümde yerleşti. Birincisi, **ölçüm ile karar** ayrımı: en yavaş görev bir
ölçümdür, ona uygulanan güvenlik payı bir karardır ve ikisi aynı cümlede eşit ağırlıkla
sunulamaz. İkincisi, **kuyrukta bekleme ile çalışma süresi** ayrımı: ilki işçinin
meşguliyetini, ikincisi işin maliyetini gösterir; zaman aşımı kararı yalnızca ikincisine
dayanır.

### 5.10. Kısıtlar

Bu bölümde ölçülenlerin sınırları şunlardır:

- **Kaynak aşinalığı.** Testteki 970 hedefin 939'u ZRI kaynağından ve ZRI eğitim
  verisinde de var. Sonuçlar bu kaynağa aşina bir model için geçerlidir.
- **Hash kontrolünün kapsamı.** Yalnızca birebir aynı dosyayı yakalar; yeniden
  sıkıştırılmış veya benzer ama farklı bir kare bu ölçümde görünmez.
- **≥ 80 px açıklaması.** Eğitim verisi tarafı ölçüldü, nedensellik kurulmadı.
- **Adım-sabit deney.** Yalnızca veri hazırlama davranışını anlatır; hangi karo boyutunun
  daha iyi model verdiği ölçülmedi.
- **Model-320 yok.** İkili deney matrisinin dördüncü hücresi hâlâ boş; karo 320 kümesiyle
  eğitim yapılmadı.
- **Motor eşdeğerliği.** Ölçülen üç eşikte metrikler aynı; sayısal farklar küçük ama sıfır
  değil. Bit düzeyinde eşitlik ölçülmedi.
- **Süre ölçümlerinin kapsamı.** Tek bir makine, iki işçi ve o anki yük altında alındı.
  Başka bir donanımda tekrarlanmalıdır.
- **Kuyrukta bekleme.** Görev süresi değildir; sistemin doluluğunu gösterir.
- **Zaman aşımı payı.** Ölçüm değil karardır; çarpanlar ölçülmedi.
- **Tek SIGKILL senaryosu.** Yalnızca işçi sürecinin ani ölümü sınandı.
- **İşleme girişimi sayısı.** Ölen girişim kayıt yazamadığı için doğrudan ölçülemedi.
- **Tek okuma deneyi.** Çıkarım süresindeki artışın ve kare toplam p95'teki yükselmenin
  mekanizması ölçülmedi.
- **Tabanın FP eğrisi.** Eğitimsiz modelin yanlış pozitif tarafı hâlâ yalnızca üç eşikte
  ölçülü; tam eğri çıkarılmadı.

### 5.11. Sonraki adım

#### 5.11.1. Ölçüm ve analiz tarafında açık kalanlar

Çıkarım süresindeki artışın mekanizması ölçülmedi; bunu ayırmak için işçi sayısını tek
değişken yapan bir ölçüm gerekir. Kare toplam p95'teki yükselmenin hangi karelerden
geldiği de çıkarılmadı. Model-320 eğitilmedi ve ölçülmedi. ≥ 80 px bandındaki düşüşün
kenar kuralıyla nedensel bağı, kural değiştirilip model yeniden eğitilmeden kurulamaz.
Eğitimsiz tabanın tam eşik eğrisi hâlâ eksik. Dayanıklılık tarafında işçi ölümü dışındaki
hata türleri sınanmadı.

#### 5.11.2. Bir sonraki adımda fiilen yapılacak iş

Sıradaki iş, sistemin operatöre dönük yüzünü kurmaktır: React, Vite ve TypeScript ile bir
arayüz, sunucu durumunu yönetmek için TanStack Query. Arayüz mevcut API'ye bağlanacak;
görüntü yükleme, görev oluşturma, tarama başlatma, ilerleme takibi ve tespitlerin görüntü
üzerinde incelenmesi bu akışın parçaları.

Bir tasarım kolaylığı hazır: tespitler sabit bir depolama tabanıyla saklandığı ve güven
eşiği okuma anında uygulandığı için arayüzde eşiği kaydırmak yeni bir tarama gerektirmez;
aynı koşunun sonucu farklı eşiklerde gösterilebilir.

Konum tarafında bir karar verilmesi gerekiyor. Şu an kullandığım veri kümesindeki
görüntülerin EXIF alanlarında koordinat yok; kare kayıtlarının konum alanları boş kalıyor.
Boş bir alanın üzerine gerçek koordinat varmış gibi yazmak, haritada var olmayan bir
kesinlik göstermek olur. Bu yüzden sonraki adımın ilk işi koordinat kaynağına karar
vermektir: gerçek uçuş kaydı olan bir veri mi kullanılacak, yoksa arayüz gösterimi için
üretilmiş koordinatlarla mı çalışılacak. İkincisi seçilirse bu veriler arayüzde ve raporda
**demo verisi** olarak açıkça etiketlenecek.

Arayüzün ayrıntılı tasarımı bu bölümün konusu değil; burada yalnızca geçişi kuruyorum.
