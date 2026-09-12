import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { hataMetni } from "../api/istemci";
import { sorguAnahtarlari } from "../api/sorguAnahtarlari";
import { gorevleriGetir, gorevOlustur } from "../api/uclar";
import type { Gorev } from "../api/tipler";
import {
  BosDurum,
  HataDurumu,
  KosuDurumRozeti,
  Yukleniyor,
  zamanMetni,
} from "../bilesenler/durumlar";

function GorevSatiri({ gorev }: { gorev: Gorev }) {
  const sayimlar = gorev.frame_counts;
  return (
    <tr>
      <td>
        <Link to={`/gorevler/${gorev.id}`}>{gorev.name}</Link>
        {gorev.description && (
          <div className="sonuk kucuk">{gorev.description}</div>
        )}
      </td>
      <td>{gorev.frame_count}</td>
      <td className="tek-aralik kucuk">
        {sayimlar.done} tamam · {sayimlar.processing + sayimlar.queued} işlemde ·{" "}
        {sayimlar.failed} başarısız
      </td>
      <td>
        {gorev.latest_run ? (
          <KosuDurumRozeti durum={gorev.latest_run.status} />
        ) : (
          <span className="sonuk kucuk">Tarama yapılmadı</span>
        )}
      </td>
      <td className="kucuk">
        {gorev.latest_run ? gorev.latest_run.model_version_name : "—"}
      </td>
      <td className="kucuk sonuk">{zamanMetni(gorev.created_at)}</td>
    </tr>
  );
}

function YeniGorevFormu({ kapat }: { kapat: () => void }) {
  const gezin = useNavigate();
  const sorguIstemcisi = useQueryClient();
  const [ad, setAd] = useState("");
  const [aciklama, setAciklama] = useState("");

  const olusturma = useMutation({
    mutationFn: () => gorevOlustur(ad.trim(), aciklama.trim()),
    onSuccess: (gorev) => {
      sorguIstemcisi.invalidateQueries({ queryKey: sorguAnahtarlari.gorevler });
      gezin(`/gorevler/${gorev.id}`);
    },
  });

  const adGecerli = ad.trim().length > 0;

  return (
    <div className="kart">
      <h2>Yeni görev</h2>
      <form
        onSubmit={(olay) => {
          olay.preventDefault();
          // Çift gönderim koruması: mutation uçarken ikincisi başlamaz.
          if (!adGecerli || olusturma.isPending) return;
          olusturma.mutate();
        }}
        noValidate
      >
        {olusturma.isError && (
          <div className="bildirim hata" role="alert">
            {hataMetni(olusturma.error)}
          </div>
        )}

        <div className="alan">
          <label htmlFor="gorevAdi">Görev adı</label>
          <input
            id="gorevAdi"
            type="text"
            value={ad}
            maxLength={200}
            onChange={(olay) => setAd(olay.target.value)}
            aria-describedby="gorevAdiYardim"
            required
          />
          <div id="gorevAdiYardim" className="yardim-metni">
            Zorunlu. En fazla 200 karakter.
          </div>
        </div>

        <div className="alan">
          <label htmlFor="gorevAciklamasi">Açıklama</label>
          <textarea
            id="gorevAciklamasi"
            value={aciklama}
            onChange={(olay) => setAciklama(olay.target.value)}
          />
        </div>

        <div className="satir">
          <button
            type="submit"
            className="birincil"
            disabled={!adGecerli || olusturma.isPending}
          >
            {olusturma.isPending ? "Oluşturuluyor…" : "Görevi oluştur"}
          </button>
          <button type="button" onClick={kapat} disabled={olusturma.isPending}>
            Vazgeç
          </button>
        </div>
      </form>
    </div>
  );
}

export function GorevListesiSayfasi() {
  const [formAcik, setFormAcik] = useState(false);
  const [sayfa, setSayfa] = useState(1);

  const sorgu = useQuery({
    queryKey: sorguAnahtarlari.gorevListesi(sayfa),
    queryFn: () => gorevleriGetir(sayfa),
  });

  return (
    <div>
      <div className="satir aralikli" style={{ marginBottom: "1rem" }}>
        <h1>Görevler</h1>
        {!formAcik && (
          <button type="button" className="birincil" onClick={() => setFormAcik(true)}>
            Yeni görev
          </button>
        )}
      </div>

      {formAcik && <YeniGorevFormu kapat={() => setFormAcik(false)} />}

      {sorgu.isPending && <Yukleniyor metin="Görevler yükleniyor…" />}

      {sorgu.isError && (
        <HataDurumu mesaj={hataMetni(sorgu.error)} yenidenDene={() => sorgu.refetch()} />
      )}

      {sorgu.isSuccess && sorgu.data.results.length === 0 && (
        <BosDurum metin="Henüz görev yok. 'Yeni görev' ile ilk görevi oluşturun." />
      )}

      {sorgu.isSuccess && sorgu.data.results.length > 0 && (
        <div className="kart">
          <div className="tablo-sarmal">
            <table>
              <caption className="gorsel-gizli">
                Görev listesi: ad, kare sayısı, kare durumları, son tarama durumu
                ve kullanılan model
              </caption>
              <thead>
                <tr>
                  <th scope="col">Görev</th>
                  <th scope="col">Kare</th>
                  <th scope="col">Kare durumu</th>
                  <th scope="col">Son tarama</th>
                  <th scope="col">Model</th>
                  <th scope="col">Oluşturulma</th>
                </tr>
              </thead>
              <tbody>
                {sorgu.data.results.map((gorev) => (
                  <GorevSatiri key={gorev.id} gorev={gorev} />
                ))}
              </tbody>
            </table>
          </div>

          {(sorgu.data.next || sorgu.data.previous) && (
            <div className="satir" style={{ marginTop: "0.8rem" }}>
              <button
                type="button"
                disabled={!sorgu.data.previous}
                onClick={() => setSayfa((s) => Math.max(1, s - 1))}
              >
                Önceki
              </button>
              <span className="kucuk sonuk">
                Sayfa {sayfa} · toplam {sorgu.data.count} görev
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
      )}
    </div>
  );
}
