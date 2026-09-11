## 3. Asenkron Tarama Boru Hattı ve Dayanıklılık

*(taramanın istek dışına çıkarılması, mimari kararlar ve elenen alternatifler, karolama mantığının saf fonksiyonlara ayrılması, sahte dedektör ve determinizm, eşzamanlılık ve idempotanslık, işçi öldürme testi, kurtarma gecikmesi kısıtı, depolama tabanı kararı, süreç dersleri)*

Bölüm 1 ve 2'de bir ölçüm yaptım ve o ölçümün etrafına görüntülerin yüklendiği bir
iskelet kurdum. Bu bölümde ölçüm yok. Burada anlattığım şey **tasarım kararları** ve o
kararların bir dayanıklılık testiyle sınanması. Bu yüzden bölüm 2'den kısa; ölçüm
tablosu yerine gerekçe ve alternatif tartışması var.

Bu adımda çözdüğüm problem şu: bir tarama, kullanıcının isteğini bekleten bir işlem
olamaz. Taramayı isteğin dışına, arka planda çalışan bir işçiye taşıdım. Operatör
taramayı başlatıyor, iş bir kuyruğa giriyor, ilerleme ayrı bir uçtan sorulabiliyor.

Bu bölümde **gerçek model çalıştırılmadı**. Yerine sahte bir dedektör koydum. Bunun
sebebi tembellik değil, yöntem: boru hattının doğruluğunu, modelin yavaşlığından
bağımsız olarak sınamak istedim. Bu kararın doğrudan bir sonucu var ve baştan yazmam
gerekiyor — **bu bölümdeki hiçbir süre, gerçek modelin süresi değildir.** Sahte
dedektörün ürettiği saniyeler, bir performans iddiası olarak okunamaz. Onlar yalnızca
boru hattının kendi gecikmesini gösterir.

---

### 3.1. Problem: bir tarama neden istek içinde çalıştırılamaz

Bölüm 2'de taban çizgisi ölçümünün tekrar koşusunu anlatmıştım. O koşu, veri
kümesinin tamamını yalnızca CPU üzerinde tarıyordu ve **156,8 dakika** sürdü. Bu sayı,
bu bölümdeki bütün mimari kararların çıkış noktası.

Bir HTTP isteği bu süreyi bekleyemez. Sebebini tek tek saymak gerekiyor, çünkü "yavaş
olduğu için" yeterince kesin bir gerekçe değil.

**Zaman aşımları.** Arada duran her katmanın kendi süre sınırı var: tarayıcı, ters
vekil sunucu, uygulama sunucusunun işçi süreci. Bunların hiçbiri saatlerce açık kalan
bir bağlantıyı normal saymaz. İstek, iş bitmeden kesilir.

**Süreç tüketimi.** Uygulama sunucusunun eşzamanlı işleyebileceği istek sayısı sınırlı.
Tek bir tarama bir süreci saatlerce tutarsa, o süreç başka hiçbir isteğe bakamaz. Beş
operatör aynı anda tarama başlatırsa sistemin tamamı cevap veremez hale gelir.

**İlerleme görünmezliği.** Senkron bir istekte cevap ya hep ya hiçtir. Operatör iki
buçuk saat boyunca işin nerede olduğunu göremez. Arama-kurtarma bağlamında "çalışıyor
mu, kaçta kaç?" sorusunun cevapsız kalması tek başına kabul edilemez.

**Kırılganlık.** Bağlantı koparsa, tarayıcı sekmesi kapanırsa veya sunucu yeniden
başlarsa iş kaybolur. İki buçuk saatlik hesabın tamamı çöpe gider ve baştan başlamak
gerekir.

Bu dört sebebin ortak çözümü aynı: işi isteğin ömründen ayırmak. İstek yalnızca işi
**kaydeder** ve bir kimlik döndürür; işin kendisi ayrı bir süreçte koşar. Operatör o
kimlikle ilerlemeyi sorar.

Bu bölümde kurduğum şey tam olarak bu ayrım. Tarama başlatma ucu artık bir kayıt
oluşturup hemen dönüyor; taramayı arka plandaki işçi yapıyor.

### 3.2. Mimari kararlar ve alternatifleri

Bu alt bölümde üç karar var. Her birinde elediğim alternatifi de yazıyorum, çünkü bir
kararın gerekçesi ancak reddedilenle birlikte anlaşılır.

#### 3.2.1 Kuyruk ve aracı seçimi

Görev kuyruğu olarak Celery'yi, aracı (broker) ve sonuç deposu olarak Redis'i seçtim.

Elediğim birinci alternatif **veritabanı temelli kuyruk** yazmaktı: işleri bir tabloya
yazıp bir döngüyle çekmek. Bunun cazip tarafı yeni bir servis eklememesi. Ama yeniden
deneme, üstel geri çekilme, zaman aşımı, birden çok işçi arasında dağıtım ve
tamamlanmayı toplama gibi şeylerin hepsini elle yazmam gerekirdi. Bunlar çözülmüş
problemler ve kendi yazdığım bir sürüm, iyi ihtimalle Celery'nin yaptığının eksik bir
kopyası olurdu. Bitirme projesinde asıl anlatmak istediğim şey tespit boru hattı, kuyruk
altyapısının yeniden icadı değil.

Elediğim ikinci alternatif **RabbitMQ**'ydu. Mesajlaşma tarafında Redis'ten daha
yetenekli ve bu bölümün 3.7'sinde anlatacağım kısıt onda yok. Buna rağmen Redis'i
seçtim: tek bir konteyner, yapılandırma yükü yok ve sonuç deposu olarak da aynı servisi
kullanabiliyorum. Bir prototipte ayakta tutulması gereken servis sayısını düşük tutmak
gerçek bir kazanç. Bu tercihin bedelini 3.7'de açıkça yazıyorum; kararı savunmuyorum,
maliyetiyle birlikte sunuyorum.

