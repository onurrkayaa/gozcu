/**
 * Rol bazlı görünürlük, inceleme yazma, bulgu formu ve denetim görünümü.
 *
 * Arayüzün denetimleri gizlemesi bir kolaylıktır, güvenlik sınırı DEĞİL:
 * yetkiyi backend uygular. Buradaki testler kullanıcının çalışmayacak bir
 * düğmeye tıklamamasını ve salt okunur kullanıcının neden yazamadığını
 * okuyabilmesini doğrular.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { IncelemePaneli } from "../bilesenler/IncelemePaneli";
import { UyeYonetimi } from "./UyeYonetimi";
import { BulguPaneli } from "./BulguPaneli";
import { DenetimGecmisi } from "./DenetimGecmisi";
import { fetchTaklidiKur, ornekTespit, sar, sayfali } from "../test/yardimcilar";
import type { Inceleme, Uyelik } from "../api/tipler";

afterEach(() => vi.unstubAllGlobals());

function ornekInceleme(ekler: Partial<Inceleme> = {}): Inceleme {
  return {
    id: 1,
    detection: 6458,
    reviewer: { id: 2, username: "operator" },
    decision: "accepted",
    note: "",
    created_at: "2026-09-13T10:00:00Z",
    updated_at: "2026-09-13T10:00:00Z",
    ...ekler,
  };
}

function ornekUyelik(ekler: Partial<Uyelik> = {}): Uyelik {
  return {
    id: 1,
    mission: 1,
    user: { id: 1, username: "sahip" },
    role: "owner",
    created_at: "2026-09-13T10:00:00Z",
    updated_at: "2026-09-13T10:00:00Z",
    ...ekler,
  };
}

// --- İnceleme -------------------------------------------------------------

describe("inceleme paneli", () => {
  it("operatör karar düğmelerini görür", () => {
    fetchTaklidiKur(() => undefined);
    sar(
      <IncelemePaneli
        kosuId={9} tespit={ornekTespit()} incelemeler={[]}
        rol="operator" kullaniciAdi="operator"
      />,
    );

    expect(screen.getByRole("button", { name: "Doğrulandı" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reddedildi" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Belirsiz" })).toBeInTheDocument();
  });

  it("viewer salt okunur görür, karar düğmesi yok", () => {
    fetchTaklidiKur(() => undefined);
    sar(
      <IncelemePaneli
        kosuId={9} tespit={ornekTespit()} incelemeler={[]}
        rol="viewer" kullaniciAdi="izleyici"
      />,
    );

    expect(screen.getByTestId("inceleme-salt-okunur")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Doğrulandı" })).not.toBeInTheDocument();
  });

  it("üye olmayan (rol null) da yazamaz", () => {
    fetchTaklidiKur(() => undefined);
    sar(
      <IncelemePaneli
        kosuId={9} tespit={ornekTespit()} incelemeler={[]}
        rol={null} kullaniciAdi="yabanci"
      />,
    );
    expect(screen.getByTestId("inceleme-salt-okunur")).toBeInTheDocument();
  });

  it("karara tıklayınca PUT gönderir", async () => {
    const kullanici = userEvent.setup();
    const { cagrilar } = fetchTaklidiKur((yol, secenekler) => {
      if (yol.includes("/reviews/") && secenekler?.method === "PUT") {
        return { durum: 201, govde: ornekInceleme() };
      }
      return { govde: sayfali([]) };
    });

    sar(
      <IncelemePaneli
        kosuId={9} tespit={ornekTespit()} incelemeler={[]}
        rol="operator" kullaniciAdi="operator"
      />,
    );
    await kullanici.click(screen.getByRole("button", { name: "Doğrulandı" }));

    await waitFor(() =>
      expect(cagrilar.some((c) => c.yontem === "PUT")).toBe(true),
    );
  });

  it("mevcut kendi kararı seçili gelir", () => {
    fetchTaklidiKur(() => undefined);
    sar(
      <IncelemePaneli
        kosuId={9}
        tespit={ornekTespit()}
        incelemeler={[ornekInceleme({ decision: "rejected" })]}
        rol="operator"
        kullaniciAdi="operator"
      />,
    );

    expect(screen.getByRole("button", { name: "Reddedildi" })).toHaveAttribute(
      "aria-pressed", "true",
    );
  });

  it("başka operatörün kararı listede görünür ama kendi seçimini etkilemez", () => {
    fetchTaklidiKur(() => undefined);
    sar(
      <IncelemePaneli
        kosuId={9}
        tespit={ornekTespit()}
        incelemeler={[ornekInceleme({ reviewer: { id: 9, username: "baskasi" } })]}
        rol="operator"
        kullaniciAdi="operator"
      />,
    );

    expect(screen.getByTestId("inceleme-listesi")).toHaveTextContent("baskasi");
    expect(screen.getByRole("button", { name: "Doğrulandı" })).toHaveAttribute(
      "aria-pressed", "false",
    );
  });

  it("istek uçarken düğmeler kilitlenir (çift gönderim yok)", async () => {
    const kullanici = userEvent.setup();
    let putSayisi = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_g: RequestInfo | URL, secenekler?: RequestInit) => {
        if (secenekler?.method === "PUT") {
          putSayisi += 1;
          await new Promise((coz) => setTimeout(coz, 50));
        }
        return new Response(JSON.stringify(ornekInceleme()), {
          status: 201, headers: { "Content-Type": "application/json" },
        });
      }),
    );

    sar(
      <IncelemePaneli
        kosuId={9} tespit={ornekTespit()} incelemeler={[]}
        rol="operator" kullaniciAdi="operator"
      />,
    );
    const dugme = screen.getByRole("button", { name: "Doğrulandı" });
    await kullanici.click(dugme);
    await kullanici.click(dugme);
    await kullanici.click(dugme);

    await waitFor(() => expect(putSayisi).toBeGreaterThan(0));
    expect(putSayisi).toBe(1);
  });
});

// --- Üye yönetimi ---------------------------------------------------------

describe("üye yönetimi", () => {
  it("owner ekleme formunu görür", async () => {
    fetchTaklidiKur(() => ({ govde: sayfali([ornekUyelik()]) }));
    sar(<UyeYonetimi gorevId={1} rol="owner" />);

    expect(await screen.findByLabelText("Kullanıcı adı")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ekle" })).toBeInTheDocument();
  });

  it("viewer salt okunur görür", async () => {
    fetchTaklidiKur(() => ({ govde: sayfali([ornekUyelik()]) }));
    sar(<UyeYonetimi gorevId={1} rol="viewer" />);

    expect(await screen.findByTestId("uye-salt-okunur")).toBeInTheDocument();
    expect(screen.queryByLabelText("Kullanıcı adı")).not.toBeInTheDocument();
  });

  it("operator da üye yönetemez", async () => {
    fetchTaklidiKur(() => ({ govde: sayfali([ornekUyelik()]) }));
    sar(<UyeYonetimi gorevId={1} rol="operator" />);
    expect(await screen.findByTestId("uye-salt-okunur")).toBeInTheDocument();
  });

  it("son sahip için rol ve çıkarma denetimleri kilitli", async () => {
    fetchTaklidiKur(() => ({ govde: sayfali([ornekUyelik({ role: "owner" })]) }));
    sar(<UyeYonetimi gorevId={1} rol="owner" />);

    expect(await screen.findByText("Görevin son sahibi")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Çıkar" })).toBeDisabled();
    expect(screen.getByLabelText("sahip rolü")).toBeDisabled();
  });

  it("iki sahip varken denetimler açık", async () => {
    fetchTaklidiKur(() => ({
      govde: sayfali([
        ornekUyelik({ id: 1, role: "owner", user: { id: 1, username: "sahip" } }),
        ornekUyelik({ id: 2, role: "owner", user: { id: 2, username: "ikinci" } }),
      ]),
    }));
    sar(<UyeYonetimi gorevId={1} rol="owner" />);

    expect(await screen.findByText("ikinci")).toBeInTheDocument();
    expect(screen.queryByText("Görevin son sahibi")).not.toBeInTheDocument();
  });

  it("üye listesi e-posta göstermez", async () => {
    fetchTaklidiKur(() => ({ govde: sayfali([ornekUyelik()]) }));
    const { container } = sar(<UyeYonetimi gorevId={1} rol="owner" />);

    await screen.findByText("sahip");
    expect(container.textContent).not.toMatch(/@[\w.-]+\.\w+/);
  });
});

// --- Bulgu formu ----------------------------------------------------------

describe("bulgu paneli", () => {
  function taklitKur(bulgular: unknown[] = []) {
    return fetchTaklidiKur((yol) => {
      if (yol.includes("/clusters/")) {
        return { govde: { esik_metre_varsayilan: 50, clusters: [] } };
      }
      if (yol.includes("/findings/")) return { govde: sayfali(bulgular) };
      return undefined;
    });
  }

  it("ölçülmüş kaynaklar seçeneklerde YOK", async () => {
    taklitKur();
    sar(<BulguPaneli gorevId={1} rol="operator" />);

    const secim = await screen.findByLabelText("Konum kaynağı");
    const secenekler = Array.from(secim.querySelectorAll("option")).map((o) => o.value);
    expect(secenekler).toEqual(["none", "manual", "demo"]);
    expect(secenekler).not.toContain("exif");
    expect(secenekler).not.toContain("flight_log");
  });

  it("konum kaynağı 'none' iken koordinat alanları gösterilmez", async () => {
    taklitKur();
    sar(<BulguPaneli gorevId={1} rol="operator" />);

    await screen.findByLabelText("Konum kaynağı");
    expect(screen.queryByLabelText(/Enlem/)).not.toBeInTheDocument();
  });

  it("elle konum seçilince koordinat alanları çıkar", async () => {
    const kullanici = userEvent.setup();
    taklitKur();
    sar(<BulguPaneli gorevId={1} rol="operator" />);

    await kullanici.selectOptions(
      await screen.findByLabelText("Konum kaynağı"), "manual",
    );
    expect(screen.getByLabelText(/Enlem/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Boylam/)).toBeInTheDocument();
  });

  it("aralık dışı enlem gönderimi engeller", async () => {
    const kullanici = userEvent.setup();
    taklitKur();
    sar(<BulguPaneli gorevId={1} rol="operator" />);

    await kullanici.selectOptions(
      await screen.findByLabelText("Konum kaynağı"), "manual",
    );
    await kullanici.type(screen.getByLabelText(/Enlem/), "95");
    await kullanici.type(screen.getByLabelText(/Boylam/), "16");

    expect(screen.getByRole("button", { name: "Bulgu ekle" })).toBeDisabled();
  });

  it("aralık dışı boylam gönderimi engeller", async () => {
    const kullanici = userEvent.setup();
    taklitKur();
    sar(<BulguPaneli gorevId={1} rol="operator" />);

    await kullanici.selectOptions(
      await screen.findByLabelText("Konum kaynağı"), "manual",
    );
    await kullanici.type(screen.getByLabelText(/Enlem/), "43");
    await kullanici.type(screen.getByLabelText(/Boylam/), "200");

    expect(screen.getByRole("button", { name: "Bulgu ekle" })).toBeDisabled();
  });

  it("viewer bulgu ekleyemez", async () => {
    taklitKur();
    sar(<BulguPaneli gorevId={1} rol="viewer" />);

    expect(await screen.findByTestId("bulgu-salt-okunur")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Bulgu ekle" })).not.toBeInTheDocument();
  });

  it("viewer kümeleme çalıştıramaz", async () => {
    taklitKur();
    sar(<BulguPaneli gorevId={1} rol="viewer" />);

    await screen.findByTestId("bulgu-salt-okunur");
    expect(
      screen.queryByRole("button", { name: "Kümelemeyi çalıştır" }),
    ).not.toBeInTheDocument();
  });

  it("kümelemenin geçişli davranışı kullanıcıya anlatılır", async () => {
    taklitKur();
    sar(<BulguPaneli gorevId={1} rol="operator" />);

    // Metin <strong> etiketleriyle bölündüğü için eşleşen düğümün kendisi
    // değil, onu içeren paragraf sınanır.
    const vurgu = await screen.findByText(/zincirleme yayılır/);
    const aciklama = vurgu.closest("p") as HTMLElement;

    expect(aciklama).toHaveTextContent(/eşik, kümenin çapı değildir/i);
    expect(aciklama).toHaveTextContent(/karar/);
    expect(aciklama).toHaveTextContent(/ölçüm değil/);
  });

  it("demo bulgu listede etiketli görünür", async () => {
    taklitKur([
      {
        id: 7, mission: 1, title: "Demo aday", note: "", status: "candidate",
        location: { type: "Point", coordinates: [16.4, 43.5] },
        latitude: 43.5, longitude: 16.4, location_source: "demo", location_note: "",
        is_demo: true, has_measured_location: false, detection: null, review: null,
        created_by: null, cluster_id: 1, cluster_key: "demo", clustered_at: null,
        created_at: "2026-09-13T10:00:00Z", updated_at: "2026-09-13T10:00:00Z",
      },
    ]);
    sar(<BulguPaneli gorevId={1} rol="operator" />);

    const satir = await screen.findByTestId("bulgu-satiri-7");
    expect(satir).toHaveTextContent("DEMO — gerçek GPS değil");
  });

  it("konumsuz bulgu 'Konum bilgisi mevcut değil' yazar, 0,0 göstermez", async () => {
    taklitKur([
      {
        id: 8, mission: 1, title: "Konumsuz", note: "", status: "candidate",
        location: null, latitude: null, longitude: null, location_source: "none",
        location_note: "", is_demo: false, has_measured_location: false,
        detection: null, review: null, created_by: null, cluster_id: null,
        cluster_key: "", clustered_at: null,
        created_at: "2026-09-13T10:00:00Z", updated_at: "2026-09-13T10:00:00Z",
      },
    ]);
    sar(<BulguPaneli gorevId={1} rol="operator" />);

    const satir = await screen.findByTestId("bulgu-satiri-8");
    expect(satir).toHaveTextContent("Konum bilgisi mevcut değil");
    expect(satir).not.toHaveTextContent("0.00000, 0.00000");
  });
});

// --- Denetim görünümü -----------------------------------------------------

describe("denetim geçmişi", () => {
  const ornekKayit = {
    id: 1,
    mission: 1,
    actor: { id: 1, username: "sahip" },
    action: "member_role_changed",
    action_display: "Üye rolü değişti",
    object_type: "MissionMember",
    object_id: "3",
    changes: { role: { onceki: "viewer", sonraki: "operator" } },
    created_at: "2026-09-13T10:00:00Z",
  };

  it("kayıtları okunabilir biçimde gösterir", async () => {
    fetchTaklidiKur(() => ({ govde: sayfali([ornekKayit]) }));
    sar(<DenetimGecmisi gorevId={1} />);

    expect(await screen.findByText("Üye rolü değişti")).toBeInTheDocument();
    expect(screen.getByText("role: viewer → operator")).toBeInTheDocument();
  });

  it("ham JSON dökmez", async () => {
    fetchTaklidiKur(() => ({ govde: sayfali([ornekKayit]) }));
    const { container } = sar(<DenetimGecmisi gorevId={1} />);

    await screen.findByText("Üye rolü değişti");
    expect(container.textContent).not.toContain('{"');
    expect(container.textContent).not.toContain('"onceki"');
  });

  it("salt okunur olduğu yazılır ve yazma denetimi yok", async () => {
    fetchTaklidiKur(() => ({ govde: sayfali([ornekKayit]) }));
    sar(<DenetimGecmisi gorevId={1} />);

    expect(
      await screen.findByText(/Salt okunur; bu kayıtlar değiştirilemez/),
    ).toBeInTheDocument();
    // Sayfalama dışında hiçbir eylem düğmesi olmamalı.
    const dugmeler = screen.queryAllByRole("button").map((d) => d.textContent);
    expect(dugmeler.filter((m) => m && !["Önceki", "Sonraki"].includes(m))).toHaveLength(0);
  });

  it("boş durumda açıklama gösterir", async () => {
    fetchTaklidiKur(() => ({ govde: sayfali([]) }));
    sar(<DenetimGecmisi gorevId={1} />);

    expect(
      await screen.findByText("Bu görevde henüz kayıtlı işlem yok."),
    ).toBeInTheDocument();
  });

  it("hata durumunda yeniden dene sunar", async () => {
    fetchTaklidiKur(() => ({ durum: 500, govde: { detail: "Sunucu hatası" } }));
    sar(<DenetimGecmisi gorevId={1} />);

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Yeniden dene" })).toBeInTheDocument();
  });
});
