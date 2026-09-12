/**
 * Kare ekleme: dosya başına sonuç, kısmi hata, tekrar yükleme (duplicate).
 *
 * Backend tek istekte bir dosya bozuksa TÜM isteği 400 ile reddediyor; arayüz
 * bu yüzden dosyaları tek tek gönderir. Buradaki testler kısmi başarının
 * korunduğunu doğrular.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { KareEkleme } from "./KareEkleme";
import { sar } from "../test/yardimcilar";

afterEach(() => vi.unstubAllGlobals());

function goruntuDosyasi(ad: string, tur = "image/jpeg", boyut = 1024): File {
  const dosya = new File([new Uint8Array(boyut)], ad, { type: tur });
  return dosya;
}

describe("kare ekleme", () => {
  it("her dosya AYRI istekle gönderilir ve tek tek sonuç gösterilir", async () => {
    const kullanici = userEvent.setup();
    let yuklemeSayisi = 0;

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        yuklemeSayisi += 1;
        return new Response(
          JSON.stringify([
            { id: yuklemeSayisi, filename: `k${yuklemeSayisi}.jpg`, duplicate: false, width: 4000, height: 3000 },
          ]),
          { status: 201, headers: { "Content-Type": "application/json" } },
        );
      }),
    );

    sar(<KareEkleme gorevId={1} />);

    await kullanici.upload(screen.getByLabelText("Görüntü dosyaları"), [
      goruntuDosyasi("bir.jpg"),
      goruntuDosyasi("iki.jpg"),
    ]);
    await kullanici.click(screen.getByRole("button", { name: /Seçilenleri yükle/ }));

    expect(await screen.findByText("2 dosya işlendi.")).toBeInTheDocument();
    expect(yuklemeSayisi).toBe(2);
  });

  it("kısmi hata: bir dosya düşse bile diğerleri yüklenir ve ikisi de rapor edilir", async () => {
    const kullanici = userEvent.setup();

    vi.stubGlobal(
      "fetch",
      vi.fn(async (_girdi: RequestInfo | URL, secenekler?: RequestInit) => {
        const form = secenekler?.body as FormData;
        const dosya = form.get("images") as File;
        if (dosya.name === "bozuk.jpg") {
          return new Response(
            JSON.stringify({ images: "bozuk.jpg: Dosya gecerli bir goruntu degil." }),
            { status: 400, headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(
          JSON.stringify([{ id: 1, filename: dosya.name, duplicate: false, width: 4000, height: 3000 }]),
          { status: 201, headers: { "Content-Type": "application/json" } },
        );
      }),
    );

    sar(<KareEkleme gorevId={1} />);

    await kullanici.upload(screen.getByLabelText("Görüntü dosyaları"), [
      goruntuDosyasi("saglam.jpg"),
      goruntuDosyasi("bozuk.jpg"),
    ]);
    await kullanici.click(screen.getByRole("button", { name: /Seçilenleri yükle/ }));

    expect(
      await screen.findByText("1 dosya işlendi, 1 dosya eklenemedi."),
    ).toBeInTheDocument();
    expect(screen.getByText("Yüklendi")).toBeInTheDocument();
    expect(
      screen.getByText(/bozuk.jpg: Dosya gecerli bir goruntu degil./),
    ).toBeInTheDocument();
  });

  it("aynı dosya tekrar eklenirse UniqueConstraint davranışı anlaşılır gösterilir", async () => {
    const kullanici = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify([
              { id: 7, filename: "ayni.jpg", duplicate: true, width: 4000, height: 3000 },
            ]),
            { status: 201, headers: { "Content-Type": "application/json" } },
          ),
      ),
    );

    sar(<KareEkleme gorevId={1} />);

    await kullanici.upload(screen.getByLabelText("Görüntü dosyaları"), [
      goruntuDosyasi("ayni.jpg"),
    ]);
    await kullanici.click(screen.getByRole("button", { name: /Seçilenleri yükle/ }));

    expect(await screen.findByText("Zaten ekliydi")).toBeInTheDocument();
  });

  it("desteklenmeyen tür sunucuya hiç gönderilmez", async () => {
    // applyAccept: false -- userEvent normalde input'un accept süzgecini
    // uygular ve dosyayı hiç eklemez. Burada arayüzün KENDİ doğrulaması
    // sınandığı için süzgeç kapatılır.
    const kullanici = userEvent.setup({ applyAccept: false });
    const taklit = vi.fn();
    vi.stubGlobal("fetch", taklit);

    sar(<KareEkleme gorevId={1} />);

    await kullanici.upload(screen.getByLabelText("Görüntü dosyaları"), [
      goruntuDosyasi("notlar.txt", "text/plain"),
    ]);
    await kullanici.click(screen.getByRole("button", { name: /Seçilenleri yükle/ }));

    expect(await screen.findByText(/Desteklenmeyen dosya türü/)).toBeInTheDocument();
    expect(taklit).not.toHaveBeenCalled();
  });

  it("dosya seçilmeden yükleme düğmesi kapalıdır", () => {
    sar(<KareEkleme gorevId={1} />);
    expect(screen.getByRole("button", { name: /Seçilenleri yükle/ })).toBeDisabled();
  });
});
