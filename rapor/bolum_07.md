## 7. Coğrafi İnceleme, Yetkilendirme ve Denetim İzi

*(bu bölümde erişimi görev üyeliğine oturtuyor, operatör kararını model çıktısından ayrı bir kayda alıyor, koordinatı değil koordinatın kaynağını modelin merkezine koyuyor, yakın bulguları metre tabanlı bir kuralla kümeliyor, haritayı yalnızca gösterilecek konum varken açıyor ve yetki denetimini dolaşan bir açığı kapatıyorum)*

---

### 7.1. Bu bölümün sorusu

Önceki adımda çalışan bir arayüz kurmuştum: operatör görev açıyor, kare yüklüyor, tarama başlatıyor ve modelin bulduğu kutuları görüntü üzerinde inceleyebiliyordu. Ama o arayüz tek bir şeyi yapamıyordu: **operatörün gördüğü hakkında ne düşündüğünü kaydetmek.** Ekranda 6622 tespit vardı ve hiçbirinin yanında "buna baktım, bu bir insan değil" diyebileceğim bir yer yoktu.

Bu bölümün sorusu şu: *Bir model tespiti, gerçek olmayan koordinat üretmeden, rol tabanlı inceleme ve denetlenebilir coğrafi bulgu akışına dönüştürülebiliyor mu?*

Sorunun üç ayrı zorluğu var ve üçünü birbirinden ayırmak gerekiyor.

**Birincisi tespit ile karar arasındaki ayrım.** Model bir kutu üretir; bu kutu bir ölçümdür ve modelin o anki ağırlıklarıyla yeniden üretilebilir. Operatör o kutuya bakıp "doğrulandı" der; bu bir yargıdır ve yeniden üretilemez. İkisini aynı alana yazmak, geçmiş ölçümleri geri dönülmez biçimde bozar: üç ay sonra "model bu karede kaç aday buldu" sorusunun cevabı, aradan geçen insan düzenlemeleriyle değişmiş olur. Bu yüzden kararı ayrı bir tabloya koydum.

**İkincisi çok kullanıcılı erişim.** O ana kadar erişim tek ölçüte bağlıydı: görevi kim oluşturduysa onu görüyordu. Arama kurtarma gibi ekip işi bir bağlamda bu yetersiz. Bir görevi birden fazla operatör izler, bazıları yalnızca bakar, koordinasyonu yürüten kişi kimin ne yaptığını görmek ister. Tek kullanıcılı bir model bunların hiçbirini karşılamıyordu.

**Üçüncüsü ve en kritiği coğrafi dürüstlük.** Önceki adımda elimdeki 1579 görüntünün tamamını tarayıp **hiçbirinde EXIF GPS bulunmadığını** ölçmüştüm. Yani haritaya konabilecek gerçek bir koordinat yok. Buna rağmen harita kurmam gerekiyordu, çünkü sistemin coğrafi bulgu akışını gösterebilmesi gerekiyor. Buradaki tehlike açık: gerçek olmayan bir koordinatı gerçekmiş gibi göstermek. Piksel koordinatını enleme çevirmek, dosya sırasını konuma dönüştürmek veya demo veriyi etiketsiz bırakmak — üçü de haritaya bakan kişiyi yanıltır ve arama kurtarma bağlamında yanıltmanın bedeli yüksektir.

Bu bölümün işini yedi kapıya bağladım: veri modeli, yetkilendirme, inceleme ve denetim, konum dürüstlüğü, kümeleme, harita ve genel kalite. Kapıların sonucu bölüm 7.9'da.

Bir de kapsam dışı bıraktığım bir şey var: bu bölümde **hiçbir yeni model iddiası kurmadım.** Kullandığım koşu önceki adımdan kalan iki karelik koşudur; 157 karelik süre ölçümünü tekrarlamadım ve doğruluk hakkında yeni bir sayı üretmedim. Buradaki her ölçüm erişim, kayıt ve arayüz davranışı hakkındadır.

---

### 7.2. MissionMember ve rol modeli

Görev ile kullanıcı arasına bir üyelik kaydı koydum. Üç rol var:

- **Sahip (owner):** üyelik ve rol yönetir, ayrıca operatörün yapabildiği her şeyi yapar.
- **Operatör (operator):** kare ekler, tarama başlatır, inceleme ve bulgu yazar, kümeleme çalıştırır. Üye yönetemez.
- **İzleyici (viewer):** yalnızca okur. Görevi, kareleri, tespitleri, incelemeleri, bulguları ve denetim geçmişini görür; hiçbirine yazamaz.

Rolleri bu üçle sınırlı tuttum çünkü dördüncü bir rolün ne yapacağını ölçemezdim. Rol sayısını artırmak matrisin hücrelerini çarpar ve her hücrenin gerçekten sınanması gerekir.

#### 7.2.1. Sahiplik bilgisini taşımak, silmemek

Eski `created_by` alanını silmedim. O alan hâlâ bir soruyu cevaplıyor: bu görevi kim açtı. Ama **artık yetki taşımıyor.** Erişim sorgusu yalnızca üyelik tablosuna bakıyor.

Bu ayrım göründüğünden önemli. İki yerden birden okusaydım — "ya üyesi ya da oluşturanı" — üyelikten çıkarılmış bir kullanıcı `created_by` üzerinden erişimini sürdürürdü. Yani üyelikten çıkarma işlemi sessizce işlevsiz olurdu. Yetkinin tek bir kaynağı olmalı.

