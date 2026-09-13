# Gözcü — tek komutla demo

Bu belge, projeyi ilk kez açan birinin sistemi **beş dakikada** çalışır hâlde
görmesi içindir. Ölçüm sonuçları için rapora bakın; burada anlatılan şey
sistemin kendisidir.

> **Bu bir eğitim ve araştırma prototipidir.** Demo, gerçek bir arama-kurtarma
> operasyonu değildir. Tespitler operatör kararının yerine geçmez.

---

## 1. Ön koşullar

| Gerekli | Neden |
|---|---|
| Docker Desktop (açık olmalı) | Beş servis konteynerde çalışır |
| ~4 GB boş disk | İmajlar + veritabanı |
| Boş 8080 portu | Arayüz buradan açılır |

Python, Node veya veritabanı kurmanız **gerekmez**; hepsi konteynerin içindedir.

## 2. Tek komut

```bash
./demo.sh
```

Bu komut sırayla şunları yapar:

1. `.env` yoksa `.env.example`'dan üretir ve **yeni bir `DJANGO_SECRET_KEY` ile
   veritabanı parolası** oluşturur (depoya girmez).
2. İmajları derler ve beş servisi başlatır (`db`, `redis`, `web`, `worker`,
   `frontend`).
3. Veritabanı şemasını uygular.
4. Sağlık kontrolünün geçmesini bekler.
5. Demo verisini kurar: iki kullanıcı, bir görev, kareler, bir tarama, tespitler,
   operatör incelemeleri, bulgular ve denetim kaydı.
6. Adresi ve demo parolasını ekrana yazar.

İlk çalıştırma imaj derlemesi yüzünden birkaç dakika sürer; sonrakiler ~1 dakika.

Bittiğinde tarayıcıda açın: **<http://localhost:8080>**

## 3. Demo hesapları

| Kullanıcı | Rol | Ne yapabilir |
|---|---|---|
| `demo` | sahip (owner) | Tarama başlatır, inceler, üye ekler |
| `demo_izleyici` | izleyici (viewer) | Yalnızca okur; yazma denemesi 403 alır |

Parola, `./demo.sh` çıktısında yazar. **Depoda sabit bir demo parolası yoktur:**
komut ilk çalıştığında rastgele bir parola üretip `.env` dosyasına yazar, sonraki
çalıştırmalarda aynısını kullanır. `.env` Git'e girmez.

## 4. İzlenecek akış

Sırayla şunlara bakın — her adım, sistemin ayrı bir kararını gösterir:

1. **Giriş** — JWT ile kimlik doğrulama. Oturum açılmadan hiçbir uç veri dönmez.
2. **Görev listesi** — kare sayıları, kare durumları, son taramanın durumu ve
   kullanılan model sürümü.
3. **Görev ayrıntısı** — tarama durumu, kare listesi, kare ekleme, tarama başlatma.
4. **Tespitleri incele** — gerçek görüntü üzerinde tespit kutuları.
   - Üstteki **görüntüleme eşiği** kaydırıcısını oynatın: kutular süzülür ama
     **model yeniden çalışmaz**. Tespitler 0,05 tabanıyla kaydedildiği için tek
     taramadan her eşik sorulabilir. Bu bir değerlendirme metriği değildir.
   - Bir tespite **Doğrulandı / Belirsiz / Reddedildi** deyin. Bu karar ayrı bir
     tabloya yazılır; modelin çıktısına **dokunmaz**.
5. **Konum uyarısı** — kare panelinde "Konum bilgisi mevcut değil" yazar. Veri
   kümesindeki 1579 görüntünün hiçbirinde EXIF GPS yoktur; arayüz koordinat
   **uydurmaz**, boş bırakır.
