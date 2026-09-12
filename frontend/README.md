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
dolayısıyla GPS de enlem/boylam da yok. Veri kümesi Roboflow üzerinden yeniden
dışa aktarıldığı için EXIF kaynağında silinmiş. Veritabanındaki Frame
kayıtlarında da `latitude`/`longitude` boş. Ayrıntı:
`reports/hafta5_gps_kaynak_karari.csv`.

Buna göre:

- Kayıtta gerçek koordinat varsa gösterilir, kaynağı da yazılır.
- Yoksa **"Konum bilgisi mevcut değil"** yazılır ve nedeni açıklanır.
- Dosya sırasından, karo satır/sütunundan veya görüntü pikselinden enlem/boylam
  **türetilmez**. Böyle bir değer ölçüm değil uydurma olur ve bir arama
  ekibini yanlış noktaya yönlendirir.
- İleride demo amaçlı koordinat kullanılırsa hem veride hem arayüzde
  **"Demo konumu — gerçek GPS değildir"** olarak etiketlenir; gerçek EXIF veya
  gerçek uçuş rotası gibi sunulmaz.

Harita (Leaflet vb.) Hafta 5'te bilinçli olarak eklenmedi: gösterilecek gerçek
bir konum yok.

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
  sayfalar/     Ekranlar: giriş, görev listesi, görev ayrıntısı, tespit inceleme
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
- **Harita yok.** Gösterilecek gerçek konum olmadığı için bilinçli bir karar.
