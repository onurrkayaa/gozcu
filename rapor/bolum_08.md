## 8. Yanlış Pozitiflerin Görsel Bağlamı

*(bu bölümde tek bir gözlemi ölçülebilir bir soruya çeviriyor, yanlış pozitif bölgeleri aynı görüntüden seçilmiş kontrol bölgeleriyle körlenmiş biçimde karşılaştırıyor, aracımdaki bir kusurun ölçümün yarısını nasıl götürdüğünü anlatıyor ve elimde kalan kanıtın neyi söyleyip neyi söylemediğini sınırlarıyla yazıyorum)*

---

### 8.1. Bu bölümün sorusu

Dördüncü haftada, eğitilmiş modelin çıktılarını gözle kontrol ederken bir şey dikkatimi çekmişti: yanlış pozitiflerden biri bir arabanın üzerine oturmuştu. Model orada bir insan gördüğünü söylüyordu, ama görüntüde bir araç vardı.

Bu tek bir kareydi. O zaman not aldım ve bıraktım, çünkü **tek bir örnek kanıt değildir.** Bir şeyin bir kez olması, sistematik olduğunu göstermez; benzer bir kareyi arayan biri neredeyse her hipotezi destekleyen bir örnek bulabilir.

Yanlış pozitiflerin neden önemli olduğunu hatırlatmak gerekiyor. Bu projede her tespit, operatörün bakması gereken bir adaydır; model bir hedefi işaretlediğinde iş bitmiyor, oradan bir insan kararı başlıyor. Elimdeki çalışma noktalarında görüntü başına yaklaşık 1,8 yanlış pozitif düşüyor. Yüz elli yedi görüntülük bir test kümesinde bu, iki yüz seksenin üzerinde boşa bakılan bölge demek; gerçek bir arama görevinde binlerce kare olacağı düşünülürse, yanlış pozitif sayısı doğrudan operatörün yorulma hızıdır. Eşiği yükselterek bu sayıyı düşürmek mümkün, ama bedeli kaçırılan hedeflerdir — önceki bölümlerde ölçtüğüm ödünleşim tam olarak budur.

Bu yüzden yanlış pozitiflerin **nerede** ortaya çıktığını bilmek, yalnızca kaç tane olduğunu bilmekten farklı bir soru. Sistematik bir örüntü varsa, ileride ele alınabilir; yoksa geriye yalnızca eşik ayarı kalır.

Yine de gözlem bir soru doğuruyordu: *yanlış pozitifler, insan faaliyetiyle ilişkili görsel yapıların bulunduğu yerlerde mi ortaya çıkıyor?* Sezgisel olarak makul: araç, çatı, direk ve yol gibi insan yapımı nesneler doğal arka plandan farklı kenar, kontrast ve geometri üretir; insan boyu bir hedefi arayan bir model bunlara takılabilir.

Bu bölümün işi o sezgiyi ölçmekti. Sorunun ölçülebilir hâli şu: **Modelin yanlış pozitif bölgeleri, aynı görüntülerden seçilmiş karşılaştırma bölgelerine göre insan faaliyeti işareti içerme bakımından farklı mı?**

Sonucu baştan söylüyorum: beklediğim yönde bir sinyal ölçtüm, ama **bağımsız bir sonuç kuracak kadar örnek toplayamadım.** Bunun sebebi verinin ya da yöntemin değil, kendi yazdığım etiketleme aracındaki bir kusurun ölçüm kapsamının yarısını götürmesidir. Bölüm 8.4'te bunu ayrıntısıyla anlatıyorum, çünkü bu haftanın en önemli dersi orada.

---

### 8.2. Neden yalnızca yanlış pozitif kategorilerini saymak yetmez

İlk aklıma gelen tasarım basitti: yanlış pozitiflerin bulunduğu yerlere bak, kaçında araç, çatı veya yol var say, oranı yaz. Bu tasarım yanlıştır ve neden yanlış olduğu bu bölümün yöntem tarafının özüdür.

#### 8.2.1. Payda problemi

Diyelim ki yanlış pozitiflerin %79'unda insan faaliyeti işareti buldum. Bu sayı tek başına hiçbir şey söylemez, çünkü karşılaştıracak bir şey yoktur. Görüntülerin kendisi insan faaliyeti bakımından zengin olabilir — arama kurtarma görüntüleri çoğu zaman yerleşim yakınında, yol kenarında veya tarım alanında çekilir. Eğer rastgele seçilmiş herhangi bir bölgede de %79 oranında insan faaliyeti görünüyorsa, ölçülen şey model hakkında değil **arazi hakkındadır.**

Bir orana anlam veren şey, karşılaştırıldığı paydadır. Bu yüzden her yanlış pozitif için bir **kontrol bölgesi** ürettim.

#### 8.2.2. Eşleştirilmiş kontrol

Kontrol bölgesi rastgele bir yerden değil, **yanlış pozitifin geldiği görüntünün kendisinden** seçiliyor. Böylece arazi türü, kaynak, çözünürlük, ışık ve çekim yüksekliği iki taraf için de aynı oluyor; geriye yalnızca "modelin işaret ettiği yer" ile "işaret etmediği yer" farkı kalıyor.

