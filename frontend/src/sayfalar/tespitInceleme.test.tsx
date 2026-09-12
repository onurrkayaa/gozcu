/**
 * Tespit inceleme katmanı ve DÜRÜSTLÜK kontrolleri.
 *
 * Dürüstlük burada test edilir çünkü bunlar gözle bakılınca kolayca kaçan ama
 * yanlış olduklarında arama ekibini yanıltan davranışlardır: olmayan konumun
 * varmış gibi gösterilmesi, model çıktısının "kesin insan" diye sunulması,
 * görüntüleme eşiğinin bir metrik gibi anlaşılması.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";

import { TespitIncelemeSayfasi } from "./TespitIncelemeSayfasi";
import { KAPSAM_IFADESI } from "../Uygulama";
import {
  fetchTaklidiKur,
  ornekKare,
  ornekKosu,
  ornekTespit,
  sar,
  sayfali,
} from "../test/yardimcilar";
import type { Tespit } from "../api/tipler";

afterEach(() => vi.unstubAllGlobals());

function incelemeSayfasi() {
  return (
    <Routes>
      <Route path="/kosular/:kosuId" element={<TespitIncelemeSayfasi />} />
    </Routes>
  );
}

/** Görüntü ucu blob döndürür; jsdom'da küçük bir ikili yeterli. */
function taklitKur(
  tespitler: Tespit[],
  kareEkleri: Partial<ReturnType<typeof ornekKare>> = {},
) {
  return fetchTaklidiKur((yol) => {
    if (yol.includes("/image/")) {
      return { blob: new Blob([new Uint8Array([0xff, 0xd8, 0xff])], { type: "image/jpeg" }) };
    }
    if (yol.includes("/detections/")) {
      const eslesme = yol.match(/min_score=([\d.]+)/);
      const esik = eslesme ? Number(eslesme[1]) : 0;
      // Backend eşiği okuma anında uygular; taklit de aynısını yapar.
      return { govde: sayfali(tespitler.filter((t) => t.score >= esik)) };
    }
    if (/\/api\/runs\/9\/$/.test(yol)) return { govde: ornekKosu() };
    if (yol.includes("/frames/")) return { govde: sayfali([ornekKare(kareEkleri)]) };
    return undefined;
  });
}

