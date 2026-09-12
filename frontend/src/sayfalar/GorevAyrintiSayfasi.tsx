import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { hataMetni } from "../api/istemci";
import { sorguAnahtarlari } from "../api/sorguAnahtarlari";
import { gorevGetir, kareleriGetir, kosulariGetir, kosuGetir } from "../api/uclar";
import { kosuTerminalMi } from "../api/tipler";
import type { Kosu } from "../api/tipler";
import {
  BosDurum,
  HataDurumu,
  KareDurumRozeti,
  KosuDurumRozeti,
  Yukleniyor,
  zamanMetni,
} from "../bilesenler/durumlar";
import { KareEkleme } from "./KareEkleme";
import { TaramaBaslatma } from "./TaramaBaslatma";

/** Aktif koşu sürerken yoklama aralığı. */
const YOKLAMA_ARALIGI_MS = 2000;

function KosuIlerlemesi({ kosu }: { kosu: Kosu }) {
  const toplam = kosu.frames_total;
  const sonuclanan = kosu.frames_done + kosu.frames_failed;
  // İlerleme GERÇEK kare sayılarından hesaplanır, tahmin edilmez.
  const yuzde = toplam > 0 ? Math.min(100, (sonuclanan / toplam) * 100) : 0;

  return (
    <div className="kart">
      <div className="kart-basligi">
        <h2>Tarama durumu</h2>
        <KosuDurumRozeti durum={kosu.status} />
        <span className="sonuk kucuk">
          {kosu.model_version_name} · başlangıç {zamanMetni(kosu.started_at)}
          {kosu.finished_at && <> · bitiş {zamanMetni(kosu.finished_at)}</>}
        </span>
      </div>

      <div
        className="ilerleme-cubugu"
        role="progressbar"
        aria-valuenow={sonuclanan}
        aria-valuemin={0}
        aria-valuemax={toplam}
        aria-label="Tarama ilerlemesi"
      >
        <div style={{ width: `${yuzde}%` }} />
      </div>
      <div className="kucuk sonuk" style={{ marginTop: "0.35rem" }}>
        {toplam} karenin {sonuclanan} tanesi sonuçlandı.
      </div>

      <div className="sayim-kutulari">
        <div className="sayim-kutusu">
          <span className="deger">{kosu.frames_total}</span>
          <span className="etiket">Toplam kare</span>
        </div>
        <div className="sayim-kutusu">
          <span className="deger">{kosu.frames_done}</span>
          <span className="etiket">Tamamlanan</span>
        </div>
        <div className="sayim-kutusu">
          <span className="deger">{kosu.frames_failed}</span>
          <span className="etiket">Başarısız</span>
        </div>
      </div>

      {kosu.status === "done" && kosu.frames_failed > 0 && (
        <div className="bildirim" style={{ marginTop: "0.8rem" }}>
          Tarama tamamlandı, ancak {kosu.frames_failed} kare işlenemedi.
          Tamamlanan karelerin sonuçları kullanılabilir.
        </div>
      )}

      {kosuTerminalMi(kosu.status) && (
        <div style={{ marginTop: "0.9rem" }}>
          <Link to={`/kosular/${kosu.id}`}>
            <button type="button" className="birincil">
              Tespitleri incele
            </button>
          </Link>
        </div>
      )}
    </div>
  );
}

