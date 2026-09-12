import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { hataMetni } from "../api/istemci";
import { useOturum } from "../kimlik/useOturum";

interface KonumDurumu {
  nereden?: string;
}

export function GirisSayfasi() {
  const { girisYap } = useOturum();
  const gezin = useNavigate();
  const konum = useLocation();

  const [kullaniciAdi, setKullaniciAdi] = useState("");
  const [parola, setParola] = useState("");
  const [hata, setHata] = useState<string | null>(null);
  const [gonderiliyor, setGonderiliyor] = useState(false);

  async function gonder(olay: React.FormEvent) {
    olay.preventDefault();
    // Çift gönderim koruması: istek uçarken ikinci gönderim başlamaz.
    if (gonderiliyor) return;

    setHata(null);
    setGonderiliyor(true);
    try {
      await girisYap(kullaniciAdi.trim(), parola);
      const nereden = (konum.state as KonumDurumu | null)?.nereden;
      gezin(nereden ?? "/gorevler", { replace: true });
    } catch (sebep) {
      setHata(hataMetni(sebep));
      setGonderiliyor(false);
    }
  }

  return (
    <div className="giris-duzeni">
      <div className="kart">
        <h1>Gözcü</h1>
        <p className="sonuk kucuk">Operatör arayüzüne giriş yapın.</p>

        <form onSubmit={gonder} noValidate>
          {hata && (
            <div className="bildirim hata" role="alert">
              {hata}
            </div>
          )}

          <div className="alan">
            <label htmlFor="kullaniciAdi">Kullanıcı adı</label>
            <input
              id="kullaniciAdi"
              name="username"
              type="text"
              autoComplete="username"
              value={kullaniciAdi}
              onChange={(olay) => setKullaniciAdi(olay.target.value)}
              required
            />
          </div>

          <div className="alan">
            <label htmlFor="parola">Parola</label>
            <input
              id="parola"
              name="password"
              type="password"
              autoComplete="current-password"
              value={parola}
              onChange={(olay) => setParola(olay.target.value)}
              required
            />
          </div>

          <button type="submit" className="birincil" disabled={gonderiliyor}>
            {gonderiliyor ? "Giriş yapılıyor…" : "Giriş yap"}
          </button>
        </form>
      </div>

      <p className="sonuk kucuk">
        Eğitim ve araştırma prototipidir. Tespitler operatör kararının yerine
        geçmez.
      </p>
    </div>
  );
}