6. **Bulgular ve harita** — demo koordinatlarıyla Leaflet haritası. Haritanın
   üstünde kaldırılamayan bir "demo konumları" uyarısı durur.
   - Yakın bulgular 50 metre kuralıyla kümelenmiştir (Union-Find).
   - Küme merkezi **ölçülmüş bir konum değildir**; üyelerin aritmetik ortalamasıdır.
   - Konumsuz bir bulgu da vardır ve haritada **gösterilmez** (0,0'a çevrilmez).
7. **Üyeler** — rol bazlı erişim. `demo_izleyici` ile giriş yapıp aynı sayfaları
   deneyin: okuma serbest, yazma 403.
8. **Faaliyet geçmişi** — denetim kaydı. Tarama başlatma, inceleme, bulgu ve
   kümeleme işlemleri burada görünür. Kayıtlar değiştirilemez ve silinemez.

Her sayfanın üstünde kapatılamayan kapsam uyarısı durur:
*"Eğitim ve araştırma prototipidir. Tespitler operatör kararının yerine geçmez."*

## 5. Hangi veri gerçek, hangisi sentetik

Bu ayrım demoda **gizlenmez**; hem arayüzde hem veritabanı alanlarında yazılıdır.

| Şey | Durum |
|---|---|
| Görüntüler | Yerel HERIDAL test görüntüleri **varsa** gerçek; yoksa üretilmiş sentetik görüntü |
| Tespitler | Gerçek modda gerçek Model-512 ONNX çıktısı; sentetik modda `fake-v0` test dedektörü |
| Koordinatlar | **Her zaman sentetik.** Sabit tohumlu, gerçek bir olay yeriyle ilgisi yok |
| Operatör incelemeleri | Demo amaçlı otomatik girildi; gerçek bir operatör kararı değil |
| Kümeler | Gerçek Union-Find çıktısı, sentetik koordinatlar üzerinde |
| Süre ve doğruluk sayıları | Demoda **ölçülmez**. Ölçülmüş sayılar rapordadır |

### Demo hangi modda çalıştı?

`./demo.sh` ikisini de destekler ve hangisini seçtiğini ekrana yazar:

| Mod | Koşul | Hız |
|---|---|---|
| **gerçek** | `agirliklar/model512_best.onnx` **ve** `data/heridal/test/images/` varsa | ~30 sn/kare (CPU) |
| **sentetik** | Model veya veri yoksa (temiz bir klonda varsayılan) | ~2 sn/kare |

Zorlamak için:

```bash
./demo.sh --sentetik     # hızlı, veri kümesi gerektirmez
./demo.sh --gercek       # gerçek model; dosyalar yoksa açık hata verir
```

Sentetik modda görev açıklaması ve komut çıktısı **"tespitler eğitilmiş bir
modelin çıktısı değildir"** der. `fake-v0`, boru hattını modelin yavaşlığından
bağımsız doğrulamak için yazılmış, sabit tohumlu bir test dedektörüdür.

## 6. Kapatma ve temizlik

```bash
./demo.sh --durdur       # servisleri durdurur, veri kalır
./demo.sh --sil          # yalnızca demo görevlerini siler, gerçek veriye dokunmaz
docker compose down -v   # her şeyi siler (veritabanı dâhil)
```

`./demo.sh` idempotenttir: ikinci kez çalıştırmak kayıtları ikiye katlamaz,
aynı görevi yeniden kurar.

## 7. Sorun giderme

| Belirti | Sebep ve çözüm |
|---|---|
| `docker calismiyor` | Docker Desktop açık değil |
| 8080 portu dolu | Başka bir uygulama kullanıyor; onu kapatın veya `docker-compose.yml` içindeki `8080:80` değerini değiştirin |
| `web servisi saglikli duruma gelmedi` | `docker compose logs web` çıktısına bakın; en sık sebep `.env` içinde boş `DJANGO_SECRET_KEY` |
| Tarama `failed` oldu | Gerçek modda ONNX dosyası yok veya bozuk. `docker compose logs worker`. Sistem sessizce sahte dedektöre **düşmez** |
| Harita boş | Konumsuz göreve bakıyorsunuz; demo görevinin "Bulgular ve harita" sekmesine geçin |
| Demo 15 dakikadan uzun sürdü | Gerçek modda CPU yavaş olabilir. `./demo.sh --sentetik` deneyin |

## 8. Bilinen kısıtlar

- Yerel, düz HTTP üzerinde çalışır. **TLS yoktur** ve bu gerçek bir internet
  dağıtımı değildir.
- Oturum belirteci tarayıcı deposunda (`localStorage`) durur. Bir XSS açığı
  oturumun çalınması demektir; kabul edilmiş prototip sınırıdır
  (ayrıntı: [docs/GUVENLIK.md](docs/GUVENLIK.md)).
- Tarama iptali veya yeniden başlatma yoktur.
- Listeler ilk sayfayla sınırlıdır (20 kayıt); toplam sayı ayrıca yazılır.
- Demo, doğruluk veya hız **ölçmez**. Ölçülmüş her sayı raporda ve `reports/`
  altındaki CSV'lerdedir.
