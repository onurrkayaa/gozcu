# Gözcü — operatör arayüzü

İnsansız hava aracı görüntülerinde insan adayı arayan Gözcü boru hattının
operatör arayüzü. React + Vite + TypeScript ile yazıldı, sunucu durumunu
TanStack Query tutuyor.

> Eğitim ve araştırma prototipidir. Tespitler operatör kararının yerine geçmez.
> Bu ifade uygulamanın her sayfasında da görünür.

## Gereksinimler

- Node.js 20 veya üstü (geliştirme Node 24.20 ile yapıldı)
- npm (depo `package-lock.json` ile geliyor; başka bir paket yöneticisi kullanmayın)
- Çalışan bir Gözcü backend'i — depo kökünde `docker compose up -d`

## Kurulum ve komutlar

```bash
cd frontend
npm install
```

| Komut | Ne yapar |
|---|---|
| `npm run dev` | Geliştirme sunucusu (http://localhost:5173) |
| `npm test` | Birim ve bileşen testleri (Vitest) |
| `npm run test:watch` | Testleri izleme kipinde çalıştırır |
| `npm run lint` | ESLint |
| `npm run typecheck` | TypeScript denetimi (çıktı üretmez) |
| `npm run build` | Üretim derlemesi (`dist/`); önce `tsc -b` çalışır |
| `npm run preview` | Üretim derlemesini yerelde sunar |

## Gerçek backend ile çalışma

Depo kökünde:

```bash
docker compose up -d          # db, redis, web (8000), worker
cd frontend && npm run dev    # 5173
```

Tarayıcıda http://localhost:5173 açılır.

Geliştirmede istekler **Vite proxy'si** üzerinden gider: `/api` ile başlayan her
adres `http://localhost:8000` adresine taşınır. Bunun iki faydası var —
tarayıcı aynı kaynakla konuştuğu için ayrıca CORS ayarı gerekmez, ve arayüzün
API adresini bilmesi gerekmez.

Bir kullanıcı yoksa oluşturun:

```bash
docker compose exec web python manage.py createsuperuser
```

## Ortam değişkenleri

| Değişken | Varsayılan | Ne işe yarar |
|---|---|---|
| `VITE_API_TABAN` | boş | API taban adresi. Boşken adresler göreli kalır ve geliştirmede proxy, üretimde arayüzle aynı kaynak kullanılır. Backend ayrı bir alan adındaysa burada verilir (örn. `https://api.ornek/`). |
| `VITE_API_PROXY_HEDEF` | `http://localhost:8000` | Yalnızca geliştirme proxy'sinin hedefi. Backend başka bir portta çalışıyorsa değiştirilir. |

Değişkenler `frontend/.env.local` dosyasına yazılabilir; bu dosya Git'e girmez.
**Sır, token veya parola bu dosyalara yazılmaz** — arayüzün derlemeye giren
hiçbir değeri gizli değildir, `VITE_` ile başlayan her şey tarayıcıya iner.

## JWT saklama kararı ve güvenlik sınırı

Backend kimliği `Authorization: Bearer <token>` başlığında bekler (DRF
SimpleJWT). **HTTP-only çerez desteği yoktur**: oturum çerezi üreten bir uç
mevcut değil. Bu yüzden token'ı tarayıcıda bir yerde tutmak zorunludur ve
seçenek ikiye iner:

- **Yalnızca bellek:** her sayfa yenilemesinde oturum kapanır. XSS'e karşı
  belirgin bir kazanç da sağlamaz, çünkü sayfada kod çalıştırabilen bir
  saldırgan zaten kullanıcı adına istek atabilir.
- **localStorage:** sayfa yenilemesinde oturum sürer. Bedeli, bir XSS açığı
  oluşursa token'ın okunabilmesidir.

Operatörün sayfayı yenilediğinde işini kaybetmemesi gerektiği için
**localStorage** seçildi. Sınır açıkça şudur: *bu arayüzde XSS, oturumun
çalınması demektir.* Kabul edilen risk budur.

Uygulanan önlemler:

- Token **URL'ye konmaz** — ne sorgu parametresinde ne de yolda. Görüntüler bile
  `Authorization` başlığıyla, blob olarak indirilir.
- Token log'a yazılmaz ve Git'e girmez.
- Access geçersizken gelen 401'de token bir kez yenilenir ve istek tekrarlanır;
  aynı anda birden çok 401 gelirse hepsi **tek** yenileme isteğini paylaşır.
- Yenileme de düşerse oturum kapatılır, saklanan her şey silinir ve sorgu
  önbelleği temizlenir.
- Çıkışta (elle veya zorunlu) aynı temizlik yapılır.

HTTP-only çerez desteği eklenirse değişmesi gereken tek yer
`src/kimlik/tokenDeposu.ts` dosyasıdır.

## GPS ve konum politikası

**Arayüz koordinat üretmez.**

`scripts/22_konum_kaynagi_tara.py` ile HERIDAL veri kümesinin tamamı
(train + valid + test, 1579 görüntü) tarandı: **hiçbirinde EXIF bloğu yok**,
dolayısıyla GPS de enlem/boylam da yok. Veritabanındaki Frame kayıtlarında da
`latitude`/`longitude` boş. Ayrıntı: `reports/hafta5_gps_kaynak_karari.csv`.

EXIF'in **neden** olmadığı ölçülmedi. Depoda veri kümesinin bir Roboflow dışa
aktarımıyla geldiğini gösteren bir künye var, ama EXIF'i o adımın sildiği
doğrulanmadı — özgün yayındaki kopya elimizde yok ve kaynakta hiç EXIF olmaması
da aynı gözlemi üretir. Yokluk ölçümdür, nedeni hipotezdir.

Buna göre:

- Kayıtta gerçek koordinat varsa gösterilir, kaynağı da yazılır.
- Yoksa **"Konum bilgisi mevcut değil"** yazılır ve nedeni açıklanır.
- Dosya sırasından, karo satır/sütunundan veya görüntü pikselinden enlem/boylam
  **türetilmez**. Böyle bir değer ölçüm değil uydurma olur ve bir arama
  ekibini yanlış noktaya yönlendirir.
- İleride demo amaçlı koordinat kullanılırsa hem veride hem arayüzde
  **"Demo konumu — gerçek GPS değildir"** olarak etiketlenir; gerçek EXIF veya
  gerçek uçuş rotası gibi sunulmaz.

Harita Hafta 5'te bilinçli olarak eklenmedi, çünkü gösterilecek gerçek bir konum
yoktu. Hafta 6'da eklendi; ama aynı karara tabi olarak: konumlu bulgu yoksa
harita hiç açılmıyor, demo koordinatlar her katmanda etiketleniyor. Ayrıntı
aşağıdaki Hafta 6 bölümünde.

## Görüntüleme eşiği

Tespit inceleme ekranındaki kaydırıcı bir **görüntüleme** eşiğidir:

- Yalnızca ekranda çizilen kutuları süzer.
- Modeli yeniden çalıştırmaz, kayıtlı tespitleri değiştirmez.
- **Bir değerlendirme metriği değildir.** Eşiği değiştirmek yeni bir recall veya
  hatalı tespit oranı iddiası üretmez.

Başlangıç değeri sabit yazılmaz; koşunun kendi `conf_threshold` değerinden
gelir. Backend kutuları sabit bir tabanla (`DETECTION_STORE_FLOOR = 0,05`)
sakladığı için tek bir pahalı taramadan daha düşük eşikler de yeniden tarama
olmadan sorulabilir.

## Dizin düzeni

```
src/
  api/          Backend sözleşmesi: tipler, HTTP katmanı, uçlar, sorgu anahtarları
  kimlik/       Token saklama, oturum bağlamı, korumalı rota
  bilesenler/   Paylaşılan parçalar: durum rozetleri, tespit katmanı, kutu geometrisi
  sayfalar/     Ekranlar: giriş, görev listesi, görev ayrıntısı, tespit inceleme,
                üye yönetimi, bulgu paneli, faaliyet geçmişi
  test/         Test kurulumu ve yardımcıları
```

Tipler gerçek serializer çıktılarından yazıldı; durum değerleri backend
enum'larıyla birebir aynıdır ve çevrilmez (`core/models.py`). Kullanılan her uç
`reports/hafta5_api_sozlesmesi.csv` dosyasında kayıtlıdır.

## Tespit kutularının hizası

Backend kutuları **orijinal görüntü pikselinde** verir (örn. 4000×3000); görüntü
ekranda çok daha küçük çizilir. Kutular yüzde olarak yerleştirilir, yani ölçeği
tarayıcı çözer: pencere yeniden boyutlandığında hiçbir JS çalışmadan hiza
korunur. En-boy oranı sarmalayıcıya değil **görüntüye** verilir; sarmalayıcıya
verilseydi yüksekliği görüntününkinden farklı yuvarlanabilir ve alt kenarda
1 piksellik kayma oluşurdu.

## Bilinen kısıtlar

- **Tarama iptali veya yeniden başlatma yok.** Backend'de böyle bir uç yok,
  arayüz de uydurma düğme göstermez.
- **Kare listesi ilk sayfayla sınırlı.** Görev ayrıntısında ve tespit inceleme
  kare seçiminde ilk 20 kare gösterilir; toplam sayı ayrıca yazılır.
- **Tespit listesi sayfalı.** Bir karede 20'den fazla aday varsa en yüksek
  güvenli 20'si çizilir ve kaç adayın olduğu yazılır.
- **Kare durumu yalnızca tarama sürerken yoklanır.** Başka bir oturum aynı
  görevde tarama başlatırsa bu sekme bunu kendiliğinden fark etmez; sayfa
  yenilenince görür.
- **Dosyalar tek tek yüklenir.** Backend tek istekte bir dosya bozuksa isteğin
  tamamını reddettiği için kısmi başarıyı korumak adına böyle yapıldı; çok
  sayıda dosyada yükleme, toplu göndermeye göre yavaştır.
- **Yükleme ilerlemesi dosya bazındadır**, bayt bazında değil. `fetch` yükleme
  ilerlemesi bildirmez.
- **Arayüz tek dildir (Türkçe).** Dil seçimi yok.
- **Gerçek konum hâlâ yok.** Harita Hafta 6'da eklendi, ama elimizdeki veri
  kümesinde ölçülmüş koordinat bulunmadığı için haritada yalnızca elle girilen
  veya demo koordinatlar görünebilir.

---

## Hafta 6: roller, inceleme, bulgu ve harita

### Roller ve yetki

Erişim artık görevi kimin oluşturduğuna değil **görev üyeliğine** bakar. Üç rol
var:

| Rol | Yapabildikleri |
|---|---|
| `owner` (Sahip) | Üyeleri ve rolleri yönetir; operatörün yaptığı her şeyi yapabilir |
| `operator` (Operatör) | Kare ekler, tarama başlatır, inceleme ve bulgu yazar, kümeleme çalıştırır |
| `viewer` (İzleyici) | Yalnızca okur; hiçbir şey değiştiremez |

Üye olmayan kullanıcı görev verisine erişemez ve **403 değil 404** alır: 403,
"böyle bir kayıt var ama senin değil" bilgisini sızdırır ve kimlik deneyerek
başkasının kaç görevi olduğunu saymayı mümkün kılar.

Arayüz rolü `my_role` alanından okuyup denetimleri gizler, ama bu bir kolaylık;
**yetki kararı backend'indir**. Gizlenmiş bir düğmenin isteği yine reddedilir.

Görevin **son sahibi** rolü düşürülemez ve çıkarılamaz; aksi halde görev
sahipsiz kalır ve üyelik bir daha hiç yönetilemez.

### İnceleme (Review) ne demek

Bir tespit için operatörün kararı: doğrulandı, reddedildi veya belirsiz.
İnceleme, `Detection` kaydına **dokunmaz** — model çıktısı ile insan yargısı
ayrı tablolarda durur. Aynı alana yazılsalardı modelin ne bulduğu ile
operatörün ne düşündüğü geri dönülmez biçimde karışır ve geçmiş ölçümler
yeniden üretilemezdi.

Her kullanıcı **kendi** kararını günceller, başkasınınkini ezmez. İki
operatörün aynı tespit hakkında anlaşamadığı bilgisi arama kurtarmada atılacak
bir şey değildir. Karar değişiklikleri faaliyet geçmişine yazılır.

### Bulgu konum kaynağı (provenance)

Bir bulgunun en kritik alanı koordinatın kendisi değil **nereden geldiği**:

| Kaynak | Anlamı | Arayüzden seçilebilir mi |
|---|---|---|
| `none` | Konum yok. **"0,0" demek değildir** | Evet |
| `exif` | Görüntünün EXIF GPS'i — ölçülmüş | Hayır |
| `flight_log` | Uçuş günlüğü — ölçülmüş | Hayır |
| `manual` | Operatörün elle girişi — beyan | Evet |
| `demo` | Gösterim amaçlı sentetik — gerçek değil | Evet |

Ölçülmüş kaynaklar arayüzden seçilemez ve backend de reddeder: elle girilen bir
koordinatın "EXIF'ten geldi" diye kaydedilmesi haritaya bakan kişiyi yanıltır.

Veritabanı seviyesinde bir kısıt, konum yokluğu ile koordinatın karışmasını
engeller: konum boşsa kaynak `none` olmak zorundadır, konum doluysa `none`
olamaz.

Koordinat formda **ayrı enlem ve boylam alanlarıyla** alınır. GeoJSON dizisinde
sıra `[boylam, enlem]`'dir ve kolayca ters yazılır; ayrı alanlarda adın kendisi
sırayı belirsiz bırakmaz. API yanıtında konum hem GeoJSON hem ayrı alanlar
olarak döner.

### Demo veri üretimi

Elimizdeki veri kümesinde gerçek GPS olmadığı için harita katmanı ayrı bir demo
göreviyle doğrulanır:

```bash
docker compose exec web python manage.py demo_konum_uret --kullanici <kullanıcı-adı>
docker compose exec web python manage.py demo_konum_uret --sil
```

Komut, adı açıkça "DEMO — sentetik konumlar (gerçek GPS değildir)" olan ayrı bir
görev açar; içindeki her kayıt `location_source = demo` ile saklanır. Noktalar
sabit bir tohumla üretilir (tekrarlanabilir) ve **gerçek görüntülerden
türetilmez**. Komut üretim ortamına kendiliğinden yüklenmez, elle çalıştırılır.

### Kümeleme eşiği ve Union-Find'in geçişli davranışı

Aynı görevdeki konumlu bulgular, metre cinsinden bir mesafe kuralıyla bağlı
bileşenlere ayrılır. Mesafe PostGIS üzerinden hesaplanır (konum `geography`
tipinde saklandığı için doğrudan metre); derece üzerinden Öklid mesafesi
**kullanılmaz**, çünkü bir derece boylam ekvatorda ~111 km, 60. enlemde ~55
km'dir.

**Eşik bir karardır, ölçüm değildir.** Varsayılan 50 metredir ve hiçbir alan
ölçümünden türetilmemiştir; gerçek uçuş verisi elde edilirse yeniden
değerlendirilmelidir.

**Geçişlilik kasıtlıdır:** A ile B eşik içindeyse ve B ile C eşik içindeyse,
A ile C arası eşikten büyük olsa bile üçü aynı kümeye girer. Bağlı bileşen
tanımı budur. Sonucu şudur: **eşik, kümenin çapı değildir** — uzun bir nokta
zinciri tek küme olarak görünebilir.

Demo ve gerçek konumlar **ayrı** kümelenir; sentetik bir nokta gerçek bir
bulguyu kendine çekerse haritada uydurma bir yoğunlaşma oluşur. Konumu olmayan
bulgular kümelenmez. Küme merkezi üyelerin ortalamasıdır ve **ölçülmüş bir konum
değildir**.

### Harita ve tile yapılandırması

Harita Leaflet ile çizilir, karolar OpenStreetMap'ten gelir ve attribution
haritada görünür durur. Kullanım koşulları gereği bu katman yalnızca bu
prototipin yerel doğrulaması içindir; yoğun veya üretim kullanımı için kendi
karo sunucunuzu ya da koşullarına uyduğunuz bir sağlayıcıyı kullanın.

Üç teknik ayrıntı bilinçli:

- **İkonlar kod içinde çizilir.** Leaflet'in varsayılan işaretçi ikonu paket içi
  göreli yollara bakar; Vite derlemesinde o yollar taşındığı için üretim
  derlemesinde ikon kaybolur. Bu bilinen tuzağı, dış dosyaya hiç bağlanmayarak
  aşıyoruz.
- **Harita kabının yüksekliği açıkça tanımlı.** Leaflet kapsayıcı yüksekliğini
  kendisi hesaplamaz; sıfır yükseklikli bir kapta sessizce görünmez olur.
- **Karo sunucusuna ulaşılamazsa** uygulama çökmez, açıklayıcı bir satır
  gösterir ve bulgu listesi okunabilir kalır.

Konumlu bulgu yoksa harita **hiç açılmaz**: boş bir dünya haritası, kullanıcıya
"konum verisi var ama bu görevde işaret yok" izlenimi verir. Onun yerine neden
konum olmadığı yazılır.

### /media/ erişim politikası

`/media/` altındaki dosyalar **hiçbir ortamda servis edilmez**. Hafta 5'e kadar
DEBUG açıkken Django o yolu kimlik doğrulaması olmadan sunuyordu; görev üyeliği
devreye girince bu, üyelik denetimini tamamen dolaşan bir açık haline geldi.

Görüntüye tek erişim `/api/frames/{id}/image/` ucudur. Bu uç `Authorization`
başlığını okur, karenin görevine üyeliği doğrular ve dosya adını istemciden
değil veritabanından alır — yani yol geçişi (path traversal) yüzeyi yoktur.

### Ek komutlar

| Komut | Ne yapar |
|---|---|
| `python scripts/23_kumeleme_dogrula.py` | Kümelemeyi on senaryoda gerçek veritabanında doğrular ve CSV yazar |
| `python scripts/24_yetki_matrisi.py` | Rol/işlem matrisini gerçek HTTP kodlarından üretir |
| `npm run preview` | Üretim derlemesini yerelde sunar (API proxy'si dâhil) |

### Hafta 6'da eklenen bilinen kısıtlar

- **Kullanıcı arama yok.** Üye eklerken kullanıcı adı elle yazılır; arayüz
  sistemdeki kullanıcıları listelemez, çünkü görevle ilgisi olmayan kişilerin
  adlarını göstermek gereksiz bir bilgi paylaşımı olurdu.
- **Bulgu düzenleme sınırlı.** Arayüzden bulgu eklenip silinebiliyor; durum ve
  başlık düzenlemesi API'de var ama arayüze bağlanmadı.
- **Kümeleme elle tetiklenir.** Yeni bulgu eklendiğinde kümeler kendiliğinden
  yeniden hesaplanmaz; konumu değişen bulgunun küme bilgisi temizlenir.
- **Harita kümeleri sunucu tarafında hesaplanır.** İstemci tarafı marker
  kümeleme (çok sayıda noktada görsel yığılma) eklenmedi.
