/**
 * Kimlik doğrulama akışı: giriş, hatalı giriş, korumalı rota, çıkış.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { gorevleriGetir } from "../api/uclar";

import { GirisSayfasi } from "./GirisSayfasi";
import { KorumaliRota } from "../kimlik/KorumaliRota";
import { tokenDeposu } from "../kimlik/tokenDeposu";
import { fetchTaklidiKur, sar } from "../test/yardimcilar";

afterEach(() => vi.unstubAllGlobals());

function KorumaliIcerik() {
  return <div>Gizli görev listesi</div>;
}

function Rotalar() {
  return (
    <Routes>
      <Route path="/giris" element={<GirisSayfasi />} />
      <Route
        path="/gorevler"
        element={
          <KorumaliRota>
            <KorumaliIcerik />
          </KorumaliRota>
        }
      />
    </Routes>
  );
}

describe("giriş", () => {
  it("başarılı girişte tokenları saklar ve korumalı sayfaya geçer", async () => {
    const kullanici = userEvent.setup();
    fetchTaklidiKur((yol) => {
      if (yol.includes("/api/auth/token/")) {
        return { govde: { access: "erisim-1", refresh: "yenileme-1" } };
      }
      return undefined;
    });

    sar(<Rotalar />, { baslangicRotasi: "/giris" });

    await kullanici.type(screen.getByLabelText("Kullanıcı adı"), "operator");
    await kullanici.type(screen.getByLabelText("Parola"), "dogru-parola");
    await kullanici.click(screen.getByRole("button", { name: "Giriş yap" }));

    expect(await screen.findByText("Gizli görev listesi")).toBeInTheDocument();
    expect(tokenDeposu.erisimTokeni()).toBe("erisim-1");
    expect(tokenDeposu.yenilemeTokeni()).toBe("yenileme-1");
  });

  it("hatalı kullanıcı/parola durumunda backend mesajını gösterir, sayfada kalır", async () => {
    const kullanici = userEvent.setup();
    fetchTaklidiKur((yol) => {
      if (yol.includes("/api/auth/token/")) {
        return {
          durum: 401,
          govde: { detail: "No active account found with the given credentials" },
        };
      }
      return undefined;
    });

    sar(<Rotalar />, { baslangicRotasi: "/giris" });

    await kullanici.type(screen.getByLabelText("Kullanıcı adı"), "operator");
    await kullanici.type(screen.getByLabelText("Parola"), "yanlis");
    await kullanici.click(screen.getByRole("button", { name: "Giriş yap" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "No active account found with the given credentials",
    );
    expect(tokenDeposu.erisimTokeni()).toBeNull();
    expect(screen.queryByText("Gizli görev listesi")).not.toBeInTheDocument();
  });

  it("giriş isteği uçarken düğme kilitlenir (çift gönderim yok)", async () => {
    const kullanici = userEvent.setup();
    let girisSayisi = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        girisSayisi += 1;
        await new Promise((coz) => setTimeout(coz, 40));
        return new Response(JSON.stringify({ access: "a", refresh: "r" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );

    sar(<Rotalar />, { baslangicRotasi: "/giris" });

    await kullanici.type(screen.getByLabelText("Kullanıcı adı"), "operator");
    await kullanici.type(screen.getByLabelText("Parola"), "parola");

    const dugme = screen.getByRole("button", { name: "Giriş yap" });
    await kullanici.click(dugme);
    // İlk istek uçarken düğme devre dışı olmalı.
    await waitFor(() => expect(screen.getByRole("button")).toBeDisabled());

    expect(girisSayisi).toBe(1);
  });

  it("korumalı rota girişsiz açılırsa giriş ekranına yönlendirir", async () => {
    fetchTaklidiKur(() => undefined);
    sar(<Rotalar />, { baslangicRotasi: "/gorevler" });

    expect(await screen.findByLabelText("Kullanıcı adı")).toBeInTheDocument();
    expect(screen.queryByText("Gizli görev listesi")).not.toBeInTheDocument();
  });

  it("saklı token varsa yeniden yüklemede korumalı sayfa açık kalır", async () => {
    tokenDeposu.yaz("erisim-kayitli", "yenileme-kayitli");
    fetchTaklidiKur(() => undefined);

    sar(<Rotalar />, { baslangicRotasi: "/gorevler" });

    expect(await screen.findByText("Gizli görev listesi")).toBeInTheDocument();
  });
});

describe("zorunlu çıkış", () => {
  it("yenileme düşünce elle çıkışla AYNI izleri siler", async () => {
    tokenDeposu.yaz("erisim", "cop-yenileme");
    window.localStorage.setItem("gozcu.kullaniciAdi", "operator");

    // İlk istek 401, yenileme de 401: oturum zorla kapanmalı.
    fetchTaklidiKur((yol) => {
      if (yol.includes("/auth/token/refresh/")) {
        return { durum: 401, govde: { detail: "Token is invalid" } };
      }
      return { durum: 401, govde: { detail: "gecersiz" } };
    });

    // Korumalı içerik GERÇEKTEN istek atmalı; yoksa 401 hiç oluşmaz.
    function IstekAtanIcerik() {
      const sorgu = useQuery({
        queryKey: ["deneme-gorevler"],
        queryFn: () => gorevleriGetir(),
        retry: false,
      });
      return <div>{sorgu.isPending ? "Yükleniyor" : "Gizli görev listesi"}</div>;
    }

    sar(
      <Routes>
        <Route path="/giris" element={<GirisSayfasi />} />
        <Route
          path="/gorevler"
          element={
            <KorumaliRota>
              <IstekAtanIcerik />
            </KorumaliRota>
          }
        />
      </Routes>,
      { baslangicRotasi: "/gorevler" },
    );

    await waitFor(() => {
      expect(tokenDeposu.erisimTokeni()).toBeNull();
      expect(tokenDeposu.yenilemeTokeni()).toBeNull();
      // Kullanıcı adı da kalmamalı: iki çıkış yolu aynı temizliği yapar.
      expect(window.localStorage.getItem("gozcu.kullaniciAdi")).toBeNull();
    });

    // Oturum düştüğü için korumalı rota artık giriş ekranına yönlendirir.
    expect(await screen.findByLabelText("Kullanıcı adı")).toBeInTheDocument();
  });
});
