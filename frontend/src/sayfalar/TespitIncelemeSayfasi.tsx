import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { hataMetni } from "../api/istemci";
import { sorguAnahtarlari } from "../api/sorguAnahtarlari";
import {
  gorevGetir,
  kareleriGetir,
  kosuGetir,
  kosuIncelemeleriniGetir,
  tespitleriGetir,
} from "../api/uclar";
import type { Tespit } from "../api/tipler";
import {
  BosDurum,
  HataDurumu,
  KareDurumRozeti,
  Yukleniyor,
  zamanMetni,
} from "../bilesenler/durumlar";
import { KonumBilgisi } from "../bilesenler/KonumBilgisi";
import { TespitKatmani } from "../bilesenler/TespitKatmani";
import { IncelemePaneli } from "../bilesenler/IncelemePaneli";
import { useOturum } from "../kimlik/useOturum";

/**
 * Görüntüleme eşiğinin alt sınırı.
 *
 * Backend kutuları DETECTION_STORE_FLOOR = 0,05 tabanıyla saklar
 * (gozcu_api/settings.py); bu değerin altını sormanın anlamı yok, kayıt zaten
 * yok. Eşik okuma anında uygulanır, kayda pişirilmez.
 */
const EN_DUSUK_ESIK = 0.05;

/** Sayfa başına tespit; backend PAGE_SIZE = 20. */
const SAYFA_BOYUTU = 20;

function TespitAyrintisi({ tespit }: { tespit: Tespit }) {
  return (
    <dl className="kucuk" style={{ margin: 0 }}>
      <div className="satir aralikli">
        <dt className="sonuk">Güven</dt>
        <dd className="tek-aralik" style={{ margin: 0 }}>
          {tespit.score.toFixed(3)}
        </dd>
      </div>
      <div className="satir aralikli">
        <dt className="sonuk">Kutu (px)</dt>
        <dd className="tek-aralik" style={{ margin: 0 }}>
          {tespit.x1}, {tespit.y1} – {tespit.x2}, {tespit.y2}
        </dd>
      </div>
      <div className="satir aralikli">
        <dt className="sonuk">Ölçü (px)</dt>
        <dd className="tek-aralik" style={{ margin: 0 }}>
          {tespit.x2 - tespit.x1}×{tespit.y2 - tespit.y1}
        </dd>
      </div>
      {tespit.tile_row !== null && tespit.tile_col !== null && (
        <div className="satir aralikli">
          <dt className="sonuk">Karo</dt>
          <dd className="tek-aralik" style={{ margin: 0 }}>
            satır {tespit.tile_row}, sütun {tespit.tile_col}
          </dd>
        </div>
      )}
    </dl>
  );
}

