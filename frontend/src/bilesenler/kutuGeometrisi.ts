/**
 * Tespit kutusu geometrisi.
 *
 * Backend kutuları ORİJİNAL görüntü pikselinde verir (örn. 4000x3000), ama
 * görüntü ekranda çok daha küçük çizilir. Kutuyu hizalamanın iki yolu var:
 *
 *   1. Ekrandaki piksel boyutunu ölçüp kutuları px cinsinden yerleştirmek.
 *      Bu yol her yeniden boyutlandırmada yeniden ölçüm ister; ölçüm bir kare
 *      geç kalırsa kutular kayar.
 *   2. Kutuyu YÜZDE olarak vermek. Yüzde, sarmalayıcının o anki boyutuna göre
 *      tarayıcı tarafından çözülür; pencere büyüyüp küçülürken hiçbir JS
 *      çalışmadan hizalı kalır.
 *
 * İkincisi seçildi. Bu fonksiyon saf ve doğrudan test edilebilir.
 *
 * Taşma: backend kutuları frame sınırlarına zaten kırpıyor, ama arayüz buna
 * GÜVENMEZ -- bozuk veya eski bir kayıt görüntünün dışına taşmasın diye
 * burada da kırpılır.
 */

export interface KutuYerlesimi {
  /** Yüzde cinsinden, sarmalayıcıya göre. */
  solYuzde: number;
  ustYuzde: number;
  genislikYuzde: number;
  yukseklikYuzde: number;
}

export interface KutuKoordinati {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

function kirp(deger: number, enAz: number, enCok: number): number {
  return Math.min(enCok, Math.max(enAz, deger));
}

/**
 * Kutuyu yüzde yerleşimine çevirir.
 *
 * kareGenisligi/kareYuksekligi, Frame kaydındaki DOĞAL ölçülerdir; ekrandaki
 * ölçü değil. Sıfır veya geçersiz ölçü gelirse kutu çizilmez (null döner):
 * sıfıra bölmek NaN üretir ve kutu ekranın rastgele bir yerine düşer.
 */
export function kutuYerlesimi(
  kutu: KutuKoordinati,
  kareGenisligi: number,
  kareYuksekligi: number,
): KutuYerlesimi | null {
  if (
    !Number.isFinite(kareGenisligi) ||
    !Number.isFinite(kareYuksekligi) ||
    kareGenisligi <= 0 ||
    kareYuksekligi <= 0
  ) {
    return null;
  }

  // Ters çevrilmiş kutu (x2 < x1) gelirse normalize et.
  const solPiksel = kirp(Math.min(kutu.x1, kutu.x2), 0, kareGenisligi);
  const ustPiksel = kirp(Math.min(kutu.y1, kutu.y2), 0, kareYuksekligi);
  const sagPiksel = kirp(Math.max(kutu.x1, kutu.x2), 0, kareGenisligi);
  const altPiksel = kirp(Math.max(kutu.y1, kutu.y2), 0, kareYuksekligi);

  const genislikPiksel = sagPiksel - solPiksel;
  const yukseklikPiksel = altPiksel - ustPiksel;

  if (genislikPiksel <= 0 || yukseklikPiksel <= 0) {
    // Kırpma sonrası hiç alanı kalmamış: görüntünün tamamen dışındaydı.
    return null;
  }

  return {
    solYuzde: (solPiksel / kareGenisligi) * 100,
    ustYuzde: (ustPiksel / kareYuksekligi) * 100,
    genislikYuzde: (genislikPiksel / kareGenisligi) * 100,
    yukseklikYuzde: (yukseklikPiksel / kareYuksekligi) * 100,
  };
}

/**
 * Yüzde yerleşimini belirli bir ekran boyutundaki piksele çevirir.
 *
 * Üretimde kullanılmaz -- tarayıcı yüzdeyi kendisi çözer. Testlerde "farklı
 * ekran boyutlarında hizalama korunuyor mu" sorusunu sayısal olarak
 * cevaplayabilmek için var.
 */
export function yerlesiminPikseli(
  yerlesim: KutuYerlesimi,
  ekranGenisligi: number,
  ekranYuksekligi: number,
): { sol: number; ust: number; genislik: number; yukseklik: number } {
  return {
    sol: (yerlesim.solYuzde / 100) * ekranGenisligi,
    ust: (yerlesim.ustYuzde / 100) * ekranYuksekligi,
    genislik: (yerlesim.genislikYuzde / 100) * ekranGenisligi,
    yukseklik: (yerlesim.yukseklikYuzde / 100) * ekranYuksekligi,
  };
}