describe("tespit katmanı", () => {
  it("kutuyu doğal görüntü ölçüsüne göre yüzdeyle yerleştirir", async () => {
    taklitKur([ornekTespit({ id: 11, x1: 1000, y1: 750, x2: 2000, y2: 1500 })]);

    sar(incelemeSayfasi(), { baslangicRotasi: "/kosular/9" });

    const kutu = await screen.findByTestId("tespit-kutusu-11");
    // 4000x3000 karede: sol %25, üst %25, genişlik %25, yükseklik %25
    expect(kutu.style.left).toBe("25%");
    expect(kutu.style.top).toBe("25%");
    expect(kutu.style.width).toBe("25%");
    expect(kutu.style.height).toBe("25%");
  });

  it("yüzde yerleşimi kullandığı için yeniden boyutlandırmada hiza korunur", async () => {
    taklitKur([ornekTespit({ id: 11, x1: 2000, y1: 1500, x2: 3000, y2: 2250 })]);

    sar(incelemeSayfasi(), { baslangicRotasi: "/kosular/9" });

    const kutu = await screen.findByTestId("tespit-kutusu-11");
    const oncekiStil = kutu.getAttribute("style");

    // Pencere boyutunu değiştir: yüzde değerleri DEĞİŞMEMELİ, çünkü ölçek
    // tarayıcı tarafından çözülür, JS ölçümüne bağlı değildir.
    window.innerWidth = 480;
    window.dispatchEvent(new Event("resize"));
    await waitFor(() =>
      expect(screen.getByTestId("tespit-kutusu-11").getAttribute("style")).toBe(oncekiStil),
    );
  });

  it("görüntü dışına taşan kutu sınırda kesilir", async () => {
    taklitKur([ornekTespit({ id: 12, x1: 3800, y1: 2800, x2: 5000, y2: 4000 })]);

    sar(incelemeSayfasi(), { baslangicRotasi: "/kosular/9" });

    const kutu = await screen.findByTestId("tespit-kutusu-12");
    const sol = Number.parseFloat(kutu.style.left);
    const genislik = Number.parseFloat(kutu.style.width);
    expect(sol + genislik).toBeLessThanOrEqual(100.0001);
  });

  it("en-boy oranı sarmalayıcıya değil GÖRÜNTÜYE verilir", async () => {
    // Oran sarmalayıcıda olsaydı yüksekliği görüntününkinden 1 px farklı
    // yuvarlanabilir ve kutular alt kenarda kayardı.
    taklitKur([]);
    sar(incelemeSayfasi(), { baslangicRotasi: "/kosular/9" });

    const goruntu = await screen.findByTestId("kare-goruntusu");
    expect(goruntu.style.aspectRatio).toBe("4000 / 3000");
    expect(screen.getByTestId("goruntu-katmani").style.aspectRatio).toBe("");
  });

  it("tespitler arasında seçim yapılabilir", async () => {
    const kullanici = userEvent.setup();
    taklitKur([
      ornekTespit({ id: 11, score: 0.9 }),
      ornekTespit({ id: 12, score: 0.7, x1: 100, y1: 100, x2: 300, y2: 400 }),
    ]);

    sar(incelemeSayfasi(), { baslangicRotasi: "/kosular/9" });

    const kutu = await screen.findByTestId("tespit-kutusu-12");
    expect(kutu).toHaveAttribute("aria-pressed", "false");
    await kullanici.click(kutu);
    expect(screen.getByTestId("tespit-kutusu-12")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Seçili aday")).toBeInTheDocument();
  });

  it("tespit olmayan karede temkinli boş durum gösterilir", async () => {
    taklitKur([]);
    sar(incelemeSayfasi(), { baslangicRotasi: "/kosular/9" });

    expect(
      await screen.findByText(/insan adayı bulunmadı/i),
    ).toBeInTheDocument();
  });

  it("karo satır/sütun bilgisi ayrıntıda gösterilir", async () => {
    const kullanici = userEvent.setup();
    taklitKur([ornekTespit({ id: 11, tile_row: 2, tile_col: 5 })]);

    sar(incelemeSayfasi(), { baslangicRotasi: "/kosular/9" });
    await kullanici.click(await screen.findByTestId("tespit-kutusu-11"));

    expect(screen.getByText(/satır 2, sütun 5/)).toBeInTheDocument();
  });
});

describe("görüntüleme eşiği", () => {
  it("yalnızca gösterimi süzer; modeli yeniden çalıştırmadığı açıkça yazılır", async () => {
    taklitKur([ornekTespit({ id: 11, score: 0.9 })]);
    sar(incelemeSayfasi(), { baslangicRotasi: "/kosular/9" });

    const yardim = await screen.findByText(/yalnızca ekranda gösterilen kutuları süzer/);
    expect(yardim).toHaveTextContent(/modeli\s+yeniden çalıştırmaz/);
    expect(yardim).toHaveTextContent(/değerlendirme metriği değildir/);
  });

  it("başlangıç değeri sabit yazılmaz; koşunun conf_threshold'undan gelir", async () => {
    taklitKur([ornekTespit({ id: 11, score: 0.9 })]);
    sar(incelemeSayfasi(), { baslangicRotasi: "/kosular/9" });

    // ornekKosu conf_threshold = 0.25
    expect(await screen.findByText("Görüntüleme eşiği: 0.25")).toBeInTheDocument();
  });

  it("eşik yükseltilince yalnızca gösterilen kutu sayısı azalır", async () => {
    const { cagrilar } = taklitKur([
      ornekTespit({ id: 11, score: 0.9 }),
      ornekTespit({ id: 12, score: 0.3, x1: 100, y1: 100, x2: 300, y2: 400 }),
    ]);

    sar(incelemeSayfasi(), { baslangicRotasi: "/kosular/9" });

    expect(await screen.findByTestId("tespit-kutusu-12")).toBeInTheDocument();

    // Kaydırıcıyı 0,80'e taşı. userEvent bir range girdisini sürükleyemediği
    // için değer React'in dinlediği yerel setter ile yazılır ve change olayı
    // elle tetiklenir.
    const kaydirici = screen.getByLabelText(/Görüntüleme eşiği/);
    const yerelSet = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype,
      "value",
    )!.set!;
    yerelSet.call(kaydirici, "0.8");
    kaydirici.dispatchEvent(new Event("change", { bubbles: true }));

    await waitFor(() =>
      expect(screen.queryByTestId("tespit-kutusu-12")).not.toBeInTheDocument(),
    );
    // Yeni eşikle gelen sorgu tamamlanana kadar bekle.
    expect(await screen.findByTestId("tespit-kutusu-11")).toBeInTheDocument();

    // Yeni tarama BAŞLATILMADI: yalnızca okuma isteği gitti.
    expect(cagrilar.some((c) => c.yontem === "POST")).toBe(false);
  });
});