Mevcut görevlerin sahipleri bir veri taşıma adımıyla üyelik tablosuna yazıldı. Bu adım olmasaydı üyelik devreye girdiği anda **mevcut bütün görevler sahipleri dâhil herkese kapanırdı** — kimse üye olmadığı için hiç kimse hiçbir şey göremezdi. Taşıma iki yönlü yazıldı: geri alma yönü yalnızca kendi ürettiği sahiplik kayıtlarını siliyor, elle eklenmiş üyeliklere dokunmuyor.

Taşımadan sonra veri sayımlarını doğruladım: **10 görev, 496 kare, 6622 tespit** korundu ve on görevin onu da sahiplik kaydını aldı. Hiçbir kayıt kaybolmadı, hiçbir görev sahipsiz kalmadı.

#### 7.2.2. Kuralı view'a değil modele bağlamak

İlk yazdığımda sahiplik kaydını görev oluşturma API ucuna koymuştum. Testleri çalıştırdığımda **28 test düştü.** Sebep ilginçti ve bir tasarım hatasını gösteriyordu: test verisi görevleri API'den değil doğrudan veri katmanından açıyor. O yoldan açılan görevlerin sahibi olmuyordu, dolayısıyla hiçbir testin kullanıcısı kendi açtığı görevi göremiyordu.

Kolay çözüm test verisini yamamaktı. Yapmadım, çünkü asıl sorun testlerde değildi: görev yalnızca API'den oluşturulmuyor. Yönetim komutları, veri yükleme adımları ve ileride yazılacak her kod parçası da doğrudan veri katmanından görev açabilir. Kural API ucunda kalsaydı bu yolların hepsi sahipsiz görev üretirdi.

Kuralı modele bağladım: görev kaydı ilk kez yazıldığında, oluşturanı varsa, sahiplik üyeliği kendiliğinden oluşuyor. Böylece *"oluşturanı olan her görevin bir sahibi vardır"* değişmezi bütün kod yollarında geçerli oluyor. Bu düzeltmeden sonra 28 testin hiçbirine dokunmadan hepsi geçti — ki bu, doğru katmanı bulduğumun kanıtı: testler yanlış olsaydı onları değiştirmem gerekirdi.

#### 7.2.3. Son sahip koruması

Bir görevin sahipsiz kalabilmesi, o görevin bir daha yönetilememesi demektir: üye eklenemez, rol değiştirilemez, kimse yetki veremez. Kayıt veritabanında durur ama kimse ona erişemez.

Bu yüzden son sahibi düşürmeyi ve çıkarmayı engelledim. İkisi de 400 dönüyor ve bu bir yetki reddi değil bir **kural engeli**: isteği yapan kullanıcının yetkisi tamdır, yapmak istediği şey tutarsızdır. Arayüzde de aynı ayrım korunuyor — denetimler kilitli ve neden kilitli olduğu yazılı.

#### 7.2.4. Üye olmayana 403 değil 404

Üye olmayan kullanıcı bir görevi istediğinde 403 değil **404** alıyor.

403 "böyle bir kayıt var ama senin değil" bilgisini sızdırır. Bu bilgiyle kimlik numarası deneyerek sistemde kaç görev olduğu, hangi numaraların kullanıldığı ve dolaylı olarak başka ekiplerin ne kadar iş yaptığı sayılabilir. 404 bu bilgiyi de vermiyor: üye olmayan için o kayıt hiç yok.

Kural görevin kendisi kadar altındaki her şey için de geçerli: kareler, kare görüntü dosyaları, koşular, tespitler, incelemeler, bulgular ve denetim kayıtları. Erişim denetimini tek bir yardımcı fonksiyonda topladım, böylece her uç kendi kuralını uydurmuyor.

---

### 7.3. Review: model çıktısı ile operatör kararının ayrılması

`Review` kaydı bir tespit için operatörün kararını tutuyor: doğrulandı, reddedildi veya belirsiz. Bir not alanı da var.

En önemli özelliği ne yaptığı değil, **ne yapmadığı**: `Detection` kaydına hiç dokunmuyor. Modelin ürettiği kutu, skor ve karo bilgisi olduğu gibi duruyor. Bu sayede "model bu karede ne buldu" sorusunun cevabı aradan geçen insan kararlarıyla değişmiyor ve geçmiş ölçümler yeniden üretilebilir kalıyor.

**Tekillik (tespit, inceleyen) çiftinde.** Her operatör kendi kararını günceller, başkasınınkini ezmez. Bu kasıtlı bir tasarım: iki operatörün aynı tespit hakkında anlaşamadığı bilgisi, arama kurtarmada atılacak bir bilgi değil. Tek bir "karar" alanı olsaydı ikinci bakan kişi birincinin yargısını sessizce silerdi ve anlaşmazlığın var olduğu bile görünmezdi.

Bu davranış ölçümde bir kez beni yanılttı. Yetki matrisini çıkarırken "aynı tespite hem sahip hem operatör inceleme yazarsa ikincisi 400 almalı" diye bir beklenti yazmıştım. Ölçüm ikisinin de 201 döndüğünü gösterdi. Sistem doğruydu, beklentim yanlıştı: ikisi de kendi kaydını açıyor, çakışma yok. Beklentiyi düzelttim.

**İzleyici salt okunur.** İnceleme listesini görüyor, kendi kararını yazamıyor; API 403 dönüyor ve arayüzde karar düğmeleri hiç çizilmiyor. Salt okunur kullanıcıya tıklayınca hata veren bir düğme göstermek kötü bir tasarım: kullanıcı yetkisinin sınırını ancak hatayı aldıktan sonra öğrenir.

