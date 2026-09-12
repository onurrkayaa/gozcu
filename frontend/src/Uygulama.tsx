import { Link, Navigate, Route, Routes, useNavigate } from "react-router-dom";

import { KorumaliRota } from "./kimlik/KorumaliRota";
import { useOturum } from "./kimlik/useOturum";
import { GirisSayfasi } from "./sayfalar/GirisSayfasi";
import { GorevAyrintiSayfasi } from "./sayfalar/GorevAyrintiSayfasi";
import { GorevListesiSayfasi } from "./sayfalar/GorevListesiSayfasi";
import { TespitIncelemeSayfasi } from "./sayfalar/TespitIncelemeSayfasi";

/**
 * Kapsam ifadesi. Her sayfada, içeriğin üstünde durur -- kaydırmadan görünür
 * ve kapatılamaz. Prototip olduğu ve operatör kararının yerine geçmediği
 * gizlenmemeli.
 */
export const KAPSAM_IFADESI =
  "Eğitim ve araştırma prototipidir. Tespitler operatör kararının yerine geçmez.";

function Kabuk({ children }: { children: React.ReactNode }) {
  const { girisYapildiMi, kullaniciAdi, cikisYap } = useOturum();
  const gezin = useNavigate();

  return (
    <div className="kabuk">
      <header className="ust-serit">
        <Link className="marka" to="/gorevler">
          Gözcü
        </Link>
        <span className="bosluk" />
        {girisYapildiMi && (
          <>
            {kullaniciAdi && <span className="kullanici">{kullaniciAdi}</span>}
            <button
              type="button"
              onClick={() => {
                cikisYap();
                gezin("/giris", { replace: true });
              }}
            >
              Çıkış yap
            </button>
          </>
        )}
      </header>

      <p className="kapsam-uyarisi" role="note">
        {KAPSAM_IFADESI}
      </p>

      <main className="icerik">{children}</main>

      <footer className="alt-bilgi">
        Gözcü · insansız hava aracı görüntülerinde insan adayı arama prototipi
      </footer>
    </div>
  );
}

export function Uygulama() {
  return (
    <Kabuk>
      <Routes>
        <Route path="/giris" element={<GirisSayfasi />} />
        <Route
          path="/gorevler"
          element={
            <KorumaliRota>
              <GorevListesiSayfasi />
            </KorumaliRota>
          }
        />
        <Route
          path="/gorevler/:gorevId"
          element={
            <KorumaliRota>
              <GorevAyrintiSayfasi />
            </KorumaliRota>
          }
        />
        <Route
          path="/kosular/:kosuId"
          element={
            <KorumaliRota>
              <TespitIncelemeSayfasi />
            </KorumaliRota>
          }
        />
        <Route path="/" element={<Navigate to="/gorevler" replace />} />
        <Route
          path="*"
          element={<div className="bildirim bos">Sayfa bulunamadı.</div>}
        />
      </Routes>
    </Kabuk>
  );
}
