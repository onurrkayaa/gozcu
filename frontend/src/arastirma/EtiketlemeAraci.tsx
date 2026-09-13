/**
 * Körlenmiş yanlış pozitif bağlam etiketleme aracı (yalnızca yerel araştırma).
 *
 * Ekranda adayın hangi modele ait olduğu, yanlış pozitif mi kontrol mü olduğu,
 * güven skoru ve kaynak öneki GÖSTERİLMEZ — bu bilgiler sunucudan da gelmez.
 * Etiketleyenin gördüğü tek kimlik, gruptan bağımsız verilmiş kör kimliktir.
 *
 * Her kayıt anında sunucuya yazılır; sayfa kapanıp açılsa bile ilk
 * etiketlenmemiş adaydan devam edilir.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

interface Oge {
  kor_kimlik: string;
  siki: string;
  baglam: string;
  mod: "ana" | "kalite";
}

interface Secenek { deger: string; etiket: string; tus: string; aciklama?: string }

interface Taksonomi {
  birincil: Secenek[];
  altKategoriler: Secenek[];
  guven: Secenek[];
  kisayollar: Record<string, string>;
}

type Etiket = Record<string, string>;

interface Durum {
  hazir: boolean;
  ogeler: Oge[];
  taksonomi: Taksonomi;
  etiketler: Record<string, Etiket>;
  sayim: { ana: number; kalite: number };
  ciktiDosyasi: string;
}

const BOS_TASLAK = {
  insan_faaliyeti: "",
  alt_kategori: "",
  guven: "yuksek",
  goruntu_yeterli: "evet",
  yeniden_incele: "hayir",
  not: "",
};

function anahtar(kimlik: string, mod: string) {
  return `${mod}:${kimlik}`;
}

export function EtiketlemeAraci() {
  const [durum, setDurum] = useState<Durum | null>(null);
  const [hata, setHata] = useState<string | null>(null);
  const [indeks, setIndeks] = useState(0);
  const [taslak, setTaslak] = useState({ ...BOS_TASLAK });
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const [bildirim, setBildirim] = useState<string | null>(null);
  const notAlani = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    let iptal = false;
    fetch("/arastirma-api/durum")
      .then((y) => y.json())
      .then((veri: Durum) => {
        if (iptal) return;
        setDurum(veri);
        // Kaldığı yerden devam: ilk etiketlenmemiş aday.
        const ilk = veri.ogeler.findIndex(
          (o) => !veri.etiketler[anahtar(o.kor_kimlik, o.mod)],
        );
        setIndeks(ilk === -1 ? Math.max(0, veri.ogeler.length - 1) : ilk);
      })
      .catch(() => !iptal && setHata("Etiketleme sunucusuna ulaşılamadı."));
    return () => { iptal = true; };
  }, []);

  const oge = durum?.ogeler[indeks] ?? null;
  const mevcutEtiket = oge && durum ? durum.etiketler[anahtar(oge.kor_kimlik, oge.mod)] : undefined;

  // Kalite turunda ÖNCEKİ CEVAP GÖSTERİLMEZ: yeniden-test ancak böyle anlamlı.
  const oncekiGoruntulenir = oge?.mod === "ana";

  useEffect(() => {
    if (!oge) return;
    if (oncekiGoruntulenir && mevcutEtiket) {
      setTaslak({
        insan_faaliyeti: mevcutEtiket.insan_faaliyeti ?? "",
        alt_kategori: mevcutEtiket.alt_kategori ?? "",
        guven: mevcutEtiket.guven ?? "yuksek",
        goruntu_yeterli: mevcutEtiket.goruntu_yeterli ?? "evet",
        yeniden_incele: mevcutEtiket.yeniden_incele ?? "hayir",
        not: mevcutEtiket.not ?? "",
      });
    } else {
      setTaslak({ ...BOS_TASLAK });
    }
  }, [oge, mevcutEtiket, oncekiGoruntulenir]);

  const ilerleme = useMemo(() => {
    if (!durum) return { etiketlenen: 0, toplam: 0, kalan: 0 };
    const toplam = durum.ogeler.length;
    const etiketlenen = durum.ogeler.filter(
      (o) => durum.etiketler[anahtar(o.kor_kimlik, o.mod)],
    ).length;
    return { etiketlenen, toplam, kalan: toplam - etiketlenen };
  }, [durum]);

  const kaydet = useCallback(
    async (veri: typeof BOS_TASLAK, ilerle: boolean) => {
      if (!oge || !durum) return;
      if (!veri.insan_faaliyeti || !veri.alt_kategori) {
        setBildirim("Önce insan faaliyeti ve alt kategori seçilmeli.");
        return;
      }
      setKaydediliyor(true);
      try {
        const yanit = await fetch("/arastirma-api/etiket", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ kor_kimlik: oge.kor_kimlik, mod: oge.mod, ...veri }),
        });
        const govde = await yanit.json();
        if (!yanit.ok) { setBildirim(govde.hata ?? "Kaydedilemedi."); return; }
        setDurum((eski) =>
          eski
            ? {
                ...eski,
                etiketler: {
                  ...eski.etiketler,
                  [anahtar(oge.kor_kimlik, oge.mod)]: { kor_kimlik: oge.kor_kimlik, mod: oge.mod, ...veri },
                },
              }
            : eski,
        );
        setBildirim(null);
        if (ilerle) setIndeks((i) => Math.min(i + 1, durum.ogeler.length - 1));
      } catch {
        setBildirim("Kaydedilemedi: sunucuya ulaşılamadı.");
      } finally {
        setKaydediliyor(false);
      }
    },
    [oge, durum],
  );

  useEffect(() => {
    function tusa(olay: KeyboardEvent) {
      if (!durum || !oge) return;
      const hedef = olay.target as HTMLElement | null;
      if (hedef && (hedef.tagName === "TEXTAREA" || hedef.tagName === "INPUT")) return;
      const tus = olay.key.toLowerCase();

      const birincil = durum.taksonomi.birincil.find((s) => s.tus === tus);
      if (birincil) {
        olay.preventDefault();
        setTaslak((t) => ({ ...t, insan_faaliyeti: birincil.deger }));
        return;
      }
      const alt = durum.taksonomi.altKategoriler.find((s) => s.tus === tus);
      if (alt) {
        olay.preventDefault();
        setTaslak((t) => {
          const yeni = { ...t, alt_kategori: alt.deger };
          // Alt kategori son adım: birincil seçiliyse kaydet ve ilerle.
          if (yeni.insan_faaliyeti) void kaydet(yeni, true);
          else setBildirim("Önce insan faaliyeti seçilmeli (v / y / b).");
          return yeni;
        });
        return;
      }
      const guven = durum.taksonomi.guven.find((s) => s.tus === tus);
      if (guven) {
        olay.preventDefault();
        setTaslak((t) => ({ ...t, guven: guven.deger }));
        return;
      }
      if (tus === "g") {
        olay.preventDefault();
        setTaslak((t) => ({ ...t, goruntu_yeterli: t.goruntu_yeterli === "evet" ? "hayir" : "evet" }));
      } else if (tus === "r") {
        olay.preventDefault();
        setTaslak((t) => ({ ...t, yeniden_incele: t.yeniden_incele === "evet" ? "hayir" : "evet" }));
      } else if (tus === "enter" || tus === " ") {
        olay.preventDefault();
        void kaydet(taslak, true);
      } else if (tus === "backspace") {
        olay.preventDefault();
        setIndeks((i) => Math.max(0, i - 1));
      } else if (tus === "k") {
        olay.preventDefault();
        setIndeks((i) => Math.min(i + 1, durum.ogeler.length - 1));
      }
    }
    window.addEventListener("keydown", tusa);
    return () => window.removeEventListener("keydown", tusa);
  }, [durum, oge, taslak, kaydet]);

  async function disaAktar() {
    const yanit = await fetch("/arastirma-api/disa-aktar", { method: "POST" });
    const govde = await yanit.json();
    setBildirim(
      `${govde.dosya} yazıldı: ${govde.yazilanKayit} kayıt` +
        (govde.eksikKayit ? ` — ${govde.eksikKayit} aday hâlâ etiketsiz.` : " — eksik kayıt yok."),
    );
  }

  if (hata) return <p className="arastirma-hata">{hata}</p>;
  if (!durum) return <p className="arastirma-bilgi">Yükleniyor…</p>;
  if (!durum.hazir || !oge) {
    return (
      <p className="arastirma-hata" data-testid="manifest-yok">
        Manifest bulunamadı. Önce <code>scripts/25_esit_fp_adaylari.py</code> ve{" "}
        <code>scripts/26_fp_kirpim_uret.py</code> çalıştırılmalı.
      </p>
    );
  }

  return (
    <div className="etiketleme">
      <header className="etiketleme-ust">
        <div>
          <span className="kor-kimlik" data-testid="kor-kimlik">{oge.kor_kimlik}</span>
          <span className="tur-rozeti">
            {oge.mod === "kalite" ? "kalite turu (yeniden-test)" : "ana tur"}
          </span>
        </div>
        <div className="ilerleme" data-testid="ilerleme">
          {indeks + 1} / {ilerleme.toplam} · etiketlenen {ilerleme.etiketlenen} · kalan{" "}
          {ilerleme.kalan}
        </div>
        <button type="button" onClick={() => void disaAktar()}>Dışa aktar</button>
      </header>

      <p className="arastirma-bilgi kucuk">
        Bu ekran körlenmiştir: adayın hangi modelden geldiği, yanlış pozitif mi
        kontrol bölgesi mi olduğu ve güven skoru gösterilmez.
      </p>

      {mevcutEtiket && oncekiGoruntulenir && (
        <p className="zaten-etiketli" data-testid="zaten-etiketli">
          Bu aday zaten etiketlendi. Yeni seçim eski kaydı değiştirir, ikinci bir
          kayıt eklemez.
        </p>
      )}

      <div className="kirpim-alani">
        <figure>
          <img src={`/arastirma-kirpim/${oge.siki}`} alt="Sıkı kırpım" data-testid="siki-kirpim" />
          <figcaption>Sıkı kırpım — bölgenin kendisi</figcaption>
        </figure>
        <figure>
          <img src={`/arastirma-kirpim/${oge.baglam}`} alt="Bağlam kırpımı" data-testid="baglam-kirpim" />
          <figcaption>Bağlam kırpımı — çevresi</figcaption>
        </figure>
      </div>

      <fieldset>
        <legend>İnsan faaliyeti</legend>
        {durum.taksonomi.birincil.map((s) => (
          <button
            key={s.deger}
            type="button"
            className={taslak.insan_faaliyeti === s.deger ? "secili" : ""}
            onClick={() => setTaslak((t) => ({ ...t, insan_faaliyeti: s.deger }))}
          >
            <kbd>{s.tus}</kbd> {s.etiket}
          </button>
        ))}
      </fieldset>

      <fieldset>
        <legend>Alt kategori (tek ve zorunlu)</legend>
        {durum.taksonomi.altKategoriler.map((s) => (
          <button
            key={s.deger}
            type="button"
            title={s.aciklama}
            className={taslak.alt_kategori === s.deger ? "secili" : ""}
            onClick={() =>
              setTaslak((t) => {
                const yeni = { ...t, alt_kategori: s.deger };
                if (yeni.insan_faaliyeti) void kaydet(yeni, true);
                return yeni;
              })
            }
          >
            <kbd>{s.tus}</kbd> {s.etiket}
          </button>
        ))}
      </fieldset>

      <fieldset>
        <legend>Güven</legend>
        {durum.taksonomi.guven.map((s) => (
          <button
            key={s.deger}
            type="button"
            className={taslak.guven === s.deger ? "secili" : ""}
            onClick={() => setTaslak((t) => ({ ...t, guven: s.deger }))}
          >
            <kbd>{s.tus}</kbd> {s.etiket}
          </button>
        ))}
        <label>
          <input
            type="checkbox"
            checked={taslak.goruntu_yeterli === "hayir"}
            onChange={(o) =>
              setTaslak((t) => ({ ...t, goruntu_yeterli: o.target.checked ? "hayir" : "evet" }))
            }
          />
          <kbd>g</kbd> Görüntü yetersiz
        </label>
        <label>
          <input
            type="checkbox"
            checked={taslak.yeniden_incele === "evet"}
            onChange={(o) =>
              setTaslak((t) => ({ ...t, yeniden_incele: o.target.checked ? "evet" : "hayir" }))
            }
          />
          <kbd>r</kbd> Yeniden incele
        </label>
      </fieldset>

      <textarea
        ref={notAlani}
        placeholder="Not (isteğe bağlı)"
        value={taslak.not}
        onChange={(o) => setTaslak((t) => ({ ...t, not: o.target.value }))}
      />

      <div className="etiketleme-alt">
        <button type="button" onClick={() => setIndeks((i) => Math.max(0, i - 1))}>
          <kbd>Backspace</kbd> Geri dön
        </button>
        <button type="button" disabled={kaydediliyor} onClick={() => void kaydet(taslak, true)}>
          <kbd>Enter</kbd> Kaydet ve ilerle
        </button>
        <button
          type="button"
          onClick={() => setIndeks((i) => Math.min(i + 1, durum.ogeler.length - 1))}
        >
          <kbd>k</kbd> Atla
        </button>
      </div>

      {bildirim && (
        <p className="arastirma-bildirim" role="status" data-testid="bildirim">{bildirim}</p>
      )}

      <p className="kucuk arastirma-bilgi">
        Kayıtlar anında <code>{durum.ciktiDosyasi}</code> dosyasına yazılır.
      </p>
    </div>
  );
}