**Review bir ground truth değildir ve yeni bir model metriği kurmaz.** Reddedilen bir aday gerçekten yanlış pozitif olabilir, ama operatör de yanılmış olabilir. Elimdeki etiketli test kümesiyle operatör kararı iki ayrı kaynaktır ve aynı sayıya karıştırılmaları gerekmiyor. Bu bölümde inceleme kayıtlarından hiçbir doğruluk değeri türetmedim; yalnızca kaydın tutulduğunu ve erişim kurallarına uyduğunu ölçtüm.

![Gözcü tespit inceleme ekranı. Gerçek veri kümesi görüntüsü üzerinde çizilmiş insan adayı kutuları, sağ panelde bir adaya verilmiş "Doğrulandı" kararı ve kararı yazan kullanıcının adı.](rapor/gorseller/hafta6/04_tespit_inceleme_karari.png)

---

### 7.4. Finding ve konum provenance

`Finding`, haritada gösterilebilen bulguyu tutuyor. Konum alanı `geography(Point, 4326)` tipinde ve uzamsal indeksi kuruldu; veritabanında `gist (location)` olarak doğruladım.

`geography` seçimi bir kolaylık değil, bir doğruluk kararı. Bu tiple mesafe sorguları doğrudan **metre** cinsinden çalışıyor. Düzlemsel `geometry` kullansaydım aynı sorgu **derece** dönerdi ve "50 metre" diye yazdığım eşik sessizce yanlış olurdu: 1 derece boylam ekvatorda yaklaşık 111 km, 60. enlemde yaklaşık 55 km'dir. Yani derece cinsinden sabit bir eşik, enleme göre anlamını değiştiren bir eşiktir.

#### 7.4.1. Modelin en kritik alanı koordinat değil kaynağı

Beş kaynak değeri ayırt ediliyor:

| Kaynak | Anlamı | Ölçülmüş sayılır mı | Arayüzden seçilebilir mi |
|---|---|---|---|
| `none` | Konum bilgisi yok | — | — |
| `exif` | Görüntünün EXIF GPS bloğu | Evet | Hayır |
| `flight_log` | Uçuş günlüğü | Evet | Hayır |
| `manual` | Operatörün elle girdiği koordinat | Hayır | Evet |
| `demo` | Gösterim amacıyla üretilmiş koordinat | Hayır | Evet (demo akışında) |

*Bu tablo ne söylüyor: Beş değerin ikisi ölçülmüş konum sayılıyor ve tam da bu ikisi arayüzden seçilemiyor. Sebep basit: elle girilen bir koordinatın "EXIF'ten geldi" diye kaydedilmesi, haritaya bakan kişinin o noktaya ölçülmüş bir veri gözüyle bakmasına yol açardı. Ölçülmüş kaynak yalnızca gerçekten ölçümden gelen bir kod yolundan yazılabilir. Elimdeki veride EXIF GPS hiç bulunmadığı için bugün bu iki satır boş — ama boş olduğu görünüyor, gizlenmiyor.*

#### 7.4.2. Konum yokluğu bir değerdir

Bir veritabanı kısıtı iki durumu birbirinden ayırıyor: konum boşsa kaynak `none` olmak **zorunda**, konum doluysa kaynak `none` **olamaz**.

Bunun nedeni şu: konum yokluğu ile "0, 0" birbirine karışmamalı. 0,0 Gine Körfezi'nde gerçek bir noktadır. Boş bir koordinat alanı sessizce sıfırlanırsa harita Afrika'nın batısında var olmayan bir bulgu gösterir ve bunu gerçek bir kayıt gibi sunar. Kısıt bu karışmayı uygulama katmanında değil **veritabanı seviyesinde** engelliyor; yani hatalı bir kod yolu bile böyle bir kaydı yazamıyor.

#### 7.4.3. Piksel dünya koordinatına çevrilmiyor

Tespit kutusundan otomatik koordinat **üretilmiyor.** Bu, yazmadığım kod olduğu için görünmez bir karar; bu yüzden burada açıkça yazıyorum.

Piksel ile dünya arasında dönüşüm yapabilmek için kameranın konumu, irtifası, yönelimi ve görüş açısı gerekir. Bunların hiçbiri kayıtlarda yok. Olmayan bu bilgileri varsayarak bir dönüşüm yazmak mümkündü ve çıktısı da inandırıcı görünürdü — haritada işaretler belirirdi. Ama o işaretlerin yeri uydurma olurdu. Aynı şekilde dosya sırasını veya karo indeksini koordinata çevirmek de teknik olarak kolay, anlam olarak yanlıştır.

#### 7.4.4. Demo verisinin görünür biçimde ayrılması

Haritayı gösterebilmek için demo koordinatlara ihtiyacım vardı. Bunları üç yerde birden etiketledim:

1. **Veritabanında:** kaynak alanı `demo`.
2. **API'de:** her bulgu kaydı bir `is_demo` ve bir `has_measured_location` alanı taşıyor; istemcinin kaynak kodunu yorumlamasına gerek yok.
3. **Arayüzde:** harita üstünde kapatılamayan bir uyarı, kesikli çerçeveli işaretler ve balonda kaynak satırı.

Demo verisi ayrı ve adı kendini söyleyen bir görevde duruyor — adında "sentetik konumlar (gerçek GPS değildir)" yazıyor — ve bir yönetim komutuyla sabit bir tohumdan üretiliyor. **Gerçek görüntülerden türetilmiyor**; yani gerçek bir kareye sahte bir koordinat iliştirilmiş olmuyor.

