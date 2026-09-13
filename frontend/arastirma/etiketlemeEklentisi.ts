/**
 * Körlenmiş etiketleme aracının yerel sunucu tarafı.
 *
 * Bu bir GELİŞTİRME eklentisidir: yalnızca `vite` geliştirme sunucusuna
 * takılır, üretim derlemesine hiç girmez. Araştırma aracının üretim operatör
 * ekranıyla ve Django arka ucuyla hiçbir bağı yok; ayrı bir HTML girişinden
 * açılır ve oturum istemez.
 *
 * KÖRLEME BURADA KORUNUR: bu sunucu körleme anahtarı dosyasını HİÇ AÇMAZ.
 * Arayüze giden veride model, FP/kontrol ayrımı, skor, kaynak öneki veya
 * gerçek görüntü adı bulunmaz.
 */
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { extname, join, resolve } from "node:path";
import type { Plugin } from "vite";

import { taksonomiPaketi } from "./taksonomi";
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

const DEPO_KOK = resolve(import.meta.dirname ?? process.cwd(), "..", "..");
const MANIFEST = join(DEPO_KOK, "reports", "hafta7_fp_etiket_manifesti.csv");
const KIRPIM_DIZIN = join(DEPO_KOK, "reports", "hafta7_kirpimlar");
const ETIKET_DOSYASI = join(DEPO_KOK, "reports", "hafta7_fp_gorsel_etiketler.csv");
const TOHUM = 20260913;

/** Manifestte arayüze GÖNDERİLEBİLECEK alanlar. Beyaz liste bilinçli. */
interface Oge {
  kor_kimlik: string;
  siki: string;
  baglam: string;
  mod: "ana" | "kalite";
}