Sürüm tarafında beklemediğim bir kısıt çıktı. Celery'nin Redis eklentisi, Python
istemcisinin sürümünü belirli bir üst sınırın altında tutuyor. Paket deposundaki en
yeni istemci sürümü bu sınırın üzerindeydi ve kurulamıyordu; sınırın altındaki en
yüksek sürüme sabitledim. Bunu not etmemin sebebi şu: "en güncel sürümü kur"
otomatizminin çalışmadığı bir yer burası, ve bağımlılık ağacının izin verdiği sürüm,
deponun sunduğu en yeni sürüm değil.

Redis imajını da yama sürümüne kadar sabitledim. Hareketli bir etiket kullansaydım,
aynı depo farklı bir tarihte farklı bir Redis sürümüyle ayağa kalkardı ve
tekrarlanabilirlik iddiası zayıflardı — bölüm 2'de taban çizgisi ölçümü için savunduğum
şeyin aynısı, altyapı tarafında.

#### 3.2.2 Görev tanesi: neden kare başına

Bir taramayı kaç parçaya bölmeli? Üç seçenek vardı.

**Tarama başına tek görev.** Bütün tarama tek bir kuyruk mesajı olurdu. Yazması en
kolayı. Üç sorunu var: iş tek bir işçiye düşer, yani ikinci bir işçi eklemek hiçbir
şeyi hızlandırmaz; işçi ölürse bütün tarama baştan başlar; ilerleme kare düzeyinde
görünmez, yalnızca "başladı / bitti" olur.

**Karo başına görev.** En ince taneleme. Paralelliği en yükseğe çıkarır. Ama her karo
için ayrı bir mesaj, ayrı bir veritabanı işlemi ve ayrı bir görüntü açma maliyeti
doğar. Tek bir görüntü 512 piksellik karolara 0,2 örtüşmeyle bölündüğünde ortaya
**80 karo** çıkıyor; beş görüntülük küçük bir görevde bile bu 400 mesaj demek. Karo
başına yapılan iş, mesajın kendi maliyetinin yanında küçük kalır.

**Kare başına görev.** Seçtiğim bu. Bir görüntünün bütün karoları tek bir görevde
işleniyor. Paralellik kare düzeyinde: iki işçi iki ayrı kareye aynı anda bakabiliyor.
İlerleme doğal bir birimle ölçülüyor — operatörün sorduğu soru "kaç görüntü tarandı",
"kaç karo tarandı" değil. Bir hata da kare düzeyinde yalıtılıyor: bozuk tek bir görüntü,
taramanın geri kalanını düşürmüyor.

Bu kararın ikinci bir faydası var: yeniden deneme birimi de kare oluyor. Bir kare
başarısız olursa yalnızca o kare tekrar denenir, tarama değil.

#### 3.2.3 Tamamlanmayı toplama: chord

Kareler ayrı görevlerse, "hepsi bitti" bilgisini kim verecek?

İlk akla gelen çözüm **yoklama**: bir görev periyodik olarak sayaçlara bakıp hepsi
tamam mı diye kontrol eder. Bu, boşa dönen iş üretir ve "ne sıklıkla yoklamalı?"
sorusunu doğurur — sık yoklarsan israf, seyrek yoklarsan gecikme.

İkinci çözüm, her karenin bitişinde "acaba sonuncu ben miyim?" diye kontrol etmesi.
Bu, yarış durumuna açık: iki kare aynı anda bitip ikisi de kendini sonuncu sanabilir
ya da ikisi de sanmayabilir.

Celery'nin **chord** yapısını kullandım. Chord, bir görev kümesinin tamamı bittiğinde
tek bir toplayıcı görevi çalıştırır. Kareler başlık (header), taramayı kapatan görev
geri çağırma (callback) oluyor. Sayma işini kuyruk sistemi yapıyor, ben yapmıyorum.

Bu kararın bir kırılganlığı var ve bölüm boyunca birkaç yerde karşıma çıkacak: **başlık
görevlerinden biri istisna fırlatırsa geri çağırma çalışmaz.** Yani bir kare hata
verirse tarama sonsuza kadar "çalışıyor" durumunda asılı kalır. 3.5.4'te ve süreç
derslerinde bunun nasıl ele alındığını yazıyorum.

### 3.3. Karolama

Havadan çekilmiş görüntülerde hedefler küçük. Görüntüyü küçültüp modele vermek, zaten
küçük olan hedefi daha da küçültür. Bunun yerine görüntü örtüşen karolara bölünüyor ve
her karo ayrı taranıyor. Bu bölümün konusu, o bölmenin **nasıl hesaplandığı**.

#### 3.3.1 Saf fonksiyon kararı

Karolama mantığını ayrı bir modüle, **saf fonksiyonlar** olarak yazdım. Saf fonksiyon,
yalnızca kendisine verilen veriye bakan ve yalnızca veri döndüren fonksiyon demek:
veritabanına, diske veya ağa dokunmuyor. Bu modül, web çatısının kendisini bile içeri
almıyor.

Bunu neden yaptığımı yazmak gerekiyor, çünkü ilk bakışta gereksiz bir ayrım gibi
görünüyor. Karolama mantığı bu boru hattının **en kritik parçası**: bir hata varsa,
sonucu yanlış koordinatlı kutular olur ve bu, operatörün yanlış yere bakması demektir.
Böyle bir mantığın testinin, ayakta bir veritabanına, yüklenmiş bir görüntüye ve çalışan
bir işçiye bağlı olması kabul edilemez. O testler yavaş olur, kurulumu kırılgan olur ve
kırılgan test koşulmaz hale gelir.

Saf fonksiyon olarak yazıldığında karolama testleri hiçbir altyapı istemiyor. Girdi
birkaç sayı, çıktı bir liste. Testler milisaniyeler içinde koşuyor.

İkinci faydası şu: bu modülün doğruluğu, sistemin geri kalanından **bağımsız olarak**
iddia edilebiliyor. Karolamanın doğru olduğunu söylediğimde, arkasında duran kanıt
dedektöre, veritabanına veya kuyruğa dair hiçbir varsayım içermiyor.

