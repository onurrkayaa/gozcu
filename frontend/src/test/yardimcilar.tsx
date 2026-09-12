/**
 * Test yardımcıları.
 *
 * Testler gerçek fetch'i taklit eder ama GERÇEK sözleşmeye göre: buradaki
 * örnek gövdeler backend serializer çıktılarından alınmıştır
 * (reports/hafta5_api_sozlesmesi.csv). Uydurma alan yok.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { RenderResult } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { vi } from "vitest";

import { OturumSaglayici } from "../kimlik/OturumBaglami";
import type { Gorev, Kare, Kosu, ModelSurumu, Tespit } from "../api/tipler";

export function testSorguIstemcisi(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      // Testte yeniden deneme yok: başarısızlık anında görünsün, zaman aşımına
      // takılmasın.
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

export function sar(
  dugum: ReactNode,
  secenekler: { baslangicRotasi?: string; istemci?: QueryClient } = {},
): RenderResult & { istemci: QueryClient } {
  const istemci = secenekler.istemci ?? testSorguIstemcisi();
  const sonuc = render(
    <QueryClientProvider client={istemci}>
      <MemoryRouter initialEntries={[secenekler.baslangicRotasi ?? "/"]}>
        <OturumSaglayici>{dugum}</OturumSaglayici>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...sonuc, istemci };
}

// --- fetch taklidi --------------------------------------------------------

export interface SahteYanit {
  durum?: number;
  govde?: unknown;
  blob?: Blob;
}

type Eslestirici = (yol: string, secenekler: RequestInit | undefined) => SahteYanit | undefined;

/**
 * fetch'i yollara göre cevaplar.
 *
 * Çağrı kaydı tutulur: testler "kaç istek gitti" sorusunu (çift mutation,
 * kontrolsüz yenileme, yoklamanın durması) sayarak cevaplayabilsin.
 */
export function fetchTaklidiKur(eslestirici: Eslestirici) {
  const cagrilar: { yol: string; yontem: string; baslikta: string | null }[] = [];

  const taklit = vi.fn(async (girdi: RequestInfo | URL, secenekler?: RequestInit) => {
    const yol = typeof girdi === "string" ? girdi : girdi.toString();
    const basliklar = (secenekler?.headers ?? {}) as Record<string, string>;
    cagrilar.push({
      yol,
      yontem: secenekler?.method ?? "GET",
      baslikta: basliklar.Authorization ?? null,
    });

    const yanit = eslestirici(yol, secenekler);
    if (!yanit) {
      return new Response(JSON.stringify({ detail: `Eşleşmeyen yol: ${yol}` }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }

    if (yanit.blob) {
      return new Response(yanit.blob, {
        status: yanit.durum ?? 200,
        headers: { "Content-Type": "image/jpeg" },
      });
    }

    return new Response(JSON.stringify(yanit.govde ?? {}), {
      status: yanit.durum ?? 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  vi.stubGlobal("fetch", taklit);
  return { taklit, cagrilar };
}

export function sayfali<T>(ogeler: T[], sonraki: string | null = null) {
  return { count: ogeler.length, next: sonraki, previous: null, results: ogeler };
}

// --- Gerçek sözleşmeden örnek gövdeler ------------------------------------

export function ornekGorev(ekler: Partial<Gorev> = {}): Gorev {
  return {
    id: 1,
    name: "Kayıp yürüyüşçü",
    description: "Deneme görevi",
    created_by: 5,
    created_at: "2026-09-12T16:38:46.138382Z",
    updated_at: "2026-09-12T16:38:46.138411Z",
    frame_count: 2,
    frame_counts: { pending: 0, queued: 0, processing: 0, done: 2, failed: 0 },
    latest_run: null,
    ...ekler,
  };
}

export function ornekKare(ekler: Partial<Kare> = {}): Kare {
  return {
    id: 500,
    mission: 1,
    image: "http://localhost:8000/media/missions/1/ornek.jpg",
    original_filename: "ornek.jpg",
    sha256: "de19397dc4bd5923a370b709f7407c548b23a25922f4ddf285172e26e6e5075e",
    width: 4000,
    height: 3000,
    captured_at: null,
    latitude: null,
    longitude: null,
    altitude_m: null,
    status: "done",
    created_at: "2026-09-12T16:38:52.770971Z",
    ...ekler,
  };
}

export function ornekKosu(ekler: Partial<Kosu> = {}): Kosu {
  return {
    id: 9,
    mission: 1,
    model_version: 2,
    model_version_name: "model512-onnx",
    status: "done",
    conf_threshold: 0.25,
    iou_threshold: 0.45,
    tile_size: 512,
    overlap_ratio: 0.2,
    frames_total: 2,
    frames_done: 2,
    frames_failed: 0,
    started_at: "2026-09-12T16:39:00.225471Z",
    finished_at: "2026-09-12T16:39:02.321077Z",
    ...ekler,
  };
}

export function ornekModel(ekler: Partial<ModelSurumu> = {}): ModelSurumu {
  return {
    id: 2,
    name: "model512-onnx",
    framework: "onnx",
    input_size: 512,
    tile_size: 512,
    overlap_ratio: 0.2,
    notes: "",
    created_at: "2026-09-12T11:21:04.624183Z",
    ...ekler,
  };
}

export function ornekTespit(ekler: Partial<Tespit> = {}): Tespit {
  return {
    id: 6458,
    inference_run: 9,
    frame: 500,
    score: 0.946,
    x1: 2080,
    y1: 1133,
    x2: 2487,
    y2: 1297,
    tile_row: 2,
    tile_col: 5,
    created_at: "2026-09-12T16:39:02.286918Z",
    ...ekler,
  };
}
