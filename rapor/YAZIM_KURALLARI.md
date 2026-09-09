# Rapor Yazım Kuralları

Bu dosya rapor gövdesinin parçası değildir; `bolum_*.md` dosyalarını yazarken
uyulacak kuralları toplar. **Yeni bir bölüm yazmadan önce bu dosya okunur.**

---

## 1. Okuyucu deponun içini bilmez

Rapor, bu projenin dosya yapısını hiç görmemiş birine yazılır. Rapor gövdesinde
**depo içi referans verilmez**: README'ye, klasör adına veya başka bir dosyanın bölüm
numarasına yönlendirme yapılmaz.

- Yanlış: "Dosya listesi için README bölüm 6'ya bakınız."
- Doğru: "Ölçüm çıktıları bölüm 1.15'te listelidir." (raporun kendi eki)

Script adları geçebilir, çünkü hangi kodun hangi sayıyı ürettiğini belirtmek okuyucuya
bilgi verir. Depoya özgü bir liste gerekiyorsa raporun kendi **ekine** konur ve rapor
içinden o eke atıf yapılır.

## 2. Bölüm dosyasının yapısı

Her bölüm dosyası şu iki satırla başlar ve başka üst düzey başlık taşımaz:

```
## N. Başlık

*(bu bölümde ele alınan konuların kısa özeti)*
```

Alt bölümler `### N.M`, onların altındakiler `#### N.M.K` biçiminde numaralanır.
Bölüm dosyasının içinde ikinci bir `##` başlığı bulunmaz.

## 3. Kanıt gücü etiketleri zorunlu

Kanıt gücü farklı olan iddialar aynı dille sunulmaz. Dört etiket kullanılır:

| Etiket | Anlamı |
|---|---|
| **BULGU** | Çok örnekli, istatistiksel olarak sağlam sonuç |
| **HİPOTEZ** | Az örnekli veya henüz ölçülmemiş açıklama |
| **ÇÜRÜTÜLDÜ** | Ölçülüp elenmiş, yanlış çıkmış tahmin |
| **İLGİNÇ AMA KANITLANMAMIŞ** | Sinyal var, ama başka bir değişkenle karışık olduğu için bağımsız açıklama sayılmaz |

Çürütülen hipotezler kısaltılmaz. Her biri için üç şey yazılır: ne tahmin edildi,
nasıl ölçüldü, ne çıktı.

## 4. Her tablonun altında yorum

Her tablodan hemen sonra italik bir **"Bu tablo ne söylüyor:"** paragrafı gelir.
Tablo tek başına bırakılmaz; okuyucunun sayılardan hangi sonucu çıkarması gerektiği
yazılır.

## 5. Ölçülmemiş şey için sayı verilmez

Rapordaki her sayı üretilmiş bir çıktı dosyasından okunur. Tahmin edilen, yuvarlanan
veya hatırlanan değer yazılmaz. Türetilmiş bir değer gerekiyorsa (örneğin bir
görüntünün kaç karoya bölündüğü) hesap kodun kendisi çalıştırılarak yaptırılır.

**Bir sayı ile CSV çelişirse CSV kazanır.** Metin düzeltilir, CSV değil.

## 6. Künyeler değiştirilmeden aktarılır

Başka kaynakların künyeleri (BibTeX, akademik atıf) hiçbir alanı değiştirilmeden,
kaynaktaki haliyle aktarılır. Yıl, ay veya yazar alanı kendiliğinden "düzeltilmez".

Erişim tarihi künyenin kendi alanlarına karıştırılmaz; ayrı bir alana (`note` gibi)
yazılır.

Emin olunmayan bir atıf yazılmaz. Künye eksikse yazar olarak işaretlenir ve teyit
edilmeden rapora girmez.

## 7. "Sonraki adım" ikiye ayrılır

Bu bölüm iki ayrı başlık taşır ve ikisi birbirine karıştırılmaz:

- **(a) Ölçüm/analiz tarafında açık kalanlar** — cevaplanmamış sorular, yapılmamış
  ölçümler, doğrulanmayı bekleyen hipotezler.
- **(b) Bir sonraki adımda fiilen yapılacak iş** — o adımda somut olarak ne
  kurulacak veya yazılacak.

Bir ölçümün açık kalması, sıradaki işin o ölçüm olduğu anlamına gelmez.

## 8. Abartı yasak

Bu bir eğitim ve araştırma prototipidir. "Hayat kurtarır", "state of the art", "en
iyi", "devrim niteliğinde" gibi ifadeler kullanılmaz. Sonuçlar ölçüldüğü kadarıyla,
sınırlarıyla birlikte sunulur.

Örneklemi 50 kutunun altında olan kaynaklar tabloda gösterilebilir, ancak **"az
örnek" olarak işaretlenir** ve metinde tek tek yorumlanmaz.

---

## Üslup

Birinci tekil ve aktif dil kullanılır: "ölçtüm", "yaptım" — "gerçekleştirilmiştir"
değil. Cümleler kısa tutulur, her paragraf tek fikir taşır. Teknik terimler ilk
geçtikleri yerde tek cümleyle açıklanır. Hiçbir sayı çıplak bırakılmaz; yanında ne
anlama geldiği yazar.
