# Hafta 7 — Yanlış pozitif görsel bağlam protokolü

Bu dosya rapor gövdesi değildir. **Sonuçlar görülmeden önce** sabitlenmesi
gereken kuralları toplar: örnekleme, taksonomi, körleme, dışlama ve analiz
kararları. Bu dosya commit edildikten sonra taksonomi veya ana analiz kuralı
"sonuçlar öyle çıktığı için" değiştirilmez. Gerçek bir hata bulunursa değişiklik
ayrı bir commit'te, eski ve yeni kural birlikte yazılarak yapılır.

Sabitlendiği an: bu dosyanın ilk commit'i. Bu commit'e kadar hiçbir aday
görüntü açılmadı, hiçbir kategori dağılımı hesaplanmadı.

---

## 1. Gözlem ve araştırma soruları

Hafta 4'ün göz kontrolünde bir yanlış pozitifin bir arabanın üzerine düştüğünü
gördüm. Bu **tek bir örnektir ve kanıt değildir**. Bu protokol o gözlemi tek
örnek olmaktan çıkarmayı, ölçülebilir bir soruya çevirmeyi amaçlıyor.

Sorular:

- **S1 (birincil).** Model-512'nin yanlış pozitif bölgeleri, aynı görüntülerden
  eşleştirilmiş kontrol bölgelerine göre insan faaliyeti işareti içerme
  bakımından farklı mı?
- **S2.** Eşit yanlış pozitif bütçesinde Taban-512 ve Model-512'nin yanlış
  pozitif bağlam dağılımı farklı mı?
- **S3.** Görülen bir ilişki belirli bir kaynak (özellikle ZRI) tarafından mı
  taşınıyor?
- **S4.** Yanlış pozitifler hangi görsel kategorilerde yoğunlaşıyor?
- **S5.** Hafta 4'teki araba örneği tekrar eden bir kategoriye mi ait, yoksa
  tekil bir örnek mi?

**S5 için baştan bilinen kısıt:** Araba gözlemi GRO kaynağından geldi. Test
bölümünde **GRO kaynaklı görüntü yok** (test bölümü: 87 ZRI + 70 VRD = 157
görüntü). Bu yüzden o örneğin kendisi bu analizde yeniden etiketlenemez. S5
ancak şu biçimde cevaplanabilir: test bölümünün yanlış pozitiflerinde araç
kategorisi tekrar ediyor mu ve minimum örnek kuralını geçiyor mu. Geçmezse
araba gözlemi tekil örnek olarak kalır ve genellenmez.

---

## 2. Ölçüm kümesi ve çalışma noktaları

**Küme:** HERIDAL test bölümü, 157 görüntü, 970 gerçek insan kutusu. Kaynaklar:
ZRI 87 görüntü / 939 kutu, VRD 70 görüntü / 31 kutu. Bu iki kaynak dışında
kaynak yok; "ZRI hariç" ile "VRD" bu bölümde aynı şeydir.

**Tarama rejimi (iki model için de aynı):** SAHI karolamalı tarama, karo 512,
örtüşme 0,2, `perform_standard_pred=False`, birleştirme NMS/IOU, eşleştirme
IoU 0,3, cihaz CPU, yalnızca `person` sınıfı.

**Taban-512 çalışma noktası — referans.** Ölçülmüş üç noktadan `conf = 0,30`
alınır. Bu noktada ölçülmüş değerler: TP 369, FP 284, FP/görüntü 1,81,
recall 0,3804 (`reports/test_taban_cizgisi.csv`, TOPLAM satırı). Bu nokta
referans seçildi çünkü tabanın ölçülmüş üç noktasından etiketleme yükü
taşınabilir olan tek nokta budur (diğer ikisi 856 ve 2863 FP üretiyor).

**FP bütçesi:** Tabanın bu noktadaki **FP/görüntü değeri**, yani 1,81.

**Model-512 çalışma noktası — bütçeye göre seçilir.** Kural: 0,05'ten 0,95'e
0,01 adımla taranan eşikler arasından `|FP_görüntü_başına − 1,81|` değerini en
küçük yapan eşik seçilir; eşitlik durumunda **büyük eşik** (daha az FP) kazanır.
Mevcut eşik taramasında bu kural `conf = 0,52` noktasını (FP/görüntü 1,83)
işaret ediyor; kesin değer ölçüm script'inde tahmin kaydından yeniden
hesaplanacak ve seçilen eşik çıktı CSV'sine yazılacak.