#### 3.3.2 Adım ile karo sayısı ayrımı

Karolamada iki ayrı büyüklük var ve bunları karıştırmak kolay.

**Adım**, iki komşu karo başlangıcı arasındaki mesafe. Karo boyundan örtüşme payı
çıkarılarak bulunuyor. Örtüşme oranı 0,2 ise, karo boyunun beşte biri kadar bir pay
çıkarılıyor ve kalan mesafe adım oluyor.

**Karo sayısı** ise adımın basit bir bölümü değil. Kenar uzunluğunu adıma bölmek yanlış
sonuç verir, çünkü son karo kenarın bittiği yerde değil, kendi boyu kadar geride
başlamak zorunda. Kenardan örtüşme payını düşüp kalanı adıma bölmek ve yukarı
yuvarlamak gerekiyor.

Bu ayrımı ayrıca yazmamın sebebi, ilk yazdığımda tam olarak bu iki büyüklüğü
karıştırmış olmam. Kenarı doğrudan adıma bölmek, görüntünün sağ ve alt şeritlerinde
eksik karo bırakıyor — yani görüntünün bir kısmı hiç taranmıyor. Böyle bir hata sessiz:
sistem çalışır, sonuç üretir, kimse bir şey fark etmez, ama kenarlardaki hedefler
görünmez olur.

#### 3.3.3 İçeri kaydırma kararı

Son karo neredeyse her zaman görüntü sınırını taşar. Adım, kenar uzunluğunu tam bölmez.
İki seçenek var.

**Kırpmak:** karoyu sınırda kesmek. Sonuç, diğerlerinden küçük bir karo olur.

**İçeri kaydırmak:** karoyu sola ya da yukarı çekip sınıra yaslamak. Karo boyu sabit
kalır, önceki karoyla örtüşmesi artar.

İçeri kaydırmayı seçtim. Gerekçesi dedektörün tarafında: bir tespit modeli, girdi
boyutuna göre ölçekleme yapar. Kırpılmış küçük bir karo modele verildiğinde farklı bir
ölçekte işlenir ve o karodaki hedeflerin görünen büyüklüğü, komşu karolardakinden farklı
olur. Bu, görüntünün kenar şeritlerini geri kalanından sistematik olarak farklı bir
rejimde taramak anlamına gelir. Bölüm 2'de recall'ı yöneten şeyin kutunun piksel
cinsinden yüksekliği olduğunu ölçmüştüm; kenar şeridinde ölçeği değiştirmek, tam da o
büyüklüğü bozar.