function tohumluKarustir<T>(ogeler: T[], tohum: number): T[] {
  // mulberry32: küçük, deterministik ve bağımlılıksız.
  let durum = tohum >>> 0;
  const sonraki = () => {
    durum = (durum + 0x6d2b79f5) >>> 0;
    let t = durum;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const kopya = [...ogeler];
  for (let i = kopya.length - 1; i > 0; i -= 1) {
    const j = Math.floor(sonraki() * (i + 1));
    [kopya[i], kopya[j]] = [kopya[j], kopya[i]];
  }
  return kopya;
}

function manifestiOku(): { ogeler: Oge[]; kimlikler: Set<string> } {
  if (!existsSync(MANIFEST)) return { ogeler: [], kimlikler: new Set() };
  const satirlar = csvCoz(readFileSync(MANIFEST, "utf-8"));
  const ana: Oge[] = satirlar
    .map((s) => ({
      kor_kimlik: s.kor_kimlik,
      siki: s.siki_kirpim,
      baglam: s.baglam_kirpim,
      mod: "ana" as const,
    }))
    .sort((a, b) => a.kor_kimlik.localeCompare(b.kor_kimlik));

  // Kalite turu: aynı adaylar, FARKLI sırada ve önceki cevap gösterilmeden.
  const kaliteKimlikleri = new Set(
    satirlar.filter((s) => s.tur === "kalite").map((s) => s.kor_kimlik),
  );
  const kalite = tohumluKarustir(
    ana.filter((o) => kaliteKimlikleri.has(o.kor_kimlik)),
    TOHUM + 2,
  ).map((o) => ({ ...o, mod: "kalite" as const }));

  return {
    ogeler: [...ana, ...kalite],
    kimlikler: new Set(ana.map((o) => o.kor_kimlik)),
  };
}

function kosuSutunlari(): Etiket {
  const manifestOzeti = existsSync(MANIFEST)
    ? createHash("sha256").update(readFileSync(MANIFEST)).digest("hex").slice(0, 16)
    : "";
  return {
    kosu_protokol: "reports/hafta7_fp_protokolu.md",
    kosu_manifest: "reports/hafta7_fp_etiket_manifesti.csv",
    kosu_manifest_ozeti: manifestOzeti,
    kosu_arac: "frontend etiketleme.html (yerel gelistirme araci)",
    kosu_tohum: String(TOHUM),
    kosu_kapsam_notu:
      "Tek etiketleyici. mod=ana birincil tur, mod=kalite ayni adaylarin " +
      "yeniden-test turudur; annotatorlar arasi guvenilirlik DEGILDIR.",
  };
}

function kayitlariOku(kimlikler: Set<string>) {
  if (!existsSync(ETIKET_DOSYASI)) return new Map<string, Etiket>();
  return kayitlariYukle(csvCoz(readFileSync(ETIKET_DOSYASI, "utf-8")), kimlikler).kayitlar;
}

function kayitlariDiskeYaz(kayitlar: ReadonlyMap<string, Etiket>) {
  const kosu = kosuSutunlari();
  const basliklar = [...ETIKET_SUTUNLARI, ...Object.keys(kosu)];
  const satirlar = disaAktarmaSirasi(kayitlar).map((s) => ({ ...s, ...kosu }));
  writeFileSync(ETIKET_DOSYASI, csvYaz(satirlar, basliklar), "utf-8");
  return satirlar.length;
}

async function govdeyiOku(istek: NodeJS.ReadableStream): Promise<Etiket> {
  const parcalar: Buffer[] = [];
  for await (const parca of istek) parcalar.push(parca as Buffer);
  return JSON.parse(Buffer.concat(parcalar).toString("utf-8") || "{}");
}

export function etiketlemeEklentisi(): Plugin {
  return {
    name: "gozcu-arastirma-etiketleme",
    apply: "serve", // ÜRETİM DERLEMESİNE GİRMEZ
    configureServer(sunucu) {
      sunucu.middlewares.use(async (istek, yanit, sonraki) => {
        const yol = (istek.url ?? "").split("?")[0];
        const json = (kod: number, govde: unknown) => {
          yanit.statusCode = kod;
          yanit.setHeader("Content-Type", "application/json; charset=utf-8");
          yanit.end(JSON.stringify(govde));
        };

        if (yol === "/arastirma-api/durum") {
          const { ogeler, kimlikler } = manifestiOku();
          const kayitlar = kayitlariOku(kimlikler);
          const etiketler: Record<string, Etiket> = {};
          for (const [anah, kayit] of kayitlar) etiketler[anah] = kayit;
          return json(200, {
            hazir: ogeler.length > 0,
            ogeler,
            taksonomi: taksonomiPaketi(),
            etiketler,
            sayim: {
              ana: ogeler.filter((o) => o.mod === "ana").length,
              kalite: ogeler.filter((o) => o.mod === "kalite").length,
            },
            ciktiDosyasi: "reports/hafta7_fp_gorsel_etiketler.csv",
          });
        }

        if (yol === "/arastirma-api/etiket" && istek.method === "POST") {
          const { kimlikler } = manifestiOku();
          let govde: Etiket;
          try { govde = await govdeyiOku(istek); }
          catch { return json(400, { hata: "Gövde çözümlenemedi." }); }
          const sonuc = etiketiDogrula(govde, kimlikler);
          if (!sonuc.gecerli) return json(400, { hata: sonuc.hata });
          const kayitlar = etiketiYerlestir(
            kayitlariOku(kimlikler), govde, new Date().toISOString(),
          );
          const yazilan = kayitlariDiskeYaz(kayitlar);
          return json(200, {
            kaydedildi: govde.kor_kimlik,
            mod: govde.mod ?? "ana",
            toplamKayit: yazilan,
          });
        }

        if (yol === "/arastirma-api/disa-aktar" && istek.method === "POST") {
          const { ogeler, kimlikler } = manifestiOku();
          const kayitlar = kayitlariOku(kimlikler);
          const yazilan = kayitlariDiskeYaz(kayitlar);
          const eksik = ogeler.filter((o) => !kayitlar.has(anahtar(o.kor_kimlik, o.mod)));
          return json(200, {
            dosya: "reports/hafta7_fp_gorsel_etiketler.csv",
            yazilanKayit: yazilan,
            eksikKayit: eksik.length,
            eksikOrnekler: eksik.slice(0, 5).map((o) => `${o.mod}:${o.kor_kimlik}`),
          });
        }

        if (yol.startsWith("/arastirma-kirpim/")) {
          const ad = decodeURIComponent(yol.slice("/arastirma-kirpim/".length));
          // Yol gecisi kapali: yalnizca duz dosya adi kabul edilir.
          if (!/^[a-z0-9_]+\.jpg$/i.test(ad)) { yanit.statusCode = 404; return yanit.end(); }
          const dosya = join(KIRPIM_DIZIN, ad);
          if (!existsSync(dosya)) { yanit.statusCode = 404; return yanit.end(); }
          yanit.setHeader("Content-Type", extname(ad) === ".png" ? "image/png" : "image/jpeg");
          yanit.setHeader("Cache-Control", "public, max-age=3600");
          return yanit.end(readFileSync(dosya));
        }

        return sonraki();
      });
    },
  };
}