**Aynı confidence değeri karşılaştırma noktası sayılmaz.** İki modelin 0,30'daki
davranışı karşılaştırılmaz; karşılaştırma yalnızca eşit FP bütçesinde yapılır.

**Eşik uygulaması ham skor üzerinden.** Tahmin kaydındaki skorlar dört basamağa
yuvarlanmış olarak saklanıyor. Karşılaştırma `skor >= eşik` biçiminde, CSV'deki
saklanan değer üzerinden yapılır ve bu kural script'te tek bir yerde durur;
ekranda gösterilen biçimlendirilmiş değer karşılaştırmada kullanılmaz.

**Yeniden çıkarım.** Model-512'nin NMS sonrası tahmin kaydı zaten var
(`reports/tahminler_model512.csv`); yeniden taranmaz. Taban-512'nin tahmin kaydı
**yok** — mevcut kutu bazında dosya yalnızca gerçek kutuları içeriyor, yanlış
pozitiflerin koordinatlarını içermiyor. Bu yüzden taban için aynı rejimle bir
kez tarama yapılır ve `reports/tahminler_taban512_hafta7.csv` üretilir. Eski
dosyaların hiçbirinin üzerine yazılmaz. Bu tarama analiz veya etiketleme
sırasında tekrarlanmaz.

---

## 3. Yanlış pozitif tanımı ve eşleştirme

- **FP:** Çalışma eşiğinde kalan, NMS sonrası bir tahmin kutusunun hiçbir gerçek
  insan kutusuyla IoU ≥ 0,3 eşleşmesi kuramaması.
- **Eşleştirme:** Mevcut ölçüm kodundaki eşleştirme kullanılır — tahminler skora
  göre azalan sırada gezilir, her gerçek kutu en fazla bir tahminle eşleşir,
  skor eşitliğinde indeks sırası belirleyicidir.
- **Eşik yükseltildiğinde eşleştirme yeniden yapılır.** Tahmin kaydındaki
  TP/FP sütunu yalnızca kayıt tabanı eşiğinde (0,05) geçerlidir. Daha yüksek bir
  eşikte düşük skorlu bir TP elendiğinde, aynı gerçek kutuyu daha düşük IoU ile
  gören başka bir tahmin TP olabilir. Bu yüzden çalışma eşiğinde eşleştirme
  sıfırdan çalıştırılır; saklanan sütun filtrelenmez.
- **Tekrarlanan/örtüşen tahmin politikası:** Tahminler zaten NMS sonrasıdır, ek
  bir birleştirme yapılmaz. Yine de aynı görüntüde iki FP birbiriyle IoU > 0,5
  örtüşürse yüksek skorlu olan tutulur, diğeri `ortusen_fp` gerekçesiyle
  dışlanır. Amaç neredeyse aynı iki kırpımı bağımsız iki örnek saymamak.

**Çapraz kontrol.** Üretilen tahmin kaydından hesaplanan TP/FP toplamları,
mevcut özet CSV'lerdeki ölçülmüş değerlerle karşılaştırılır (taban için
conf 0,05 / 0,15 / 0,30; model için aynı üç nokta). Uyuşmazsa analiz
durdurulur.

---

## 4. Kontrol bölgeleri

Yalnızca FP kategorilerini saymak bir ilişki ölçmez: görüntülerin kendisi zaten
insan faaliyeti bakımından zengin olabilir. Bu yüzden her FP için bir **kontrol
bölgesi** üretilir.

Kontrol kuralları:

1. **Aynı görüntüden** seçilir; böylece arazi, kaynak, çözünürlük ve çekim
   koşulu eşlenmiş olur.
2. FP kutusuyla **aynı genişlik ve yüksekliğe** sahiptir.
3. Görüntü sınırları içinde tamamen geçerlidir.
4. Hiçbir gerçek insan kutusuyla **çakışmaz** (IoU = 0 ve merkez içermez).
5. İlgili modelin o görüntüdeki hiçbir tahminiyle (TP veya FP) IoU > 0,1
   çakışmaz.
6. Konum **rastgele** seçilir; tohum sabittir (`TOHUM = 20260913`).
7. İçeriğine bakılarak seçilmez. Kontrolün insan faaliyeti içerip içermediği
   seçim ölçütü değildir.