Kontrolün kuralları, sonuçlar görülmeden önce sabitlendi: yanlış pozitif kutusuyla aynı genişlik ve yükseklikte olacak, görüntü sınırları içinde kalacak, hiçbir gerçek insan kutusuyla çakışmayacak, ilgili modelin o görüntüdeki hiçbir tahminiyle anlamlı biçimde örtüşmeyecek ve **konumu rastgele, sabit tohumla seçilecek.**

Son kural en kritiği: kontrolün yeri **içeriğine bakılarak seçilmiyor.** İçeriğe bakarak seçseydim — örneğin "boş görünen bir yer" arasaydım — kontrolü tanımı gereği insan faaliyeti olmayan bir bölge hâline getirir ve farkı kendi elimle üretmiş olurdum.

#### 8.2.3. Örneklemin katmanlı olması ve ağırlıklandırma

Bütün yanlış pozitifleri etiketlemek iki model için yaklaşık 570 kutu artı bir o kadar kontrol demekti; bu, tek bir kişi için taşınabilir bir yük değil. Bu yüzden model başına 110 yanlış pozitif örneklendi.

Örnekleme rastgele değil **katmanlı** yapıldı. Test bölümünde iki kaynak var ve yanlış pozitiflerin büyük çoğunluğu ZRI'dan geliyor. Oransal bir örnekleme yapsaydım küçük kaynaktan yaklaşık yirmi kutu gelir ve kaynak sorusu daha başlamadan cevapsız kalırdı. Bunun yerine, yanlış pozitif sayısı belirli bir tabanın altında kalan kaynağın **tamamı** alındı, kalan kontenjan büyük kaynaktan sabit tohumlu rastgele örneklemeyle dolduruldu.

Bunun bir bedeli var: örneklem artık popülasyonun oranlarını yansıtmıyor, küçük kaynak olduğundan fazla temsil ediliyor. Birleşik oranlar bu yüzden düz ortalama değil, her çiftin kendi katmanının **seçilme olasılığının tersiyle** ağırlıklandırılmış ortalaması olarak hesaplanıyor. Kaynak bazındaki oranlar ise ayrıca, ağırlıksız hâlleriyle veriliyor.

#### 8.2.4. Görüntü düzeyinde bağımlılık

Üçüncü sorun daha sinsi. Aynı görüntüden birden fazla yanlış pozitif çıkabiliyor. Bunları bağımsız gözlemler gibi saymak, elimdeki bağımsız bilgi miktarını olduğundan büyük gösterir ve güven aralığını yapay olarak daraltır: on farklı görüntüden gelen on çift ile tek bir görüntüden gelen on çift aynı ağırlıkta değildir.

Bu yüzden güven aralığını **görüntü düzeyinde küme bootstrap** ile ürettim: yeniden örneklenen birim çift değil, görüntüdür; bir görüntü seçildiğinde o görüntünün bütün çiftleri birlikte geliyor. Test tarafında da eşleştirilmiş tasarıma uygun olanı, yani uyumsuz çiftler üzerinden çalışan McNemar'ı kullandım; iki bağımsız oranı karşılaştıran bir test burada geçerli olmazdı, çünkü çiftin iki üyesi aynı görüntüden geliyor.

Bütün bu kurallar — örnekleme, kontrol tanımı, taksonomi, dışlama, istatistik yöntemi ve hangi sonucun hangi kanıt etiketini alacağı — **hiçbir aday görüntü açılmadan ve hiçbir dağılım hesaplanmadan** yazıldı ve kayda geçirildi. Sonradan iki kural düzeltildi ve ikisi de eski hâliyle birlikte kaydedildi; ikisi de sonuçlara bakılmadan, yalnızca işleyiş sorunları yüzünden değişti.

---

### 8.3. Körleme ve etiket taksonomisi

Görsel içerik etiketini bir insanın koyması gerekiyordu. Bu, ölçümün en kırılgan yeri: etiketi koyan kişi hangi bölgenin yanlış pozitif hangisinin kontrol olduğunu bilirse, beklentisi etiketi çeker ve ölçüm kendi hipotezini doğrular.

Bu yüzden etiketleme körlendi. Etiketleyenin gördüğü tek şey **kör bir kimlik** ve iki kırpımdı. Model adı, bölgenin yanlış pozitif mi kontrol mü olduğu, güven skoru, kaynak öneki ve gerçek dosya adı ne ekranda görünüyor ne de arayüze gönderilen veride bulunuyor. Kör kimlikler, iki modelin yanlış pozitifleri ve kontrolleri tek havuzda karıştırıldıktan sonra veriliyor, dolayısıyla kimlik sırası gruptan bağımsız. Çözüm anahtarı ayrı bir dosyada duruyor ve etiketleme aracı o dosyayı hiç açmıyor.

Her aday için iki kırpım üretildi. **Sıkı kırpım** kutunun kendisini gösteriyor: modelin tam olarak neye baktığını. **Bağlam kırpımı** kutu merkezli, kutunun uzun kenarının sekiz katı (en az 512 piksel) kenarlı bir pencere: çevrede araç, çatı, yol veya çit olup olmadığını değerlendirmeye yetecek alan. Bu katsayı bir karardır, ölçümden türetilmedi. Kırpımların üzerine kutu **çizilmedi** — çizilseydi kutunun içeriğe oturma biçimi yanlış pozitif ile kontrolü ayırt etmede ipucu verebilirdi.

