/**
 * Oturum durumu.
 *
 * Sayfa yeniden yüklendiğinde token localStorage'dan okunur; oturum sürer.
 * Token gerçekten geçersizse ilk korumalı istek 401 alır, istemci katmanı bir
 * kez yenilemeyi dener ve başarısız olursa oturumu kapatır.
 */

import { createContext, useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { oturumDustugundeCalistir } from "../api/istemci";
import { girisYap as girisIstegi } from "../api/uclar";
import { tokenDeposu } from "./tokenDeposu";

export interface OturumDurumu {
  girisYapildiMi: boolean;
  kullaniciAdi: string | null;
  girisYap: (kullaniciAdi: string, parola: string) => Promise<void>;
  cikisYap: () => void;
}

export const OturumBaglami = createContext<OturumDurumu | null>(null);

const KULLANICI_ADI_ANAHTARI = "gozcu.kullaniciAdi";

function kayitliKullaniciAdi(): string | null {
  try {
    return window.localStorage.getItem(KULLANICI_ADI_ANAHTARI);
  } catch {
    return null;
  }
}

/** Oturuma ait ne varsa siler. Elle çıkış ile zorunlu çıkış AYNI temizliği
 *  yapmalı; aksi halde biri diğerinden artık bırakır. */
function oturumIzleriniSil(): void {
  tokenDeposu.temizle();
  try {
    window.localStorage.removeItem(KULLANICI_ADI_ANAHTARI);
  } catch {
    // Yazılamıyorsa bile bellek durumu temizlenir.
  }
}

export function OturumSaglayici({ children }: { children: ReactNode }) {
  const sorguIstemcisi = useQueryClient();
  const [girisYapildiMi, setGirisYapildiMi] = useState(
    () => tokenDeposu.erisimTokeni() !== null,
  );
  const [kullaniciAdi, setKullaniciAdi] = useState<string | null>(kayitliKullaniciAdi);

  const cikisYap = useCallback(() => {
    oturumIzleriniSil();
    setGirisYapildiMi(false);
    setKullaniciAdi(null);
    // Önbellekte önceki kullanıcının verisi kalmasın.
    sorguIstemcisi.clear();
  }, [sorguIstemcisi]);

  // Token yenilemesi başarısız olduğunda istemci katmanı burayı tetikler.
  useEffect(() => {
    oturumDustugundeCalistir(() => {
      // Zorunlu çıkış da elle çıkışla aynı temizliği yapar.
      oturumIzleriniSil();
      setGirisYapildiMi(false);
      setKullaniciAdi(null);
      sorguIstemcisi.clear();
    });
    return () => oturumDustugundeCalistir(null);
  }, [sorguIstemcisi]);

  const girisYap = useCallback(
    async (ad: string, parola: string) => {
      const tokenlar = await girisIstegi(ad, parola);
      tokenDeposu.yaz(tokenlar.access, tokenlar.refresh);
      try {
        window.localStorage.setItem(KULLANICI_ADI_ANAHTARI, ad);
      } catch {
        // Kullanıcı adı yalnızca gösterim içindir; yazılamazsa oturum yine açılır.
      }
      setKullaniciAdi(ad);
      setGirisYapildiMi(true);
    },
    [],
  );

  const deger = useMemo<OturumDurumu>(
    () => ({ girisYapildiMi, kullaniciAdi, girisYap, cikisYap }),
    [girisYapildiMi, kullaniciAdi, girisYap, cikisYap],
  );

  return <OturumBaglami.Provider value={deger}>{children}</OturumBaglami.Provider>;
}