8. En fazla 200 deneme yapılır. Uygun bölge bulunamazsa FP–kontrol çifti
   **birlikte** dışlanır ve gerekçe `kontrol_bulunamadi` olarak kaydedilir.

---

## 5. Örnekleme

Bütün FP'leri etiketlemek iki model için yaklaşık 570 kutu + 570 kontrol =
1140 kırpım demektir; bu tek bir kişi için taşınabilir bir yük değil. Bu yüzden
önceden tanımlı bir örnekleme yapılır.

- **Model başına hedef: 110 FP.** Dışlamalar sonrasında her ana grupta en az
  100 geçerli kutu kalmasını hedefler (100 ve üzeri ana bulgu için
  kullanılabilir).
- **Katmanlama kaynağa göre.** Bir kaynağın o modeldeki FP sayısı 55'ten azsa o
  kaynağın **tamamı** alınır; kalan kontenjan diğer kaynaktan sabit tohumlu
  rastgele örneklemeyle doldurulur. Amaç, kaynak sorusunun (S3) cevaplanabilmesi
  için küçük kaynağın örneklemde ezilmemesi.
- **Katmanlama analizde telafi edilir.** Örnekleme oransal olmadığı için
  birleşik oranlar, her katmanın seçilme olasılığının tersiyle ağırlıklandırılır.
  Ağırlıksız kaynak bazında oranlar ayrıca raporlanır.
- **Her FP için bir kontrol**, yani model başına en fazla 220 kırpım çifti, iki
  model için toplam en fazla **440 aday**.
- Örnek büyüklüğü **sonuçlara bakılarak değiştirilmez.**

---

## 6. Görsel kırpımlar

Her aday için iki görsel üretilir.

- **Sıkı kırpım:** kutunun kendisi, her yönde kutu kenarının %10'u kadar pay ile;
  kenar uzunluğu en az 64 piksel olacak biçimde genişletilir.
- **Bağlam kırpımı:** kutu merkezli kare pencere. Kenar = `max(8 × kutunun uzun
  kenarı, 512 piksel)`. **Bu katsayı bir karardır**, ölçümden türetilmedi:
  insan boyu bir kutunun çevresinde araç, çatı, yol veya çit görülebilmesi için
  kutunun birkaç katı alan gerektiği varsayımına dayanır.
- Pencere görüntü sınırını aşarsa **kaydırılır** (kırpılmaz), böylece alan
  korunur; kaydırma miktarı manifest'e yazılır.
- Görüntüler gösterim için en fazla 640 piksel genişliğe küçültülür; kutunun
  kendisi işaretlenmez — işaretlemek FP ile kontrolü ayırt edilebilir kılabilir.
- Kırpımlar Git'e eklenmez: üretilebilir ve büyüktürler. Üreten script,
  manifest ve etiketler commit edilir.

---

## 7. Körleme

Etiketleyen kişi şunların **hiçbirini** görmez:

- model kimliği (Taban-512 / Model-512),
- adayın FP mi kontrol mü olduğu,
- güven skoru,
- TP/FP bilgisi,
- kaynak öneki,
- görüntü dosyasının gerçek adı.

Her aday `a0001` biçiminde bir **kör kimlik** alır. Kimlikler bütün adaylar
(iki model, FP ve kontrol) birlikte karıştırıldıktan sonra sabit tohumla
verilir; kimlik sırası gruptan bağımsızdır. Kırpım dosyaları yalnızca kör
kimliğe göre adlandırılır.

- **Etiketleme arayüzü körleme anahtarını okumaz.**
- Anahtar ayrı dosyada: `reports/hafta7_fp_korleme_anahtari.csv`.
- Çözüm yalnızca etiketler kilitlendikten sonra, analiz aşamasında yapılır.

---

## 8. Taksonomi

**Birincil alan — insan faaliyeti (`insan_faaliyeti`):** `var` / `yok` /
`belirsiz`.

"Var" için görünür kanıt örnekleri: araç; bina, çatı veya yapı; yol, patika veya
zemin izi; çit, direk veya altyapı; makine/ekipman; düzenli tarım ya da insan
yapımı geometrik düzen; başka açık insan yapımı nesne.