Etiket şeması iki katmanlı. Birincil alan ikili bir yargı: **insan faaliyeti var / yok / belirsiz.** "Var" için araç, bina veya çatı, yol veya patika, çit veya direk, makine, düzenli tarım izi ya da başka açık bir insan yapımı nesne yeterli. İkinci katman tek ve zorunlu bir alt kategori; birden fazla öğe varsa kutuya en yakın olan seçiliyor. Ayrıca güven düzeyi, "görüntü yeterli mi" işareti ve serbest bir not alanı var.

Körlemenin gerçekten kurulduğunu etiketleme başlamadan önce denetledim: 440 adayın 880 kırpımının hepsi diskte var, bozuk dosya yok, kör kimlikler tekil, manifest ile çözüm anahtarı birebir eşleşiyor, her adayın eşi karşılıklı ve karşıt türde, hiçbir kontrol bölgesi gerçek insan kutusuyla çakışmıyor. Ayrıca hem dosya adlarında hem manifest alanlarında model adı, kaynak öneki ve özgün dosya adı aranıp bulunamadığı doğrulandı. Denetimlerden biri bile kalsaydı etiketlemeye başlanmayacaktı.

İki tasarım tercihi ayrıca önemli. Birincisi, **araç için özel bir kategori yaratılmadı**: araba gözlemi genel `araç` kategorisine doğal olarak düşsün diye. Kendi gözlemime özel bir kutu açsaydım, o kutunun dolması bir keşif değil bir kendini gerçekleştiren tasarım olurdu. İkincisi, **belirsiz etiketler zorla bir sınıfa sokulmuyor.** Birincil analizde belirsiz içeren çift dışlanıyor; ayrıca belirsizleri "yok" ve "var" sayan iki duyarlılık analizi ayrı ayrı raporlanıyor, böylece sonucun bu tercihe ne kadar duyarlı olduğu görünüyor.

---

### 8.4. Etiketleme aracındaki StrictMode kusuru

Etiketleme aracını, alt kategori tuşuna basıldığında kaydın kendiliğinden yazılıp bir sonraki adaya geçmesi üzerine kurdum: hızlı olsun diye, 484 ekran için tuş sayısı önemliydi.

Kaydetme işlemini, taslak durumunu güncelleyen fonksiyonun **içine** koydum. Bu bir hata. React, durum güncelleyicisini saf bir fonksiyon sayar ve geliştirme kipindeki katı denetim altında onu **iki kez** çalıştırır — bunu, saf olmayan güncelleyicileri yakalamak için kasten yapar. Sonuç şuydu: her etikette kayıt ve ilerleme iki kez tetiklendi. Kayıt doğru yazıldı, ama imleç bir yerine iki aday ileri gitti ve **aradaki aday hiç gösterilmeden atlandı.**

Kusur, kapsam dosyasında çıplak gözle görülebilen bir desen bıraktı: ilk on iki adaydan sonra bir dolu bir boş, düzenli biçimde. Bu düzenlilik kusurun kendisini ele verdi; bir insanın etiketleme davranışı böyle metronom gibi olmaz.

**Testim bunu neden yakalamadı?** Çünkü test, aracı katı denetim sarmalayıcısı olmadan kuruyordu. Üretimde araç o sarmalayıcının içinde çalışıyor, testte çalışmıyordu; yani test, ürünü gerçekten çalıştığı koşulda sınamıyordu. Kusurun kendisi kadar öğretici olan bu: **bir testin geçmesi, test ettiği şeyin üretimdeki hâlini test ettiği anlamına gelmiyor.**

Düzeltme iki parçalı oldu. Yan etki durum güncelleyicisinin dışına, tek sefer çalışacak yere alındı. Test, aracı üretimdekiyle aynı biçimde katı denetim altında kuracak şekilde yeniden yazıldı ve üç regresyon testi eklendi: bir etiketin tam bir adım ilerletmesi, art arda üç etiketin üç ardışık adayı kapsaması ve düğmeyle etiketlemenin de tek adım ilerletmesi. Düzeltmeyi geri alıp testleri çalıştırdığımda üçü de düştü ve kaydedilen kimlik dizisi tam olarak gerçek dosyadaki deseni verdi.

**Ölçüm kapsamına etkisi ağır oldu.** Etiketlenen kayıtların kendisi geçerli: her biri gerçekten ekranda görülmüş bir adaya ait, hiçbir veri bozulmadı. Ama eşleştirilmiş tasarımda kayıp, etiket sayısındaki eksilmenin iki katı hızda büyüyor. Atlamalar bir çiftin iki üyesini rastgele biçimde birbirinden ayırdı; bir çiftin kullanılabilmesi için **hem yanlış pozitifin hem kendi kontrolünün** etiketli olması gerekiyor, dolayısıyla yarı yarıya bir kapsam, dörtte bire yakın bir çift oranına dönüştü.

---

### 8.5. Etiket kapsamı ve kalite

Ölçüm için iki modelden 110'ar yanlış pozitif örneklendi ve her birine aynı görüntüden bir kontrol bölgesi eşleştirildi: 220 çift, 440 aday, 880 kırpım. Etiketleme turu buna kalite turunu da ekliyordu.

