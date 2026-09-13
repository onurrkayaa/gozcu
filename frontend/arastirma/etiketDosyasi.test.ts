/**
 * Etiket dosyası kuralları.
 *
 * Buradaki testler dosya sistemine dokunmaz; körlemenin ve kayıt bütünlüğünün
 * kurallarını doğrudan sınar.
 */
import { describe, expect, it } from "vitest";

import {
  anahtar,
  csvCoz,
  csvYaz,
  disaAktarmaSirasi,
  ETIKET_SUTUNLARI,
  etiketiDogrula,
  etiketiYerlestir,
  kayitlariYukle,
  type Etiket,
} from "./etiketDosyasi";

const MANIFEST = new Set(["a0001", "a0002", "a0003"]);

function gecerliIstek(ekler: Partial<Etiket> = {}): Etiket {
  return {
    kor_kimlik: "a0001",
    mod: "ana",
    insan_faaliyeti: "var",
    alt_kategori: "arac",
    guven: "yuksek",
    goruntu_yeterli: "evet",
    yeniden_incele: "hayir",
    not: "",
    ...ekler,
  };
}

describe("manifest dışı kayıt", () => {
  it("bilinmeyen kör kimliği reddeder", () => {
    const sonuc = etiketiDogrula(gecerliIstek({ kor_kimlik: "z9999" }), MANIFEST);
    expect(sonuc.gecerli).toBe(false);
    expect(sonuc.hata).toMatch(/Manifest dışı/);
  });

  it("boş kimliği reddeder", () => {
    expect(etiketiDogrula(gecerliIstek({ kor_kimlik: "" }), MANIFEST).gecerli).toBe(false);
  });

  it("dosyadan okurken manifest dışı satırı atar", () => {
    const { kayitlar, atilan } = kayitlariYukle(
      [gecerliIstek(), gecerliIstek({ kor_kimlik: "z9999" })],
      MANIFEST,
    );
    expect(kayitlar.size).toBe(1);
    expect(atilan).toBe(1);
  });
});

describe("alan doğrulaması", () => {
  it("eksik insan faaliyetini reddeder", () => {
    expect(etiketiDogrula(gecerliIstek({ insan_faaliyeti: "" }), MANIFEST).gecerli).toBe(false);
  });

  it("eksik alt kategoriyi reddeder", () => {
    expect(etiketiDogrula(gecerliIstek({ alt_kategori: "" }), MANIFEST).gecerli).toBe(false);
  });

  it("taksonomi dışı değeri reddeder", () => {
    expect(etiketiDogrula(gecerliIstek({ alt_kategori: "araba" }), MANIFEST).gecerli).toBe(false);
    expect(etiketiDogrula(gecerliIstek({ guven: "cok" }), MANIFEST).gecerli).toBe(false);
  });

  it("belirsiz kaydı geçerli sayar", () => {
    const sonuc = etiketiDogrula(
      gecerliIstek({ insan_faaliyeti: "belirsiz", alt_kategori: "belirsiz", guven: "dusuk" }),
      MANIFEST,
    );
    expect(sonuc.gecerli).toBe(true);
  });

  it("evet/hayir dışı bayrağı reddeder", () => {
    expect(etiketiDogrula(gecerliIstek({ goruntu_yeterli: "belki" }), MANIFEST).gecerli).toBe(false);
  });

  it("bilinmeyen modu reddeder", () => {
    expect(etiketiDogrula(gecerliIstek({ mod: "deneme" }), MANIFEST).gecerli).toBe(false);
  });
});

describe("tek aktif etiket", () => {
  it("aynı kimliği ikinci kez etiketlemek satır EKLEMEZ, değiştirir", () => {
    let kayitlar = etiketiYerlestir(new Map(), gecerliIstek(), "2026-09-13T10:00:00Z");
    kayitlar = etiketiYerlestir(
      kayitlar, gecerliIstek({ insan_faaliyeti: "yok", alt_kategori: "kaya_toprak" }),
      "2026-09-13T10:01:00Z",
    );
    expect(kayitlar.size).toBe(1);
    const kayit = kayitlar.get(anahtar("a0001", "ana"))!;
    expect(kayit.insan_faaliyeti).toBe("yok");
    // Sıra numarası ilk etiketlemeden korunur.
    expect(kayit.etiket_sirasi).toBe("1");
  });

  it("ana ve kalite turu AYRI kayıtlardır", () => {
    let kayitlar = etiketiYerlestir(new Map(), gecerliIstek(), "2026-09-13T10:00:00Z");
    kayitlar = etiketiYerlestir(kayitlar, gecerliIstek({ mod: "kalite" }), "2026-09-13T11:00:00Z");
    expect(kayitlar.size).toBe(2);
  });

  it("notu 300 karakterle sınırlar", () => {
    const kayitlar = etiketiYerlestir(
      new Map(), gecerliIstek({ not: "x".repeat(500) }), "2026-09-13T10:00:00Z",
    );
    expect(kayitlar.get(anahtar("a0001", "ana"))!.not).toHaveLength(300);
  });
});

describe("dışa aktarma şeması", () => {
  it("sütun listesi sabit ve model/FP bilgisi taşımıyor", () => {
    const birlesik = ETIKET_SUTUNLARI.join(" ");
    for (const yasak of ["model", "tp_fp", "skor", "kaynak", "goruntu_adi", "aday_turu"]) {
      expect(birlesik).not.toContain(yasak);
    }
    expect(ETIKET_SUTUNLARI).toContain("kor_kimlik");
    expect(ETIKET_SUTUNLARI).toContain("mod");
  });

  it("önce mod sonra kimlik sırasına koyar", () => {
    let kayitlar = etiketiYerlestir(new Map(), gecerliIstek({ kor_kimlik: "a0003" }), "z");
    kayitlar = etiketiYerlestir(kayitlar, gecerliIstek({ kor_kimlik: "a0001" }), "z");
    kayitlar = etiketiYerlestir(kayitlar, gecerliIstek({ kor_kimlik: "a0002", mod: "kalite" }), "z");
    expect(disaAktarmaSirasi(kayitlar).map((s) => `${s.mod}:${s.kor_kimlik}`)).toEqual([
      "ana:a0001", "ana:a0003", "kalite:a0002",
    ]);
  });

  it("CSV gidiş dönüşünde virgüllü ve tırnaklı not bozulmaz", () => {
    const satirlar: Etiket[] = [
      { kor_kimlik: "a0001", not: 'kenarda "araba", yanında çit' },
    ];
    const cozulen = csvCoz(csvYaz(satirlar, ["kor_kimlik", "not"]));
    expect(cozulen).toHaveLength(1);
    expect(cozulen[0].not).toBe('kenarda "araba", yanında çit');
  });

  it("boş dosyadan boş liste döner", () => {
    expect(csvCoz("")).toEqual([]);
    expect(csvCoz("kor_kimlik,not\n")).toEqual([]);
  });
});