---

### 7.5. AuditLog

Denetim kaydı on işlem türünü izliyor: üye eklendi, üye rolü değişti, üye çıkarıldı, inceleme oluşturuldu, inceleme güncellendi, bulgu oluşturuldu, bulgu güncellendi, bulgu silindi, kümeleme çalıştırıldı, tarama başlatıldı. Her kayıt işlemi yapan kullanıcıyı, ilgili görevi, nesne türünü ve kimliğini, bir de değişiklik özetini taşıyor.

**Eklemeli ve kilitli.** Kayıt bir kez yazıldıktan sonra değiştirilemiyor ve hiçbir koşulda silinemiyor; API'de yazma ucu zaten yok. Yetki matrisinde denetim yazma satırı her rolde 405: sahip bile yazamıyor.

**İşlemle aynı veritabanı işlemi içinde yazılıyor.** Bu, denetim kaydının en kolay gözden kaçan özelliği. Kayıt ayrı bir işlemde yazılsaydı, asıl işlem sonradan geri alındığında denetim geçmişinde **olmamış bir şey** yazılı kalırdı. Bunu doğrudan ölçtüm: son sahibi düşürme isteği 400 ile reddedildiğinde denetim kaydı sayısı değişmedi.

**Hassas veri girmiyor.** `changes` alanına ham nesne dökülmüyor; yalnızca gerçekten değişen alanların önceki ve sonraki değerleri yazılıyor. Parola, token, oturum anahtarı, çerez, e-posta ve benzeri anahtarlar bir engel listesiyle eleniyor; uzun metinler kırpılıyor. Tarayıcıda beş yasak dizgeyi ayrı ayrı aradım, hiçbiri görünmüyor ve ham JSON ekrana basılmıyor.

**Sınırı da yazmak gerekiyor: bu tablo bütün güvenlik olaylarının eksiksiz kanıtı değildir.** İki nedenle. Birincisi kapsam: yalnızca yukarıdaki on işlem izleniyor; okuma istekleri, başarısız giriş denemeleri ve token kullanımı izlenmiyor. İkincisi koruma katmanı: değiştirilemezlik uygulama katmanında sağlanıyor, veritabanına doğrudan erişimi olan biri yine de geçmişe müdahale edebilir. Amaç, uygulama kodunun veya bir API ucunun kazara ya da kötü niyetle geçmişi bozmasını engellemek — bundan fazlası değil.

![Gözcü faaliyet geçmişi ekranı. Zaman sırasıyla listelenmiş denetim kayıtları: işlemi yapan kullanıcı, işlem türü, nesne ve önceki/sonraki değer özeti; üstte kayıtların değiştirilemeyeceğini söyleyen not.](rapor/gorseller/hafta6/05_faaliyet_gecmisi.png)

---

### 7.6. Yetki matrisi ve görüntü erişimi

Rol matrisini bir niyet beyanı olarak bırakmak istemedim. Yirmi işlemi dört ayrı kullanıcı sınıfıyla **gerçekten çağırdım** ve dönen HTTP kodlarını kaydettim.

| İşlem | owner | operator | viewer | üye değil |
|---|---|---|---|---|
| Görev listeleme | 200 | 200 | 200 | 200 (liste boş) |
| Görev görüntüleme | 200 | 200 | 200 | 404 |
| Üye listeleme | 200 | 200 | 200 | 404 |
| Üye ekleme | 201 | 403 | 403 | 404 |
| Rol değiştirme | 200 | 403 | 403 | 404 |
| Üye çıkarma (son sahip) | 400 | 403 | 403 | 404 |
| Kare listeleme | 200 | 200 | 200 | 404 |
| Kare ekleme | 201 | 201 | 403 | 404 |
| Kare görüntü dosyası | 200 | 200 | 200 | 404 |
| Koşu listeleme | 200 | 200 | 200 | 404 |
| Koşu görüntüleme | 200 | 200 | 200 | 404 |
| Tespit listeleme | 200 | 200 | 200 | 404 |
| İnceleme okuma | 200 | 200 | 200 | 404 |
| İnceleme yazma | 201 | 201 | 403 | 404 |
| Bulgu okuma | 200 | 200 | 200 | 404 |
| Bulgu yazma | 201 | 201 | 403 | 404 |
| Kümeleme çalıştırma | 200 | 200 | 403 | 404 |
| Denetim okuma | 200 | 200 | 200 | 404 |
| Denetim yazma girişimi | 405 | 405 | 405 | 405 |
| Görüntüye doğrudan dosya yolundan erişim | 404 | 404 | 404 | 404 |

*Bu tablo ne söylüyor: Yirmi işlemin hepsinde gerçekleşen kod beklenen kodla uyuştu; hiçbir satır kalmadı. Üç satır ayrıca açıklama istiyor. Görev listeleme satırında üye olmayan da 200 alıyor — çünkü liste ucunun kendisi herkese açık, ama dönen liste boş; "senin görevin yok" ile "böyle bir uç yok" farklı şeylerdir. Son sahip çıkarma satırındaki 400 bir yetki reddi değil kural engeli: sahibin yetkisi tam, istediği şey tutarsız. Denetim yazma satırındaki 405 her rolde aynı, çünkü yazma ucu hiç yok; üye olmayanın da 405 alması bilgi sızdırmaz, zira 405 görevin var olup olmadığını söylemez.*

#### 7.6.1. Üyelik denetimini dolaşan açık