| Büyüklük | Planlanan | Gerçekleşen |
|---|---|---|
| Ana tur ekranı | 440 | 226 |
| Kalite turu ekranı | 44 | 22 |
| Her iki üyesi etiketli çift | 220 | 55 |
| Belirsiz yüzünden düşen çift | — | 10 |
| Birincil analizde geçerli çift | ≥ 100 | **45** |
| Geçerli çiftlerin geldiği görüntü | — | 35 |

Kaynak: `reports/hafta7_fp_insan_faaliyeti_analizi.csv` ve `reports/hafta7_fp_gorsel_etiketler.csv`

*Bu tablo ne söylüyor: Etiketlenen ekran sayısı planın yaklaşık yarısı, ama kullanılabilir çift sayısı dörtte biri. Aradaki fark eşleştirilmiş tasarımdan geliyor: 165 çiftte üyelerden yalnızca biri etiketli kaldı ve bunlar karşılaştırmaya hiç giremedi. Geriye kalan 55 çiftin 10'u da belirsiz etiket içerdiği için düştü. Sonuç olarak birincil analiz 45 çift üzerinde çalışıyor ve bu, önceden yazılmış 100 çiftlik ana bulgu eşiğinin altında kalıyor.*

Kalite tarafında tek etiketleyiciyle bir **yeniden-test** turu yapıldı: aynı adaylar, farklı sırayla ve önceki cevap gösterilmeden yeniden etiketlendi. Kalite turu da atlama kusurundan etkilendiği için karşılaştırılabilen kayıt sayısı 14'te kaldı.

| Ölçüm | Uyuşan / karşılaştırılan | Oran |
|---|---|---|
| İnsan faaliyeti (ikili alan) | 14 / 14 | 1,0000 |
| Güven düzeyi | 14 / 14 | 1,0000 |
| Alt kategori | 10 / 14 | 0,7143 |
| Üç alan birden (tam uyum) | 10 / 14 | 0,7143 |
| Ana turda belirsiz oranı | 16 / 226 | 0,0708 |
| "Görüntü yetersiz" işareti | 0 / 226 | 0,0000 |
| "Yeniden incele" işareti | 0 / 226 | 0,0000 |

Kaynak: `reports/hafta7_fp_etiket_kalite.csv` (`scripts/27_fp_analiz.py`)

*Bu tablo ne söylüyor: Birincil ikili alanda aynı kişi 14 kaydın 14'ünde aynı kararı verdi, alt kategoride 10'unda. Bu **tek etiketleyici yeniden-test tutarlılığıdır; annotatorlar arası güvenilirlik değildir** ve öyle adlandırılamaz — iki farklı kişinin aynı görüntüye aynı etiketi verip vermeyeceği bu projede hiç ölçülmedi. Üstelik 14 kayıt, tutarlılık hakkında güçlü bir iddia için de az. İkili alandaki yüksek uyumun bir kısmı, o alanın alt kategoriye göre daha kaba ve daha kolay olmasından gelebilir. Belirsiz oranının %7 civarında kalması ve "görüntü yetersiz" işaretinin hiç kullanılmaması, kırpımların değerlendirmeye elverişli olduğunu gösteriyor.*

---

### 8.6. Birincil yanlış pozitif – kontrol sonucu

45 geçerli çift, 35 görüntü üzerinden:

| Büyüklük | Değer |
|---|---|
| Yanlış pozitif bölgelerinde insan faaliyeti (ağırlıklı oran) | 0,7930 |
| Kontrol bölgelerinde insan faaliyeti (ağırlıklı oran) | 0,3180 |
| Ağırlıklı eşleştirilmiş fark | +0,4751 |
| %95 güven aralığı (görüntü düzeyinde küme bootstrap) | [0,2623; 0,6609] |
| Uyumsuz çift: yalnızca yanlış pozitifte işaret var | 23 |
| Uyumsuz çift: yalnızca kontrolde işaret var | 3 |
| Eşleştirilmiş odds oranı | 7,6667 |
| McNemar (tam binom) p | 9·10⁻⁵ |
| Duyarlılık: belirsizler "yok" sayılırsa | +0,4369 |
| Duyarlılık: belirsizler "var" sayılırsa | +0,4678 |

Kaynak: `reports/hafta7_fp_insan_faaliyeti_analizi.csv` (`scripts/27_fp_analiz.py`)

*Bu tablo ne söylüyor: Sinyal beklenen yönde ve tek tek bakıldığında güçlü görünüyor — yanlış pozitif bölgelerinde insan faaliyeti işareti, kendi kontrollerine göre yaklaşık iki buçuk kat sık; uyumsuz 26 çiftin 23'ü yanlış pozitif lehine; güven aralığı sıfırı dışlıyor ve belirsizleri hangi yöne saydığım sonucu değiştirmiyor. Buna rağmen bu bir bulgu değildir, çünkü 45 çift, önceden yazılmış 100 çiftlik eşiğin altındadır.*