İçeri kaydırmanın bedeli, kenarlarda örtüşmenin artması: oradaki bazı pikseller
fazladan bir kez taranıyor. Bu, hesap maliyeti dışında bir zarar vermiyor — aynı hedefin
iki karoda birden bulunması zaten örtüşmenin doğal sonucu ve bunu temizleyen bir
adım var (3.5'te geçen kutu birleştirme).

Bir uç durum daha var: karo boyu görüntüden büyükse içeri kaydıracak yer yok. O zaman
tek bir karo dönüyor ve görüntü sınırına kırpılıyor. Bu, kaydırma kuralının istisnası
değil, kaydırmanın tanımsız olduğu tek durum.

#### 3.3.4 80 karonun bağımsız doğrulanması

Karolama mantığının sınandığı asıl yer testler. Burada önemli olan, testin kodun
söylediğini tekrar etmemesi.

4000×3000 piksellik bir görüntü, 512 karo boyu ve 0,2 örtüşme oranıyla bölündüğünde
**80 karo** çıkıyor — yatayda 10, dikeyde 8. Bu sayı testte sabit olarak yazılı ve
elle hesaplanabilir. Kodun ürettiği sonucu test içinde yeniden hesaplasaydım test hiçbir
şey kanıtlamazdı; aynı yanlış formül iki yerde birden dururdu.

Karo sayısı tek başına yeterli bir kanıt değil, çünkü doğru sayıda ama yanlış yerde
karo üretmek mümkün. Üç şey daha test ediliyor:

- Hiçbir karonun görüntü sınırını aşmaması.
- Karoların görüntünün **bütün piksellerini** kapsaması, yani iki eksende de boşluk
  kalmaması. Bu test, 3.3.2'de anlattığım sessiz hatayı yakalayan test.
- Son karonun kırpılmamış, yani tam boyunda olması — 3.3.3'teki kararın kodda gerçekten
  uygulandığının kontrolü.

Kapsama testini ayrıca yazmak istiyorum, çünkü bu bölümdeki en değerli test o. Karo
sayısı doğru çıktığı halde kapsamanın delik olması mümkün, ve böyle bir hata hiçbir
hata mesajı üretmez. Kapsama testi, karo aralıklarını sıralayıp birleştiriyor ve
kenarın başından sonuna kesintisiz örtülüp örtülmediğine bakıyor.

Karolama modülünde ayrıca kutu geometrisiyle ilgili üç fonksiyon var: karo düzlemindeki
bir kutuyu görüntü düzlemine taşıyan dönüşüm, iki kutunun örtüşme oranını veren hesap ve
örtüşen kutulardan yüksek skorlu olanı tutan eleme. Bunların testlerinde de elle
hesaplanmış değerler kullandım: aynı kutu için örtüşme oranı 1, ayrık kutular için 0 ve
bilinen bir örnek için kâğıt üzerinde çıkardığım kesir.

### 3.4. Sahte dedektör

#### 3.4.1 Arayüz arkasına alma

Bu adımda gerçek model yok. Ama modelin olmaması, model geldiğinde boru hattının
baştan yazılması anlamına gelmemeli.

Bunun için soyut bir dedektör arayüzü tanımladım: bir görüntü yolu ve bir karo alıp
kutu listesi döndüren tek bir işlem. Sahte dedektör bu arayüzü uyguluyor. Görevlerin
içinde dedektör doğrudan seçilmiyor; bir fabrika fonksiyonu üzerinden alınıyor.

Amaç şu: gerçek model geldiğinde değişecek yer **yalnızca o fabrika fonksiyonunun
içi** olacak. Karolama, koordinat dönüşümü, kutu eleme, görev akışı, veritabanına yazma,
uçlar ve testler olduğu gibi kalacak. Bu bir tahmin değil, arayüzün dayattığı bir
kısıt: boru hattının geri kalanı dedektörün ne olduğunu bilmiyor.

#### 3.4.2 sha256 tohumlama

Sahte dedektör her karo için rastgele sayıda kutu üretiyor ve her kutuya rastgele bir
skor veriyor. Ayrıca karo başına kısa bir süre bekliyor, ki gerçek bir modelin karo
başına maliyet doğurduğu görülsün.

Kritik ayrıntı şu: bu rastgelelik **tohumlanmış**. Tohum, görüntünün sha256 özetiyle
karonun satır ve sütun indeksinden türetiliyor. Sonuç olarak aynı görüntünün aynı
karosu, her zaman aynı kutuları ve aynı skorları veriyor. Bekleme süresi de aynı
tohumdan geliyor.

Görüntünün sha256 özeti zaten sistemde vardı — bölüm 2'de aynı görüntünün aynı göreve
iki kez yüklenmesini engellemek için hesaplanıyordu. Burada ikinci bir işe yaradı.

#### 3.4.3 Determinizm neden test edilebilirliğin ön koşulu

Bu, bu bölümdeki en önemli tasarım kararlarından biri ve gerekçesi ilk bakışta görünmüyor.

Bu boru hattının sağlaması gereken temel özelliklerden biri, aynı görevin iki kez
çalışması durumunda tespitlerin ikiye katlanmaması (3.5.3). Bunu test etmenin yolu
görevi iki kez çalıştırıp tespit sayısına bakmak.

Şimdi dedektörün tohumlanmamış olduğunu varsayalım. İkinci koşuda kutular zaten farklı
sayıda ve farklı yerlerde çıkardı. Tespit sayısının değişmemesi ya da değişmesi hiçbir
şey söylemezdi: sayı aynı çıksa tesadüf olabilirdi, farklı çıksa sebebi
idempotansızlık mı yoksa rastgelelik mi olduğu ayrılamazdı. Test, geçse de kalsa da
bilgi taşımazdı.

Tohumlama bunu değiştiriyor. İkinci koşu **aynı** kutuları üretiyor, dolayısıyla tespit
sayısındaki her değişim yalnızca yazma mantığından gelebilir. Test artık tek bir şeyi
ölçüyor.

Genel ilke olarak yazacak olursam: bir davranışı test etmek istiyorsanız, o davranışın
dışındaki her şeyin tekrar edilebilir olması gerekir. Rastgelelik, testin ölçmek
istediği sinyali gürültünün altında bırakır. Bölüm 2'de taban çizgisi ölçümünün bit
düzeyinde tekrar üretilebilir olmasını neden önemsediğimi yazmıştım; buradaki gerekçe
aynı gerekçenin yazılım tarafındaki karşılığı.

### 3.5. Eşzamanlılık ve idempotanslık

Birden çok işçi aynı anda çalıştığında ve mesajlar tekrar edebildiğinde, "aynı kareyi
iki kez işlemek" teorik bir ihtimal değil, beklenen bir durum. Bu alt bölüm o duruma
verilen cevapları anlatıyor.

#### 3.5.1 Satır kilidi

Bir kareyi işleyen görev, işe başlamadan önce o karenin veritabanı satırını
`select_for_update` ile kilitliyor. Bu, PostgreSQL'in satır düzeyinde kilit almasını
sağlayan bir sorgu biçimi: kilidi alan işlem bitene kadar aynı satırı kilitlemek isteyen
ikinci işlem bekler.

Kilit alındıktan sonra görev karenin durumuna bakıyor. Kare zaten tamamlanmışsa dedektör
hiç çalıştırılmadan dönülüyor.

İki işçinin aynı kareye aynı anda uzanması durumunda olan şey şu: ikincisi birincinin
işlemi bitene kadar bekliyor, sonra satırı **yeniden okuyor** ve tamamlanmış olduğunu
görüp çıkıyor. Buradaki kritik nokta, ikinci işçinin kilit sonrası satırı yeniden
okuması. Kilitten önce okunmuş bir değere güvenseydi, beklerken değişen durumu
göremezdi.

#### 3.5.2 Kilidin kapsamının bilinçli daraltılması

Kilidi, görevin tamamı boyunca tutmak en kolay çözüm olurdu. Bilerek yapmadım.

Bir karenin işlenmesi, 80 karonun her biri için dedektörün çağrılması demek. Gerçek
modelle bu, kare başına ciddi bir süre. Kilit bu süre boyunca tutulsaydı, aynı kareye
uzanan ikinci işçi bütün o süre boyunca bloke olurdu — üstelik hiçbir iş yapmayacağı
halde, çünkü sonunda kareyi tamamlanmış bulup çıkacak. Bu, kilidi bir eşzamanlılık
aracından bir darboğaza çevirir.

Onun yerine kilit iki kısa aralıkta tutuluyor. Birincisinde durum okunuyor ve kare
"işleniyor" olarak işaretleniyor. Kilit bırakılıyor. Ağır iş — karolama ve dedektör
çağrıları — **kilidin dışında** yapılıyor. Sonra kilit yeniden alınıyor, sonuçlar
yazılıyor ve kare tamamlandı olarak işaretleniyor.

Bu tasarımın bir bedeli var ve onu da yazmak gerekiyor: ağır iş sırasında kilit açık
olduğu için, o aralıkta ikinci bir işçi aynı kareye girip işi **tekrar yapabilir**.
Yani bu tasarım, işin tekrarlanmasını engellemiyor; yalnızca sonucun bozulmasını
engelliyor. Bunu kabul edilebilir kılan şey bir sonraki başlık.

İkinci kilitte durum yeniden kontrol ediliyor: ağır iş sürerken başka bir işçi kareyi
bitirmişse, sonuçlar yazılmadan çıkılıyor.

#### 3.5.3 Sil-sonra-yaz

Görev, tespitleri yazmadan hemen önce o **koşu–kare çiftine ait** mevcut tespitleri
siliyor, sonra yenilerini yazıyor. Silme ve yazma aynı veritabanı işleminin içinde.

Bunun sonucu şu: aynı görev ikinci kez çalışırsa sonuç **eklenmiyor, yerine
konuyor**. Tespit sayısı değişmiyor.

Elediğim alternatif, her tespite tekil bir anahtar verip çakışmaları yoksaymaktı.
Kutu koordinatları ve skor üzerinden böyle bir anahtar kurmak kırılgan olurdu: kayan
noktalı bir skorun eşitlik karşılaştırması güvenilir değil ve aynı kutunun iki kez
üretilmesi meşru bir durum olabilir. Silme, anahtar tasarımına hiç girmeden aynı
garantiyi veriyor.

Sayaçlar da aynı mantıkla korunuyor. Tamamlanan kare sayısı, yalnızca karenin durumu
gerçekten değiştiğinde artıyor ve artırma, okunan değerin üzerine yazılarak değil,
veritabanının kendi içinde hesaplanan bir artırma ifadesiyle yapılıyor. Okuyup bire
ekleyip geri yazsaydım, iki işçinin aynı anda okuduğu değer aynı olur ve artışlardan
biri kaybolurdu.

#### 3.5.4 acks_late idempotanslığı zorunlu kılıyor

Kuyruk sisteminde bir mesajın ne zaman "alındı" sayılacağı ayarlanabilir bir şey.
Varsayılan davranışta mesaj, işçi onu aldığı anda onaylanır. Ben bunu değiştirdim:
mesaj, görev **bittikten sonra** onaylanıyor.

Gerekçesi dayanıklılık. Varsayılan davranışta işçi iş ortasında ölürse mesaj çoktan
onaylanmıştır ve kaybolur. Kare sonsuza kadar "işleniyor" durumunda asılı kalır, chord
hiçbir zaman tamamlanmaz, tarama bitmez. Geç onaylamada mesaj onaylanmamış olarak durur
ve yeniden dağıtılabilir.

Bunun bedeli doğrudan: **görev iki kez çalışabilir.** İşçi, işi neredeyse bitirip
onaylamadan hemen önce ölürse, mesaj yeniden dağıtılır ve aynı kare baştan işlenir.

Yani 3.5.3'teki sil-sonra-yaz mantığı bir zarafet tercihi değil, bu ayarın **zorunlu
eşi**. İkisini ayrı ayrı düşünmek yanlış; birlikte tek bir karar oluşturuyorlar.
Birini alıp diğerini bırakmak bozuk bir sistem veriyor:

| Geç onaylama | İdempotanslık | Sonuç |
|---|---|---|
| Açık | Yok | İşçi öldüğünde tespitler ikiye katlanır |
| Kapalı | Var | İşçi öldüğünde iş sessizce kaybolur, tarama bitmez |
| Açık | Var | İş kaybolmaz, tekrar çalışsa da sonuç bozulmaz |

*Bu tablo ne söylüyor: geç onaylama ve idempotanslık birbirinden bağımsız iki ayar gibi
görünse de, yalnızca ikisi birlikte açıkken tutarlı bir davranış çıkıyor. Tablodaki ilk
iki satır, bu bölümde kaçınılan iki ayrı hatayı gösteriyor.*

Bir kare bütün deneme haklarını tükettiğinde ne olduğu da bu başlığa ait. Hata,
chord'un dışına **taşırılmıyor**. Taşırılsaydı, 3.2.3'te yazdığım kırılganlık devreye
girer ve toplayıcı görev hiç çalışmazdı — yani tek bir bozuk kare bütün taramayı
sonsuza kadar asılı bırakırdı. Onun yerine kare başarısız olarak işaretleniyor,
başarısız sayacı artıyor ve görev normal dönüyor. Tarama tamamlanıyor, kısmi
başarısızlık sayaçta görünür kalıyor.

Bu kararın gerekçesi teknik olduğu kadar kullanım tarafında. Çok görüntülü bir taramada
bir görüntünün bozuk çıkması yüzünden bütün koşuyu "başarısız" ilan etmek, işlenmiş
görüntülerin sonucunu gizler. Operatörün bakması gereken şey tam olarak o sonuçlar.

### 3.6. Dayanıklılık testi

Yukarıdaki kararların hepsi iddia. Bu alt bölüm, o iddiaların sınandığı testi anlatıyor.

Testin sorusu şu: tarama sürerken işçi öldürülürse tarama kaldığı yerden devam eder mi?

Kurulum: beş görüntülük bir görev. Her görüntü 4000×3000, yani görüntü başına
**80 karo**, toplam **400 karo**. Sahte dedektörün karo başına bekleme süresini
geçici olarak artırdım, ki tarama öldürmeye yetecek kadar uzun sürsün. Bu değişiklik
depoya alınmadı.

Tarama başlatıldı. Tamamlanan kare sayısı **2** olduğunda işçi öldürüldü. O anda
sistemin durumu şuydu: iki kare tamamlanmış ve kendi tespitlerini yazmış, **iki kare
"işleniyor" durumunda yarım**, bir kare kuyrukta bekliyor. İki karenin aynı anda yarım
kalması işçinin aynı anda iki görev işlemesinden.

Öldürmenin gerçekten sert olduğunu ayrıca doğruladım. İşçi önce nazik kapanma sinyali
alıyor, ama yarım kalan kareler bu sinyalin tanıdığı süre içinde bitecek kadar kısa
değildi; süre dolunca süreç zorla sonlandırıldı. Yani bu, işini bitirip düzgünce kapanan
bir süreç değil, iş ortasında kesilen bir süreç.

Öldürme anında aracıdaki onaylanmamış mesaj sayısına baktım: **2**. Bu, yarım kalan iki
karenin mesajlarının kaybolmadığının doğrudan kanıtı. Geç onaylama ayarı, tam olarak
bunun için açıktı.

İşçi yeniden başlatıldı. Kuyrukta bekleyen kare hemen alındı ve işlendi. Yarım kalan iki
kare ise bir süre sonra yeniden dağıtıldı — bu gecikme 3.7'nin konusu — ve sıfırdan
işlendi.

Taramanın sonu:

| Ölçü | Değer |
|---|---|
| Koşu durumu | tamamlandı |
| Tamamlanan kare | 5 |
| Başarısız kare | 0 |
| Kesinti anında yarım kalan karelerin tespitleri | ikisi de yazıldı |
| Toplam tespit | 627 |
| Baştan sona geçen süre | 16 dakika 22 saniye |

*Bu tablo ne söylüyor: tarama kesintiden sonra tamamlandı ve hiçbir kare başarısız
sayılmadı. Kesinti anında tespiti bulunmayan iki kare, yeniden başlatmadan sonra kendi
tespitlerini yazdı — testin asıl kanıtı bu satır. Süre satırı bir performans ölçüsü
değil; içindeki beklemenin sebebi 3.7'de anlatılıyor.*

Testin ikinci kanıtı tutarlılık tarafında. Aynı beş görüntüyle **kesintisiz** koşan bir
taramanın toplam tespit sayısı da **627**'ydi. İki sayının eşit olması tesadüf değil:
sahte dedektör görüntünün sha256 özetinden tohumlu olduğu için aynı görüntüler aynı
kutuları üretiyor (3.4.2). Dolayısıyla bu eşitlik iki şeyi birden gösteriyor — kesinti
hiçbir tespiti **kaybetmedi** ve yeniden işlenen kareler hiçbir tespiti
**çiftlemedi**.

**BULGU:** Geç onaylama ve sil-sonra-yaz idempotanslığı birlikte, işçinin sert biçimde
öldürüldüğü bir kesintide taramanın veri kaybı veya veri çiftlemesi olmadan
tamamlanmasını sağlıyor. Kesinti anında yarım kalan iki kare yeniden işlendi, toplam
tespit sayısı kesintisiz koşuyla birebir aynı çıktı.

Bu bulgunun kapsamını daraltmak gerekiyor. Test **tek bir kesinti senaryosunu** sınadı:
tek işçinin sert biçimde öldürülmesi. Sınanmayanlar: aracının kendisinin ölmesi,
veritabanının kopması, birden çok işçinin ayrı ayrı ölmesi, ağın bölünmesi. Bunların
hiçbiri hakkında bu testten sonuç çıkarılamaz.

Bu bölümdeki testlerin toplam sayısı **41** ve hepsi geçiyor. Bunların bir kısmı
karolama ve kutu geometrisinin saf fonksiyon testleri, bir kısmı uçların ve görev
akışının testleri.

### 3.7. KISIT: kurtarma 15 dakika sürdü

Bu, testin ortaya çıkardığı gerçek bir sınırlama ve bu bölümün en dürüst kısmı.
3.6'daki tablo taramanın tamamlandığını gösteriyor, ama **ne zaman** tamamlandığını da
gösteriyor: baştan sona 16 dakika 22 saniye. Bunun büyük kısmı hesap değil, bekleme.

**KISIT — işçi öldükten sonra yarım kalan kareler hemen değil, aracı zaman aşımı
dolduktan sonra yeniden dağıtılıyor.**

Sebebi Redis'in mesajlaşma modeli. Redis, bir aracı olarak kullanıldığında bir işçinin
öldüğünü **öğrenemiyor**. Bağlantı koptuğunda tetiklenen bir bildirim yok. Onaylanmamış
mesajlar bir kenarda, teslim zaman damgalarıyla birlikte duruyor ve ancak üzerlerinden
belirli bir süre geçtikten sonra kuyruğa geri konuyor. O süre `visibility_timeout`
ayarı ve ben onu **900 saniye** seçmiştim. Testte gözlenen bekleme bu süreden geliyor.

Bu ayarın **çift görevi** var ve problemin kaynağı tam olarak bu:

1. Hâlâ çalışmakta olan bir görevin "ölmüş" sayılıp ikinci bir işçiye verilmesini
   engelliyor. Bu yüzden en uzun görev süresinden büyük olmak zorunda.
2. Ölmüş bir işçinin görevinin ne kadar sonra geri geleceğini belirliyor. Bu yüzden
   küçük olması isteniyor.

Bu iki istek birbirine zıt. Ayarı küçültmek kurtarmayı hızlandırır ama uzun süren bir
kareyi yanlışlıkla yeniden dağıtma riskini doğurur. Büyütmek riski azaltır ama kurtarmayı
yavaşlatır. Ortada bir uzlaşma noktası var ve o nokta, **görevlerin gerçekte ne kadar
sürdüğü** bilinmeden seçilemez.

900 saniyeyi seçerken dayandığım şey ölçüm değil, bir üst sınırdı: görev için tanımlı
katı zaman sınırı **660 saniye**. Bir görev bu süreyi aşarsa kuyruk sistemi tarafından
zaten sonlandırılıyor. Dolayısıyla 900, hiçbir çalışan görevin yanlışlıkla yeniden
dağıtılmayacağını garanti ediyor. Güvenli tarafta duran bir seçim, ama kurtarma
gecikmesi açısından **kötü** bir seçim.

RabbitMQ'da bu problem yok. Orada işçinin bağlantısı koptuğunda onaylanmamış mesajlar
anında kuyruğa dönüyor, çünkü aracı bağlantının koptuğunu görüyor. 3.2.1'de Redis'i
işletme kolaylığı için seçtiğimi yazmıştım; bu kısıt, o seçimin bedeli. Kararı geri
almıyorum ama bedelin ne olduğu artık ölçülmüş durumda.

**Bunu şimdi neden değiştirmiyorum.** Ayarı küçültmek için doğru değeri bilmem
gerekiyor ve doğru değer, gerçek modelle bir karenin ne kadar sürdüğüne bağlı. Elimde
o sayı yok — sahte dedektörün süresi gerçek modelin süresi değil ve bu bölümde ölçülen
hiçbir süreden gerçek modelin kare süresi türetilemez. Şu anda bir değer seçseydim,
tahmine dayanan bir ayar olurdu. Tahmine dayanan bir ayarın yanlış tarafa düşmesi,
çalışan görevlerin yeniden dağıtılması demek — yani 3.6'da gösterilen tutarlılığın
kaybı.

**AÇIK SORU:** Gerçek modelle bir karenin işlenmesi ne kadar sürüyor? Bu sayı
ölçülmeden `visibility_timeout` için doğru değer seçilemez. Hafta 4'te gerçek model
bağlandığında kare süresi ölçülecek, katı zaman sınırı ona göre daraltılacak ve
`visibility_timeout` o yeni sınırın hemen üzerine çekilecek. Kurtarma gecikmesinin ne
kadar düşeceği **ölçülmedi**.

Bir uyarı daha eklemem gerekiyor. Bu kısıt, tarama süresi boyunca bir işçinin ölme
ihtimalinin düşük olduğu varsayımıyla kabul edilebilir. Gerçek modelle bir taramanın
saatler sürdüğü düşünülürse, o pencere içinde bir yeniden başlatma olma ihtimali de
artar. Yani bu kısıt, gerçek modele geçildiğinde daha az değil, **daha çok** önem
kazanacak.

### 3.8. Depolama tabanı kararı: eşiğin okuma anına taşınması

Bu bölümün ikinci önemli tasarım kararı, güven eşiğinin nerede uygulanacağıyla ilgili.

Bir tespit modelinin ürettiği her kutunun bir güven skoru var. Bir eşik seçilip altı
atılıyor. Sorun, bu elemenin **ne zaman** yapılacağı.

Doğal görünen seçenek, koşunun eşiğini kayıt sırasında uygulamak: eşiğin altındaki
kutular hiç saklanmasın. Veritabanı küçük kalır, okuma basitleşir.

Bu seçeneği reddettim. Gerekçesi bölüm 1 ve 2'nin ölçümlerinde.

Bölüm 2'de eşik düşürmenin bedelini ölçmüştüm: en düşük eşikte görüntü başına yaklaşık
**13,5 yanlış alarm** oluşuyor. Yani eşik, sonucu kökten değiştiren bir seçim ve doğru
değeri kullanım koşuluna bağlı. "Hangi eşik doğru?" sorusu bu projede kapanmış bir soru
değil; tersine, cevabı aranan sorulardan biri.

Şimdi 3.1'deki sayıyı hatırlayalım: bir tam tarama **156,8 dakika** sürüyor. Eşik kayda
gömülseydi, "0,15 eşiğinde ne olurdu?" sorusunun tek cevabı baştan taramak olurdu. Her
eşik denemesi iki buçuk saat.

Onun yerine şunu yaptım: kutular sabit ve düşük bir **depolama tabanının** üstündeyse
saklanıyor. Taban bir ayar değeri olarak tanımlı ve koşudan koşuya değişmiyor. Koşunun
kendi eşiği yine kaydediliyor — koşunun hangi niyetle başlatıldığı belli olsun diye —
ama kutuları elemekte kullanılmıyor.

Eleme **okuma anında** yapılıyor. Tespit listeleme ucu, istemci bir değer vermezse
koşunun kendi eşiğini uyguluyor; verirse onu uyguluyor.

Testte doğrulanan davranış şu: aynı koşudan, koşunun eşiği olan 0,25 ile **494** tespit
okunuyor; depolama tabanına inildiğinde **627** tespit okunuyor. İkisi de aynı taramanın
çıktısı ve arada yeniden tarama yok.

*Bu iki sayı ne söylüyor: eşik bir sorgu parametresine dönüştü. Kayda gömülseydi 627'nin
494'e düşen kısmı geri getirilemezdi ve farklı bir eşikte ne olacağı ancak yeni bir
taramayla öğrenilebilirdi.*

Bu kararın bedeli depolama alanı: eşiğin altındaki kutular da saklanıyor, yani tablo
daha hızlı büyüyor. Bunu kabul edilebilir buluyorum, çünkü karşılığında elde edilen şey
tekrar tarama maliyetinden kurtulmak. Depolama ucuz, iki buçuk saatlik hesap değil.

Genelleştirilebilir bir ilke olarak: pahalı bir hesabın çıktısı kaydedilirken, sonradan
değiştirilebilecek her parametre kayda gömülmemeli. Gömülen her parametre, o parametreyi
değiştirmek isteyen herkesi hesabı baştan yapmaya mahkûm ediyor.

**SINIR — depolama tabanının kendisi hâlâ bir gömülü karardır.** Tabanın altına düşen
kutular saklanmıyor, dolayısıyla o bölgeye ait sorular yine ancak yeniden tarayarak
cevaplanabilir. Taban düşük seçildi ama sıfır değil; sıfır seçmek tabloyu modelin ürettiği
her kutuyla doldururdu. Bu tabanın doğru yerde olup olmadığı bu bölümde **ölçülmedi**.

### 3.9. Süreç dersleri

#### 3.9.1 Ders — Bir kütüphanenin hata yolu, belgelendiği gibi davranmayabilir

Başarısız kareyi ele alan kod ilk yazdığımda testte kaldı. Sebebi, yeniden deneme
işlevinin davranışı hakkındaki varsayımımdı.

**ÇÜRÜTÜLDÜ — "deneme hakları tükenince kütüphane kendi tanımladığı istisnayı
fırlatır":**

Varsayımım şuydu: deneme hakları tükendiğinde kuyruk kütüphanesi kendi tanımladığı
"deneme hakkı bitti" istisnasını fırlatır, ben de onu yakalarım. Kodu buna göre yazdım.

Gerçekte olan şey farklı. Yeniden deneme çağrısına özgün hata nesnesi verildiğinde,
haklar tükendiğinde kütüphane kendi istisnasını değil **özgün istisnayı** yeniden
fırlatıyor. Benim yakalamaya çalıştığım istisna hiç ortaya çıkmıyordu, dolayısıyla hata
yakalanmadan yukarı çıkıyor ve chord'u bozuyordu — yani 3.2.3'te yazdığım kırılganlığın
tam olarak gerçekleşmesi.

İkinci bir ayrıntı da testte çıktı: görevler senkron kipte koşturulduğunda yeniden
deneme çağrısı görevi kendi içinde tekrar çalıştırıyor ve davranış gerçek işçidekinden
ayrışıyor.

Düzeltme, istisna türünü yakalamaya çalışmak yerine deneme sayısını doğrudan kontrol
etmek oldu. Alınan ders şu: bir kütüphanenin hata yolu, mutlu yolundan daha az
denenmiştir ve davranışı hakkındaki varsayım, o yol gerçekten çalıştırılmadan
doğrulanmış sayılmaz. Burada hatayı yakalayan şey, başarısız kareyi **bilerek üreten**
bir testti.

#### 3.9.2 Ders — Bir testin geçmesi, test ettiğini sandığınız şeyi test ettiği anlamına gelmez

Entegrasyon testlerini ilk yazdığımda, her testten sonra tabloları tamamen boşaltan bir
kip kullanmıştım. Bu kip, sistemin ilk açılışta kullanılabilir olması için veri
göçüyle oluşturulan model kaydını da siliyordu. Testler kaydı bulamayıp hata verdi.

Buradaki asıl ders hatanın kendisi değil, hatanın **görünür olması**. Eğer testler o
kaydı fixture'dan alsaydı hepsi geçerdi ve veri göçünün gerçekten çalışıp çalışmadığı
hiç sınanmamış olurdu. Çözüm, tabloları boşaltmayan bir kipe geçip taramayı başlatan
işlemin veritabanı işlemi tamamlandıktan sonra tetiklendiğini ayrıca ele almak oldu.

#### 3.9.3 Ders — Ayarların yüklendiğini varsaymak yerine doğrulamak

3.6'daki testte, işçiyi öldürmeden önce dayanıklılık ayarlarının çalışan süreçte
gerçekten yüklü olduğunu kontrol ettim. Bu fazladan bir adım gibi görünüyor ama değil:
eğer geç onaylama ayarı bir sebeple yüklenmemiş olsaydı, test başarısız olurdu ve ben
sebebini idempotanslık mantığında arardım. Ayarın yüklü olduğunu önceden doğrulamak, bir
başarısızlık durumunda arama alanını daraltıyor.

Aynı disiplin imaj seçiminde de işe yaradı. Kullandığım Redis imajının hedef mimariyi
desteklediğini varsaymak yerine imajı çekip mimarisini doğruladım.

### 3.10. Sonraki adım

#### 3.10.1 Ölçüm ve analiz tarafında açık kalanlar

Bunlar cevaplanmamış sorular; sıradaki işin bunlar olduğu anlamına gelmiyor.

**Gerçek modelle kare başına işleme süresi ölçülmedi.** 3.7'deki `visibility_timeout`
kararı bu sayıya bağlı. Ölçülene kadar kurtarma gecikmesi düşürülemez.

**Depolama tabanının doğru yerde olup olmadığı ölçülmedi** (3.8). Tabanın altında
kalan bölgede kaç kutu olduğu ve bunların içinde gerçek hedef bulunup bulunmadığı
bilinmiyor.

**Kutu eleme eşiğinin karo sınırlarındaki davranışı ölçülmedi.** Örtüşen karolarda aynı
hedefin iki kez bulunması bekleniyor ve eleme bunu temizliyor, ama elemenin karo
sınırında hedefin bir kısmını gördüğü durumlarda ne yaptığı bu bölümde sınanmadı. Bunun
için gerçek tespitler gerekiyor; sahte dedektörün kutuları bu soruyu cevaplayamaz.

**Tek kesinti senaryosu dışındaki dayanıklılık soruları açık** (3.6). Aracının ölmesi,
veritabanı kopması ve ağın bölünmesi sınanmadı.

**Bölüm 2'den devreden sorular kapanmadı.** Koordinat kaynağı kararı hâlâ verilmedi ve
etiket kalitesi denetimi tek örnekle sınırlı kaldı.

#### 3.10.2 Hafta 3'te fiilen yapılacak iş

Sıradaki adımda kurulacak olan şey **eğitim tarafı**.

Birincisi, gerçek eğitim koşusunun hazırlanması: veri kümesinin eğitim ve doğrulama
olarak ayrılması, eğitim koşusunun tekrar üretilebilir biçimde kaydedilmesi ve eğitilen
modelin taban çizgisiyle aynı ölçüm yöntemiyle karşılaştırılması. Karşılaştırmanın
bölüm 1'deki ölçümle aynı zemine oturması şart; farklı bir ölçüm yöntemiyle alınan sayı,
taban çizgisine karşı bir iddia oluşturmaz.

İkincisi, **karo küçültme denemesi**. Bölüm 2'de recall'ı yöneten şeyin kutunun piksel
cinsinden yüksekliği olduğunu ölçmüştüm. Karoyu küçültmek, modele giden girdide hedefin
oransal olarak daha büyük görünmesini sağlıyor. Bu denemenin gerekçesi ölçüme dayanıyor
ama sonucu **ölçülmedi**; karo küçültmenin recall'a etkisi bu adımda ölçülecek.
Karolama mantığı karo boyunu parametre olarak aldığı için bu deneme, boru hattında
değişiklik gerektirmiyor.

Üçüncüsü, gerçek dedektörün fabrika fonksiyonunun arkasına bağlanması (3.4.1). Bu iş
Hafta 4'e ait, ama eğitim koşusunun çıktısı doğrudan oraya gideceği için Hafta 3'te
üretilen model dosyasının nasıl sürümleneceği şimdiden kararlaştırılmalı.

Bu bölümde kurulan boru hattı, gerçek model bağlandığında değişmeyecek biçimde
tasarlandı. O iddianın sınanacağı yer Hafta 4; bu bölümde sınanmadı.
