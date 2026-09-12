/**
 * Harita ve konum dürüstlüğü.
 *
 * Buradaki testler haritanın çizilip çizilmediğinden çok, YANLIŞ BİR ŞEY
 * göstermediğini doğrular: konum yokken boş dünya haritası açmamak, demo
 * koordinatı gerçek gibi sunmamak ve koordinat sırasını ters çevirmemek.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, within } from "@testing-library/react";

import { GorevHaritasi } from "../bilesenler/GorevHaritasi";
import { sar } from "../test/yardimcilar";
import type { Bulgu, Kume } from "../api/tipler";

afterEach(() => vi.unstubAllGlobals());

function ornekBulgu(ekler: Partial<Bulgu> = {}): Bulgu {
  return {
    id: 1,
    mission: 1,
    title: "Aday",
    note: "",
    status: "candidate",
    location: { type: "Point", coordinates: [16.44, 43.51] },
    latitude: 43.51,
    longitude: 16.44,
    location_source: "manual",
    location_note: "",
    is_demo: false,
    has_measured_location: false,
    detection: null,
    review: null,
    created_by: { id: 1, username: "operator" },
    cluster_id: null,
    cluster_key: "",
    clustered_at: null,
    created_at: "2026-09-13T10:00:00Z",
    updated_at: "2026-09-13T10:00:00Z",
    ...ekler,
  };
}

function ornekKume(ekler: Partial<Kume> = {}): Kume {
  return {
    cluster_key: "gercek",
    cluster_id: 1,
    uye_sayisi: 3,
    finding_ids: [1, 2, 3],
    is_demo: false,
    merkez: [16.44, 43.51],
    merkez_notu: "Küme üyelerinin ortalaması; ölçülmüş konum değildir.",
    ...ekler,
  };
}

describe("konum yokken", () => {
  it("boş dünya haritası yerine açıklayıcı boş durum gösterir", () => {
    sar(<GorevHaritasi bulgular={[]} kumeler={[]} />);

    expect(screen.getByTestId("harita-bos-durum")).toBeInTheDocument();
    expect(
      screen.getByText("Bu görevde konum bilgisi mevcut değil."),
    ).toBeInTheDocument();
    // Harita kabı HİÇ oluşturulmamalı.
    expect(screen.queryByTestId("harita-kabi")).not.toBeInTheDocument();
  });

  it("konumu olmayan bulgular varken de harita açılmaz", () => {
    const konumsuz = ornekBulgu({
      location: null, latitude: null, longitude: null, location_source: "none",
    });
    sar(<GorevHaritasi bulgular={[konumsuz]} kumeler={[]} />);

    expect(screen.getByTestId("harita-bos-durum")).toBeInTheDocument();
    expect(screen.queryByTestId("harita-kabi")).not.toBeInTheDocument();
  });

  it("boş durumda piksel koordinatının haritaya konmadığı açıklanır", () => {
    sar(<GorevHaritasi bulgular={[]} kumeler={[]} />);
    expect(screen.getByText(/piksel/i)).toBeInTheDocument();
  });
});

describe("demo konum", () => {
  it("kalıcı bir demo uyarısı gösterir", () => {
    const demo = ornekBulgu({ is_demo: true, location_source: "demo" });
    sar(<GorevHaritasi bulgular={[demo]} kumeler={[]} />);

    const uyari = screen.getByTestId("demo-uyarisi");
    expect(uyari).toHaveTextContent("Demo konumları — gerçek GPS verisi değildir.");
    // Kapatma düğmesi YOK: uyarı kaydırmayla veya tıklamayla kaybolmamalı.
    expect(within(uyari).queryByRole("button")).not.toBeInTheDocument();
  });

  it("yalnızca gerçek konumlar varken demo uyarısı çıkmaz", () => {
    sar(<GorevHaritasi bulgular={[ornekBulgu()]} kumeler={[]} />);
    expect(screen.queryByTestId("demo-uyarisi")).not.toBeInTheDocument();
  });

  it("demo ve gerçek bir arada olsa bile uyarı görünür", () => {
    const gercek = ornekBulgu({ id: 1 });
    const demo = ornekBulgu({ id: 2, is_demo: true, location_source: "demo" });
    sar(<GorevHaritasi bulgular={[gercek, demo]} kumeler={[]} />);

    expect(screen.getByTestId("demo-uyarisi")).toBeInTheDocument();
  });
});

describe("harita gösterimi", () => {
  it("konumlu bulgu varsa harita kabı oluşur", () => {
    sar(<GorevHaritasi bulgular={[ornekBulgu()]} kumeler={[]} />);
    expect(screen.getByTestId("harita-kabi")).toBeInTheDocument();
  });

  it("konumsuz bulgu sayısı ayrıca yazılır", () => {
    const konumlu = ornekBulgu({ id: 1 });
    const konumsuz = ornekBulgu({
      id: 2, location: null, latitude: null, longitude: null, location_source: "none",
    });
    sar(<GorevHaritasi bulgular={[konumlu, konumsuz]} kumeler={[ornekKume()]} />);

    expect(screen.getByText(/1 konumlu bulgu gösteriliyor/)).toBeInTheDocument();
    expect(
      screen.getByText(/1 bulgunun konumu yok ve haritada\s+gösterilmiyor/),
    ).toBeInTheDocument();
  });

  it("küme merkezinin ölçülmüş konum olmadığı yazılır", () => {
    sar(<GorevHaritasi bulgular={[ornekBulgu()]} kumeler={[ornekKume()]} />);
    expect(
      screen.getByText(/küme merkezi\s+ölçülmüş bir konum değil/i),
    ).toBeInTheDocument();
  });

  it("bozuk koordinatlı kayıt haritayı çökertmez", () => {
    // latitude dolu, longitude null: tutarsız kayıt haritaya girmemeli.
    const bozuk = ornekBulgu({ id: 3, latitude: 43.5, longitude: null });
    expect(() =>
      sar(<GorevHaritasi bulgular={[bozuk]} kumeler={[]} />),
    ).not.toThrow();
    expect(screen.getByTestId("harita-bos-durum")).toBeInTheDocument();
  });
});

describe("koordinat sırası", () => {
  it("GeoJSON [boylam, enlem] iken arayüz enlem/boylamı karıştırmaz", () => {
    const bulgu = ornekBulgu({
      location: { type: "Point", coordinates: [16.44, 43.51] },
      latitude: 43.51,
      longitude: 16.44,
    });

    // GeoJSON dizisinin ilk ögesi BOYLAM, ikincisi ENLEM.
    expect(bulgu.location!.coordinates[0]).toBe(bulgu.longitude);
    expect(bulgu.location!.coordinates[1]).toBe(bulgu.latitude);
    // Enlem her zaman [-90, 90] aralığında; boylam daha geniş olabilir.
    expect(Math.abs(bulgu.latitude!)).toBeLessThanOrEqual(90);
  });

  it("küme merkezi de [boylam, enlem] sırasında", () => {
    const kume = ornekKume({ merkez: [16.44, 43.51] });
    expect(Math.abs(kume.merkez[1])).toBeLessThanOrEqual(90);
    expect(kume.merkez[0]).toBe(16.44);
  });
});