export function TespitIncelemeSayfasi() {
  const { kosuId: hamKosuId } = useParams();
  const kosuId = Number(hamKosuId);
  const { kullaniciAdi } = useOturum();

  const [seciliKareId, setSeciliKareId] = useState<number | null>(null);
  const [seciliTespitId, setSeciliTespitId] = useState<number | null>(null);
  const [esik, setEsik] = useState<number | null>(null);

  const kosuSorgusu = useQuery({
    queryKey: sorguAnahtarlari.kosu(kosuId),
    queryFn: () => kosuGetir(kosuId),
    enabled: Number.isFinite(kosuId),
  });

  const gorevId = kosuSorgusu.data?.mission;

  const kareSorgusu = useQuery({
    queryKey: sorguAnahtarlari.kareler(gorevId ?? -1, 1),
    queryFn: () => kareleriGetir(gorevId as number, 1),
    enabled: gorevId !== undefined,
  });

  const kareler = useMemo(() => kareSorgusu.data?.results ?? [], [kareSorgusu.data]);

  // Rol, hangi denetimlerin gösterileceğini belirler; yetkiyi backend uygular.
  const gorevSorgusu = useQuery({
    queryKey: sorguAnahtarlari.gorev(gorevId ?? -1),
    queryFn: () => gorevGetir(gorevId as number),
    enabled: gorevId !== undefined,
  });

  // Koşudaki bütün incelemeler tek istekte gelir; her tespit için ayrı istek
  // atmak seçim değiştikçe gereksiz trafik üretirdi.
  const incelemeSorgusu = useQuery({
    queryKey: sorguAnahtarlari.incelemeler(kosuId),
    queryFn: () => kosuIncelemeleriniGetir(kosuId),
    enabled: Number.isFinite(kosuId),
  });

  // İlk kare kendiliğinden seçilsin; kullanıcı boş ekranla karşılaşmasın.
  useEffect(() => {
    if (seciliKareId === null && kareler.length > 0) {
      setSeciliKareId(kareler[0].id);
    }
  }, [kareler, seciliKareId]);

  // Eşiğin başlangıç değeri SABİT YAZILMAZ: koşunun kendi conf_threshold'u
  // kullanılır, yani kullanıcı taramayı hangi eşikle başlattıysa ekran oradan
  // açılır.
  const kosuEsigi = kosuSorgusu.data?.conf_threshold;
  useEffect(() => {
    if (esik === null && kosuEsigi !== undefined) {
      setEsik(kosuEsigi);
    }
  }, [kosuEsigi, esik]);

  const etkinEsik = esik ?? kosuEsigi ?? EN_DUSUK_ESIK;

  const tespitSorgusu = useQuery({
    queryKey: sorguAnahtarlari.tespitler(kosuId, seciliKareId ?? undefined, etkinEsik),
    queryFn: () =>
      tespitleriGetir(kosuId, {
        kareId: seciliKareId ?? undefined,
        minSkor: etkinEsik,
      }),
    enabled: Number.isFinite(kosuId) && seciliKareId !== null,
  });

  const tespitler = useMemo(
    () => tespitSorgusu.data?.results ?? [],
    [tespitSorgusu.data],
  );

  // Kare veya eşik değişince önceki seçim geçersizleşir.
  useEffect(() => {
    if (seciliTespitId !== null && !tespitler.some((t) => t.id === seciliTespitId)) {
      setSeciliTespitId(null);
    }
  }, [tespitler, seciliTespitId]);

  if (!Number.isFinite(kosuId)) return <HataDurumu mesaj="Geçersiz koşu adresi." />;
  if (kosuSorgusu.isPending) return <Yukleniyor metin="Koşu yükleniyor…" />;
  if (kosuSorgusu.isError) {
    return (
      <HataDurumu
        mesaj={hataMetni(kosuSorgusu.error)}
        yenidenDene={() => kosuSorgusu.refetch()}
      />
    );
  }

  const kosu = kosuSorgusu.data;
  const seciliKare = kareler.find((kare) => kare.id === seciliKareId) ?? null;
  const seciliTespit = tespitler.find((t) => t.id === seciliTespitId) ?? null;

  return (
    <div>
      <p className="kucuk">
        <Link to={`/gorevler/${kosu.mission}`}>← Görev ayrıntısı</Link>
      </p>

      <div className="kart">
        <div className="kart-basligi">
          <h1>Tespit inceleme</h1>
          <span className="sonuk kucuk">
            {kosu.model_version_name} · {kosu.frames_done}/{kosu.frames_total} kare ·{" "}
            {zamanMetni(kosu.started_at)}
          </span>
        </div>

        <div className="alan" style={{ maxWidth: "480px", marginBottom: 0 }}>
          <label htmlFor="goruntulemeEsigi">
            Görüntüleme eşiği: {etkinEsik.toFixed(2)}
          </label>
          <input
            id="goruntulemeEsigi"
            type="range"
            min={EN_DUSUK_ESIK}
            max={0.95}
            step={0.01}
            value={etkinEsik}
            onChange={(olay) => setEsik(Number(olay.target.value))}
            aria-describedby="esikYardim"
            style={{ width: "100%" }}
          />
          <div id="esikYardim" className="yardim-metni">
            Bu kaydırıcı yalnızca ekranda gösterilen kutuları süzer; modeli
            yeniden çalıştırmaz ve kayıtlı tespitleri değiştirmez. Bir
            değerlendirme metriği değildir — eşiği değiştirmek yeni bir recall
            veya hatalı tespit oranı iddiası üretmez. Tarama {kosu.conf_threshold.toFixed(2)}{" "}
            eşiğiyle başlatıldı; kutular 0,05 tabanına kadar saklandığı için
            daha düşük eşikler yeniden tarama olmadan sorulabilir.
          </div>
        </div>
      </div>

      <div className="inceleme-duzeni">
        <div>
          {kareSorgusu.isPending && <Yukleniyor metin="Kareler yükleniyor…" />}
          {kareSorgusu.isError && (
            <HataDurumu
              mesaj={hataMetni(kareSorgusu.error)}
              yenidenDene={() => kareSorgusu.refetch()}
            />
          )}
          {kareSorgusu.isSuccess && kareler.length === 0 && (
            <BosDurum metin="Bu görevde kare yok." />
          )}

          {seciliKare && (
            <TespitKatmani
              kare={seciliKare}
              tespitler={tespitler}
              seciliTespitId={seciliTespitId}
              tespitSecildi={setSeciliTespitId}
            />
          )}
        </div>

        <div>
          <div className="kart">
            <h2>Kare</h2>
            <div className="alan" style={{ marginBottom: "0.6rem" }}>
              <label htmlFor="kareSecimi" className="gorsel-gizli">
                İncelenecek kare
              </label>
              <select
                id="kareSecimi"
                value={seciliKareId ?? ""}
                onChange={(olay) => {
                  setSeciliKareId(Number(olay.target.value));
                  setSeciliTespitId(null);
                }}
              >
                {kareler.map((kare) => (
                  <option key={kare.id} value={kare.id}>
                    {kare.original_filename}
                  </option>
                ))}
              </select>
            </div>
            {seciliKare && (
              <div className="satir kucuk">
                <KareDurumRozeti durum={seciliKare.status} />
                <span className="sonuk tek-aralik">
                  {seciliKare.width}×{seciliKare.height}
                </span>
              </div>
            )}
          </div>

          <div className="kart">
            <h2>Konum</h2>
            <KonumBilgisi kare={seciliKare} />
          </div>

          <div className="kart">
            <h2>
              İnsan adayları{" "}
              {tespitSorgusu.isSuccess && (
                <span className="sonuk kucuk">({tespitSorgusu.data.count})</span>
              )}
            </h2>

            {tespitSorgusu.isPending && <Yukleniyor metin="Tespitler yükleniyor…" />}
            {tespitSorgusu.isError && (
              <HataDurumu
                mesaj={hataMetni(tespitSorgusu.error)}
                yenidenDene={() => tespitSorgusu.refetch()}
              />
            )}

            {tespitSorgusu.isSuccess && tespitler.length === 0 && (
              <BosDurum metin="Bu karede, seçilen görüntüleme eşiğinde insan adayı bulunmadı." />
            )}

            {tespitler.length > 0 && (
              <>
                <div className="tespit-listesi">
                  {tespitler.map((tespit, sira) => (
                    <button
                      key={tespit.id}
                      type="button"
                      className={`tespit-satiri${
                        tespit.id === seciliTespitId ? " secili" : ""
                      }`}
                      aria-pressed={tespit.id === seciliTespitId}
                      onClick={() => setSeciliTespitId(tespit.id)}
                    >
                      <span>Aday {sira + 1}</span>
                      <span className="tek-aralik">{tespit.score.toFixed(3)}</span>
                    </button>
                  ))}
                </div>
                {(tespitSorgusu.data?.count ?? 0) > SAYFA_BOYUTU && (
                  <p className="kucuk sonuk">
                    {tespitSorgusu.data?.count} adayın en yüksek güvenli{" "}
                    {tespitler.length} tanesi gösteriliyor.
                  </p>
                )}
              </>
            )}

            {seciliTespit && (
              <div style={{ marginTop: "0.8rem" }}>
                <h3>Seçili aday</h3>
                <p className="kucuk sonuk" style={{ marginTop: 0 }}>
                  Modelin çıktısı:
                </p>
                <TespitAyrintisi tespit={seciliTespit} />

                <IncelemePaneli
                  kosuId={kosuId}
                  tespit={seciliTespit}
                  incelemeler={(incelemeSorgusu.data?.results ?? []).filter(
                    (inceleme) => inceleme.detection === seciliTespit.id,
                  )}
                  rol={gorevSorgusu.data?.my_role ?? null}
                  kullaniciAdi={kullaniciAdi}
                />
              </div>
            )}

            <p className="yardim-metni" style={{ marginTop: "0.8rem" }}>
              Kutular modelin insan <em>adayı</em> olarak işaretlediği bölgelerdir.
              Kesin insan tespiti değildir; her aday operatör tarafından
              doğrulanmalıdır.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
