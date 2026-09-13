# Güvenlik modeli ve sınırları

Bu belge **güvenlik sertifikası değildir.** Bir eğitim ve araştırma
prototipinin hangi varlıkları koruduğunu, hangi kontrolleri uyguladığını, bu
kontrollerin nasıl sınandığını ve **neyin hâlâ açık kaldığını** yazar.

Buradaki testlerin geçmesi "bütün saldırılar engellendi" anlamına gelmez;
yalnızca yazılı kuralların ölçülen davranışla uyuştuğu anlamına gelir.

Güvenlik sorunu bildirimi: depoda bir konu (issue) açın.

---

## 1. Korunan varlıklar

| Varlık | Nerede durur | Neden önemli |
|---|---|---|
| Kullanıcı hesabı ve oturum belirteci | PostgreSQL + tarayıcı deposu | Belirteç ele geçerse tüm görevler okunabilir |
| Görev üyeliği | `MissionMember` | Erişimin tamamı buna dayanır |
| Görev görüntüleri | `backend/media/`, konteyner birimi | Arama alanına dair ham veri |
| Tespit / inceleme / bulgu | PostgreSQL | Operatör kararının kaydı |
| Denetim kaydı | `AuditLog` | Kimin ne yaptığının tek kaydı |
| Model ağırlığı | `agirliklar/` (Git'te **yok**) | Lisans ve boyut; ayrıca çıkarım davranışını belirler |
| Yapılandırma sırları | `.env` (Git'te **yok**) | Veritabanı parolası, Django anahtarı |

## 2. Tehdit modeli

Her satır: tehdit → uygulanan kontrol → nasıl sınandı → **kalan risk**.

### 2.1. Kimlik doğrulama ve oturum

| Tehdit | Kontrol | Sınama | Kalan risk |
|---|---|---|---|
| Kimliksiz erişim | Bütün uçlar `IsAuthenticated`; yalnızca `/api/health/` açık | `test_yetki_matrisi.py` | — |
| Kaba kuvvetle parola denemesi | Giriş ve yenileme uçları ayrı ve dar bir hız sınırı kovasında (varsayılan 10/dk) | `test_guvenlik_ayarlari.py` | Sınır bir **karardır**, ölçülmüş eşik değildir; dağıtık deneme yavaşlar ama engellenmez |
| Uzun ömürlü çalınmış belirteç | Erişim belirteci 15 dk, yenileme 12 saat; süreler ayardan gelir | `test_guvenlik_ayarlari.py` | **Yenileme rotasyonu ve kara liste yok.** Çalınan bir yenileme belirteci ömrü boyunca geçerlidir |
| Belirtecin sızması | Belirteç URL'ye, log'a veya Git'e yazılmaz; görüntüler bile `Authorization` başlığıyla blob olarak indirilir | `test_guvenlik_ayarlari.py`, `istemci.test.ts` | — |
| XSS ile belirteç çalınması | Belirteç `localStorage`'da; React varsayılan olarak kaçış yapar, `dangerouslySetInnerHTML` kullanılmıyor | — | **AÇIK: kabul edilmiş sınır.** Bkz. bölüm 3 |
| Oturum artıkları | Yenileme düşerse tam temizlik: belirteçler silinir, sorgu önbelleği boşaltılır; çıkışta da aynısı | `kimlikAkisi.test.tsx` | — |

### 2.2. Nesne düzeyi yetkilendirme

| Tehdit | Kontrol | Sınama | Kalan risk |
|---|---|---|---|
| IDOR — kimlik tahmin ederek başkasının görevi | Erişim **üyelikten** geçer (`core/yetki.py`); üye olmayana tutarlı **404** döner (403 değil, böylece kaynağın varlığı sızmaz) | `test_uyelik.py`, `test_yetki_matrisi.py`, `scripts/24_yetki_matrisi.py` | — |
| Salt okunur üyenin yazması | Yazma işlemleri `yazma=True` ister; izleyici 403 alır | `test_yetki_matrisi.py` | — |
| İç içe uçlarda karışıklık (`runs/<id>/detections`) | Her uç kendi görevini üyelikten çözer; istemciden gelen kimliğe güvenilmez | `test_yetki_matrisi.py` | — |
| Başka görevin nesnesini ilişkilendirme | Serileştiriciler ilişkiyi görev sınırında doğrular | `test_bulgu.py`, `test_inceleme.py` | — |

### 2.3. Görüntü ve dosya

| Tehdit | Kontrol | Sınama | Kalan risk |
|---|---|---|---|
| Kimlik doğrulamasız görüntü indirme | `/media/` **kapalı**: Django yayınlamıyor, nginx 404 döndürüyor. Tek yol `/api/frames/{id}/image/` ve o uç üyeliği doğruluyor | `test_yetki_matrisi.py`, dağıtım iş akışı | — |
| Yol geçişi (path traversal) | Dosya adı istemciden değil **veritabanından** okunur | `test_yetki_matrisi.py` | — |
| Görüntü olmayan dosya yükleme | Pillow ile `verify()` + yeniden açma; uzantıya güvenilmez | `test_ingest.py` | Derin içerik denetimi (polyglot dosya) yapılmadı |
| Aynı dosyanın tekrar yüklenmesi | Görev içinde SHA-256 tekilliği; ikinci yükleme yeni kayıt açmaz | `test_ingest.py` | — |
| Aşırı büyük yükleme | nginx `client_max_body_size 32m` | — | Sıkıştırma bombası için ayrı bir piksel sınırı **yok** |

### 2.4. Denetim kaydı

| Tehdit | Kontrol | Sınama | Kalan risk |
|---|---|---|---|
| Geçmişin değiştirilmesi/silinmesi | `AuditLog.save()` yalnızca ilk yazmaya izin verir, `delete()` her zaman hata verir | `test_denetim.py` | **ORM seviyesinde**: veritabanına doğrudan erişimi olan biri yine müdahale edebilir |
| Başarısız işlemin kayda geçmesi | Kayıt, işlemle **aynı transaction** içinde yazılır; işlem geri alınırsa kayıt da geri alınır | `test_denetim.py` | — |
| Hassas verinin log'a düşmesi | `changes` alanında parola/token/e-posta gibi anahtarlar maskelenir, değerler 200 karakterle sınırlanır | `test_denetim.py` | Anahtar listesi elle tutulur; yeni bir hassas alan eklenirse listeye de eklenmeli |

### 2.5. Konum ve demo verisi

| Tehdit | Kontrol | Sınama | Kalan risk |
|---|---|---|---|
| Demo koordinatın gerçek sanılması | `location_source` alanı (`demo` / `manual` / `exif` / `none`) veride durur; arayüz demo görevde kaldırılamayan uyarı gösterir | `harita.test.tsx`, `test_bulgu.py` | — |
| Konumsuz kaydın 0,0 olması | Konum yoksa `NULL`; "0,0" **üretilmez** | `test_bulgu.py`, `test_demo_kur.py` | — |
| Enlem/boylam sırasının karışması | `Point(boylam, enlem)` dönüşümü tek bir yerde | `test_bulgu.py`, `test_kumeleme.py` | — |
| Tespit pikselinden koordinat türetilmesi | Yapılmıyor ve yapılmayacak; böyle bir değer ölçüm değil uydurma olur | — | — |

### 2.6. Servis ve konteyner yüzeyi

| Tehdit | Kontrol | Sınama | Kalan risk |
|---|---|---|---|
| Veritabanı/Redis'in dışarı açılması | Üretim benzeri yığında ikisinin de yayınlanmış portu **yok**; yalnızca iç ağdan erişilir | `dagitim.yml` iş akışı | — |
| Gereksiz dış port | Dışarı açılan tek adres `127.0.0.1:8080` (arayüz) | `dagitim.yml` | — |
| Konteynerde root | Backend imajı `gozcu` (uid 10001) kullanıcısıyla çalışır | — | `db` ve `redis` resmi imajların kendi davranışında bırakıldı; körlemesine değiştirilmedi |
| Pickle ile kod çalıştırma | Celery yalnızca `json` kabul eder | `settings.py` | — |
| Ayakta kalan asılı görev | Yumuşak/sert zaman aşımı (600/660 sn) ve `acks_late` + idempotanslık | `test_runs.py`, `scripts/20_onnx_sigkill_dayaniklilik.py` | — |
| Sırların imaja girmesi | `.dockerignore` `.env`'i dışarıda tutar; sırlar çalışma anında ortamdan gelir | `depo_denetimi.py` | — |

### 2.7. Yapılandırma

| Tehdit | Kontrol | Sınama | Kalan risk |
|---|---|---|---|
| `DEBUG` açık unutulması | `DJANGO_DEBUG` ortamdan; üretim benzeri varsayılan **0** | `check --deploy` | — |
| Gizli anahtarın koda gömülmesi | `DJANGO_SECRET_KEY` zorunlu, varsayılanı **yok**; boşsa uygulama açılmaz | `settings.py` | — |
| Joker CORS | `CORS_ALLOW_ALL_ORIGINS` yalnızca `DEBUG` iken açık; üretimde yalnızca açık liste | `test_guvenlik_ayarlari.py` | — |
| Eksik güvenlik başlıkları | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin` her ortamda açık | `test_guvenlik_ayarlari.py` | — |
| Sırların Git'e girmesi | `depo_denetimi.py` hem çalışma ağacını hem geçmişi tarar, CI'da kapı olarak koşar | `test_depo_denetimi.py` | Tarama **yüzeyseldir**; "hiçbir sır sızmamıştır" kanıtı değildir |

## 3. Açıkça kabul edilen sınırlar

Bunlar bilinen ve **kapatılmamış** risklerdir. Kapatılmış gibi sunulmazlar.

### 3.1. Oturum belirteci tarayıcı deposunda

Backend kimliği `Authorization: Bearer <token>` başlığında bekler; HTTP-only
çerez üreten bir uç **yoktur**. Belirteci tarayıcıda tutmak zorunlu ve seçenek
ikiye iniyor:

- **Yalnızca bellek:** her sayfa yenilemesinde oturum kapanır. XSS'e karşı
  belirgin bir kazanç da sağlamaz — sayfada kod çalıştırabilen saldırgan zaten
  kullanıcı adına istek atabilir.
- **`localStorage`:** oturum yenilemede sürer; bedeli, XSS varsa belirtecin
  okunabilmesidir.

Operatörün sayfayı yenilediğinde işini kaybetmemesi için `localStorage` seçildi.
Sınır açıktır: **bu arayüzde XSS, oturumun çalınması demektir.** HTTP-only çerez
desteği eklenirse değişmesi gereken tek dosya `frontend/src/kimlik/tokenDeposu.ts`.

### 3.2. Yenileme belirteci rotasyon yapmıyor

Yenileme ucu yeni bir yenileme belirteci üretmez ve kullanılmış belirteci kara
listeye almaz. Çalınan bir yenileme belirteci **ömrü boyunca (12 saat)**
geçerlidir. Rotasyon ve kara liste eklenmedi; bu bir kapsam kararıdır.

### 3.3. TLS yok

Yerel yığın düz HTTP konuşur. `DJANGO_HTTPS=1` yapıldığında HSTS, güvenli çerez
ve HTTPS yönlendirmesi açılır ve `manage.py check --deploy` **sıfır uyarıyla**
geçer; ama bu ayarlar yalnızca önünde gerçek TLS sonlandıran bir ters vekil
varsa anlamlıdır. **Bu depoda gerçek bir internet dağıtımı yoktur.**

### 3.4. Denetim kaydı yalnızca uygulama seviyesinde korunuyor

Amaç, uygulama kodunun veya bir API ucunun geçmişi kazara ya da kötü niyetle
bozmasını engellemek. Veritabanına doğrudan erişimi olan biri yine müdahale
edebilir.

### 3.5. Bağımlılık taraması otomatikleştirilmedi

`pip-audit` / `npm audit` sürekli entegrasyona **kapı olarak eklenmedi**. Sürüm
yükseltmeleri ölçüm sonuçlarını etkileyebildiği için bu bilinçli bir karardır:
sürümler ölçümün yapıldığı sürümlerdir. Elle çalıştırılabilir, ama bu depoda
"temiz" diye bir iddia yoktur — çalıştırılmamıştır.

## 4. Ne ölçülmedi

- Sızma testi yapılmadı.
- Otomatik güvenlik tarayıcısı (ZAP, Burp vb.) çalıştırılmadı.
- Bağımlılık zinciri (supply chain) denetimi yapılmadı.
- Hizmet reddi dayanıklılığı ölçülmedi; hız sınırı bir karardır.
- Sıkıştırma bombası ve polyglot dosya senaryoları denenmedi.
