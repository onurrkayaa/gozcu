/**
 * Körlenmiş etiketleme arayüzü.
 *
 * Buradaki testlerin asıl işi aracın çalıştığını değil, ETİKETLEYENE HİÇBİR
 * GRUP BİLGİSİ SIZMADIĞINI doğrulamak. Sızarsa kör etiketleme kör olmaktan
 * çıkar ve ölçüm baştan geçersiz olur.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { EtiketlemeAraci } from "./EtiketlemeAraci";
import { taksonomiPaketi } from "../../arastirma/taksonomi";

afterEach(() => vi.unstubAllGlobals());

function ornekOgeler() {
  return [
    { kor_kimlik: "a0001", siki: "a0001_siki.jpg", baglam: "a0001_baglam.jpg", mod: "ana" },
    { kor_kimlik: "a0002", siki: "a0002_siki.jpg", baglam: "a0002_baglam.jpg", mod: "ana" },
    { kor_kimlik: "a0003", siki: "a0003_siki.jpg", baglam: "a0003_baglam.jpg", mod: "ana" },
    { kor_kimlik: "a0002", siki: "a0002_siki.jpg", baglam: "a0002_baglam.jpg", mod: "kalite" },
  ];
}

function sunucuTaklidi(baslangicEtiketleri: Record<string, unknown> = {}) {
  const etiketler: Record<string, unknown> = { ...baslangicEtiketleri };
  const gonderilen: unknown[] = [];
  const taklit = vi.fn(async (girdi: RequestInfo | URL, secenekler?: RequestInit) => {
    const yol = String(girdi);
    if (yol === "/arastirma-api/durum") {
      return new Response(JSON.stringify({
        hazir: true,
        ogeler: ornekOgeler(),
        taksonomi: taksonomiPaketi(),
        etiketler,
        sayim: { ana: 3, kalite: 1 },
        ciktiDosyasi: "reports/hafta7_fp_gorsel_etiketler.csv",
      }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    if (yol === "/arastirma-api/etiket") {
      const govde = JSON.parse(String(secenekler?.body ?? "{}"));
      gonderilen.push(govde);
      if (!["a0001", "a0002", "a0003"].includes(govde.kor_kimlik)) {
        return new Response(JSON.stringify({ hata: "Manifest dışı kimlik reddedildi." }),
          { status: 400, headers: { "Content-Type": "application/json" } });
      }
      etiketler[`${govde.mod}:${govde.kor_kimlik}`] = govde;
      return new Response(JSON.stringify({ kaydedildi: govde.kor_kimlik }),
        { status: 200, headers: { "Content-Type": "application/json" } });
    }
    if (yol === "/arastirma-api/disa-aktar") {
      return new Response(JSON.stringify({
        dosya: "reports/hafta7_fp_gorsel_etiketler.csv",
        yazilanKayit: Object.keys(etiketler).length,
        eksikKayit: 4 - Object.keys(etiketler).length,
      }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    return new Response("{}", { status: 404 });
  });
  vi.stubGlobal("fetch", taklit);
  return { taklit, gonderilen, etiketler };
}

async function araciAc(baslangic: Record<string, unknown> = {}) {
  const sunucu = sunucuTaklidi(baslangic);
  render(<EtiketlemeAraci />);
  await screen.findByTestId("kor-kimlik");
  return sunucu;
}

describe("körleme", () => {
  it("ekranda model, FP/kontrol, skor ve kaynak bilgisi geçmez", async () => {
    await araciAc();
    const metin = document.body.textContent ?? "";
    for (const yasak of ["Taban-512", "Model-512", "ZRI", "VRD", "TP", ".rf.", "yolo11n"]) {
      expect(metin).not.toContain(yasak);
    }
    // Skorun kendisi de görünmemeli: ekranda ondalık bir güven değeri yok.
    expect(metin).not.toMatch(/0[.,]\d{2,}/);
    // "skor" sözcüğü yalnızca körleme açıklamasında geçer, bir değer olarak değil.
    expect(metin).toContain("güven skoru gösterilmez");
  });

  it("görsel kaynakları yalnızca kör kimlik taşır", async () => {
    await araciAc();
    const siki = screen.getByTestId("siki-kirpim") as HTMLImageElement;
    const baglam = screen.getByTestId("baglam-kirpim") as HTMLImageElement;
    expect(siki.getAttribute("src")).toBe("/arastirma-kirpim/a0001_siki.jpg");
    expect(baglam.getAttribute("src")).toBe("/arastirma-kirpim/a0001_baglam.jpg");
    expect(siki.getAttribute("src")).not.toMatch(/taban|model|fp|kontrol/i);
  });

  it("körlendiğini kullanıcıya da söyler", async () => {
    await araciAc();
    expect(screen.getByText(/Bu ekran körlenmiştir/)).toBeInTheDocument();
  });
});

describe("klavye ile etiketleme", () => {
  it("insan faaliyeti + alt kategori tuşu kaydeder ve ilerler", async () => {
    const kullanici = userEvent.setup();
    const { gonderilen } = await araciAc();

    await kullanici.keyboard("v");
    await kullanici.keyboard("1");

    await waitFor(() => expect(gonderilen).toHaveLength(1));
    expect(gonderilen[0]).toMatchObject({
      kor_kimlik: "a0001", mod: "ana",
      insan_faaliyeti: "var", alt_kategori: "arac", guven: "yuksek",
    });
    // Otomatik ilerleme
    await waitFor(() => expect(screen.getByTestId("kor-kimlik")).toHaveTextContent("a0002"));
  });

  it("güven tuşu kayda yansır", async () => {
    const kullanici = userEvent.setup();
    const { gonderilen } = await araciAc();
    await kullanici.keyboard("d");
    await kullanici.keyboard("y");
    await kullanici.keyboard("7");
    await waitFor(() => expect(gonderilen).toHaveLength(1));
    expect(gonderilen[0]).toMatchObject({ guven: "dusuk", insan_faaliyeti: "yok" });
  });

  it("belirsiz kayıt yazılabilir", async () => {
    const kullanici = userEvent.setup();
    const { gonderilen } = await araciAc();
    await kullanici.keyboard("b");
    await kullanici.keyboard("m");
    await waitFor(() => expect(gonderilen).toHaveLength(1));
    expect(gonderilen[0]).toMatchObject({
      insan_faaliyeti: "belirsiz", alt_kategori: "belirsiz",
    });
  });

  it("görüntü yetersiz ve yeniden incele bayrakları klavyeden açılır", async () => {
    const kullanici = userEvent.setup();
    const { gonderilen } = await araciAc();
    await kullanici.keyboard("g");
    await kullanici.keyboard("r");
    await kullanici.keyboard("v");
    await kullanici.keyboard("2");
    await waitFor(() => expect(gonderilen).toHaveLength(1));
    expect(gonderilen[0]).toMatchObject({ goruntu_yeterli: "hayir", yeniden_incele: "evet" });
  });

  it("geri dön önceki adaya götürür", async () => {
    const kullanici = userEvent.setup();
    await araciAc();
    await kullanici.keyboard("k");
    expect(screen.getByTestId("kor-kimlik")).toHaveTextContent("a0002");
    await kullanici.keyboard("{Backspace}");
    expect(screen.getByTestId("kor-kimlik")).toHaveTextContent("a0001");
  });

  it("atlamak kayıt göndermez", async () => {
    const kullanici = userEvent.setup();
    const { gonderilen } = await araciAc();
    await kullanici.keyboard("k");
    expect(gonderilen).toHaveLength(0);
  });
});

describe("eksik alan", () => {
  it("alt kategori olmadan Enter kaydetmez", async () => {
    const kullanici = userEvent.setup();
    const { gonderilen } = await araciAc();
    await kullanici.keyboard("v");
    await kullanici.keyboard("{Enter}");
    expect(await screen.findByTestId("bildirim")).toHaveTextContent(
      /insan faaliyeti ve alt kategori/i,
    );
    expect(gonderilen).toHaveLength(0);
  });

  it("insan faaliyeti seçilmeden alt kategori tek başına kaydetmez", async () => {
    const kullanici = userEvent.setup();
    const { gonderilen } = await araciAc();
    await kullanici.keyboard("3");
    expect(await screen.findByTestId("bildirim")).toHaveTextContent(/Önce insan faaliyeti/i);
    expect(gonderilen).toHaveLength(0);
  });
});

describe("otomatik kayıt ve devam", () => {
  it("her etiket anında sunucuya yazılır", async () => {
    const kullanici = userEvent.setup();
    const { taklit } = await araciAc();
    await kullanici.keyboard("v");
    await kullanici.keyboard("1");
    await waitFor(() =>
      expect(taklit.mock.calls.some(([yol, s]) =>
        String(yol) === "/arastirma-api/etiket" && (s as RequestInit)?.method === "POST",
      )).toBe(true),
    );
  });

  it("yeniden açıldığında ilk etiketlenmemiş adaydan devam eder", async () => {
    await araciAc({
      "ana:a0001": { kor_kimlik: "a0001", mod: "ana", insan_faaliyeti: "var" },
      "ana:a0002": { kor_kimlik: "a0002", mod: "ana", insan_faaliyeti: "yok" },
    });
    expect(screen.getByTestId("kor-kimlik")).toHaveTextContent("a0003");
    expect(screen.getByTestId("ilerleme")).toHaveTextContent("etiketlenen 2");
  });

  it("etiketli bir adaya dönülünce ikinci kayıt açılmayacağı yazılır", async () => {
    const kullanici = userEvent.setup();
    await araciAc({
      "ana:a0001": {
        kor_kimlik: "a0001", mod: "ana", insan_faaliyeti: "var",
        alt_kategori: "arac", guven: "yuksek", goruntu_yeterli: "evet", yeniden_incele: "hayir",
      },
      "ana:a0002": { kor_kimlik: "a0002", mod: "ana", insan_faaliyeti: "yok" },
    });
    await kullanici.keyboard("{Backspace}");
    await kullanici.keyboard("{Backspace}");
    expect(screen.getByTestId("kor-kimlik")).toHaveTextContent("a0001");
    expect(screen.getByTestId("zaten-etiketli")).toHaveTextContent(/ikinci bir\s+kayıt eklemez/);
  });
});

describe("kalite turu", () => {
  it("aynı adayın kalite turunda önceki cevap gösterilmez", async () => {
    const kullanici = userEvent.setup();
    await araciAc({
      "ana:a0001": { kor_kimlik: "a0001", mod: "ana", insan_faaliyeti: "var", alt_kategori: "arac" },
      "ana:a0002": {
        kor_kimlik: "a0002", mod: "ana", insan_faaliyeti: "var", alt_kategori: "arac",
        guven: "yuksek", goruntu_yeterli: "evet", yeniden_incele: "hayir",
      },
      "ana:a0003": { kor_kimlik: "a0003", mod: "ana", insan_faaliyeti: "yok", alt_kategori: "su" },
    });
    // Kalan tek kayıt kalite turundaki a0002.
    expect(screen.getByTestId("kor-kimlik")).toHaveTextContent("a0002");
    expect(screen.getByText(/kalite turu/)).toBeInTheDocument();
    expect(screen.queryByTestId("zaten-etiketli")).not.toBeInTheDocument();
    // Cevap alanlarında hiçbir seçim yok: eski cevap sızmıyor. (Güven alanının
    // "yüksek" varsayılanı bir cevap değil, taslak başlangıcıdır.)
    const cevapAlanlari = [...document.querySelectorAll("fieldset")].slice(0, 2);
    expect(cevapAlanlari.flatMap((a) => [...a.querySelectorAll("button.secili")])).toHaveLength(0);
    await kullanici.keyboard("y");
    expect(screen.getByRole("button", { name: /İnsan faaliyeti YOK/ })).toHaveClass("secili");
  });
});

describe("dışa aktarma", () => {
  it("eksik kayıt sayısını bildirir", async () => {
    const kullanici = userEvent.setup();
    await araciAc({ "ana:a0001": { kor_kimlik: "a0001", mod: "ana" } });
    await kullanici.click(screen.getByRole("button", { name: "Dışa aktar" }));
    expect(await screen.findByTestId("bildirim")).toHaveTextContent(
      /hafta7_fp_gorsel_etiketler\.csv yazıldı: 1 kayıt — 3 aday hâlâ etiketsiz/,
    );
  });
});

describe("manifest yoksa", () => {
  it("etiketlemeye başlatmadan ne yapılması gerektiğini söyler", async () => {
    vi.stubGlobal("fetch", vi.fn(async () =>
      new Response(JSON.stringify({ hazir: false, ogeler: [], taksonomi: taksonomiPaketi(),
        etiketler: {}, sayim: { ana: 0, kalite: 0 }, ciktiDosyasi: "" }),
        { status: 200, headers: { "Content-Type": "application/json" } })));
    render(<EtiketlemeAraci />);
    expect(await screen.findByTestId("manifest-yok")).toHaveTextContent(/25_esit_fp_adaylari/);
  });
});
