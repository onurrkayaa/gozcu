/**
 * Hafta 7 görsel bağlam taksonomisi.
 *
 * Tek tanım burada durur ve arayüze API üzerinden JSON olarak gider. Arayüzde
 * ikinci bir kopya tutulsaydı, sunucu tarafındaki doğrulama ile ekrandaki
 * seçenekler birbirinden sessizce ayrışabilirdi.
 *
 * Taksonomi `reports/hafta7_fp_protokolu.md` içinde, sonuçlar görülmeden önce
 * sabitlendi. Buradaki değerler o dosyayla birebir aynı olmalıdır.
 */

export interface AltKategori {
  deger: string;
  etiket: string;
  tus: string;
  aciklama: string;
}

export const BIRINCIL = [
  { deger: "var", etiket: "İnsan faaliyeti VAR", tus: "v" },
  { deger: "yok", etiket: "İnsan faaliyeti YOK", tus: "y" },
  { deger: "belirsiz", etiket: "Belirsiz", tus: "b" },
] as const;

export const ALT_KATEGORILER: AltKategori[] = [
  { deger: "arac", etiket: "Araç", tus: "1", aciklama: "Araba, kamyon, traktör, motosiklet" },
  { deger: "yapi_cati", etiket: "Yapı / çatı", tus: "2", aciklama: "Bina, çatı, baraka, duvar" },
  { deger: "yol_patika", etiket: "Yol / patika", tus: "3", aciklama: "Yol, patika, tekerlek izi" },
  { deger: "altyapi_ekipman", etiket: "Altyapı / ekipman", tus: "4", aciklama: "Direk, çit, tank, makine" },
  { deger: "tarimsal_duzen", etiket: "Tarımsal / düzenli iz", tus: "5", aciklama: "Tarla, sıra dikim, geometrik düzen" },
  { deger: "dogal_bitki", etiket: "Doğal bitki", tus: "6", aciklama: "Ağaç, çalı, ot" },
  { deger: "kaya_toprak", etiket: "Kaya / toprak", tus: "7", aciklama: "Kaya, taş, çıplak toprak" },
  { deger: "golge_isik", etiket: "Gölge / ışık", tus: "8", aciklama: "Gölge, parlama, kontrast" },
  { deger: "su", etiket: "Su", tus: "9", aciklama: "Birikinti, dere, göl" },
  { deger: "insan_suphesi", etiket: "İnsan şüphesi", tus: "0", aciklama: "Gerçek insan olabilir / etiket şüphesi" },
  { deger: "baska", etiket: "Başka", tus: "n", aciklama: "Hiçbirine girmiyor" },
  { deger: "belirsiz", etiket: "Belirsiz", tus: "m", aciklama: "Karar verilemedi" },
];

export const GUVEN = [
  { deger: "yuksek", etiket: "Yüksek", tus: "a" },
  { deger: "orta", etiket: "Orta", tus: "s" },
  { deger: "dusuk", etiket: "Düşük", tus: "d" },
] as const;

export const EVET_HAYIR = ["evet", "hayir"] as const;

/** Arayüze gönderilen taksonomi paketi. Model/FP bilgisi İÇERMEZ. */
export function taksonomiPaketi() {
  return {
    birincil: BIRINCIL.map((b) => ({ ...b })),
    altKategoriler: ALT_KATEGORILER.map((a) => ({ ...a })),
    guven: GUVEN.map((g) => ({ ...g })),
    kisayollar: {
      kaydet: "Enter / Boşluk",
      geri: "Backspace",
      atla: "k",
      goruntuYetersiz: "g",
      yenidenIncele: "r",
    },
  };
}