**Alt kategori (`alt_kategori`) — tek ve zorunlu.** Birden çok öğe varsa
**kutuya en yakın olan** seçilir; eşit yakınlıkta görsel olarak **baskın** olan
seçilir.

| Değer | Anlamı |
|---|---|
| `arac` | Araba, kamyon, traktör, motosiklet vb. |
| `yapi_cati` | Bina, çatı, baraka, duvar |
| `yol_patika` | Yol, patika, tekerlek izi, açılmış zemin |
| `altyapi_ekipman` | Direk, çit, tank, makine, ekipman |
| `tarimsal_duzen` | Tarla, sıra dikim, insan yapımı geometrik düzen |
| `dogal_bitki` | Ağaç, çalı, ot, yaprak |
| `kaya_toprak` | Kaya, taş, çıplak toprak, moloz |
| `golge_isik` | Gölge, parlama, kontrast artefaktı |
| `su` | Su birikintisi, dere, göl |
| `insan_suphesi` | Gerçek insan olabilir veya etiket eksikliği şüphesi |
| `baska` | Yukarıdakilerin hiçbiri |
| `belirsiz` | Karar verilemedi |

`arac` kategorisi araba gözlemi için **özel olarak yaratılmadı**; genel bir
kategoridir ve araba doğal olarak içine düşer.

**Ek alanlar:**

- `guven`: `yuksek` / `orta` / `dusuk`
- `goruntu_yeterli`: `evet` / `hayir`
- `yeniden_incele`: `evet` / `hayir`
- `not`: isteğe bağlı serbest metin

**Birincil sonuç ikili insan faaliyeti alanıdır**; alt kategoriler açıklayıcıdır
ve çoğu 50'nin altında kalabilir.

---

## 9. Dışlama ve belirsizlik kuralları

Bir aday şu gerekçelerle analiz dışı kalır:

| Gerekçe | Ne zaman |
|---|---|
| `ortusen_fp` | Aynı görüntüde başka bir FP ile IoU > 0,5 |
| `kontrol_bulunamadi` | 200 denemede geçerli kontrol bölgesi bulunamadı |
| `kirpim_gecersiz` | Kırpım üretilemedi veya bozuk |
| `goruntu_yetersiz` | Etiketleyen "görüntü yeterli değil" dedi |
| `esi_dislandi` | Çiftin diğer üyesi dışlandı |

**Eşleştirilmiş tasarım gereği dışlama çift bazındadır:** FP veya kontrolden
biri düşerse ikisi birden düşer.

**Belirsiz etiketler zorla bir sınıfa sokulmaz.** Birincil analizde
`insan_faaliyeti = belirsiz` olan çiftler dışlanır. Ayrıca iki duyarlılık
analizi yapılır ve üçü birlikte raporlanır: (a) belirsiz → `yok`,
(b) belirsiz → `var`. Üç sonucun yönü aynı değilse sonuç en fazla "ilginç ama
kanıtlanmamış" olabilir.

---

## 10. Etiket kalitesi