Tablodaki uyumsuz çift satırlarının neden ayrıca yazıldığını açıklamak gerekiyor. Eşleştirilmiş bir karşılaştırmada bilgi taşıyan çiftler, iki üyesinin **farklı** etiket aldığı çiftlerdir. Kırk beş çiftin on dokuzunda hem yanlış pozitif hem kontrol aynı yanıtı aldı — ikisinde de işaret var ya da ikisinde de yok — ve bu çiftler hangi tarafın daha sık işaret taşıdığı sorusuna hiçbir şey söylemez; yalnızca o görüntünün genel olarak zengin veya boş olduğunu gösterirler. Geriye kalan yirmi altı çift ayrışıyor ve karar bunlara dayanıyor: yirmi üçünde işaret yalnızca modelin gösterdiği yerde, üçünde yalnızca rastgele seçilen kontrolde. Yazı tura atılıyor olsaydı bu ayrışmanın yaklaşık yarı yarıya olması beklenirdi; testin ölçtüğü şey, gözlenen dağılımın rastlantıyla ne kadar uyuştuğu.

Bu ayrımın üzerinde durmak gerekiyor, çünkü en kolay kendimi kandıracağım yer burasıdır. Küçük p değeri ve sıfırı dışlayan aralık, **örnek sayısı kuralının yerine geçmez.** Aralık, verinin içindeki değişkenliği tarif eder; örnek sayısı kuralı ise o verinin ne kadar temsil edici olduğu hakkındaki şüpheyi tarif eder. 45 çift 35 görüntüden geliyor ve bu görüntüler, atlamalar yüzünden benim seçmediğim, aracın kusurunun belirlediği bir alt küme. Kusurun etiketlerle bir ilişkisi yok — deseni mekanik ve düzenli — ama "ilişkisi olmadığını düşünüyorum" ile "ölçtüm" aynı şey değil.

Bu yüzden bu bölümün ana sonucu şu etiketi taşıyor:

**İLGİNÇ AMA KANITLANMAMIŞ.** Bu test kümesinde ve önceden tanımlanmış görsel bağlam kuralında, yanlış pozitif bölgelerinde insan faaliyeti etiketi eşleştirilmiş kontrol bölgelerinden daha sık çıktı; yön beklenen biçimdeydi ve duyarlılık analizleri aynı yönü verdi. Ancak geçerli çift sayısı, önceden belirlenmiş eşiğin altında kaldığı için bağımsız bir sonuç kurulmuyor.

Hipotezin **doğrulandığı** söylenemez. Hipotezin **çürütüldüğü** de söylenemez: çürütme, beklenen yönün çıkmaması ya da farkın pratikte sıfıra yakın olduğunun gösterilmesi demektir; ölçülen bunun tam tersidir. Sonuç ikisinin arasında, açıkça işaretlenmiş bir yerde duruyor.

Bir noktanın altını ayrıca çiziyorum: **etiketlemenin burada durdurulması bir kapsam ve iş yükü kararıdır, ölçümün bir sonucu değildir.** Sayılar "yeterli veri toplandı, sonuç bu" demiyor; "toplanabilen veri bu kadar" diyor.

---

### 8.7. Eksik etiket ihtimali

Kategori dağılımına bakarken beklemediğim bir şey çıktı ve sonucun yorumunu doğrudan etkiliyor.

Geçerli çiftlerdeki 45 yanlış pozitifin **20'si**, alt kategori olarak "gerçek insan olabilir veya etiket şüphesi" seçeneğini aldı — yani etiketleyen, o bölgede gerçekten bir insan bulunabileceğini ya da veri kümesindeki etiketin eksik olabileceğini düşündü. Bu 20 kaydın hepsi birincil alanda "insan faaliyeti var" sayıldı; bir insan, tanımı gereği insan faaliyetidir.

Bunun anlamı şu: ölçülen farkın bir bölümü, "modelin insan yapımı nesnelere takılması"ndan değil, **veri kümesinde etiketlenmemiş gerçek insanlardan** geliyor olabilir. Böyle bir durumda o kutular aslında yanlış pozitif değil, eksik etiket yüzünden yanlış pozitif **sayılan** doğru tespitlerdir.

Bu iki mekanizma birbirinden çok farklı sonuçlar doğurur. Birincisi doğruysa, modelin öğrendiği görsel ipuçlarıyla ilgili bir sorun vardır. İkincisi doğruysa, sorun modelde değil **ölçüm hedefinin kendisindedir** ve o zaman bu projedeki bütün yanlış pozitif sayıları bir miktar şişkin demektir.

**Bu ayrım ölçülmedi.** Ayırmak için bu 20 kutunun gerçekten insan içerip içermediğini bağımsız biçimde belirlemek, yani veri kümesinin etiketlerini o karelerde yeniden değerlendirmek gerekir. Bu, ayrı bir iştir ve bu bölümün kapsamında yapılmadı. Burada yapabileceğim tek doğru şey, sayıyı yazmak ve farkın ne kadarının hangi mekanizmadan geldiğini **bilmediğimi** söylemektir.

Veri kalitesi ile model hatasını aynı sayıya karıştırmamak, bu projenin baştan beri taşıdığı ilkenin bu haftaki karşılığı.

---

### 8.8. Model ve kaynak kırılımları

