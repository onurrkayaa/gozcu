/**
 * Görev listesi ve görev oluşturma: yükleme, boş, hata, yeniden dene, çift
 * mutation engeli.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { GorevListesiSayfasi } from "./GorevListesiSayfasi";
import { fetchTaklidiKur, ornekGorev, ornekKosu, sar, sayfali } from "../test/yardimcilar";

afterEach(() => vi.unstubAllGlobals());

describe("görev listesi", () => {
  it("yükleniyor durumunu gösterir", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise(() => {
            /* hiç çözülmeyen istek: yükleme durumu görünür kalsın */
          }),
      ),
    );

    sar(<GorevListesiSayfasi />);
    expect(await screen.findByRole("status")).toHaveTextContent("Görevler yükleniyor…");
  });

  it("boş listede yönlendirici bir boş durum gösterir", async () => {
    fetchTaklidiKur((yol) =>
      yol.includes("/api/missions/") ? { govde: sayfali([]) } : undefined,
    );

    sar(<GorevListesiSayfasi />);
    expect(await screen.findByText(/Henüz görev yok/)).toBeInTheDocument();
  });

  it("hata durumunda mesaj ve 'Yeniden dene' gösterir; tekrar denenince veri gelir", async () => {
    const kullanici = userEvent.setup();
    let cagri = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        cagri += 1;
        if (cagri === 1) {
          return new Response(JSON.stringify({ detail: "Sunucu hatası" }), {
            status: 500,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(JSON.stringify(sayfali([ornekGorev({ name: "Sonra gelen" })])), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );

    sar(<GorevListesiSayfasi />);

    const uyari = await screen.findByRole("alert");
    expect(uyari).toBeInTheDocument();
    await kullanici.click(screen.getByRole("button", { name: "Yeniden dene" }));

    expect(await screen.findByText("Sonra gelen")).toBeInTheDocument();
  });

  it("görevin kare sayımlarını ve son koşu durumunu gösterir", async () => {
    fetchTaklidiKur((yol) =>
      yol.includes("/api/missions/")
        ? {
            govde: sayfali([
              ornekGorev({
                name: "Orman araması",
                frame_count: 7,
                frame_counts: {
                  pending: 1,
                  queued: 2,
                  processing: 1,
                  done: 2,
                  failed: 1,
                },
                latest_run: {
                  ...ornekKosu({ status: "running" }),
                  model_version: 2,
                  model_version_name: "model512-onnx",
                },
              }),
            ]),
          }
        : undefined,
    );

    sar(<GorevListesiSayfasi />);

    expect(await screen.findByText("Orman araması")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    // 2 tamam, queued+processing = 3 işlemde, 1 başarısız
    expect(screen.getByText(/2 tamam · 3 işlemde · 1 başarısız/)).toBeInTheDocument();
    expect(screen.getByText("Çalışıyor")).toBeInTheDocument();
    expect(screen.getByText("model512-onnx")).toBeInTheDocument();
  });

  it("taraması olmayan görevde 'Tarama yapılmadı' yazar, uydurma durum göstermez", async () => {
    fetchTaklidiKur((yol) =>
      yol.includes("/api/missions/")
        ? { govde: sayfali([ornekGorev({ latest_run: null })]) }
        : undefined,
    );

    sar(<GorevListesiSayfasi />);
    expect(await screen.findByText("Tarama yapılmadı")).toBeInTheDocument();
  });
});

describe("görev oluşturma", () => {
  it("boş ad ile gönderim düğmesi kapalıdır", async () => {
    const kullanici = userEvent.setup();
    fetchTaklidiKur((yol) =>
      yol.includes("/api/missions/") ? { govde: sayfali([]) } : undefined,
    );

    sar(<GorevListesiSayfasi />);
    await kullanici.click(await screen.findByRole("button", { name: "Yeni görev" }));

    expect(screen.getByRole("button", { name: "Görevi oluştur" })).toBeDisabled();
  });

  it("geçerli ad ile POST atar ve listeyi geçersiz kılar", async () => {
    const kullanici = userEvent.setup();
    const { cagrilar } = fetchTaklidiKur((yol, secenekler) => {
      if (yol.includes("/api/missions/") && secenekler?.method === "POST") {
        return { durum: 201, govde: ornekGorev({ id: 42, name: "Yeni arama" }) };
      }
      if (yol.includes("/api/missions/")) return { govde: sayfali([]) };
      return undefined;
    });

    sar(<GorevListesiSayfasi />);
    await kullanici.click(await screen.findByRole("button", { name: "Yeni görev" }));
    await kullanici.type(screen.getByLabelText("Görev adı"), "Yeni arama");
    await kullanici.click(screen.getByRole("button", { name: "Görevi oluştur" }));

    await waitFor(() =>
      expect(cagrilar.some((c) => c.yontem === "POST")).toBe(true),
    );
  });

  it("çift tıklama ikinci bir POST üretmez", async () => {
    const kullanici = userEvent.setup();
    let postSayisi = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (girdi: RequestInfo | URL, secenekler?: RequestInit) => {
        const yol = String(girdi);
        if (yol.includes("/api/missions/") && secenekler?.method === "POST") {
          postSayisi += 1;
          await new Promise((coz) => setTimeout(coz, 50));
          return new Response(JSON.stringify(ornekGorev({ id: 42 })), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(JSON.stringify(sayfali([])), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );

    sar(<GorevListesiSayfasi />);
    await kullanici.click(await screen.findByRole("button", { name: "Yeni görev" }));
    await kullanici.type(screen.getByLabelText("Görev adı"), "Çift tıklama");

    const dugme = screen.getByRole("button", { name: "Görevi oluştur" });
    await kullanici.click(dugme);
    await kullanici.click(dugme);
    await kullanici.click(dugme);

    await waitFor(() => expect(postSayisi).toBeGreaterThan(0));
    expect(postSayisi).toBe(1);
  });

  it("backend doğrulama hatasını okunabilir biçimde gösterir, ham JSON basmaz", async () => {
    const kullanici = userEvent.setup();
    fetchTaklidiKur((yol, secenekler) => {
      if (yol.includes("/api/missions/") && secenekler?.method === "POST") {
        return { durum: 400, govde: { name: ["This field may not be blank."] } };
      }
      if (yol.includes("/api/missions/")) return { govde: sayfali([]) };
      return undefined;
    });

    sar(<GorevListesiSayfasi />);
    await kullanici.click(await screen.findByRole("button", { name: "Yeni görev" }));
    await kullanici.type(screen.getByLabelText("Görev adı"), "x");
    await kullanici.click(screen.getByRole("button", { name: "Görevi oluştur" }));

    const uyari = await screen.findByRole("alert");
    expect(uyari).toHaveTextContent("This field may not be blank.");
    expect(uyari.textContent).not.toContain("{");
  });
});
