/**
 * Bir tespit için operatör kararı.
 *
 * Model çıktısı ile operatör yargısı görsel olarak AYRI durur: üstte modelin
 * ne bulduğu (güven skoru), altta insanın ne dediği. İkisi aynı kutuda
 * gösterilseydi kullanıcı modelin "karar verdiğini" sanardı.
 */

import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { hataMetni } from "../api/istemci";
import { sorguAnahtarlari } from "../api/sorguAnahtarlari";
import { incelemeYaz } from "../api/uclar";
import type { Inceleme, Karar, Rol, Tespit } from "../api/tipler";
import { yazabilirMi } from "../api/tipler";

const KARAR_ETIKETLERI: Record<Karar, string> = {
  accepted: "Doğrulandı",
  rejected: "Reddedildi",
  uncertain: "Belirsiz",
};

const KARAR_SIRASI: Karar[] = ["accepted", "uncertain", "rejected"];

interface Ozellikler {
  kosuId: number;
  tespit: Tespit;
  incelemeler: Inceleme[];
  rol: Rol | null;
  kullaniciAdi: string | null;
}

export function IncelemePaneli({
  kosuId,
  tespit,
  incelemeler,
  rol,
  kullaniciAdi,
}: Ozellikler) {
  const sorguIstemcisi = useQueryClient();
  const kendiIncelemesi =
    incelemeler.find((i) => i.reviewer.username === kullaniciAdi) ?? null;

  const [karar, setKarar] = useState<Karar | null>(kendiIncelemesi?.decision ?? null);
  const [not, setNot] = useState(kendiIncelemesi?.note ?? "");

  // Tespit değişince form o tespitin kendi kararını göstermeli.
  useEffect(() => {
    setKarar(kendiIncelemesi?.decision ?? null);
    setNot(kendiIncelemesi?.note ?? "");
  }, [tespit.id, kendiIncelemesi?.decision, kendiIncelemesi?.note]);

  const kaydet = useMutation({
    mutationFn: (secilen: Karar) => incelemeYaz(tespit.id, secilen, not),
    onSuccess: () => {
      sorguIstemcisi.invalidateQueries({ queryKey: sorguAnahtarlari.incelemeler(kosuId) });
    },
  });

  const yazabilir = yazabilirMi(rol);

  return (
    <div className="operator-karari">
      <h3>Operatör kararı</h3>

      {!yazabilir && (
        <p className="salt-okunur-notu" data-testid="inceleme-salt-okunur">
          Bu görevde salt okunur yetkiniz var; karar yazamazsınız.
        </p>
      )}

      {kaydet.isError && (
        <div className="bildirim hata" role="alert">
          {hataMetni(kaydet.error)}
        </div>
      )}

      {yazabilir && (
        <>
          <div className="karar-serisi" role="group" aria-label="Tespit kararı">
            {KARAR_SIRASI.map((secenek) => (
              <button
                key={secenek}
                type="button"
                className={`karar-dugmesi${karar === secenek ? " secili" : ""}`}
                data-karar={secenek}
                aria-pressed={karar === secenek}
                disabled={kaydet.isPending}
                onClick={() => {
                  // Çift gönderim koruması: istek uçarken ikincisi başlamaz.
                  if (kaydet.isPending) return;
                  setKarar(secenek);
                  kaydet.mutate(secenek);
                }}
              >
                {KARAR_ETIKETLERI[secenek]}
              </button>
            ))}
          </div>

          <div className="alan" style={{ marginTop: "0.6rem" }}>
            <label htmlFor="incelemeNotu">Not (isteğe bağlı)</label>
            <textarea
              id="incelemeNotu"
              value={not}
              maxLength={2000}
              onChange={(olay) => setNot(olay.target.value)}
              onBlur={() => {
                // Not değiştiyse ve karar zaten verilmişse kaydı güncelle.
                if (karar && not !== (kendiIncelemesi?.note ?? "")) {
                  kaydet.mutate(karar);
                }
              }}
            />
          </div>
        </>
      )}

      {incelemeler.length > 0 ? (
        <div style={{ marginTop: "0.6rem" }}>
          <h4 className="kucuk sonuk">Bu tespit için kararlar</h4>
          <ul className="dosya-listesi" data-testid="inceleme-listesi">
            {incelemeler.map((inceleme) => (
              <li key={inceleme.id}>
                <span>{inceleme.reviewer.username}</span>
                <span>{KARAR_ETIKETLERI[inceleme.decision]}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="kucuk sonuk" style={{ marginTop: "0.6rem" }}>
          Bu tespit için henüz operatör kararı yok.
        </p>
      )}
    </div>
  );
}
