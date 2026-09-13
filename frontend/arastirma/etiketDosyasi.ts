/**
 * Etiket dosyasının saf (dosya sistemi bilmeyen) kuralları.
 *
 * Burada dosya okunmaz/yazılmaz; yalnızca CSV çözümleme, doğrulama ve sıraya
 * koyma yapılır. Böylece kurallar gerçek dosya açmadan test edilebiliyor.
 *
 * İki değişmez bu dosyanın varlık sebebi:
 *   1. Manifestte olmayan bir kör kimlik kabul edilmez.
 *   2. Bir (kimlik, mod) çiftinin AKTİF etiketi tektir; yeniden etiketleme
 *      eskisini değiştirir, ikinci bir satır eklemez.
 */

import { ALT_KATEGORILER, BIRINCIL, GUVEN } from "./taksonomi";

export const ETIKET_SUTUNLARI = [
  "kor_kimlik",
  "mod",
  "insan_faaliyeti",
  "alt_kategori",
  "guven",
  "goruntu_yeterli",
  "yeniden_incele",
  "not",
  "etiket_sirasi",
  "kaydedilme_zamani",
] as const;

export type EtiketSutunu = (typeof ETIKET_SUTUNLARI)[number];
export type Etiket = Record<string, string>;

export const MODLAR = ["ana", "kalite"] as const;

const BIRINCIL_DEGERLER = new Set<string>(BIRINCIL.map((b) => b.deger));
const ALT_DEGERLER = new Set<string>(ALT_KATEGORILER.map((a) => a.deger));
const GUVEN_DEGERLER = new Set<string>(GUVEN.map((g) => g.deger));

export function anahtar(kimlik: string, mod: string): string {
  return `${mod}:${kimlik}`;
}

/** Basit ama alıntılı alanları doğru çözen CSV okuyucu. */
export function csvCoz(metin: string): Etiket[] {
  const satirlar = csvSatirlari(metin);
  if (satirlar.length === 0) return [];
  const basliklar = satirlar[0];
  return satirlar.slice(1)
    .filter((s) => s.length > 1 || (s.length === 1 && s[0] !== ""))
    .map((s) => Object.fromEntries(basliklar.map((b, i) => [b, s[i] ?? ""])));
}

function csvSatirlari(metin: string): string[][] {
  const satirlar: string[][] = [];
  let alan = "";
  let satir: string[] = [];
  let alintida = false;
  for (let i = 0; i < metin.length; i += 1) {
    const karakter = metin[i];
    if (alintida) {
      if (karakter === '"') {
        if (metin[i + 1] === '"') { alan += '"'; i += 1; } else { alintida = false; }
      } else { alan += karakter; }
      continue;
    }
    if (karakter === '"') { alintida = true; }
    else if (karakter === ",") { satir.push(alan); alan = ""; }
    else if (karakter === "\n") { satir.push(alan); satirlar.push(satir); satir = []; alan = ""; }
    else if (karakter !== "\r") { alan += karakter; }
  }
  if (alan !== "" || satir.length > 0) { satir.push(alan); satirlar.push(satir); }
  return satirlar;
}

