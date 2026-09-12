/**
 * Görev faaliyet geçmişi — SALT OKUNUR.
 *
 * Ham JSON kullanıcıya dökülmez: değişiklik özeti okunabilir satırlara
 * çevrilir. Backend zaten hassas anahtarları kayda yazmıyor, ama arayüz de
 * gelen sözlüğü olduğu gibi basmıyor; iki katman birbirini yedekliyor.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { hataMetni } from "../api/istemci";
import { sorguAnahtarlari } from "../api/sorguAnahtarlari";
import { denetimKayitlariniGetir } from "../api/uclar";
import type { DenetimKaydi } from "../api/tipler";
import { BosDurum, HataDurumu, Yukleniyor, zamanMetni } from "../bilesenler/durumlar";

/** Değişiklik sözlüğünü okunabilir tek satırlara çevirir. */
function degisiklikSatirlari(kayit: DenetimKaydi): string[] {
  const satirlar: string[] = [];
  for (const [alan, deger] of Object.entries(kayit.changes ?? {})) {
    if (deger !== null && typeof deger === "object" && "onceki" in deger) {
      const cift = deger as { onceki?: unknown; sonraki?: unknown };
      satirlar.push(
        `${alan}: ${String(cift.onceki ?? "—")} → ${String(cift.sonraki ?? "—")}`,
      );
    } else {
      satirlar.push(`${alan}: ${String(deger)}`);
    }
  }
  return satirlar;
}

export function DenetimGecmisi({ gorevId }: { gorevId: number }) {
  const [sayfa, setSayfa] = useState(1);

  const sorgu = useQuery({
    queryKey: sorguAnahtarlari.denetim(gorevId, sayfa),
    queryFn: () => denetimKayitlariniGetir(gorevId, sayfa),
  });

  const kayitlar = sorgu.data?.results ?? [];

  return (
    <div className="kart">
      <div className="kart-basligi">
        <h2>Faaliyet geçmişi</h2>
        <span className="sonuk kucuk">Salt okunur; bu kayıtlar değiştirilemez.</span>
      </div>

      {sorgu.isPending && <Yukleniyor metin="Geçmiş yükleniyor…" />}
      {sorgu.isError && (
        <HataDurumu mesaj={hataMetni(sorgu.error)} yenidenDene={() => sorgu.refetch()} />
      )}
      {sorgu.isSuccess && kayitlar.length === 0 && (
        <BosDurum metin="Bu görevde henüz kayıtlı işlem yok." />
      )}

      {kayitlar.length > 0 && (
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }} data-testid="denetim-listesi">
          {kayitlar.map((kayit) => (
            <li key={kayit.id} className="denetim-satiri">
              <div className="satir aralikli">
                <span>
                  <strong>{kayit.action_display}</strong>{" "}
                  <span className="sonuk kucuk">
                    · {kayit.object_type}
                    {kayit.object_id && ` #${kayit.object_id}`}
                  </span>
                </span>
                <span className="kucuk sonuk">{zamanMetni(kayit.created_at)}</span>
              </div>
              <div className="kucuk sonuk">
                {kayit.actor ? kayit.actor.username : "sistem"}
              </div>
              {degisiklikSatirlari(kayit).map((satir) => (
                <div key={satir} className="denetim-degisiklik tek-aralik">
                  {satir}
                </div>
              ))}
            </li>
          ))}
        </ul>
      )}

      {sorgu.data && (sorgu.data.next || sorgu.data.previous) && (
        <div className="satir" style={{ marginTop: "0.8rem" }}>
          <button
            type="button"
            disabled={!sorgu.data.previous}
            onClick={() => setSayfa((s) => Math.max(1, s - 1))}
          >
            Önceki
          </button>
          <span className="kucuk sonuk">
            Sayfa {sayfa} · toplam {sorgu.data.count} kayıt
          </span>
          <button
            type="button"
            disabled={!sorgu.data.next}
            onClick={() => setSayfa((s) => s + 1)}
          >
            Sonraki
          </button>
        </div>
      )}
    </div>
  );
}