İkinci soru, iki modelin yanlış pozitiflerinin bağlam bakımından farklı olup olmadığıydı. Bunun için iki modeli benzer bir yanlış pozitif yoğunluğunda çalıştırmak gerekiyordu; aynı güven eşiğinde karşılaştırmak anlamsız olurdu, çünkü aynı eşik iki modelde bambaşka çalışma noktalarına denk geliyor.

Burada bir engel vardı: tabanın yanlış pozitif **koordinatları** elimizde yoktu. Önceki bölümlerdeki kutu bazında kayıt yalnızca gerçek hedefleri ve onların eşleşip eşleşmediğini tutuyor; hiç eşleşmemiş bir tahminin nerede olduğunu söylemiyor. Kırpım üretebilmek için o koordinatlara ihtiyaç vardı, dolayısıyla taban bir kez daha tarandı — aynı karolama, aynı örtüşme, aynı eşleştirme ölçütü ve aynı cihazla, yalnızca bu kez tahmin kaydı da yazdırılarak. Tarama 16,8 dakika sürdü ve **önceki ölçümü birebir yeniden üretti**: üç güven eşiğinde de doğru bulunan ve yanlış pozitif sayıları eskisiyle aynı çıktı. Eski dosyaların hiçbirinin üzerine yazılmadı.

Model tarafında yeni bir tarama yapılmadı; önceki bölümden kalan tahmin kaydı kullanıldı. Onun da doğru okunduğunu aynı çapraz kontrolle sınadım ve altı kontrol noktasının beşinde sayılar birebir uyuştu. Altıncısında bir kutuluk fark çıktı ve sebebi öğretici: tahmin kayıtlarında skorlar dört basamağa yuvarlanarak saklanıyor. Ham skoru eşiğin hemen altında olan bir tahmin, yuvarlandıktan sonra eşiğe tam eşit görünüyor ve "eşikten büyük veya eşit" kuralından geçiyor. Fark tam olarak böyle bir tahminden geliyordu. Bunu bir ölçüm tutarsızlığı saymak yanlış olurdu; dosya biçiminin bilinen bir sınırı. Çapraz kontrol kuralını, farkın **yalnızca** bu yuvarlamayla açıklanabildiği durumda geçecek biçimde netleştirdim ve kuralın eski hâlini de kayda geçirdim.

Model eşiği, taban noktasının yanlış pozitif yoğunluğuna mutlak farkı en küçük yapan eşik olarak, önceden yazılmış bir kuralla seçildi. Eşik yükseltildiğinde eşleştirme baştan çalıştırılıyor; kayıttaki doğru/yanlış etiketi filtrelenmiyor, çünkü o etiket yalnızca kaydın yazıldığı taban eşiğinde geçerlidir.

| Model | Çalışma eşiği | Doğru bulunan | Yanlış pozitif | FP / görüntü | Recall |
|---|---|---|---|---|---|
| Taban-512 | 0,30 | 369 | 284 | 1,8089 | 0,3804 |
| Model-512 | 0,52 | 667 | 288 | 1,8344 | 0,6876 |

Kaynak: `reports/hafta7_esit_fp_adaylari.csv` (`scripts/25_esit_fp_adaylari.py`)

*Bu tablo ne söylüyor: İki nokta **yakın** ama eşit değil. Model-512'nin çalışma noktası tabanın yanlış pozitif yoğunluğunu 0,0255 kadar, yani görüntü başına yaklaşık %1,4 oranında aşıyor — mutlak olarak 4 kutu. Bu yüzden karşılaştırmayı "eşit yanlış pozitif bütçesi" diye adlandırmıyorum; doğru ifade **yakın yanlış pozitif çalışma noktalarıdır.** Aynı yoğunlukta Model-512'nin recall'ı tabanın neredeyse iki katı, ama bu bölümün konusu doğruluk değil; bu satırlar yalnızca karşılaştırmanın hangi noktada yapıldığını gösteriyor.*

Eşiği 0,53'e çekseydim model noktası tabanın altına inerdi. Bunu yapmadım: yeni bir çalışma noktası, yeni bir aday listesi ve yeni bir etiketleme turu demek olurdu ve etiketleme yükü burada durduruldu. Uyumsuzluğu düzeltmek yerine **kısıt olarak kaydediyorum.**

Bu kısıt yalnızca ikincil model karşılaştırmasını değil, birincil sonucu da ilgilendiriyor: 45 çift, iki modelin **yakın fakat tam eşit olmayan** çalışma noktalarından gelen örneklerin birleştirilmesiyle oluşuyor. Bu, birincil sonucu güçlendiren değil, ona bir belirsizlik daha ekleyen bir durumdur ve öyle yazılmalıdır.

| Grup | Geçerli çift | FP oranı | Kontrol oranı | Fark | %95 aralık | Örnek |
|---|---|---|---|---|---|---|
| Model-512 | 19 | 0,8353 | 0,3048 | +0,5305 | [0,1856; 0,8241] | bağımsız sonuç değil |
| Taban-512 | 26 | 0,7682 | 0,3257 | +0,4426 | [0,1642; 0,6870] | bağımsız sonuç değil |
| ZRI | 32 | 0,8398 | 0,3456 | +0,4942 | [0,2512; 0,7007] | bağımsız sonuç değil |
| ZRI hariç (VRD) | 13 | 0,3846 | 0,0769 | +0,3077 | [0,0000; 0,6154] | bağımsız sonuç değil |

