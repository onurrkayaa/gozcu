/**
 * Kare görüntüsü + tespit kutuları.
 *
 * Görüntü, kimlik doğrulamalı uçtan blob olarak indirilir ve nesne URL'si
 * olarak bağlanır; token URL'ye konmaz. Bileşen kaldırıldığında hem istek
 * iptal edilir hem de nesne URL'si serbest bırakılır -- aksi halde her kare
 * değişiminde bellekte bir kopya kalır.
 */

import { useEffect, useRef, useState } from "react";

import { kareGoruntusunuGetir } from "../api/uclar";
import { hataMetni } from "../api/istemci";
import type { Kare, Tespit } from "../api/tipler";
import { kutuYerlesimi } from "./kutuGeometrisi";
import { HataDurumu, Yukleniyor } from "./durumlar";

interface Ozellikler {
  kare: Kare;
  tespitler: Tespit[];
  seciliTespitId: number | null;
  tespitSecildi: (tespitId: number) => void;
}

export function TespitKatmani({ kare, tespitler, seciliTespitId, tespitSecildi }: Ozellikler) {
  const [goruntuAdresi, setGoruntuAdresi] = useState<string | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [yukleniyor, setYukleniyor] = useState(true);
  // Yeniden denemede etkiyi tekrar tetiklemek için sayaç.
  const [deneme, setDeneme] = useState(0);
  const nesneAdresiRef = useRef<string | null>(null);

  useEffect(() => {
    const iptalDenetleyici = new AbortController();
    let gecerli = true;

    setYukleniyor(true);
    setHata(null);

    kareGoruntusunuGetir(kare.id, iptalDenetleyici.signal)
      .then((blob) => {
        if (!gecerli) return;
        const adres = URL.createObjectURL(blob);
        nesneAdresiRef.current = adres;
        setGoruntuAdresi(adres);
        setYukleniyor(false);
      })
      .catch((sebep) => {
        if (!gecerli || iptalDenetleyici.signal.aborted) return;
        setHata(hataMetni(sebep));
        setYukleniyor(false);
      });

    return () => {
      gecerli = false;
      iptalDenetleyici.abort();
      if (nesneAdresiRef.current) {
        URL.revokeObjectURL(nesneAdresiRef.current);
        nesneAdresiRef.current = null;
      }
      setGoruntuAdresi(null);
    };
  }, [kare.id, deneme]);

  if (yukleniyor) return <Yukleniyor metin="Görüntü yükleniyor…" />;
  if (hata) {
    return <HataDurumu mesaj={hata} yenidenDene={() => setDeneme((d) => d + 1)} />;
  }
  if (!goruntuAdresi) return null;

  return (
    <div
      className="goruntu-katmani"
      /* En-boy oranı sarmalayıcıda da sabitlenir: görüntü yüklenirken kutular
         kaymasın ve düzen zıplamasın. */
      style={{ aspectRatio: `${kare.width} / ${kare.height}` }}
      data-testid="goruntu-katmani"
    >
      <img src={goruntuAdresi} alt={`${kare.original_filename} karesi`} />

      {tespitler.map((tespit) => {
        const yerlesim = kutuYerlesimi(tespit, kare.width, kare.height);
        if (!yerlesim) return null;
        const secili = tespit.id === seciliTespitId;
        return (
          <button
            key={tespit.id}
            type="button"
            className={`tespit-kutusu${secili ? " secili" : ""}`}
            data-testid={`tespit-kutusu-${tespit.id}`}
            aria-pressed={secili}
            aria-label={`İnsan adayı, güven ${tespit.score.toFixed(2)}`}
            onClick={() => tespitSecildi(tespit.id)}
            style={{
              left: `${yerlesim.solYuzde}%`,
              top: `${yerlesim.ustYuzde}%`,
              width: `${yerlesim.genislikYuzde}%`,
              height: `${yerlesim.yukseklikYuzde}%`,
            }}
          />
        );
      })}
    </div>
  );
}