describe("dürüstlük", () => {
  it("GPS yokken koordinat üretmez, yokluğu açıkça söyler", async () => {
    taklitKur([], { latitude: null, longitude: null });
    sar(incelemeSayfasi(), { baslangicRotasi: "/kosular/9" });

    expect(await screen.findByText("Konum bilgisi mevcut değil.")).toBeInTheDocument();
    // Ondalık derece gibi duran hiçbir sayı ekranda olmamalı.
    const konumPaneli = screen.getByText("Konum bilgisi mevcut değil.").closest("div")!;
    expect(konumPaneli.textContent).not.toMatch(/\d+\.\d{4,}/);
  });

  it("kayıtta gerçek koordinat varsa kaynağıyla gösterir", async () => {
    taklitKur([], { latitude: 43.51234, longitude: 16.44321 });
    sar(incelemeSayfasi(), { baslangicRotasi: "/kosular/9" });

    expect(await screen.findByText("Kayıtlı konum")).toBeInTheDocument();
    expect(screen.getByText(/43\.512340, 16\.443210/)).toBeInTheDocument();
    expect(screen.getByText(/EXIF GPS alanı/)).toBeInTheDocument();
  });

  it("tespitler 'kesin insan' diye adlandırılmaz, 'aday' denir", async () => {
    taklitKur([ornekTespit({ id: 11 })]);
    sar(incelemeSayfasi(), { baslangicRotasi: "/kosular/9" });

    const baslik = await screen.findByRole("heading", { name: /İnsan adayları/ });
    expect(baslik).toBeInTheDocument();

    const panel = baslik.closest(".kart") as HTMLElement;
    expect(within(panel).getByText(/Kesin insan tespiti değildir/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/kesin insan bulundu/i);
  });

  it("kutunun erişilebilir adı adayı 'insan adayı' olarak bildirir", async () => {
    taklitKur([ornekTespit({ id: 11, score: 0.87 })]);
    sar(incelemeSayfasi(), { baslangicRotasi: "/kosular/9" });

    const kutu = await screen.findByTestId("tespit-kutusu-11");
    expect(kutu).toHaveAttribute("aria-label", "İnsan adayı, güven 0.87");
  });

  it("kapsam ifadesi operatör uyarısını içerir", () => {
    expect(KAPSAM_IFADESI).toContain("Eğitim ve araştırma prototipidir");
    expect(KAPSAM_IFADESI).toContain("operatör kararının yerine geçmez");
  });
});