Önceki bölümde açık bir kısıt olarak kaydettiğim bir davranış vardı: geliştirme kipinde sunucu, yüklenen dosyaların bulunduğu dizini **kimlik doğrulaması istemeden** servis ediyordu. O zaman bu yalnızca bir geliştirme kolaylığıydı.

Üyelik devreye girdiği anda aynı davranış nitelik değiştirdi. Yukarıdaki matrisin tamamı bir anlam taşıyabilmek için tek bir şeye dayanır: göreve ait verilere yalnızca üyelerin ulaşabilmesi. Görüntüler dosya yolundan herkese açıksa, üyelik denetimi **anlamsızlaşır** — çünkü korunmak istenen asıl içerik zaten dışarıda durur. Kare kaydını göremeyen bir kullanıcı, kareye ait görüntüyü doğrudan indirebilir.

Yolu tamamen kaldırdım. Görüntüye tek erişim, üyelik denetleyen uç üzerinden: istek başlığındaki kimliği okuyor, karenin görevine üyeliği doğruluyor ve **dosya adını istemciden değil veritabanından** alıyor. Bu sonuncusu yol geçişi denemelerini baştan geçersiz kılıyor; uç yalnızca bir birincil anahtar alıyor. Yine de denedim: yol parçası içeren istekler ve bunların kodlanmış biçimleri 404 dönüyor.

Ölçüm sonucu: kimliksiz istek 404, kimlikli üyenin aynı yola isteği de 404 (yol kapalı), güvenli uçtan üye 200 ve üye olmayan 404.

---

### 7.7. Union-Find kümeleme

Aynı hedef birden fazla bulgu üretebilir. Örtüşen karolar aynı kişiyi iki kez bulabilir, iki operatör aynı noktaya ayrı bulgu açabilir. Haritada bunlar ayrı işaretler olarak görünürse operatör tek bir hedefi birden fazla hedef sanar — arama kurtarmada bu, kaynağın yanlış dağıtılması demektir.

Çözüm olarak birbirine belirli bir mesafeden yakın bulguları aynı bağlı bileşene koyuyorum. Bunun için birleştir-bul (Union-Find) yapısını kullandım: her bulgu başta kendi kümesinde başlar, eşik içindeki her çift birleştirilir, sonuçta kalan gruplar kümelerdir.

**Aday çiftlerini veritabanı buluyor.** Python'da her çifti karşılaştırmak bulgu sayısının karesiyle büyürdü. Bunun yerine her bulgu için yalnızca eşik içindeki komşular sorgulanıyor ve uzamsal indeks aday sayısını baştan daraltıyor.

**Eşik bir KARARDIR, ölçüm değildir.** Varsayılan 50 metre ve bu değer hiçbir alan ölçümünden türetilmedi. Dayanağı bir varsayım: insan boyu bir hedefin çevresinde bu yarıçapta ikinci bir işaret görülürse operatörün bunu ayrı bir hedef değil aynı hedefin tekrarı sayacağı varsayımı. Gerçek uçuş verisi elde edilirse yeniden değerlendirilmesi gerekir.

**Geçişlilik kasıtlıdır.** A ile B eşik içindeyse ve B ile C eşik içindeyse, A ile C arasındaki mesafe eşikten büyük olsa bile üçü aynı kümeye girer. Bu bir hata değil, bağlı bileşen tanımıdır. Ama bedeli var ve kullanıcıya söylenmesi gerekiyor: **eşik, kümenin çapı değildir.** "Eşik 50 metre" ifadesi kümenin 50 metreye sığdığını düşündürür; oysa uzun bir yakınlık zinciri tek küme olarak görünebilir.

| Senaryo | Beklenen küme | Gerçek küme | Deterministik | İdempotent |
|---|---|---|---|---|
| Tek nokta | 1 | 1 | evet | evet |
| İki yakın nokta (10 m) | 1 | 1 | evet | evet |
| İki uzak nokta (500 m) | 2 | 2 | evet | evet |
| Geçişli üçlü (40 + 40 m, uçlar 80 m) | 1 | 1 | evet | evet |
| Aynı koordinat (üç kayıt) | 1 | 1 | evet | evet |
| Eşik sınırının hemen içinde (49 m) | 1 | 1 | evet | evet |
| Eşik sınırının hemen dışında (51 m) | 2 | 2 | evet | evet |
| Demo ve gerçek yan yana (5 m) | 2 | 2 | evet | evet |
| Konumsuz kayıt dâhil | 1 | 1 | evet | evet |
| Farklı görevlerde aynı koordinatlar | 2 | 2 | evet | evet |

*Bu tablo ne söylüyor: On senaryonun onunda da beklenen ve gerçek küme sayısı uyuştu ve hepsi hem deterministik hem idempotent çıktı. Üç satır ayrı ayrı bir şeyi kanıtlıyor. 49 ve 51 metre satırları mesafenin gerçekten metre cinsinden ölçüldüğünü gösteriyor — derece tabanlı bir hesap bu iki metrelik farkı ayırt edemezdi. Geçişli üçlü satırı kasıtlı davranışın kanıtı: uçları birbirinden 80 metre uzak olduğu hâlde zincir tek küme üretiyor. Demo–gerçek satırında iki nokta yalnızca 5 metre arayken bile ayrı kümelerde kalıyor, çünkü ayrım mesafeye değil kaynağa bakıyor.*