Kaynak: `reports/hafta7_fp_insan_faaliyeti_analizi.csv` ve `reports/hafta7_fp_kaynak_kirilimi.csv`

*Bu tablo ne söylüyor: Dört grubun dördü de 50 çiftin altında, yani hiçbiri bağımsız olarak yorumlanamaz. Dolayısıyla **iki modelin bağlam dağılımının farklı olup olmadığı bu veriyle söylenemez** — aradaki 0,09'luk fark, her iki grubun kendi aralığının genişliği yanında anlamsızdır. Aynı şekilde ilişkinin tek bir kaynağa bağlı olup olmadığı da ayrılamadı: yön iki kaynakta da aynı, ama VRD tarafında 13 çift var ve aralığın alt ucu sıfıra değiyor. Burada dikkat edilecek bir nokta daha: VRD kaynağının test bölümünde 31 gerçek hedefi bulunuyor; bu sayı ile buradaki 13 çift farklı büyüklüklerdir ve birbirinin yerine kullanılamaz.*

---

### 8.9. Kategoriler ve araba örneği

Alt kategoriler, birincil ikili alanın altında açıklayıcı bir katman. 45 çiftin iki tarafındaki dağılım şöyle:

| Alt kategori | Yanlış pozitif bölgelerinde | Kontrol bölgelerinde |
|---|---|---|
| Gerçek insan olabilir / etiket şüphesi | 20 | 0 |
| Altyapı / ekipman | 14 | 0 |
| Başka | 8 | 0 |
| Belirsiz | 2 | 3 |
| Doğal bitki | 1 | 19 |
| Yol / patika | 0 | 12 |
| Kaya / toprak | 0 | 6 |
| Tarımsal / düzenli iz | 0 | 5 |
| **Araç** | **0** | 0 |

Kaynak: `reports/hafta7_fp_kategori_kirilimi.csv` (`scripts/27_fp_analiz.py`)

*Bu tablo ne söylüyor: İki taraf birbirinden belirgin biçimde ayrışıyor — yanlış pozitif tarafında insan şüphesi ve altyapı, kontrol tarafında doğal bitki ve yol öne çıkıyor. Ama **her hücre 50'nin altında**, dolayısıyla hiçbir kategori bağımsız bir sonuç taşımıyor; tablo yalnızca sinyalin nereden gelebileceğini gösteren bir betimlemedir. En büyük iki yanlış pozitif kategorisinin, bölüm 8.7'de anlattığım etiket şüphesi ile arazi üstü yapılar olması dikkat çekici, fakat ölçülmüş bir açıklama değil.*

Şimdi bu bölümü başlatan soruya dönüyorum. **Araç kategorisi, etiketlenen yanlış pozitiflerin hiçbirinde görülmedi.** Sayı sıfır.

Üstelik bunun yapısal bir sebebi de var: araba gözlemi GRO kaynaklı bir görüntüden geliyordu ve **test bölümünde GRO kaynaklı görüntü bulunmuyor.** Test bölümü 157 görüntüden oluşuyor ve biri ZRI (87 görüntü), diğeri VRD (70 görüntü) olmak üzere yalnızca iki kaynak içeriyor. Yani o örneğin kendisi bu ölçümde yeniden değerlendirilemezdi; ölçülebilecek tek şey, araç kategorisinin **başka görüntülerde tekrar edip etmediğiydi.**

Cevap: bu örneklemde tekrar etmedi. Dolayısıyla **dördüncü haftadaki araba gözlemi tekil bir gözlem olarak kalıyor ve genellenemiyor.** Yanlış pozitiflerin araçlarla ilişkili olduğu yönünde bir iddia bu bölümden çıkarılamaz. Ölçülen sinyal insan faaliyetiyle ilgilidir ve o sinyalin taşıyıcıları — görülebildiği kadarıyla — araçlar değil, altyapı öğeleri ve etiket şüphesi taşıyan bölgelerdir.

Protokolde önceden açıklayıcı olarak işaretlenmiş bir bakış daha var: insan faaliyeti işareti bulunan yanlış pozitiflerin ortalama güven skoru 0,5991, bulunmayanların 0,4855. Bu satır **bulgu etiketi taşımaz**; sonucu gördükten sonra bir eşik aranmadı ve bundan bir kural türetilmedi.

---

### 8.10. Ürün kararı

Ölçülen sinyal beklenen yöndeydi. Buna rağmen **operatör arayüzünde hiçbir şey değişmedi.**

- Aday sıralaması değişmedi.
- İnsan faaliyeti bağlamına dayanan yeni bir kural veya sezgisel eleme eklenmedi.
- Otomatik bir "insan faaliyeti skoru" yazılmadı.
- İnceleme kaydının ve model çıktısının anlamı aynı kaldı.

Bunun sebebi basit: **elimdeki kanıt bir müdahaleyi haklı çıkarmaya yetmiyor.** 45 çiftlik, tek etiketleyicili, kaynak ayrımı yapılamamış ve bir bölümü muhtemelen eksik etiketten gelen bir sinyalden yola çıkıp sıralamayı değiştirmek, operatörün gerçek adayları görme sırasını ölçülmemiş bir varsayıma bağlamak olurdu. Arama kurtarma bağlamında bunun bedeli, kaçırılan bir hedeftir.