- Sabit tohumlu **%10'luk** bir kalite örneği **manifestten** seçilir ve aynı
  etiketleme oturumunun ikinci turunda, farklı bir sırayla ve önceki cevap
  gösterilmeden yeniden etiketlenir. Örnek grup bilgisinden hâlâ kördür.

  > **Kural değişikliği (protokol ilk commit'inden sonra, sonuçlar görülmeden).**
  > Eski kural: "Etiketler kilitlendikten sonra sabit tohumlu %10'luk bir kalite
  > örneği seçilir." Yeni kural: örnek manifestten, etiketlerden bağımsız olarak
  > önceden seçilir ve aynı oturumun ikinci turunda etiketlenir.
  > Gerekçe: eski kural etiketleme bittikten sonra ikinci bir insan oturumu
  > gerektiriyordu; oysa bu iş için tek bir duraklama öngörülmüştü. Seçim
  > etiketlerin içeriğine hiçbir aşamada bakmadığı için sonuç üzerindeki etkisi
  > yoktur: her iki kuralda da örnek sabit tohumlu ve gruptan kördür. Değişiklik
  > hiçbir aday görüntü açılmadan ve hiçbir dağılım hesaplanmadan yapıldı.
- Ölçülenler: tam uyum oranı, insan faaliyeti ikili alanında uyum, belirsiz
  oranı, alt kategori uyumu.
- Bu **tek annotator yeniden-test tutarlılığıdır**; annotatorlar arası
  güvenilirlik DEĞİLDİR ve öyle adlandırılmaz.
- İkili alandaki yeniden-test uyumu **0,80'in altında kalırsa** dağılım
  "ölçüldü" diye kapatılmaz: sonuç en fazla "ilginç ama kanıtlanmamış" olur ve
  belirsizlik raporlanır. Taksonomi sonuçlara göre değiştirilmez.

---

## 11. İstatistik planı

**Birincil analiz — eşleştirilmiş karşılaştırma.** Her FP ve kendi kontrolü bir
çifttir. Ölçülen büyüklük, insan faaliyeti oranları arasındaki **eşleştirilmiş
fark**: `p(FP) − p(kontrol)`.

- **Test:** uyumsuz çiftler üzerinde McNemar (tam binom). Eşleştirilmiş tasarıma
  uygun olan budur; iki bağımsız oran testi burada geçerli değildir, çünkü çiftin
  iki üyesi aynı görüntüden geliyor.
- **Görüntü düzeyinde bağımlılık:** Aynı görüntüden birden çok çift gelebilir;
  bunları bağımsız saymak güven aralığını yapay olarak daraltır. Bu yüzden güven
  aralığı **görüntü düzeyinde küme bootstrap** ile üretilir: görüntüler yerine
  koymalı olarak 10 000 kez yeniden örneklenir (tohum sabit), her yinelemede o
  görüntülerin bütün çiftleri birlikte alınır, ağırlıklı fark hesaplanır ve
  %2,5–%97,5 yüzdelikleri raporlanır.
- **Katmanlama ağırlığı:** Her çift, kendi katmanının (model × kaynak) seçilme
  olasılığının tersiyle ağırlıklandırılır.
- **Etki büyüklüğü:** mutlak fark ve odds oranı (eşleştirilmiş, uyumsuz çift
  oranından) birlikte verilir.
- **İstatistiksel anlamlılık tek başına pratik önem sayılmaz;** mutlak fark ve
  güven aralığının genişliği birlikte yorumlanır.

**İkincil analiz 1 — model karşılaştırması (S2).** Eşit FP bütçesinde Taban-512
ve Model-512 FP'lerinin insan faaliyeti oranı, kategori dağılımı ve kaynak
dağılımı karşılaştırılır. İki modelin FP'leri aynı görüntülerden geldiği için
bağımsız değildir; fark için güven aralığı yine görüntü düzeyinde küme bootstrap
ile üretilir. Bu, çifte eşleştirilmiş bir tasarım değildir ve kısıt olarak
yazılır.

**İkincil analiz 2 — kaynak kırılımı (S3).** ZRI, ZRI hariç (VRD) ve varsa
toplam ayrı ayrı raporlanır. Bir kaynakta geçerli örnek sayısı 50'nin altındaysa
o kaynak bağımsız yorumlanmaz; sayı yazılır ve "az örnek" bayrağı konur.
Kaynak başına gerçek FP/kontrol örnek sayısı, o kaynaktaki gerçek hedef
sayısından (VRD'de 31) ayrı bir büyüklüktür ve karıştırılmaz.

**İkincil analiz 3 — kategori dağılımı ve araba sorusu (S4, S5).** Alt kategori
sayımları verilir. `arac` kategorisinin toplam örnek sayısı ayrıca yazılır;
50'nin altındaysa yalnızca örnek olarak kalır ve oran ya da mekanizma iddiası
kurulmaz.

**İkincil analiz 4 — skor ilişkisi (açıklayıcı).** FP güven skoru ile insan
faaliyeti etiketi arasındaki ilişki incelenir. **Bu analiz baştan açıklayıcı
olarak işaretlenmiştir:** sonucu görüp uygun eşik aranmaz, çoklu deneme yapılmaz
ve bulgu etiketi verilmez.

---

## 12. Sonuç dili ve karar kuralları

Sonuç üç etiketten biriyle yazılır ve etiket aşağıdaki kurallarla önceden
bağlanmıştır.

**BULGU** — hepsi birden sağlanırsa:

1. Birincil karşılaştırmada geçerli çift sayısı ≥ 100.
2. Ağırlıklı eşleştirilmiş farkın %95 güven aralığı sıfırı **dışlıyor** ve
   beklenen yönde (FP oranı > kontrol oranı).
3. İki duyarlılık analizi (belirsiz → yok, belirsiz → var) de aynı yönü veriyor.
4. Yeniden-test ikili uyumu ≥ 0,80.
5. Yön, geçerli örneği 50 ve üzeri olan hiçbir kaynakta tersine dönmüyor.

**ÇÜRÜTÜLDÜ** — şunlardan biri olursa:

1. Güven aralığı sıfırı dışlıyor ama **ters yönde**; veya
2. Geçerli çift sayısı ≥ 100 iken güven aralığı sıfırı içeriyor **ve** iki ucu da
   ±0,05'ten küçük, yani beklenen yönde pratikte anlamlı bir fark yok.

**İLGİNÇ AMA KANITLANMAMIŞ** — yukarıdaki iki kümenin dışındaki her durum:
yön beklenen biçimde ama güven aralığı sıfırı içeriyor, örnek yetersiz,
duyarlılık analizleri ayrışıyor, yeniden-test uyumu düşük veya etki tek bir
kaynağa bağlı.

**Kurulmayacak cümleler.** Sonuç ne çıkarsa çıksın şunlar yazılmaz: "model insan
faaliyetini anlıyor", "yanlış pozitifler kesinlikle insan faaliyetidir",
"araçlar yanlış pozitiflerin sebebidir", "bu ilişki bütün arazi türlerinde
geçerlidir", "ZRI sonucu veri kümesinin tamamını temsil eder", "istatistiksel
fark sahada güvenli çalışma kanıtıdır". Bu bir **ilişki** ölçümüdür; nedensellik
iddiası kurulmaz ve model doğruluğu yeniden tanımlanmaz.

---

## 13. Ürün davranışına etki

Bu hafta **yeni heuristic, yeni model veya otomatik "insan faaliyeti skoru"
eklenmez.** Analiz sonucu ne olursa olsun operatör sıralaması bu ölçümle
doğrudan değiştirilmez; karar ayrı bir adımda ve ayrı bir müdahale deneyiyle ele
alınır. Önce gözlem ölçülür.

---

## 14. Üretilecek dosyalar

| Dosya | İçerik |
|---|---|
| `reports/tahminler_taban512_hafta7.csv` | Taban-512 NMS sonrası tahmin kaydı (yalnızca eksik olduğu için üretilir) |
| `reports/hafta7_esit_fp_adaylari.csv` | Eşit FP bütçesinde iki modelin tahminleri, TP/FP durumu ve kör aday kimliği |
| `reports/hafta7_fp_etiket_manifesti.csv` | Etiketlenecek kör adaylar ve kırpım yolları |
| `reports/hafta7_fp_korleme_anahtari.csv` | Kör kimlik → model, FP/kontrol, kaynak, skor çözümü |
| `reports/hafta7_fp_gorsel_etiketler.csv` | Etiketleme aracının çıktısı |
| `reports/hafta7_fp_etiket_kalite.csv` | Yeniden-test tutarlılığı |
| `reports/hafta7_fp_insan_faaliyeti_analizi.csv` | Birincil analiz |
| `reports/hafta7_fp_kaynak_kirilimi.csv` | Kaynak bazında kırılım |
| `reports/hafta7_fp_kategori_kirilimi.csv` | Alt kategori kırılımı |

---

## 15. Sabitlenen kararlar özeti

Aşağıdakiler **karardır, ölçüm değildir** ve sonuçlara göre değiştirilmez:

- FP bütçesi referansı: Taban-512 `conf = 0,30` (FP/görüntü 1,81).
- Model eşiği seçim kuralı: bütçeye mutlak farkı en küçük eşik, eşitlikte büyük
  eşik.
- Eşleştirme IoU'su: 0,3.
- Örtüşen FP eleme eşiği: IoU > 0,5.
- Kontrol–tahmin çakışma sınırı: IoU > 0,1.
- Bağlam kırpım katsayısı: 8×, en az 512 piksel.
- Model başına hedef FP sayısı: 110; katman tabanı 55.
- Rastgelelik tohumu: 20260913.
- Bootstrap yineleme sayısı: 10 000.
- Minimum örnek kuralları: ≥ 100 ana bulgu, 50–99 "az örnek", < 50 bağımsız
  sonuç değil.
- Yeniden-test kabul eşiği: ikili alanda 0,80.