Üç ayırma kuralı daha var. **Görev sınırı:** kümeler görevi aşmıyor; iki ayrı görevdeki aynı koordinatlar birleşmiyor. **Demo/gerçek ayrımı:** sentetik bir nokta gerçek bir bulguyu kendine çekemiyor, aksi hâlde harita üzerinde uydurma bir yoğunlaşma oluşurdu. **Konumsuz kayıtlar dışarıda:** konumu olmayan bulgularda kümelenecek bir şey yok ve bunları tek bir "konumsuzlar" kümesine toplamak aralarında coğrafi bir ilişki varmış izlenimi verirdi.

**İdempotanslık** şuradan geliyor: küme kimlikleri her koşuda sıfırdan, sıralı bir kuraldan türetiliyor; önceki koşunun kimliklerine hiç bakılmıyor. **Determinizm** ise birleştirmede eşit rütbedeki iki kökten küçük anahtarlının seçilmesinden geliyor; aynı girdi her zaman aynı kökleri üretiyor.

**Küme sonucu bir doğruluk ölçüsü değildir.** Üç bulgunun tek kümeye düşmesi, orada bir kişi olduğunu değil, üç kaydın birbirine yakın olduğunu söyler. Kümenin merkezi de üyelerin aritmetik ortalamasıdır ve ölçülmüş bir konum değildir; API bu notu her küme kaydının içinde taşıyor.

---

### 7.8. Leaflet arayüzü

Haritayı Leaflet ile ekledim. En önemli davranışı ne gösterdiği değil, **ne zaman hiç açılmadığı.**

**Konumlu bulgu yoksa harita kabı hiç oluşturulmuyor.** Boş bir dünya haritası göstermek "konum verisi var ama işaret yok" izlenimi verirdi; oysa gerçek durum "konum verisi hiç yok". Onun yerine açıklayıcı bir boş durum çıkıyor ve piksel koordinatının haritaya konmadığı orada yazıyor. Elimdeki gerçek görevde durum tam olarak budur.

![Gözcü görev ayrıntısında bulgular sekmesi, gerçek görevde. Harita yerine açıklayıcı boş durum: bu görevde konum bilgisi bulunmadığı ve piksel koordinatının haritaya çevrilmediği yazılı.](rapor/gorseller/hafta6/01_konumsuz_gorev_bos_durum.png)

**Demo uyarısı kapatılamıyor.** Harita üstündeki uyarının kapatma düğmesi yok; kaydırmayla veya tıklamayla kaybolmuyor. Kapatılabilir bir uyarı, kapatıldıktan sonra sentetik koordinatları gerçek gibi bırakırdı.

**İşaretler ve balonlar.** Her bulgu bir işaret; balonda başlık, demo rozeti, kaynak, durum, koordinat, küme bilgisi ve bulguyu ekleyen kullanıcı görünüyor. Demo işaretleri kesikli çerçeveyle çiziliyor, yani uyarıyı görmeyen biri bile işaretin farklı olduğunu fark ediyor.

**Katman atfı görünür:** harita köşesinde OpenStreetMap katkıda bulunanlarının atfı duruyor.

**Karo servisi erişilemezken uygulama çökmüyor.** Tarayıcıda karo hatası olayını tetikledim: "Harita karoları yüklenemedi" mesajı çıktı, harita kabı ve bulgu tablosu ayakta kaldı. Harita dış bir servise bağlı olduğu için bu yolun sınanması gerekiyordu.

**Üretim derlemesinde ayrıca doğruladım.** Leaflet'in varsayılan işaret ikonu üretim paketlemesinde kaybolan bilinen bir davranıştır ve tam olarak geliştirme kipinde görünmez. Bu yüzden ikonları kod içinde çizdim ve ölçümü üretim derlemesi üzerinde yaptım: harita kabının konumlandırması uygulanmış, 10 işaret çizilmiş, 18 karo yüklenmiş, atıf ve demo uyarısı yerinde.

![Gözcü bulgular sekmesi, demo görevinde. Haritada kesikli çerçeveli işaretler, üstte kapatılamayan demo uyarısı; açık bir balonda bulgu başlığı, DEMO rozeti, konum kaynağı, koordinat ve küme bilgisi.](rapor/gorseller/hafta6/03_bulgu_balonu_ve_kume.png)

---

### 7.9. Doğrulama kapıları

| Kapı | Konu | Ölçüt | Sonuç |
|---|---|---|---|
| A | Veri modeli | Üyelik, inceleme, bulgu ve denetim tabloları kuruldu; veri taşıma kayıpsız; uzamsal indeks doğrulandı | geçti |
| B | Yetkilendirme | 20 işlem × 4 kullanıcı sınıfı gerçek çağrılarla ölçüldü; görüntü yolu kapatıldı | geçti |
| C | İnceleme ve denetim | Karar ayrı tabloda; kayıt eklemeli ve kilitli; başarısız işlem kayıt üretmiyor; hassas veri girmiyor | geçti |
| D | Konum dürüstlüğü | Kaynak alanı zorunlu; kısıt konum yokluğunu 0,0'dan ayırıyor; pikselden koordinat türetilmiyor; demo üç yerde etiketli | geçti |
| E | Kümeleme | 10 senaryonun hepsi beklenen sonucu verdi; deterministik ve idempotent | geçti |
| F | Harita | Konum yokken açılmıyor; demo uyarısı kalıcı; karo hatasına dayanıklı; üretim derlemesinde doğrulandı | geçti |
| G | Kalite | Üç test paketi, lint, tür denetimi, derleme ve veri taşıma tutarlılığı | geçti |