Bundan daha temel bir sebep de var: **bir ilişki ölçümü, bir müdahalenin işe yarayacağının kanıtı değildir.** Yanlış pozitiflerin insan faaliyeti yakınında yoğunlaştığını göstermek, "insan faaliyeti olan yerleri aşağı sıralarsak sistem iyileşir" demek değildir; tam tersine, gerçek insanlar da çoğu zaman insan faaliyetinin yakınında bulunur. Böyle bir kuralın etkisi ancak ayrı bir müdahale deneyiyle ölçülebilir.

Bu haftanın kararı, gözlemi ölçmekle yetinmek oldu.

---

### 8.11. Kısıtlar ve sonraki adım

Bu bölümün ürettiği kanıt dar, ve sınırlarının tamamını yazmak sonucun kendisi kadar önemli:

- **45 geçerli çift**, önceden belirlenmiş 100 çiftlik eşiğin altında.
- **Görsel etiketleme tamamlanmadı**; kapsam bir iş yükü kararıyla durduruldu.
- **Tek etiketleyici**; annotatorlar arası güvenilirlik hiç ölçülmedi.
- **Yeniden-test yalnızca 14 kayıt** üzerinden yapılabildi.
- **Yanlış pozitiflerin 20'si etiket şüphesi taşıyor**; farkın ne kadarının eksik etiketten geldiği ölçülmedi.
- **Çalışma noktaları yakın ama eşit değil**; Model-512 tabanın yanlış pozitif yoğunluğunu %1,4 aşıyor ve birincil sonuç bu iki noktanın örneklerini birleştiriyor.
- **Kaynak grupları 50'nin altında**; ilişkinin kaynağa bağlı olup olmadığı ayrılamadı.
- **Bütün alt kategoriler 50'nin altında**; kategori dağılımı betimlemedir.
- **GRO kaynağı test bölümünde yok**; araba örneği yapısal olarak yeniden değerlendirilemezdi.
- **Tek veri kümesi ve iki kaynak**; başka arazi türlerine genelleme yapılamaz.
- **Nedensellik kurulmadı**; ölçülen bir birliktelik, bir mekanizma değil.

#### 8.11.1. Ölçüm ve analiz tarafında açık kalanlar

1. Yanlış pozitif ile kontrol bölgeleri arasındaki farkın, örnek sayısı eşiğini geçen bir kümede de sürüp sürmediği. Protokol, adaylar, kırpımlar ve analiz zinciri hazır ve değiştirilmedi; çalışma ileride genişletilirse aynı karar kuralı yeniden uygulanabilir. Bu bir **araştırma borcudur**, sıradaki zorunlu iş değildir.
2. Etiket şüphesi taşıyan yanlış pozitiflerin gerçekte eksik etiket olup olmadığı; bu ayrım yapılmadan farkın kaynağı bilinemez.
3. İki modelin bağlam dağılımının farklı olup olmadığı; gruplar 19 ve 26 çiftte kaldı.
4. İlişkinin kaynağa bağlı olup olmadığı; ZRI 32, VRD 13 çift.
5. Önceki bölümlerden devreden açık ölçümler: ONNX çıkarım süresindeki artışın mekanizması, kare toplam süresinin üst yüzdeliğindeki yükselmenin kaynağı, Model-320'nin eğitilip kendi ölçek tabanına karşı değerlendirilmesi ve büyük kutu bandındaki düşüşün kenar kuralıyla nedensel bağı.

#### 8.11.2. Bir sonraki adımda fiilen yapılacak iş

Sıradaki iş **projenin kapanışıdır** ve ölçüm değil mühendislik ve derleme işidir:

- **Güvenlik:** oturum belirtecinin saklanma biçimi, yenileme rotasyonunun bulunmayışı ve üretim ayarlarının gözden geçirilmesi. Bunlar önceki bölümlerde açık kısıt olarak kaydedilmişti.
- **Sürekli entegrasyon:** üç test paketinin, lint ve tür denetiminin her değişiklikte otomatik çalışması.
- **Dağıtım:** sistemin tek komutla ayağa kalkacak biçimde paketlenmesi ve kurulum adımlarının yazılması.
- **Gösterim:** uçtan uca çalışan bir tanıtım akışı.
- **Rapor bütünlemesi:** sekiz bölümün tek bir belgede birleştirilmesi, numaralandırmanın ve çapraz atıfların tutarlı hâle getirilmesi.
- **İngilizce çeviri** ve son kanıt denetimi: her sayının kaynağının ve her bağlantının yerinde olduğunun doğrulanması.

Bu bölümün bıraktığı en somut ders, ölçümle ilgili değil ölçüm aracıyla ilgili: **ölçüm aracı da ölçülmelidir.** Bir kusuru veriyi bozmadan, yalnızca kapsamı daraltarak da bir ölçümü sonuçsuz bırakabilir; üstelik böyle bir kusur, ürettiği veri tutarlı göründüğü için kolayca fark edilmeden kalır. Aracı üretimde çalıştığı koşulda sınamak, bu haftadan sonra ayrı bir adım değil, aracın kendisinin bir parçası.
