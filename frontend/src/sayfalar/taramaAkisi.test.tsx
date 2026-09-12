/**
 * Tarama akışı: model seçimi, çift tarama engeli, yoklamanın başlaması ve
 * terminal durumda DURMASI, kare durum sayımları, kısmi başarısızlık.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";

import { GorevAyrintiSayfasi } from "./GorevAyrintiSayfasi";
import { varsayilanModeliSec } from "./TaramaBaslatma";
import {
  fetchTaklidiKur,
  ornekGorev,
  ornekKare,
  ornekKosu,
  ornekModel,
  sar,
  sayfali,
} from "../test/yardimcilar";
import type { Kosu } from "../api/tipler";

afterEach(() => vi.unstubAllGlobals());

function ayrintiSayfasi() {
  return (
    <Routes>
      <Route path="/gorevler/:gorevId" element={<GorevAyrintiSayfasi />} />
    </Routes>
  );
}

describe("varsayılan model seçimi", () => {
  it("model adı sabit yazılmaz; gerçek dedektörlü (onnx) kayıt tercih edilir", () => {
    const modeller = [
      ornekModel({ id: 1, name: "fake-v0", framework: "fake" }),
      ornekModel({ id: 2, name: "model512-onnx", framework: "onnx" }),
    ];
    expect(varsayilanModeliSec(modeller)?.name).toBe("model512-onnx");
  });

  it("onnx kaydı yoksa listenin ilkine düşer", () => {
    const modeller = [ornekModel({ id: 1, name: "fake-v0", framework: "fake" })];
    expect(varsayilanModeliSec(modeller)?.id).toBe(1);
  });

  it("hiç model yoksa null döner", () => {
    expect(varsayilanModeliSec([])).toBeNull();
  });
});

describe("tarama başlatma", () => {
  it("karesiz görevde düğme kapalıdır ve nedeni yazılır", async () => {
    fetchTaklidiKur((yol) => {
      if (yol.includes("/api/models/")) return { govde: sayfali([ornekModel()]) };
      if (yol.includes("/runs/")) return { govde: sayfali([]) };
      if (yol.includes("/frames/")) return { govde: sayfali([]) };
      if (yol.includes("/api/missions/1/")) {
        return { govde: ornekGorev({ frame_count: 0, frame_counts: {
          pending: 0, queued: 0, processing: 0, done: 0, failed: 0 } }) };
      }
      return undefined;
    });

    sar(ayrintiSayfasi(), { baslangicRotasi: "/gorevler/1" });

    expect(
      await screen.findByRole("button", { name: "Taramayı başlat" }),
    ).toBeDisabled();
    expect(screen.getByText(/Görevde kare yok/)).toBeInTheDocument();
  });

  it("çift tıklama ikinci bir tarama başlatmaz", async () => {
    const kullanici = userEvent.setup();
    let baslatmaSayisi = 0;

    vi.stubGlobal(
      "fetch",
      vi.fn(async (girdi: RequestInfo | URL, secenekler?: RequestInit) => {
        const yol = String(girdi);
        const json = (govde: unknown, durum = 200) =>
          new Response(JSON.stringify(govde), {
            status: durum,
            headers: { "Content-Type": "application/json" },
          });

        if (yol.includes("/runs/") && secenekler?.method === "POST") {
          baslatmaSayisi += 1;
          await new Promise((coz) => setTimeout(coz, 60));
          return json({ run_id: 9, status: "pending", frames_total: 2 }, 202);
        }
        if (yol.includes("/api/models/")) return json(sayfali([ornekModel()]));
        if (yol.includes("/runs/")) return json(sayfali([]));
        if (yol.includes("/frames/")) return json(sayfali([ornekKare()]));
        if (yol.includes("/api/missions/1/")) return json(ornekGorev());
        return json({ detail: "yok" }, 404);
      }),
    );

    sar(ayrintiSayfasi(), { baslangicRotasi: "/gorevler/1" });

    const dugme = await screen.findByRole("button", { name: "Taramayı başlat" });
    await waitFor(() => expect(dugme).toBeEnabled());

    await kullanici.click(dugme);
    await kullanici.click(dugme);
    await kullanici.click(dugme);

    await waitFor(() => expect(baslatmaSayisi).toBeGreaterThan(0));
    expect(baslatmaSayisi).toBe(1);
  });
});

describe("yoklama (polling)", () => {
  it("koşu çalışırken yoklar, terminal duruma gelince DURUR", async () => {
    // Koşu iki yoklamada "running", sonra "done" olur. done olduktan sonra
    // /api/runs/9/ ucuna yeni istek GİTMEMELİ.
    const durumSirasi: Kosu["status"][] = ["running", "running", "done"];
    let kosuIstegiSayisi = 0;

    vi.stubGlobal(
      "fetch",
      vi.fn(async (girdi: RequestInfo | URL) => {
        const yol = String(girdi);
        const json = (govde: unknown) =>
          new Response(JSON.stringify(govde), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });

        if (/\/api\/runs\/9\/$/.test(yol)) {
          const durum = durumSirasi[Math.min(kosuIstegiSayisi, durumSirasi.length - 1)];
          kosuIstegiSayisi += 1;
          return json(
            ornekKosu({
              status: durum,
              frames_done: durum === "done" ? 2 : 1,
              finished_at: durum === "done" ? "2026-09-12T16:39:02Z" : null,
            }),
          );
        }
        if (yol.includes("/api/models/")) return json(sayfali([ornekModel()]));
        if (yol.includes("/runs/")) return json(sayfali([ornekKosu({ status: "running" })]));
        if (yol.includes("/frames/")) return json(sayfali([ornekKare()]));
        if (yol.includes("/api/missions/1/")) return json(ornekGorev());
        return json({});
      }),
    );

    sar(ayrintiSayfasi(), { baslangicRotasi: "/gorevler/1" });

    // Terminal duruma ulaşılsın.
    expect(await screen.findByText("Tamamlandı", {}, { timeout: 8000 })).toBeInTheDocument();

    const durmaAnindakiSayi = kosuIstegiSayisi;
    // Yoklama aralığından uzun bir süre bekle: yeni istek gitmemeli.
    await new Promise((coz) => setTimeout(coz, 2600));
    expect(kosuIstegiSayisi).toBe(durmaAnindakiSayi);
  }, 15000);

  it("koşu sürerken ilerleme gerçek kare sayılarından hesaplanır", async () => {
    fetchTaklidiKur((yol) => {
      if (/\/api\/runs\/9\/$/.test(yol)) {
        return {
          govde: ornekKosu({
            status: "running",
            frames_total: 10,
            frames_done: 3,
            frames_failed: 1,
            finished_at: null,
          }),
        };
      }
      if (yol.includes("/api/models/")) return { govde: sayfali([ornekModel()]) };
      if (yol.includes("/runs/")) return { govde: sayfali([ornekKosu({ status: "running" })]) };
      if (yol.includes("/frames/")) return { govde: sayfali([ornekKare()]) };
      if (yol.includes("/api/missions/1/")) return { govde: ornekGorev() };
      return undefined;
    });

    sar(ayrintiSayfasi(), { baslangicRotasi: "/gorevler/1" });

    // 3 done + 1 failed = 4 sonuçlanan; hedefi olmayan kareler başarısız sayılmaz.
    expect(
      await screen.findByText("10 karenin 4 tanesi sonuçlandı."),
    ).toBeInTheDocument();
    const cubuk = screen.getByRole("progressbar");
    expect(cubuk).toHaveAttribute("aria-valuenow", "4");
    expect(cubuk).toHaveAttribute("aria-valuemax", "10");
  });

  it("kısmi başarısızlık gizlenmez: tamamlanan koşuda başarısız kare sayısı yazılır", async () => {
    fetchTaklidiKur((yol) => {
      if (/\/api\/runs\/9\/$/.test(yol)) {
        return {
          govde: ornekKosu({ status: "done", frames_total: 5, frames_done: 3, frames_failed: 2 }),
        };
      }
      if (yol.includes("/api/models/")) return { govde: sayfali([ornekModel()]) };
      if (yol.includes("/runs/")) return { govde: sayfali([ornekKosu()]) };
      if (yol.includes("/frames/")) return { govde: sayfali([ornekKare()]) };
      if (yol.includes("/api/missions/1/")) return { govde: ornekGorev() };
      return undefined;
    });

    sar(ayrintiSayfasi(), { baslangicRotasi: "/gorevler/1" });

    expect(
      await screen.findByText(/2 kare işlenemedi/),
    ).toBeInTheDocument();
  });
});

describe("kare durumları", () => {
  it("backend enum'larının her biri kendi Türkçe etiketiyle gösterilir", async () => {
    fetchTaklidiKur((yol) => {
      if (yol.includes("/api/models/")) return { govde: sayfali([ornekModel()]) };
      if (yol.includes("/runs/")) return { govde: sayfali([]) };
      if (yol.includes("/frames/")) {
        return {
          govde: sayfali([
            ornekKare({ id: 1, original_filename: "a.jpg", status: "pending" }),
            ornekKare({ id: 2, original_filename: "b.jpg", status: "queued" }),
            ornekKare({ id: 3, original_filename: "c.jpg", status: "processing" }),
            ornekKare({ id: 4, original_filename: "d.jpg", status: "done" }),
            ornekKare({ id: 5, original_filename: "e.jpg", status: "failed" }),
          ]),
        };
      }
      if (yol.includes("/api/missions/1/")) return { govde: ornekGorev() };
      return undefined;
    });

    sar(ayrintiSayfasi(), { baslangicRotasi: "/gorevler/1" });

    expect(await screen.findByText("a.jpg")).toBeInTheDocument();

    // Sorgu kare TABLOSUNA daraltılır: "Başarısız" metni sayım kutularında da
    // geçiyor, rozetle karışmasın.
    const tablo = within(screen.getByRole("table", { name: /Görevin kareleri/ }));
    for (const etiket of ["Bekliyor", "Kuyrukta", "İşleniyor", "Tamam", "Başarısız"]) {
      expect(tablo.getByText(etiket)).toBeInTheDocument();
    }
  });
});