export function GorevAyrintiSayfasi() {
  const { gorevId: hamGorevId } = useParams();
  const gorevId = Number(hamGorevId);
  const sorguIstemcisi = useQueryClient();
  const [izlenenKosuId, setIzlenenKosuId] = useState<number | null>(null);

  const gorevSorgusu = useQuery({
    queryKey: sorguAnahtarlari.gorev(gorevId),
    queryFn: () => gorevGetir(gorevId),
    enabled: Number.isFinite(gorevId),
  });

  // Koşu listesi, sayfa yeniden yüklendiğinde aktif/son koşuyu bulmayı sağlar:
  // run_id yalnızca bellekte tutulsaydı yenilemede kaybolurdu.
  const kosuListesi = useQuery({
    queryKey: sorguAnahtarlari.kosular(gorevId),
    queryFn: () => kosulariGetir(gorevId),
    enabled: Number.isFinite(gorevId),
  });

  const sonKosu = kosuListesi.data?.results[0] ?? null;
  const etkinKosuId = izlenenKosuId ?? sonKosu?.id ?? null;

  const kosuSorgusu = useQuery({
    queryKey: sorguAnahtarlari.kosu(etkinKosuId ?? -1),
    queryFn: () => kosuGetir(etkinKosuId as number),
    enabled: etkinKosuId !== null,
    // Yoklama YALNIZCA koşu terminal olmadığında sürer; done/failed olunca
    // false döner ve TanStack Query zamanlayıcıyı durdurur.
    refetchInterval: (sorgu) => {
      const veri = sorgu.state.data;
      if (!veri) return YOKLAMA_ARALIGI_MS;
      return kosuTerminalMi(veri.status) ? false : YOKLAMA_ARALIGI_MS;
    },
  });

  const kosu = kosuSorgusu.data ?? sonKosu ?? null;
  const taramaSuruyor = kosu !== null && !kosuTerminalMi(kosu.status);

  const kareSorgusu = useQuery({
    queryKey: sorguAnahtarlari.kareler(gorevId, 1),
    queryFn: () => kareleriGetir(gorevId, 1),
    enabled: Number.isFinite(gorevId),
    // Kare durumları tarama sürerken değişir; yalnızca o sırada yoklanır.
    refetchInterval: taramaSuruyor ? YOKLAMA_ARALIGI_MS : false,
  });

  // Koşu terminal hale gelince görev özeti (kare sayımları, son koşu) bayat
  // kalmasın.
  const kosuDurumu = kosu?.status;
  useEffect(() => {
    if (kosuDurumu && kosuTerminalMi(kosuDurumu)) {
      sorguIstemcisi.invalidateQueries({ queryKey: sorguAnahtarlari.gorev(gorevId) });
      sorguIstemcisi.invalidateQueries({ queryKey: sorguAnahtarlari.gorevler });
    }
  }, [kosuDurumu, gorevId, sorguIstemcisi]);

  if (!Number.isFinite(gorevId)) {
    return <HataDurumu mesaj="Geçersiz görev adresi." />;
  }

  if (gorevSorgusu.isPending) return <Yukleniyor metin="Görev yükleniyor…" />;
  if (gorevSorgusu.isError) {
    return (
      <HataDurumu
        mesaj={hataMetni(gorevSorgusu.error)}
        yenidenDene={() => gorevSorgusu.refetch()}
      />
    );
  }

  const gorev = gorevSorgusu.data;
  const kareler = kareSorgusu.data?.results ?? [];

  return (
    <div>
      <p className="kucuk">
        <Link to="/gorevler">← Görevler</Link>
      </p>

      <div className="kart">
        <div className="kart-basligi">
          <h1>{gorev.name}</h1>
          <span className="sonuk kucuk">
            Oluşturulma {zamanMetni(gorev.created_at)}
          </span>
        </div>
        {gorev.description && <p className="sonuk">{gorev.description}</p>}

        <div className="sayim-kutulari">
          <div className="sayim-kutusu">
            <span className="deger">{gorev.frame_count}</span>
            <span className="etiket">Kare</span>
          </div>
          <div className="sayim-kutusu">
            <span className="deger">{gorev.frame_counts.done}</span>
            <span className="etiket">Tamamlanan</span>
          </div>
          <div className="sayim-kutusu">
            <span className="deger">
              {gorev.frame_counts.queued + gorev.frame_counts.processing}
            </span>
            <span className="etiket">İşlemde</span>
          </div>
          <div className="sayim-kutusu">
            <span className="deger">{gorev.frame_counts.failed}</span>
            <span className="etiket">Başarısız</span>
          </div>
        </div>
      </div>

      {kosu && <KosuIlerlemesi kosu={kosu} />}

      <TaramaBaslatma
        gorevId={gorevId}
        kareSayisi={gorev.frame_count}
        taramaSuruyor={taramaSuruyor}
        baslatildi={(kosuId) => setIzlenenKosuId(kosuId)}
      />

      <KareEkleme gorevId={gorevId} />

      <div className="kart">
        <h2>Kareler</h2>

        {kareSorgusu.isPending && <Yukleniyor metin="Kareler yükleniyor…" />}
        {kareSorgusu.isError && (
          <HataDurumu
            mesaj={hataMetni(kareSorgusu.error)}
            yenidenDene={() => kareSorgusu.refetch()}
          />
        )}
        {kareSorgusu.isSuccess && kareler.length === 0 && (
          <BosDurum metin="Bu görevde henüz kare yok." />
        )}

        {kareler.length > 0 && (
          <div className="tablo-sarmal">
            <table>
              <caption className="gorsel-gizli">
                Görevin kareleri: dosya adı, ölçü, durum ve konum bilgisi
              </caption>
              <thead>
                <tr>
                  <th scope="col">Dosya</th>
                  <th scope="col">Ölçü</th>
                  <th scope="col">Durum</th>
                  <th scope="col">Konum</th>
                </tr>
              </thead>
              <tbody>
                {kareler.map((kare) => (
                  <tr key={kare.id}>
                    <td className="kucuk">{kare.original_filename}</td>
                    <td className="kucuk tek-aralik">
                      {kare.width}×{kare.height}
                    </td>
                    <td>
                      <KareDurumRozeti durum={kare.status} />
                    </td>
                    <td className="kucuk sonuk">
                      {kare.latitude !== null && kare.longitude !== null
                        ? `${kare.latitude.toFixed(5)}, ${kare.longitude.toFixed(5)}`
                        : "Konum bilgisi mevcut değil"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {kareSorgusu.data && kareSorgusu.data.count > kareler.length && (
              <p className="kucuk sonuk">
                {kareSorgusu.data.count} kareden ilk {kareler.length} tanesi
                gösteriliyor.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
