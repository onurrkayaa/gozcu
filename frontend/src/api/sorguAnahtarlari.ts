/**
 * TanStack Query anahtarları tek yerde.
 *
 * Dağınık dizi değişmezleri yerine burada durur ki bir mutation sonrası
 * geçersiz kılma (invalidation) yanlış anahtarı hedefleyip sessizce bayat
 * veri bırakmasın.
 */

export const sorguAnahtarlari = {
  gorevler: ["gorevler"] as const,
  gorevListesi: (sayfa: number) => ["gorevler", "liste", sayfa] as const,
  gorev: (gorevId: number) => ["gorevler", "ayrinti", gorevId] as const,

  kareler: (gorevId: number, sayfa: number) => ["kareler", gorevId, sayfa] as const,
  kareleriGecersizKil: (gorevId: number) => ["kareler", gorevId] as const,

  modeller: ["modeller"] as const,

  kosular: (gorevId: number) => ["kosular", gorevId] as const,
  kosu: (kosuId: number) => ["kosu", kosuId] as const,

  tespitler: (kosuId: number, kareId: number | undefined, minSkor: number) =>
    ["tespitler", kosuId, kareId ?? "tumu", minSkor] as const,

  kareGoruntusu: (kareId: number) => ["kare-goruntusu", kareId] as const,

  // --- Hafta 6 ---
  uyeler: (gorevId: number) => ["uyeler", gorevId] as const,
  incelemeler: (kosuId: number) => ["incelemeler", kosuId] as const,
  bulgular: (gorevId: number) => ["bulgular", gorevId] as const,
  kumeler: (gorevId: number) => ["kumeler", gorevId] as const,
  denetim: (gorevId: number, sayfa: number) => ["denetim", gorevId, sayfa] as const,
  denetimiGecersizKil: (gorevId: number) => ["denetim", gorevId] as const,
};