*Bu tablo ne söylüyor: Yedi kapının yedisi de geçti, dolayısıyla bu haftanın işi kapanabilir durumda. Kapıların hiçbiri model doğruluğu hakkında değil; hepsi erişim, kayıt ve arayüz davranışını ölçüyor. D kapısı özellikle bir "yapmama" kapısı: geçmesi için yazılmayan kodun gerçekten yazılmamış olduğunu doğrulamak gerekiyordu.*

Test sayıları:

| Denetim | Sonuç |
|---|---|
| Sunucu tarafı testleri | 215 test, tamamı geçti (önceki bölüm sonunda 97 idi) |
| Ölçüm script'i testleri | 145 test, tamamı geçti |
| Arayüz testleri | 9 dosyada 105 test, tamamı geçti (önceki bölüm sonunda 63 idi) |
| Arayüz lint | 0 hata |
| Tür denetimi | Geçti |
| Arayüz üretim derlemesi | Geçti |
| Veri taşıma tutarlılığı | Bekleyen adım yok |
| Uzamsal indeks | `gist (location)` doğrulandı |
| Rol/işlem matrisi | 20 işlem, tamamı beklenen kodu döndü |
| Kümeleme senaryoları | 10 senaryo, tamamı geçti |
| Uçtan uca tarayıcı doğrulaması | 26 kontrol, tamamı geçti |
| Tarayıcı konsolu ve ağ | Uygulama kaynaklı hata yok; API isteklerinin hepsi 200 |

*Bu tablo ne söylüyor: Sunucu testleri 97'den 215'e çıktı; artışın tamamı bu bölümde eklenen üyelik, inceleme, bulgu, denetim ve kümeleme testlerinden geliyor — sırasıyla 23, 13, 20, 19, 22 ve rol matrisi için 21 test. Uçtan uca doğrulama dört ayrı kullanıcı sınıfıyla gerçek tarayıcıda yürütüldü, yani matristeki kodlar hem sunucu tarafında hem kullanıcı akışında sınandı. Bu tabloda hiçbir satır model performansı hakkında değil; kullanılan koşu önceki bölümden kalan iki karelik koşudur.*

---

### 7.10. Süreçte bulunan kusurlar ve ölçüm artefaktları

Bu ikisini karıştırmak kolay ve karıştırmak zararlı: ölçüm aracımın hatasını sistem kusuru gibi sunmak, düzeltilmesi gereken bir şey varmış izlenimi verir; tersi ise gerçek bir kusuru ölçüm gürültüsü sayıp bırakmak olur. Ayrı ayrı yazıyorum.

#### 7.10.1. Sistem kusurları

**İngilizce 404 metni ve kaydın varlığını ima etmesi.** Tarayıcıda üye olmayan bir kullanıcıyla gezinirken ekranda çerçevenin kendi İngilizce mesajı göründü: bir görevin sorguyla eşleşmediğini söyleyen teknik bir cümle. İki sorun birden vardı. Birincisi dil ve okunabilirlik: son kullanıcıya gösterilecek bir metin değil. İkincisi ve daha önemlisi anlam: metin, aranan şeyin ne olduğunu söylüyor ve dolaylı olarak kayıt uzayı hakkında bilgi veriyor — oysa 404 tercihimin bütün amacı bu bilgiyi vermemekti. Sunucunun 404 gövdesini kullanıcıya hiç göstermeyip uygulamanın kendi genel mesajını koydum ve iki testle sabitledim.

**Kırılgan yoklama testi.** Tarama ilerlemesini yoklayan arayüz testi, sunucu testleriyle aynı anda çalışırken bir kez düştü; tek başına üç kez arka arkaya geçti. Sebep testin kendisiydi: sabit bir duvar saati süresi bekleyip "bu süre içinde şu kadar istek gitmiş olmalı" diye ölçüyordu. Yüklü bir makinede o süre yetmiyor. Süre beklemeyi kaldırdım; test artık istek sayacının arka arkaya turlarda sabit kalmasını kontrol ediyor, yani zamana değil davranışa bakıyor.

#### 7.10.2. Yanlış ölçüm veya test beklentileri

| Gözlem | Ne bekliyordum | Nasıl sınadım | Ne çıktı |
|---|---|---|---|
| Üye ekleme satırı "kaldı" | Sahip için 201 | Matris script'ini çalıştırdım | Eklenecek aday kullanıcıları hiç oluşturmamıştım; kurulumu düzeltince 201 |
| İnceleme yazma satırı "kaldı" | İkinci inceleyen çakışma alır | İki rolle aynı tespite yazdım | İkisi de 201: her inceleyen kendi kaydını açıyor, tasarım böyle |
| Denetim yazma satırı "kaldı" | Üye olmayan 404 alır | Dört kullanıcı sınıfıyla POST denedim | Dördü de 405: çerçeve yöntem denetimini yetkiden önce yapıyor; 405 görevin varlığını söylemiyor |
| Matrisin ilk koşusunda her istek 400 | Gerçek yetki kodları | Script'i çalıştırdım | Test istemcisinin sunucu adı izinli adlar listesinde yoktu; istek yetkiye hiç ulaşmadan reddediliyordu |
| Klavye odağı görünmüyor sanmak | Odaklanan denetimde çerçeve | Odak durumunu kodla tetikleyip ölçtüm | Tarayıcı odak görünürlüğünü gerçek klavye girdisine bağlıyor; gerçek sekme tuşuyla ölçünce 3 px'lik çerçeve göründü |

