/**
 * Geometri kapısı: tespit kutuları gerçek görüntü üzerinde doğru hizalanmalı.
 *
 * Backend kutuları orijinal görüntü pikselinde verir; ekranda görüntü çok daha
 * küçük çizilir. Buradaki testler ölçeklemenin, yeniden boyutlandırma
 * dayanıklılığının ve taşma kırpmasının doğruluğunu sayısal olarak doğrular.
 */

import { describe, expect, it } from "vitest";

import { kutuYerlesimi, yerlesiminPikseli } from "./kutuGeometrisi";

const KARE_GENISLIGI = 4000;
const KARE_YUKSEKLIGI = 3000;

describe("kutuYerlesimi", () => {
  it("doğal görüntü ölçüsünden yüzde yerleşimi üretir", () => {
    const yerlesim = kutuYerlesimi(
      { x1: 1000, y1: 750, x2: 2000, y2: 1500 },
      KARE_GENISLIGI,
      KARE_YUKSEKLIGI,
    );

    expect(yerlesim).not.toBeNull();
    expect(yerlesim!.solYuzde).toBeCloseTo(25, 6);
    expect(yerlesim!.ustYuzde).toBeCloseTo(25, 6);
    expect(yerlesim!.genislikYuzde).toBeCloseTo(25, 6);
    expect(yerlesim!.yukseklikYuzde).toBeCloseTo(25, 6);
  });

  it("ekran boyutuna ölçeklenince kutu doğru piksele düşer", () => {
    // 4000x3000 görüntü ekranda 800x600 çiziliyor: ölçek 1/5.
    const yerlesim = kutuYerlesimi(
      { x1: 2080, y1: 1133, x2: 2487, y2: 1297 },
      KARE_GENISLIGI,
      KARE_YUKSEKLIGI,
    )!;
    const piksel = yerlesiminPikseli(yerlesim, 800, 600);

    expect(piksel.sol).toBeCloseTo(2080 / 5, 6);
    expect(piksel.ust).toBeCloseTo(1133 / 5, 6);
    expect(piksel.genislik).toBeCloseTo((2487 - 2080) / 5, 6);
    expect(piksel.yukseklik).toBeCloseTo((1297 - 1133) / 5, 6);
  });

  it("yeniden boyutlandırma sonrası hizalama korunur", () => {
    // Aynı yerleşim, üç farklı ekran genişliğinde. Kutunun görüntüye göre
    // ORANI her boyutta aynı kalmalı -- hizanın tanımı budur.
    const kutu = { x1: 3000, y1: 300, x2: 3400, y2: 600 };
    const yerlesim = kutuYerlesimi(kutu, KARE_GENISLIGI, KARE_YUKSEKLIGI)!;

    for (const ekranGenisligi of [320, 800, 1440, 2560]) {
      const ekranYuksekligi = (ekranGenisligi * KARE_YUKSEKLIGI) / KARE_GENISLIGI;
      const piksel = yerlesiminPikseli(yerlesim, ekranGenisligi, ekranYuksekligi);

      expect(piksel.sol / ekranGenisligi).toBeCloseTo(kutu.x1 / KARE_GENISLIGI, 6);
      expect(piksel.ust / ekranYuksekligi).toBeCloseTo(kutu.y1 / KARE_YUKSEKLIGI, 6);
      expect(piksel.genislik / ekranGenisligi).toBeCloseTo(
        (kutu.x2 - kutu.x1) / KARE_GENISLIGI,
        6,
      );
    }
  });

  it("sınır değerleri: tüm görüntüyü kaplayan kutu tam 0-100 aralığında durur", () => {
    const yerlesim = kutuYerlesimi(
      { x1: 0, y1: 0, x2: KARE_GENISLIGI, y2: KARE_YUKSEKLIGI },
      KARE_GENISLIGI,
      KARE_YUKSEKLIGI,
    )!;

    expect(yerlesim.solYuzde).toBe(0);
    expect(yerlesim.ustYuzde).toBe(0);
    expect(yerlesim.genislikYuzde).toBe(100);
    expect(yerlesim.yukseklikYuzde).toBe(100);
  });

  it("görüntü dışına taşan kutu sınıra kırpılır, dışarı çıkmaz", () => {
    const yerlesim = kutuYerlesimi(
      { x1: 3900, y1: 2900, x2: 4600, y2: 3800 },
      KARE_GENISLIGI,
      KARE_YUKSEKLIGI,
    )!;

    expect(yerlesim.solYuzde + yerlesim.genislikYuzde).toBeLessThanOrEqual(100);
    expect(yerlesim.ustYuzde + yerlesim.yukseklikYuzde).toBeLessThanOrEqual(100);
    expect(yerlesim.solYuzde + yerlesim.genislikYuzde).toBeCloseTo(100, 6);
  });

  it("negatif koordinat sıfıra kırpılır", () => {
    const yerlesim = kutuYerlesimi(
      { x1: -200, y1: -100, x2: 400, y2: 300 },
      KARE_GENISLIGI,
      KARE_YUKSEKLIGI,
    )!;

    expect(yerlesim.solYuzde).toBe(0);
    expect(yerlesim.ustYuzde).toBe(0);
    expect(yerlesim.genislikYuzde).toBeCloseTo((400 / KARE_GENISLIGI) * 100, 6);
  });

  it("tamamen görüntü dışındaki kutu çizilmez", () => {
    const yerlesim = kutuYerlesimi(
      { x1: 5000, y1: 4000, x2: 5200, y2: 4200 },
      KARE_GENISLIGI,
      KARE_YUKSEKLIGI,
    );
    expect(yerlesim).toBeNull();
  });

  it("ters çevrilmiş kutu normalize edilir", () => {
    const duz = kutuYerlesimi({ x1: 100, y1: 100, x2: 500, y2: 400 }, 1000, 1000);
    const ters = kutuYerlesimi({ x1: 500, y1: 400, x2: 100, y2: 100 }, 1000, 1000);
    expect(ters).toEqual(duz);
  });

  it("geçersiz kare ölçüsünde kutu çizilmez (sıfıra bölme yok)", () => {
    expect(kutuYerlesimi({ x1: 0, y1: 0, x2: 10, y2: 10 }, 0, 100)).toBeNull();
    expect(kutuYerlesimi({ x1: 0, y1: 0, x2: 10, y2: 10 }, 100, 0)).toBeNull();
    expect(kutuYerlesimi({ x1: 0, y1: 0, x2: 10, y2: 10 }, Number.NaN, 100)).toBeNull();
  });

  it("genişliği sıfır kalan kutu çizilmez", () => {
    expect(kutuYerlesimi({ x1: 250, y1: 100, x2: 250, y2: 400 }, 1000, 1000)).toBeNull();
  });
});