export function csvYaz(satirlar: Etiket[], basliklar: string[]): string {
  const kacir = (deger: string) =>
    /[",\n]/.test(deger) ? `"${deger.replace(/"/g, '""')}"` : deger;
  const govde = satirlar.map((s) => basliklar.map((b) => kacir(s[b] ?? "")).join(","));
  return [basliklar.join(","), ...govde].join("\n") + "\n";
}

export interface DogrulamaSonucu {
  gecerli: boolean;
  hata?: string;
}

/**
 * Gelen bir etiket isteğini doğrular.
 *
 * Manifest dışı kimlik reddedilir: aksi halde elle uydurulmuş veya eski bir
 * koşudan kalmış bir kimlik analiz dosyasına sızabilirdi.
 */
export function etiketiDogrula(
  istek: Etiket,
  manifestKimlikleri: ReadonlySet<string>,
): DogrulamaSonucu {
  const kimlik = (istek.kor_kimlik ?? "").trim();
  if (!kimlik) return { gecerli: false, hata: "Kör kimlik boş." };
  if (!manifestKimlikleri.has(kimlik)) {
    return { gecerli: false, hata: `Manifest dışı kimlik reddedildi: ${kimlik}` };
  }
  const mod = (istek.mod ?? "ana").trim();
  if (!(MODLAR as readonly string[]).includes(mod)) {
    return { gecerli: false, hata: `Bilinmeyen mod: ${mod}` };
  }
  if (!BIRINCIL_DEGERLER.has(istek.insan_faaliyeti ?? "")) {
    return { gecerli: false, hata: "İnsan faaliyeti alanı eksik veya geçersiz." };
  }
  if (!ALT_DEGERLER.has(istek.alt_kategori ?? "")) {
    return { gecerli: false, hata: "Alt kategori eksik veya geçersiz." };
  }
  if (!GUVEN_DEGERLER.has(istek.guven ?? "")) {
    return { gecerli: false, hata: "Güven alanı eksik veya geçersiz." };
  }
  for (const alan of ["goruntu_yeterli", "yeniden_incele"]) {
    if (!["evet", "hayir"].includes(istek[alan] ?? "")) {
      return { gecerli: false, hata: `${alan} yalnızca evet/hayir olabilir.` };
    }
  }
  return { gecerli: true };
}

/**
 * Etiketi kayıt kümesine yerleştirir. Aynı (kimlik, mod) varsa DEĞİŞTİRİR.
 * Sıra numarası korunur; böylece etiketleme sırası yeniden yazmada kaybolmaz.
 */
export function etiketiYerlestir(
  mevcut: ReadonlyMap<string, Etiket>,
  istek: Etiket,
  zaman: string,
): Map<string, Etiket> {
  const sonuc = new Map(mevcut);
  const mod = (istek.mod ?? "ana").trim();
  const kimlik = istek.kor_kimlik.trim();
  const anah = anahtar(kimlik, mod);
  const onceki = sonuc.get(anah);
  const sira = onceki?.etiket_sirasi ?? String(sonuc.size + 1);
  sonuc.set(anah, {
    kor_kimlik: kimlik,
    mod,
    insan_faaliyeti: istek.insan_faaliyeti,
    alt_kategori: istek.alt_kategori,
    guven: istek.guven,
    goruntu_yeterli: istek.goruntu_yeterli,
    yeniden_incele: istek.yeniden_incele,
    not: (istek.not ?? "").slice(0, 300),
    etiket_sirasi: sira,
    kaydedilme_zamani: zaman,
  });
  return sonuc;
}

/** Kayıtları dosyaya yazılacak kesin sıraya koyar: önce mod, sonra kimlik. */
export function disaAktarmaSirasi(kayitlar: ReadonlyMap<string, Etiket>): Etiket[] {
  return [...kayitlar.values()].sort((a, b) =>
    a.mod === b.mod
      ? a.kor_kimlik.localeCompare(b.kor_kimlik)
      : a.mod.localeCompare(b.mod),
  );
}

/** Dosyadan okunan satırları kayıt kümesine çevirir; manifest dışı olanı atar. */
export function kayitlariYukle(
  satirlar: Etiket[],
  manifestKimlikleri: ReadonlySet<string>,
): { kayitlar: Map<string, Etiket>; atilan: number } {
  const kayitlar = new Map<string, Etiket>();
  let atilan = 0;
  for (const satir of satirlar) {
    const kimlik = (satir.kor_kimlik ?? "").trim();
    const mod = (satir.mod ?? "ana").trim();
    if (!manifestKimlikleri.has(kimlik) || !(MODLAR as readonly string[]).includes(mod)) {
      atilan += 1;
      continue;
    }
    kayitlar.set(anahtar(kimlik, mod), satir);
  }
  return { kayitlar, atilan };
}