*Bu tablo ne söylüyor: Beş gözlemin beşi de sistemde değil ölçümümde kusurluydu. İlk üçü matris script'inin ilk koşusunda "kaldı" satırı olarak göründü ve düzeltilen şey beklenti ya da kurulum oldu, ürün kodu değil. Dördüncüsü bütün satırları aynı anda bozduğu için kolay fark edildi — bir ölçümün hepsini birden bozması genellikle ölçüm aracını işaret eder. Sonuncusu en sinsisi: ölçüm aracının kendisi ölçtüğü şeyi değiştiriyordu, çünkü tarayıcı odak çerçevesini ancak gerçek klavye kullanımında gösteriyor.*

---

### 7.11. Kısıtlar ve sonraki adım

Bu bölümün sonunda ürün, girişteki soruyu karşılıyor: bir tespit, gerçek olmayan koordinat üretilmeden rol tabanlı incelemeye ve denetlenebilir bir coğrafi bulguya dönüşebiliyor. Ama bunun etrafındaki sınırlar dar ve hepsini yazmak gerekiyor.

- **Gerçek GPS yok.** Elimdeki 1579 görüntünün hiçbirinde EXIF GPS bulunmadığı için ölçülmüş kaynak iki değeri de kullanılmadı. Harita bugün yalnızca elle girilen veya demo koordinatlarla çalışabiliyor.
- **Demo konumu saha kanıtı değildir.** Sentetik koordinatlar gösterim içindir; hiçbir gerçek görüntüden türetilmemiştir ve hiçbir arazi hakkında bilgi taşımaz.
- **50 metre eşiği bir karardır.** Hangi eşiğin doğru olduğu ölçülmedi, çünkü ölçmek için gerçek uçuş verisi gerekiyor.
- **Geçişlilik uzun zincir üretebilir.** Aralarında yakınlık zinciri olan noktalar, uçları birbirinden çok uzak olsa da tek küme görünür. Bu davranış kasıtlı ama sınırı ölçülmedi; gerçek veride ne kadar uzayabileceğini bilmiyorum.
- **İnceleme kararı ground truth değildir.** Operatör de yanılabilir; bu kayıtlardan model doğruluğu hesaplanamaz.
- **Denetim kaydının kapsamı sınırlıdır.** On işlem türü izleniyor; okuma istekleri ve kimlik doğrulama olayları izlenmiyor. Koruma uygulama katmanındadır.
- **Tek yerel bütünleşme ortamı.** Bütün ölçümler tek bir yerel kurulumda yapıldı; farklı bir dağıtımda davranışın aynı kalacağı sınanmadı.
- **Harita dış bir karo servisine bağlı.** Servis erişilemezken uygulamanın çökmediğini ölçtüm, ama harita o durumda işlevsiz kalıyor.
- **Rol modeli üç rolle sınırlı.** Sınanan matris bu üç rol içindir; başka bir rol eklenirse matrisin yeniden ölçülmesi gerekir.
- **Kümeleme elle tetikleniyor.** Yeni bulgu eklendiğinde kümeler kendiliğinden yeniden hesaplanmıyor.

#### 7.11.1. Ölçüm ve analiz tarafında açık kalanlar

1. ONNX çıkarım süresindeki artışın mekanizması; tek işçiyle ve iki işçiyle ayrı ölçüm gerekiyor.
2. Kare toplam süresinin üst yüzdeliğindeki yükselmenin hangi karelerden geldiği.
3. Model-320'nin eğitilmesi ve kendi ölçek tabanına karşı değerlendirilmesi; deney matrisinin dördüncü hücresi hâlâ boş.
4. Büyük kutu bandındaki düşüşün kenar kuralıyla nedensel bağı; eğitim verisi tarafı ölçüldü, model tarafı ölçülmedi.
5. Taban çizgisinin yanlış pozitif eğrisi yalnızca üç eşikte ölçülü.

#### 7.11.2. Bir sonraki adımda fiilen yapılacak iş

Sıradaki iş **yanlış pozitiflerin görsel bağlamının ölçülmesidir.** Buradaki gözlem şu: bazı yanlış pozitifler insan faaliyetiyle ilişkili görsel yapılarda ortaya çıkıyor olabilir. Gözlemi doğuran örnek, bir kaynakta modelin bir arabayı insan adayı olarak işaretlemesiydi. **Tek örnek kanıt değildir**; bir sonraki adımın işi tam olarak bu gözlemi tek örnek olmaktan çıkarmak.

Somut olarak şunları yapacağım:

- **Karşılaştırma paydası kurmak.** Yalnızca yanlış pozitiflerin kategorilerini saymak bir ilişki ölçmez; her yanlış pozitif için aynı görüntüden eşleştirilmiş bir kontrol bölgesi üretmek gerekiyor.
- **Körlenmiş etiketleme.** Görsel içerik etiketleri, etiketi koyan kişi bölgenin hangi modele ait olduğunu, yanlış pozitif mi kontrol mü olduğunu ve skorunu görmeden atanmalı.
- **Kaynak ve model ayrımı.** Görülen bir ilişkinin tek bir kaynaktan mı taşındığı ayrıca incelenmeli; iki modelin yanlış pozitifleri eşit bir bütçede karşılaştırılmalı.
- **Sonucun inceleme akışına etkisinin değerlendirilmesi.** Ölçüm doğrudan bir sıralama kuralına çevrilmeyecek; önce gözlemin ölçülmesi, sonra ürün davranışının ayrı bir kararla ele alınması gerekiyor.

Bu analiz yapılırken korunacak ayrım bu bölümde kurulanla aynı: operatör kararı bir etiket değildir, kümeleme bir doğruluk ölçüsü değildir ve bir kategorinin sayısı tek başına bir ilişki kurmaz.
