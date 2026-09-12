/**
 * API katmanı: token yenileme, oturum düşmesi ve hata çevirisi.
 *
 * Buradaki en kritik davranış, eşzamanlı 401'lerin TEK yenileme isteği
 * üretmesidir: aksi halde her istek kendi yenilemesini başlatır ve backend'e
 * aynı refresh ile N istek gider.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiHatasi, apiIstegi, oturumDustugundeCalistir, yenilemeDurumunuSifirla } from "./istemci";
import { tokenDeposu } from "../kimlik/tokenDeposu";

function jsonYanit(govde: unknown, durum = 200) {
  return new Response(JSON.stringify(govde), {
    status: durum,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  yenilemeDurumunuSifirla();
  oturumDustugundeCalistir(null);
  tokenDeposu.temizle();
});

afterEach(() => {
  vi.unstubAllGlobals();
  oturumDustugundeCalistir(null);
});

describe("apiIstegi", () => {
  it("erişim tokenını Authorization başlığında gönderir, URL'ye koymaz", async () => {
    tokenDeposu.yaz("erisim-abc", "yenileme-xyz");
    const taklit = vi.fn(async () => jsonYanit({ count: 0, results: [] }));
    vi.stubGlobal("fetch", taklit);

    await apiIstegi("/api/missions/");

    const [adres, secenekler] = taklit.mock.calls[0] as unknown as [string, RequestInit];
    expect((secenekler.headers as Record<string, string>).Authorization).toBe(
      "Bearer erisim-abc",
    );
    expect(adres).not.toContain("erisim-abc");
    expect(adres).not.toContain("token");
  });

  it("401 alınca tokenı yeniler ve isteği bir kez tekrarlar", async () => {
    tokenDeposu.yaz("eski-erisim", "yenileme-xyz");

    const taklit = vi
      .fn()
      .mockResolvedValueOnce(jsonYanit({ detail: "token gecersiz" }, 401))
      .mockResolvedValueOnce(jsonYanit({ access: "yeni-erisim" }, 200))
      .mockResolvedValueOnce(jsonYanit({ count: 1, results: [{ id: 1 }] }, 200));
    vi.stubGlobal("fetch", taklit);

    const sonuc = await apiIstegi<{ count: number }>("/api/missions/");

    expect(sonuc.count).toBe(1);
    expect(tokenDeposu.erisimTokeni()).toBe("yeni-erisim");
    // Yenileme sonrası refresh DEĞİŞMEZ: backend yalnızca access döner.
    expect(tokenDeposu.yenilemeTokeni()).toBe("yenileme-xyz");

    const yollar = taklit.mock.calls.map((c) => c[0] as string);
    expect(yollar[1]).toContain("/api/auth/token/refresh/");
    expect(yollar[2]).toContain("/api/missions/");
  });

  it("yenileme başarısızsa oturumu kapatır ve tokenları siler", async () => {
    tokenDeposu.yaz("eski-erisim", "cop-yenileme");
    const oturumDustuDinleyici = vi.fn();
    oturumDustugundeCalistir(oturumDustuDinleyici);

    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonYanit({ detail: "gecersiz" }, 401))
        .mockResolvedValueOnce(jsonYanit({ detail: "Token is invalid" }, 401)),
    );

    await expect(apiIstegi("/api/missions/")).rejects.toBeInstanceOf(ApiHatasi);

    expect(oturumDustuDinleyici).toHaveBeenCalledTimes(1);
    expect(tokenDeposu.erisimTokeni()).toBeNull();
    expect(tokenDeposu.yenilemeTokeni()).toBeNull();
  });

  it("yenileme tokenı yoksa yenilemeye kalkmadan oturumu kapatır", async () => {
    tokenDeposu.yaz("eski-erisim", "");
    tokenDeposu.erisimiGuncelle("eski-erisim");
    window.localStorage.removeItem("gozcu.yenileme");

    const taklit = vi.fn().mockResolvedValue(jsonYanit({ detail: "gecersiz" }, 401));
    vi.stubGlobal("fetch", taklit);

    await expect(apiIstegi("/api/missions/")).rejects.toBeInstanceOf(ApiHatasi);
    // Yalnızca ilk istek gitti; yenileme ucu HİÇ çağrılmadı.
    expect(taklit).toHaveBeenCalledTimes(1);
  });

  it("eşzamanlı 401'ler TEK yenileme isteği üretir", async () => {
    tokenDeposu.yaz("eski-erisim", "yenileme-xyz");

    let yenilemeSayisi = 0;
    const taklit = vi.fn(async (girdi: RequestInfo | URL) => {
      const yol = String(girdi);
      if (yol.includes("/auth/token/refresh/")) {
        yenilemeSayisi += 1;
        // Gerçekçi gecikme: yenileme anında dönmez, istekler üst üste biner.
        await new Promise((coz) => setTimeout(coz, 10));
        return jsonYanit({ access: "yeni-erisim" }, 200);
      }
      const erisim = tokenDeposu.erisimTokeni();
      if (erisim !== "yeni-erisim") {
        return jsonYanit({ detail: "token gecersiz" }, 401);
      }
      return jsonYanit({ tamam: true }, 200);
    });
    vi.stubGlobal("fetch", taklit);

    await Promise.all([
      apiIstegi("/api/missions/"),
      apiIstegi("/api/models/"),
      apiIstegi("/api/runs/9/"),
      apiIstegi("/api/missions/1/frames/"),
    ]);

    expect(yenilemeSayisi).toBe(1);
  });

  it("ağ hatası oturumu KAPATMAZ", async () => {
    tokenDeposu.yaz("erisim", "yenileme");
    const oturumDustuDinleyici = vi.fn();
    oturumDustugundeCalistir(oturumDustuDinleyici);

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(apiIstegi("/api/missions/")).rejects.toBeTruthy();
    expect(oturumDustuDinleyici).not.toHaveBeenCalled();
    expect(tokenDeposu.erisimTokeni()).toBe("erisim");
  });
});

describe("hata çevirisi", () => {
  it("DRF detail alanını kullanıcıya gösterilecek mesaja çevirir", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonYanit({ detail: "No active account found with the given credentials" }, 401),
      ),
    );

    await expect(
      apiIstegi("/api/auth/token/", { kimlikDogrulamasiz: true, yontem: "POST" }),
    ).rejects.toMatchObject({
      durumKodu: 401,
      message: "No active account found with the given credentials",
    });
  });

  it("alan bazlı doğrulama hatalarını toplar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonYanit({ name: ["This field may not be blank."] }, 400),
      ),
    );

    try {
      await apiIstegi("/api/missions/", { yontem: "POST", govde: { name: "" } });
      expect.unreachable("400 bekleniyordu");
    } catch (hata) {
      expect(hata).toBeInstanceOf(ApiHatasi);
      const apiHatasi = hata as ApiHatasi;
      expect(apiHatasi.durumKodu).toBe(400);
      expect(apiHatasi.alanHatalari.name).toEqual(["This field may not be blank."]);
      expect(apiHatasi.message).toContain("This field may not be blank.");
    }
  });

  it("gövdesi olmayan hatada genel Türkçe mesaj verir, ham JSON göstermez", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html>500</html>", { status: 500 })),
    );

    await expect(apiIstegi("/api/missions/")).rejects.toMatchObject({
      message: "Sunucuda beklenmeyen bir hata oluştu.",
    });
  });
});

describe("404 metni", () => {
  it("Django'nun İngilizce 404 gövdesi kullanıcıya gösterilmez", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonYanit({ detail: "No Mission matches the given query." }, 404),
      ),
    );

    await expect(apiIstegi("/api/missions/12/")).rejects.toMatchObject({
      durumKodu: 404,
      message: "Aradığınız kayıt bulunamadı.",
    });
  });

  it("404 mesajı kaydın varlığını ima etmez", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonYanit({ detail: "Gorev bulunamadi." }, 404)),
    );

    try {
      await apiIstegi("/api/missions/12/");
      expect.unreachable("404 bekleniyordu");
    } catch (hata) {
      const metin = (hata as Error).message;
      expect(metin).not.toMatch(/Mission|query|görev bulunamadı/i);
    }
  });
});
