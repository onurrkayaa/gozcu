## 6. Operatör Arayüzü ve Konum Kaynağı Kararı

*(bu bölümde çalışan backend'in sözleşmesini koddan ve gerçek isteklerden çıkarıyor, operatörün görev açıp tarama başlatabildiği bir arayüz kuruyor, tespit kutularının gerçek görüntü üzerinde doğru oturduğunu ölçüyor, elimdeki veride konum bilgisi olup olmadığını sayarak karara bağlıyor ve süreçte bulduğum kusurları düzeltiyorum)*

---

### 6.1. Bu bölümün sorusu

Önceki bölümün sonunda elimde çalışan bir tarama hattı vardı: eğitilmiş model ONNX
biçiminde dışa aktarılmış, iki motorun aynı sonucu verdiği ölçülmüş, model gerçek
Celery kuyruğuna bağlanmış ve bir işçi öldürüldüğünde işin kaybolmadığı
gösterilmişti. Ama o hattı yalnızca ben, komut satırından çalıştırabiliyordum.
Hattın kendisi hazırdı; kullanıcısı yoktu.

Bu bölümün sorusu şu: **operatör, gerçek backend üzerinden görev oluşturabiliyor,
görüntü ekleyebiliyor, taramayı izleyebiliyor ve tespitleri yanıltıcı bir konum
iddiası olmadan inceleyebiliyor mu?**

Sorunun içindeki "yanıltıcı konum iddiası olmadan" kısmı sonradan eklenmiş bir
süs değil. Arama kurtarma bağlamında bir arayüzün en tehlikeli davranışı, olmayan
bir bilgiyi varmış gibi göstermektir. Bir harita üzerinde duran işaret, onu gören
kişiye "burada bir şey bulundu" der. Elimdeki veride o "burası" yoksa, işareti
koymak bilgi değil zarar üretir. Bu yüzden arayüz kodunu yazmadan önce, elimde
gerçekten koordinat olup olmadığını saydım.

Modelin bu akıştaki rolünü de baştan sınırlamak gerekiyor. Model karar vermiyor.
Model, bir operatörün tek tek bakması gereken kare yığınını önceliklendiriyor:
hangi karelerde insan olabilecek bölgeler var, bunlar karenin neresinde. Nihai
yargı operatörde. Arayüzün dili bu sınırı yansıtmak zorunda, çünkü arayüz
"tespit edildi" derse kullanıcı modeli hakem sanır. Bunu koda da yazdım:
kutuların başlığı "insan adayları", ve her sonuç ekranında kesin tespit
olmadığını söyleyen bir not duruyor.

Haftayı beş doğrulama kapısına böldüm: API sözleşmesi, konum dürüstlüğü, operatör
akışı, geometri ve kalite. Kapılar bölüm 6.8'de tek tabloda. Bir kapı kalırsa
haftanın kapandığını yazmıyorum.

---

### 6.2. API sözleşmesinin çıkarılması

Arayüz yazmaya başlamadan önce bir şeyi bilerek yapmadım: backend'in ne
döndürdüğünü tahmin etmedim. Frontend'i uydurma bir JSON'a göre yazmak, sonra
gerçek API'ye bağlandığında alan adlarının tutmadığını görmek, bu tür projelerde
en sık kaybedilen zamandır. Onun yerine sözleşmeyi iki bağımsız kaynaktan
çıkardım.

Birinci kaynak kod: URL tanımları, view'lar, serializer'lar, izin sınıfları ve
sayfalama ayarları. İkinci kaynak çalışan sistemin kendisi: yerel Docker
yığınını ayağa kaldırıp geçici bir kullanıcıyla her uca gerçek istek attım ve
dönen gövdeyi okudum. İki kaynak çelişirse kazanan çalışan sistemdir, çünkü
frontend koda değil yanıta bağlanır.

Bu çalışmanın çıktısı `hafta5_api_sozlesmesi.csv` dosyası: on dört işlem, her
biri için yöntem, yol, kimlik doğrulama gereksinimi, istek ve yanıt alanları,
başarı kodu, beklenen hata kodları, sayfalama davranışı, kaynak kod konumu ve
doğrulama biçimi. Doğrulama biçimi sütunu önemli — her satırın kodla mı, çalışan
istekle mi, testle mi doğrulandığını ayrı ayrı söylüyor, böylece "bu alan gerçekten
var mı" sorusu açık kalmıyor.

On dört işlemi okunabilirlik için gruplayarak veriyorum.

| Grup | İşlemler | Kimlik doğrulama | Sayfalama |
|---|---|---|---|
| Kimlik | `POST /api/auth/token/`, `POST /api/auth/token/refresh/` | Hayır (kimlik bilgisi gövdede) | Yok |
| Sistem | `GET /api/health/` | Hayır | Yok |
| Görev | `GET /api/missions/`, `POST /api/missions/`, `GET /api/missions/{id}/` | Evet | Liste uçlarında sayfa başına 20 |
| Kare | `GET /api/missions/{id}/frames/`, `POST /api/missions/{id}/frames/`, `GET /api/frames/{id}/image/` | Evet | Liste ucunda sayfa başına 20 |
| Model | `GET /api/models/` | Evet | Sayfa başına 20 |
| Tarama | `POST /api/missions/{id}/runs/`, `GET /api/missions/{id}/runs/`, `GET /api/runs/{id}/` | Evet | Liste ucunda sayfa başına 20 |
| Tespit | `GET /api/runs/{id}/detections/` | Evet | Sayfa başına 20 |

*Bu tablo ne söylüyor: Arayüzün ihtiyaç duyduğu her şey on dört işleme sığıyor ve
kimlik doğrulaması istemeyen yalnızca üç uç var — ikisi token alma, biri sistem
sağlığı. Geri kalan her uç `Authorization` başlığı istiyor, yani arayüzün
oturumsuz erişebileceği hiçbir görev verisi yok. Liste uçlarının hepsi sayfalı,
bu da arayüzün "hepsini çektim" varsayamayacağı anlamına geliyor.*

#### 6.2.1. Eksik çıkan üç uç

Sözleşmeyi çıkarırken arayüzün zorunlu akışını mevcut uçlarla tamamlayamadığım
üç yer buldum.

Birincisi görev ayrıntısı. `GET /api/missions/{id}/` diye bir uç yoktu; o adres
404 dönüyordu. Görev listesi vardı, ama operatör bir görev sayfasını yeniden
yüklediğinde veya adresi yer imine aldığında arayüzün o tek görevi okuyabilmesi
gerekiyor. Listeyi çekip içinden süzmek, sayfalama yüzünden doğru bile değil:
aranan görev ikinci sayfadaysa bulunamaz.

İkincisi koşu listesi. Tarama başlatma yolu yalnızca `POST` kabul ediyordu; aynı
adrese `GET` atınca 405 dönüyordu. Tarama başlatıldığında koşu kimliği yanıtla
geliyor, ama o kimliği yalnızca istemci belleğinde tutarsam sayfa yenilendiğinde
kayboluyor ve arayüz "bu görevde bir tarama var mı, hangi durumda" sorusunu
cevaplayamıyor.

Üçüncüsü görüntü erişimi. Kare serializer'ı `image` alanında bir adres
döndürüyor, ama o adres medya klasörünün altında ve **kimlik doğrulaması
olmadan** servis ediliyor. Token'ı adrese sorgu parametresi olarak eklemek çözüm
değil: adres tarayıcı geçmişinde, sunucu günlüğünde ve `Referer` başlığında
kalır. Arayüzün görüntüyü `Authorization` başlığıyla okuyabileceği bir uca
ihtiyacı vardı.

Üçünü de ekledim. Ekleme kararını dar tuttum: **yeni veri modeli ve yeni
migration yok.** Üçü de mevcut modellerin üzerinde duruyor, mevcut alanların
anlamını değiştirmiyor ve sahiplik süzgeci mevcut uçlardaki kalıbı izliyor —
başkasının kaydı 403 değil 404 dönüyor, böylece kaydın varlığı bile sızmıyor.

Görüntü ucunda dosya yolunun istemciden gelmemesine ayrıca dikkat ettim. Uç
yalnızca kare birincil anahtarını alıyor, dosya adını veritabanı kaydından
okuyor. Bu, yol gecişi (path traversal — kullanıcının `../` gibi parçalarla
izinsiz dosyalara ulaşması) yüzeyini tamamen ortadan kaldırıyor, çünkü
kullanıcının yol üzerinde hiçbir etkisi yok.

#### 6.2.2. Serializer'a eklenen salt okunur özetler

Görev listesinin operatöre işe yarar bir şey söylemesi için kare sayısı, kare
durumlarının kırılımı ve son taramanın durumu gerekiyordu. Bunların hiçbiri
serializer'da yoktu.

Üçünü de **salt okunur** alan olarak ekledim. Mevcut alanların anlamına
dokunmadım, yazma yüzeyini değiştirmedim. Sayımları tek sorguda toplu hesaplattım
ve koşuları önceden yükledim; aksi halde listedeki her görev için ayrı sorgu
çalışır ve görev sayısı arttıkça sorgu sayısı da artardı.

Kare sayımları sözlüğünde bir ayrıntı var: sıfır olan durum da anahtar olarak
bulunuyor. Backend'in beş kare durumunun hepsi her yanıtta yer alıyor, değeri
sıfır olsa bile. Böylece istemci "bu anahtar var mı" diye savunma kodu yazmak
zorunda kalmıyor.

#### 6.2.3. Sözleşmenin kısıtları

Sözleşmeyi çıkarırken arayüzü şekillendiren üç kısıt buldum.

Tarama başlatma ucu 202 dönüyor. Bu "kabul edildi", "bitti" değil. Yanıttaki
durum alanı daima bekliyor durumunda; gerçek ilerleme ayrı bir uçtan izleniyor.
Arayüzün 202'yi başarı mesajı olarak göstermemesi gerekiyor, çünkü henüz hiçbir
kare işlenmedi.

Toplu dosya yükleme ucu, gönderilen dosyalardan biri geçersizse **isteğin
tamamını** 400 ile reddediyor. Yani beş dosyadan biri bozuksa diğer dördü de
yüklenmiyor. Bunu backend'de değiştirmek yerine arayüzde çözdüm: dosyalar tek tek
gönderiliyor. Böylece kısmi başarı korunuyor ve kullanıcı hangi dosyanın neden
eklenemediğini görebiliyor.

Tarama iptali veya yeniden başlatma ucu yok. Arayüze böyle bir düğme koymadım.
Çalışmayan bir düğme, olmayan bir özellikten daha kötüdür.

---

### 6.3. Frontend mimarisi

Arayüzü React, Vite ve TypeScript ile kurdum; sunucu durumunu TanStack Query
tutuyor, sayfa geçişini bir yönlendirici sağlıyor. Arayüz dili Türkçe.

Yığın seçimi bu haftanın araştırma konusu değildi, bu yüzden kararı kısa
tutuyorum: TypeScript'i, sözleşmeyi derleme zamanında zorlamak için seçtim —
backend bir alan adı değiştirirse arayüz çalışma anında bozulmak yerine derlemede
hata versin istiyorum. TanStack Query'yi, sunucu durumunu elle yönetmenin
ürettiği hata sınıfını (bayat önbellek, yarış koşulları, unutulmuş yükleme
durumları) tekrar yazmamak için seçtim.

Tipler gerçek serializer çıktılarından yazıldı. Bunu bir kural olarak uyguladım:
arayüzde geçen hiçbir alan, gerçek bir yanıtta görmediğim bir alan değil. Durum
değerleri backend'in kendi değerleriyle birebir aynı ve **çevrilmiyor**. Türkçe
etiketler ayrı bir eşlemede duruyor. Böylece bir durum değerinin yazımı Türkçe
metin yüzünden bozulmuyor ve backend yeni bir durum eklerse eşleme eksik kalıp
fark ediliyor.

Sorgu anahtarlarını tek bir dosyada topladım. Bunun nedeni pratik: bir yazma
işleminden sonra hangi sorguların geçersiz kılınacağı, anahtarlar kodun içine
dağılmışsa kolayca yanlış hedeflenir ve arayüz sessizce bayat veri gösterir.
Anahtarlar tek yerdeyken bu hata görünür oluyor.

Her veri çeken ekranda dört durum ayrı ayrı ele alındı: yükleniyor, boş, hata ve
veri. Hata durumunda kullanıcıya ham JSON gösterilmiyor; backend'in hata gövdesi
okunabilir bir cümleye çevriliyor ve yanına "Yeniden dene" düğmesi konuyor. Boş
durum da yönlendirici: görev yoksa "Henüz görev yok" deyip ne yapılacağını
söylüyor.

#### 6.3.1. Yoklama ve yoklamanın durması

Tarama sürerken arayüzün koşu durumunu düzenli aralıklarla sorması gerekiyor.
Buradaki asıl tasarım kararı sormak değil, **durmak**.

Koşu durumu sorgusunun yenileme aralığı sabit bir sayı değil, koşunun durumuna
bakan bir fonksiyon. Koşu terminal duruma (tamamlandı veya başarısız) ulaştığında
fonksiyon "yenileme yok" döndürüyor ve zamanlayıcı duruyor. Kare listesi sorgusu
da aynı şarta bağlı: yalnızca aktif bir tarama varken yokluyor.

Bunun ölçülmesi gerekiyordu, çünkü durmayan bir yoklama sessizce çalışır ve
kimse fark etmez. Tarayıcıda gerçek koşu üzerinde ölçtüm: koşu tamamlandıktan
sonraki **10 saniyede koşu durumu ucuna giden istek sayısı 0**. Aynı davranışı
otomatik test de koruyor.

#### 6.3.2. Varsayılan modelin seçimi

Tarama başlatma formunda hangi modelin varsayılan geleceği küçük ama kritik bir
karar. Model adını veya kimliğini koda yazmak, model kaydı değiştiğinde arayüzün
sessizce yanlış modeli seçmesi demek.

Onun yerine arayüz, model listesinden **çerçeve alanına** bakıyor: gerçek ONNX
dedektörünü çalıştıran kaydı tercih ediyor, yoksa listenin ilkine düşüyor.
Çerçeve alanı zaten backend'in dedektör seçiminde kullandığı alan, yani arayüz
backend'le aynı ölçüte bakıyor. Tarayıcıda doğruladım: form açıldığında gerçek
model seçili geliyor, sahte dedektör kaydı değil.

#### 6.3.3. Görüntüleme eşiği bir metrik değildir

Sonuç ekranında bir güven eşiği kaydırıcısı var. Bunun ne **olmadığını** yazmak,
ne olduğunu yazmaktan daha önemli.

Bu kaydırıcı yalnızca ekranda çizilen kutuları süzüyor. Modeli yeniden
çalıştırmıyor, kayıtlı tespitleri değiştirmiyor ve **bir değerlendirme metriği
değil**. Eşiği kaydırmak yeni bir recall veya yanlış pozitif oranı iddiası
üretmez; önceki bölümlerdeki metrikler belirli bir protokolle, belirli bir veri
kümesi üzerinde ölçüldü ve arayüzdeki bir kaydırıcı onları değiştirmez.

Kaydırıcının başlangıç değeri de koda yazılmıyor, koşunun kendi eşik değerinden
geliyor. Arka planda kutular sabit ve düşük bir tabanla saklandığı için tek bir
pahalı taramadan daha düşük eşikler yeniden tarama yapmadan sorulabiliyor — bu,
önceki bölümde verilmiş bir tasarım kararının arayüzdeki karşılığı. Bütün bunlar
kaydırıcının hemen altında kullanıcıya de yazıyor.

---

### 6.4. JWT oturumu ve güvenlik sınırı

Backend kimliği `Authorization` başlığında bekliyor. Bu, arayüzün token'ı bir
yerde tutması gerektiği anlamına geliyor ve burada kolay bir cevap yok.

Uyguladığım davranışlar şunlar. Giriş, access ve refresh token'larını alıyor.
Herhangi bir istek 401 alırsa istemci katmanı token'ı bir kez yeniliyor ve isteği
tekrarlıyor; kullanıcı bir şey görmüyor. Yenileme de başarısız olursa oturum
kapanıyor, saklanan her şey siliniyor ve sorgu önbelleği temizleniyor. Çıkış aynı
temizliği yapıyor. Token hiçbir yerde adrese konmuyor — görüntüler bile başlıkla,
ikili veri olarak indiriliyor.

![Gözcü giriş ekranı. Kullanıcı adı ve parola alanları, giriş düğmesi ve hem üst şeritte hem form altında yinelenen kapsam uyarısı.](rapor/gorseller/hafta5/01_giris_ekrani.png)

Bu görsel, kapsam uyarısının oturum açılmadan önce de göründüğünü kanıtlıyor:
kullanıcı sistemi ilk gördüğü anda bunun bir prototip olduğunu okuyor.

Oturumun sayfa yenilemesinde sürmesi bilinçli bir tercih. Operatör bir tarama
izlerken sayfayı yenilediğinde yeniden giriş yapmak zorunda kalırsa arayüz
kullanılamaz hâle gelir. Yenilemeden sonra arayüz saklanan token'la devam ediyor;
token gerçekten geçersizse ilk korumalı istek 401 alıyor ve yenileme akışı
devreye giriyor. Bunu tarayıcıda, saklanan token'ı kasten bozarak doğruladım:
arayüz kullanıcıyı giriş ekranına atmadan listeyi getirdi.

Aynı anda birden fazla isteğin 401 alması ayrı bir sorun. Her 401 kendi
yenilemesini başlatırsa backend'e aynı refresh token'ıyla birden çok istek gider
ve yarış oluşur. İstemci katmanında uçuştaki yenilemeyi paylaştırdım: eşzamanlı
401'lerin hepsi **tek** yenileme isteğini bekliyor. Testte dört eşzamanlı istekle
doğruladım, yenileme sayısı 1.

Şimdi sınırı açıkça yazıyorum, çünkü bu bölümün en kolay gizlenecek kısmı.

Token'ı `localStorage` içinde tutuyorum. Backend'de HTTP-only çerez desteği yok —
oturum çerezi üreten bir uç mevcut değil. Seçenek yalnızca bellekle
`localStorage` arasındaydı. Bellekte tutmak her sayfa yenilemesinde oturumu
kapatır ve operatör için kullanılamaz; üstelik siteler arası betik çalıştırma
(XSS — saldırganın sayfaya kendi kodunu sokması) karşısında belirgin bir kazanç
da sağlamaz, çünkü sayfada kod çalıştırabilen biri zaten kullanıcı adına istek
atabilir. `localStorage`'ı seçtim ve bedeli şu: **bu arayüzde bir XSS açığı,
oturumun çalınması demektir.**

Buna bir şey daha eklemek gerekiyor: yenileme ucu **rotasyon yapmıyor.** Yanıt
yalnızca yeni bir access token döndürüyor, refresh token değişmiyor. Yani çalınan
bir refresh token'ı kendi ömrü boyunca geçerli kalıyor ve kullanımı tespit
edilmiyor.

Bu düzeni güvenli bir üretim kimlik doğrulaması olarak sunmuyorum. Bir eğitim
prototipinde kabul edilmiş bir sınır. Gerçek dağıtım için HTTP-only çerez,
refresh rotasyonu ve token iptali gerekir; hiçbiri bu haftanın kapsamında değil.

---

### 6.5. Operatör görev akışı

Arayüzün kurduğu akış şu: giriş, görev listesi, görev oluşturma, kare ekleme,
model seçimi ve tarama başlatma, ilerleme izleme, sonuçların incelenmesi, çıkış.

Görev listesi her görev için adı, kare sayısı, kare durumlarının kırılımı, son
taramanın durumu, kullanılan model ve oluşturulma zamanını gösteriyor. Taraması
olmayan görevde "Tarama yapılmadı" yazıyor — uydurma bir durum rozeti değil.

![Gözcü görev listesi ekranı. Üstte kalıcı kapsam uyarısı, altında iki görevin adı, kare sayısı, kare durum kırılımı, son tarama durumu, kullanılan model ve oluşturulma zamanı.](rapor/gorseller/hafta5/02_gorev_listesi.png)

Bu görsel iki şeyi kanıtlıyor: serializer'a eklenen salt okunur özetlerin gerçek
veriyle dolduğunu, ve kapsam uyarısının kaydırmadan görünür olduğunu.

Görev oluşturma formunda ad zorunlu ve boşken gönderim düğmesi kapalı. Başarılı
oluşturmadan sonra arayüz doğrudan görev ayrıntısına geçiyor. İstek uçarken düğme
kilitleniyor; üç kez tıklandığında giden istek sayısını testle ölçtüm, 1.

Kare ekleme bölüm 6.2.3'te anlattığım nedenle dosyaları tek tek gönderiyor.
Kullanıcı her dosya için ayrı sonuç görüyor: yüklendi, zaten ekliydi veya hata
mesajı. "Zaten ekliydi", backend'in aynı görevde aynı dosya özetine ikinci kayıt
açmaması davranışının arayüzdeki karşılığı.

Tarama başlatıldığında düğme ve model seçimi kilitleniyor, ilerleme çubuğu
gerçek kare sayılarından hesaplanıyor ve kare tablosu durumları backend'in kendi
değerleriyle gösteriyor.

![Gözcü görev ayrıntısı, tarama sürerken. Tarama durumu Çalışıyor, ilerleme çubuğu, kare sayaçları, kilitlenmiş tarama düğmesi ve kareleri İşleniyor durumunda gösteren tablo.](rapor/gorseller/hafta5/03_gorev_ayrinti_tarama_suruyor.png)

Bu görsel, yoklamanın çalıştığını ve çift tarama korumasının etkin olduğunu
gösteriyor: durum "Çalışıyor" iken tarama düğmesi kapalı ve nedeni yazılı.

Sayfa yenileme davranışını ayrıca doğruladım, çünkü koşu kimliği yalnızca
istemci belleğinde tutulsaydı yenileme sonrası kaybolurdu. Görev ayrıntısı
yeniden yüklendiğinde arayüz koşu listesi ucundan görevin son koşusunu buluyor ve
durumunu olduğu gibi gösteriyor. Bölüm 6.2.1'de eklediğim koşu listesi ucunun
gerekçesi tam olarak bu.

Akışın tamamını gerçek backend üzerinde uçtan uca çalıştırdım. Entegrasyon koşusu
gerçek ONNX modeliyle, gerçek iki veri kümesi görüntüsüyle yapıldı; koşu
tamamlandı, iki kare işlendi, başarısız kare olmadı.

Bu koşunun ne olmadığını açıkça yazıyorum: **bu bir performans ölçümü değildir.**
Önceki bölümdeki 157 karelik süre koşusunu tekrarlamadım ve buradan hiçbir hız
sayısı türetmedim. İki karelik koşu yalnızca "arayüzden başlatılan tarama gerçek
model hattında baştan sona çalışıyor mu" sorusunun işlevsel cevabıdır. Model
doğruluğu hakkında da yeni bir iddia kurmuyorum; önceki bölümlerin metrikleri
olduğu gibi geçerli.

---

### 6.6. Tespit kutularının görüntü üzerinde gösterilmesi

Backend tespit kutularını **orijinal görüntü pikselinde** veriyor. Kullandığım
görüntüler 4000×3000 piksel; ekranda ise görüntü çok daha küçük çiziliyor ve
boyutu pencereye göre değişiyor. Kutuyu doğru yere koymak bir ölçek problemi.

İki yol vardı. Birincisi, görüntünün ekrandaki piksel boyutunu JavaScript ile
ölçüp kutuları piksel cinsinden yerleştirmek. Bu yol her yeniden boyutlandırmada
yeniden ölçüm ister ve ölçüm bir kare geç kalırsa kutular kayar. İkincisi,
kutuları **yüzde** olarak vermek: yüzdeyi tarayıcı, sarmalayıcının o anki
boyutuna göre kendisi çözer, pencere büyüyüp küçülürken hiçbir JavaScript
çalışmadan hiza korunur.

İkincisini seçtim. Dönüşüm saf bir fonksiyonda duruyor ve doğrudan test
edilebiliyor: kutu koordinatı ile karenin doğal ölçüsü girip yüzde yerleşimi
alıyorum. Fonksiyon ayrıca kutuyu görüntü sınırlarına kırpıyor. Backend zaten
kırpıyor, ama arayüz buna güvenmiyor — bozuk veya eski bir kayıt görüntünün
dışına taşmasın diye ikinci kez kırpılıyor. Ölçüsü sıfır kalan veya tamamen
görüntü dışında olan kutu hiç çizilmiyor, çünkü sıfıra bölmek kutuyu ekranın
rastgele bir yerine düşürür.

#### 6.6.1. En-boy oranı hatası ve 1 piksellik kayma

Tarayıcıda sayısal ölçüm yaparken bir hata buldum. Kutuların oturduğu
sarmalayıcıya, görüntü yüklenirken düzen zıplamasın diye en-boy oranı vermiştim.
802 piksel genişlikte sarmalayıcının yüksekliği 601 piksele yuvarlanıyordu;
görüntü ise kendi doğal oranıyla 602 piksel çiziliyordu. Kutular yüzdeyi
sarmalayıcının kutusuna göre çözdüğü için aradaki **1 piksellik fark** alt
kenarda hizayı kaydırıyordu.

Oranı sarmalayıcıdan alıp **görüntünün kendisine** verdim. Böylece sarmalayıcı
tam görüntü kadar oluyor, yükleme sırasında yer ayırma davranışı da korunuyor.

Düzeltmeden sonra hizayı gerçek görüntü ve gerçek tespitler üzerinde ölçtüm: 18
kutunun hepsi görüntü sınırları içinde ve ölçtüğüm kutularda beklenen konumdan
sapma **0,01 pikselin altında**. Yeniden boyutlandırma dayanıklılığını da
ölçtüm: pencere daraltıldığında görüntü **802 pikselden 333 piksele** indi ve
bütün kutular hizalı kaldı.

![Gözcü tespit inceleme ekranı. Solda gerçek veri kümesi görüntüsü üzerinde çizilmiş insan adayı kutuları, sağda görüntüleme eşiği açıklaması, kare bilgisi, "Konum bilgisi mevcut değil" paneli ve güven skorlarıyla aday listesi.](rapor/gorseller/hafta5/04_tespit_inceleme.png)

Bu görsel bölümün üç iddiasını birden kanıtlıyor: kutular gerçek görüntü üzerinde
oturuyor, konum paneli yokluğu açıkça söylüyor, ve aday listesi "insan adayları"
dilini kullanıyor.

#### 6.6.2. Tespit bulunmadığında ne yazıyor

Bir karede aday yoksa arayüz "Bu karede, seçilen görüntüleme eşiğinde insan adayı
bulunmadı" diyor. Cümlenin iki parçası da kasıtlı. "İnsan adayı bulunmadı",
"insan yok" demek değil — model bulmadı, o kadar. "Seçilen görüntüleme eşiğinde"
ise sonucun eşiğe bağlı olduğunu hatırlatıyor; kullanıcı eşiği düşürürse aday
görebilir.

Aynı temkinli dil kutuların kendisinde de var. Panel başlığı "İnsan adayları",
ve altında her adayın operatör tarafından doğrulanması gerektiği, bunun kesin bir
insan tespiti olmadığı yazıyor. Kutuların erişilebilir adı da aynı dili
kullanıyor, yani ekran okuyucuyla gezen bir kullanıcı "insan adayı" ifadesini
duyuyor.

Erişilebilirlik tarafında iki şeyi daha ölçtüm. Klavyeyle gezerken odak her
denetimde görünür kalıyor: tarayıcıda odak zincirini gezdim ve denetimlerin
hepsinde belirgin bir odak çerçevesi bulduğumu doğruladım. Dar ekranda düzen de
bozulmuyor: 390 piksel genişlikte yatay kaydırma oluşmuyor, taşan öge yok ve
tespit kutuları küçülmüş görüntü üzerinde hizalı kalıyor. Durum rozetlerinde renk
tek başına anlam taşımıyor; her rozet renkle birlikte metin de gösteriyor, böylece
renk ayrımı yapamayan bir operatör durumu yine okuyabiliyor.

---

### 6.7. GPS kaynağı kararı

Haritayı yazmadan önce şu soruyu sayıyla cevapladım: elimde gerçekten koordinat
var mı?

Taramayı `scripts/22` yapıyor. Script hiçbir çıkarım çalıştırmıyor, yalnızca
metadata okuyor; bu yüzden ucuz ve veri kümesinin tamamı tek koşuda taranabildi.
Sonuçlar `hafta5_gps_kaynak_karari.csv` dosyasında, ölçüm satırlarıyla karar
satırları ayrı sütunda işaretli.

| İncelenen kaynak | Bölüm | İncelenen | EXIF bulunan | GPS bulunan | Enlem/boylam bulunan |
|---|---|---|---|---|---|
| Görüntü dosyası | train | 1106 | 0 | 0 | 0 |
| Görüntü dosyası | valid | 316 | 0 | 0 | 0 |
| Görüntü dosyası | test | 157 | 0 | 0 | 0 |
| **Görüntü dosyası** | **toplam** | **1579** | **0** | **0** | **0** |
| Veritabanı kare kaydı | yerel | 494 | 0 | — | 0 |
| Yan dosya (uçuş günlüğü vb.) | depo | — | — | — | 0 |

*Bu tablo ne söylüyor: Veri kümesinin üç bölümünün tamamında, 1579 görüntünün
hiçbirinde EXIF bloğu yok. EXIF olmadığı için GPS alt bloğu ve enlem/boylam da
yok — sıfırlar birbirinden bağımsız üç ayrı eksiklik değil, aynı eksikliğin üç
sonucu. Alım hattından geçmiş 494 kare kaydında da konum alanları boş, yani
eksiklik veri kümesinden veritabanına olduğu gibi taşınmış. Depoda koordinat
taşıyan bir uçuş günlüğü veya yan dosya da bulunmuyor.*

#### 6.7.1. Ölçüm, açıklama ve karar

Bu üç şeyi birbirine karıştırmamak gerekiyor.

**EXIF yokluğu bir ölçümdür (BULGU).** 1579 görüntü tarandı, sayılar yukarıdaki
tabloda ve üreten script belli. Bu sayı tartışmaya açık değil.

**Bu yokluğun nedeni bir hipotezdir (HİPOTEZ).** Depoda, veri kümesinin bir
Roboflow dışa aktarımıyla geldiğini söyleyen bir künye dosyası var; dışa aktarım
tarihi de yazılı. Yani veri zincirinde böyle bir adımın bulunduğu kanıtlı. Ama
"EXIF'i o adım sildi" iddiası kanıtlı değil: özgün HERIDAL yayınındaki
görüntülerde EXIF olup olmadığını ölçmedim, elimde o kopya yok. Kaynakta hiç
EXIF olmaması da, aktarımda silinmesi de aynı gözlemi üretir. Bu yüzden nedeni
olası bir veri zinciri açıklaması olarak yazıyorum, kesin sebep olarak değil.
Ayrımın pratik sonucu şu: özgün veri bulunabilirse konum kazanma ihtimali var,
ama bu ihtimal ölçülmedi.

**Konumu kullanmamak bir karardır (KARAR).** Ölçüm "koordinat yok" diyor; buna
karşılık ne yapılacağı mühendislik kararı. Kararım şu: arayüz koordinat
üretmiyor. Kayıtta gerçek değer varsa gösteriliyor ve kaynağı yazılıyor, yoksa
"Konum bilgisi mevcut değil" deniyor ve nedeni kısaca açıklanıyor.

#### 6.7.2. Üretilmeyecek koordinatlar

Koordinat üretmenin cazip ama yanlış birkaç yolu var; hepsini açıkça dışarıda
bıraktım.

Dosya adından üretmek: adlar kaynak önekini ve sıra numarasını taşıyor, konum
taşımıyor. Ondalık derece kalıbına uyan ad sayısını da saydım, sıfır.

Dosya sırasından veya karo indeksinden üretmek: bunlar veri kümesi içi
düzenleme bilgisi, coğrafi bilgi değil. Sıra numarasını enleme çevirmek, sayının
sayı olmasından başka hiçbir gerekçesi olmayan bir uydurma olur.

Görüntü pikselinden üretmek: bir tespit kutusunun merkezini dünya koordinatına
çevirmek için kameranın konumu, irtifası, yönelimi ve görüş açısı gerekir.
Bunların hiçbiri elimde yok. Piksel ile dünya arasında jeoreferans olmadan
kurulan her dönüşüm, doğru görünen ama tamamen uydurma bir sayı üretir. Arama
kurtarma bağlamında bunun maliyeti yüksek.

Gelecekte gösterim amaçlı demo koordinat kullanılırsa, sentetik olduğu hem
veride hem arayüzde görünür olmalı ve gerçek bir uçuş kaydı gibi sunulmamalı.
Koordinat saklanmaya başlandığında değerin yanında **kaynağının** da saklanması
gerektiğini not ettim; bu alan bu hafta eklenmedi.

---

### 6.8. Doğrulama kapıları

Haftayı beş kapıya bölmüştüm. Kapıların sonucu aşağıda; sayılar test
çıktılarından ve doğrulama kaydından okundu.

| Kapı | Ne soruyor | Sonuç | Dayanak |
|---|---|---|---|
| A — API | Kullanılan her uç gerçek kod veya çalışan istekle doğrulandı mı, uydurma alan var mı | Geçti | 14 işlem, her satırda doğrulama biçimi işaretli |
| B — Konum | Koordinat kaynakları ölçüldü mü, olmayan konum varmış gibi gösteriliyor mu | Geçti | 1579 görüntü + 494 kare kaydı tarandı, arayüz koordinat üretmiyor |
| C — Operatör akışı | Giriş, görev, kare, tarama, sonuç ve hata durumları çalışıyor mu | Geçti | 34 kontrolün tamamı geçti |
| D — Geometri | Kutular gerçek görüntüde doğru oturuyor, yeniden boyutlandırmada hizalı kalıyor mu | Geçti | Sapma < 0,01 piksel; 802 → 333 piksel yeniden boyutlandırmada hiza korundu |
| E — Kalite | Testler, lint, tip denetimi, derleme ve gerçek entegrasyon geçiyor mu | Geçti | Aşağıdaki tablo |

*Bu tablo ne söylüyor: Beş kapının beşi de geçti, yani bu haftanın kapandığını
yazabiliyorum. Kapıların hepsinin bir dayanağı var ve dayanaklar ya sayılmış ya
da bir dosyaya yazılmış; "çalışıyor gibi görünüyor" tek başına kapı geçirmiyor.*

Kalite kapısının ayrıntısı:

| Denetim | Sonuç |
|---|---|
| Arayüz testleri | 7 dosyada 63 test, tamamı geçti |
| Arayüz lint denetimi | 0 hata |
| TypeScript tip denetimi | Geçti |
| Arayüz üretim derlemesi | Geçti |
| Backend testleri | 97 test, tamamı geçti |
| Ölçüm script'i testleri | 145 test, tamamı geçti |
| Terminal durumdan sonra yoklama | 10 saniyede 0 istek |
| Tarayıcı konsolu | Uygulama kaynaklı hata yok |
| Ağ istekleri | Beklenmeyen başarısız istek yok |

*Bu tablo ne söylüyor: Üç ayrı test paketi de geçiyor ve arayüz üretim derlemesi
alınabiliyor. Backend testlerinin 97'ye çıkması bu haftanın eklemesi — önceki
bölüm sonunda 80 testti, eklenen üç uç için 17 test yazıldı. Yoklama satırı
önemli çünkü durmayan bir yoklama hata vermez, yalnızca sessizce kaynak tüketir;
ölçülmeseydi fark edilmezdi.*

Doğrulamanın 34 kontrolü `hafta5_frontend_dogrulama.csv` dosyasında. Her satır
beklenen davranışı, gerçekleşeni, doğrulama türünü ve kanıtı taşıyor.
Kontrollerin 16'sı hem tarayıcıda hem otomatik testle, 9'u yalnızca tarayıcıda,
geri kalanı otomatik testle doğrulandı.

Konsol satırına bir açıklama borçluyum. Sessiz token yenileme senaryosunda
tarayıcının kendi günlüğünde bir 401 satırı görünüyor. Bu uygulamanın hatası
değil: tarayıcı başarısız her yanıtı günlüğe yazar, uygulama o isteği yenileyip
tamamlıyor ve kullanıcı hiçbir kesinti görmüyor. Bunu gizlemek yerine doğrulama
kaydına not olarak yazdım.

---

### 6.9. Süreçte bulunan kusurlar

Bu bölümde bulduğum kusurları, ne beklediğim ve ne öğrendiğimle birlikte
yazıyorum.

**Eksik üç uç.** Arayüzün zorunlu akışının mevcut API ile tamamlanacağını
varsaymıştım. Sözleşmeyi çıkarırken görev ayrıntısının 404, koşu listesinin 405
döndüğünü ve görüntünün kimlik doğrulamalı bir yolu olmadığını gördüm. Üçünü de
en küçük yüzeyle ekledim; yeni model veya migration gerekmedi. Ders: sözleşmeyi
frontend kodundan **önce** çıkarmak bu üç eksiği ilk günde görünür yaptı. Kod
yazdıktan sonra keşfedilseydi üçü de yeniden yazım gerektirirdi.

**1 piksellik kutu kayması.** Kutuların hizalı olduğunu düşünüyordum, çünkü gözle
bakınca hizalı görünüyorlardı. Tarayıcıda kutu dikdörtgenini beklenen piksel
konumuyla sayısal olarak karşılaştırınca sarmalayıcı ile görüntünün yüksekliği
arasında 1 piksel fark olduğunu gördüm. En-boy oranını sarmalayıcıdan görüntüye
taşıdım. Ders: geometri gözle doğrulanmaz. Gözle bakmak 1 pikseli yakalamaz, ama
1 piksel küçük bir hedefin kutusunu hedefin dışına taşıyabilir.

**Zorunlu çıkışta kalan kullanıcı adı.** Çıkış davranışını doğrularken, elle
çıkışın her şeyi temizlediğini ama yenileme başarısız olunca tetiklenen zorunlu
çıkışın kullanıcı adını tarayıcı deposunda bıraktığını gördüm. Gizli bir veri
değil, ama iki çıkış yolunun farklı davranması bir tutarsızlık ve bu tür
tutarsızlıklar zamanla büyür. İki yolu aynı temizlik fonksiyonuna bağladım ve
testle sabitledim. Ders: aynı işi yapan iki yol varsa ikisi de test edilmeli.

**Bayat konteyner imajı.** Backend testleri bir noktada hiç toplanamadı: bir
bağımlılık eksikti. Kodda değil ortamda sorun vardı — web konteyneri, bağımlılık
listesine yeni paketler eklenmeden önce üretilmiş bir imajla çalışıyordu. İmajı
yeniden ürettim. Ders: "testler çalışmıyor" bulgusunun kaynağı her zaman kod
değil; ortamın kodla aynı sürümde olduğunu doğrulamak ayrı bir adım.

**Kimlik doğrulamasız medya erişimi — bu bölüm yazılırken hâlâ açık.** Arayüze
kimlik doğrulamalı görüntü ucunu ekledim ve arayüz yalnızca onu kullanıyor. Ama
eski medya yolu geliştirme ayarında hâlâ açık: adresi bilen biri, oturum açmadan
görev görüntüsünü indirebiliyor. Bunu bu hafta kapatmadım, çünkü doğru çözümü
kullanıcı bazlı erişim modeliyle birlikte kurmak gerekiyor — şu an her kullanıcı
yalnızca kendi oluşturduğu görevleri görüyor, ama görev üyeliği diye bir kavram
yok. Kısıt olarak kaydettim ve sıradaki adımın parçası yaptım.

---

### 6.10. Kısıtlar

Bu bölümün sonuçları aşağıdaki sınırlar içinde geçerli.

**Token tarayıcı deposunda.** HTTP-only çerez desteği olmadığı için token
`localStorage` içinde. Bir XSS açığı oturumun çalınması demektir. Kabul edilmiş
bir prototip sınırı, güvenli üretim kimlik doğrulaması değil.

**Yenileme rotasyonu yok.** Yenileme ucu yalnızca yeni access token döndürüyor;
refresh token değişmiyor ve iptal edilemiyor.

**Medya yolu açık.** Kimlik doğrulamasız medya erişimi geliştirme ayarında hâlâ
mümkün. Arayüz kullanmıyor ama açık duruyor.

**Toplu yükleme atomik.** Tek bozuk dosya, aynı istekteki bütün dosyaların
reddedilmesine yol açıyor. Arayüz dosyaları tek tek göndererek bunu aşıyor, ama
backend davranışı değişmedi ve çok sayıda dosyada tek tek gönderim yavaş.

**Tarama iptali yok.** Başlatılan bir taramayı durdurma veya yeniden başlatma ucu
bulunmuyor.

**Gerçek GPS yok.** Taranan 1579 görüntünün hiçbirinde koordinat yok. Bu yüzden
harita kurulmadı ve konum doğruluğu hakkında hiçbir iddia yok.

**Entegrasyon koşusu performans ölçümü değil.** Gerçek modelle yapılan koşu iki
karelik. İşlevsel kanıt üretir, hız veya doğruluk sayısı üretmez.

**Harita ve çok kullanıcılı yetkilendirme yok.** Görev üyeliği, rol ayrımı ve
harita bu haftanın kapsamı dışında kaldı. Şu an erişim tek ölçüte bağlı: görevi
kim oluşturduysa onu görüyor.

**Görüntüleme eşiği bir değerlendirme aracı değil.** Kaydırıcı yalnızca görünürlüğü
değiştirir; recall veya yanlış pozitif oranı hakkında sonuç üretmez.

---

### 6.11. Sonraki adım

#### 6.11.1. Ölçüm ve analiz tarafında açık kalanlar

Önceki bölümlerden devreden ve bu hafta kapanmayan ölçümler duruyor: ONNX çıkarım
süresindeki artışın mekanizması tek ve iki işçiyle ayrı ayrı ölçülmedi; kare
toplam süresinin üst dilimindeki yükselmenin hangi karelerden geldiği
belirlenmedi; 320 piksellik karolarla eğitilmiş model ve kendi ölçek tabanına
karşı değerlendirmesi yapılmadı; büyük hedef bandındaki düşüşün kenar kuralıyla
nedensel bağı yalnızca eğitim verisi tarafında ölçüldü, model tarafı ölçülmedi.

Bu haftanın eklediği açık ölçüm şu: özgün HERIDAL yayınındaki görüntülerde EXIF
bulunup bulunmadığı ölçülmedi. Elimdeki kopyada yok, ama yokluğun kaynağı
ölçülmüş değil. Özgün veri erişilebilir olursa bu ölçüm konum kazanma ihtimalini
netleştirir.

Ayrıca arayüzün yoklama davranışı yalnızca tek oturumda ölçüldü. Aynı görevde
ikinci bir oturumun başlattığı taramanın birinci oturumda ne kadar sürede
göründüğü ölçülmedi.

#### 6.11.2. Bir sonraki adımda fiilen yapılacak iş

Sıradaki adım, operatörün **kararını** sisteme yazabilmesi ve erişimin görev
bazına oturtulmasıdır.

Görev üyeliği modeli kurulacak: bir görevin sahibi, işlem yapabilen kullanıcıları
ve yalnızca okuyabilen kullanıcıları ayrı roller olarak tanımlanacak, mevcut görev
sahipleri veri kaybı olmadan bu modele taşınacak. Erişim denetimi bütün görev
verisine — kareler, koşular, tespitler ve görüntü dosyaları dâhil — aynı sınırdan
uygulanacak.

Operatör incelemesi ayrı bir kayıt olarak saklanacak: bir tespitin doğrulanıp
doğrulanmadığı, kimin karar verdiği ve isteğe bağlı notu. Bu kayıt tespitin
kendisini değiştirmeyecek, çünkü model çıktısıyla insan yargısını aynı alana
yazmak ikisini de geri dönülmez biçimde karıştırır.

Coğrafi bulgu kaydı, veritabanının coğrafi nokta tipiyle ve uygun bir uzamsal
indeksle kurulacak. Bu kaydın taşıyacağı en kritik alan koordinatın kendisi değil,
**kaynağı**: koordinatın gerçek bir EXIF'ten mi, bir uçuş günlüğünden mi,
operatörün elle girişinden mi geldiği, yoksa demo amaçlı sentetik bir değer mi
olduğu ayırt edilebilir olacak. Konumu olmayan kayıt ile koordinatı sıfır olan
kayıt birbirine karışmayacak.

Kritik işlemler için değiştirilemez bir işlem kaydı tutulacak: üyelik
değişiklikleri, inceleme kararları ve bulgu değişiklikleri kim tarafından ne
zaman yapıldığıyla kaydedilecek, kayıt normal API üzerinden değiştirilemeyecek.

Aynı görevdeki coğrafi bulgular, metre cinsinden bir mesafe kuralıyla bağlı
bileşenlere ayrılacak. Birleştir-bul (Union-Find) yapısının geçişli davranışı
burada kasıtlı: iki nokta eşik içindeyse aynı kümeye girer, ve bu ilişki zincir
hâlinde yayılır. Mesafe eşiği bir ölçüm değil, açıkça yazılacak bir karardır.

Harita katmanı eklenecek, ama bölüm 6.7'deki karara tabi olarak: konum yoksa
harita boş dünya gösterip konum varmış izlenimi vermeyecek, demo veri kullanılırsa
sentetik olduğu kalıcı ve görünür biçimde yazacak.

Son olarak, bölüm 6.9'da açık bıraktığım medya yolu kapatılacak. Bu iş üyelik
modeliyle birlikte anlam kazanıyor: üyelik denetimini dolaşan bir dosya yolu,
üyelik modelini baştan anlamsız kılar.
