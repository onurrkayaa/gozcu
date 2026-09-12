/**
 * Bulgular: liste, oluşturma formu, kümeleme ve harita.
 *
 * Konum kaynağı formda ZORUNLU ve açık bir seçim. Ölçülmüş kaynaklar (EXIF,
 * uçuş günlüğü) listede YOKTUR: elle girilen bir koordinatın ölçülmüş gibi
 * kaydedilmesi, haritaya bakan kişiyi yanıltır. Backend de bu iki kaynağı
 * reddeder, yani kural tek yerde değil iki yerde birden duruyor.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { hataMetni } from "../api/istemci";
import { sorguAnahtarlari } from "../api/sorguAnahtarlari";
import {
  bulguOlustur,
  bulguSil,
  bulgulariGetir,
  kumeleriGetir,
  kumelemeCalistir,
} from "../api/uclar";
import type { BulguDurumu, KonumKaynagi, Rol } from "../api/tipler";
import {
  KONUM_KAYNAK_ETIKETLERI,
  SECILEBILIR_KAYNAKLAR,
  yazabilirMi,
} from "../api/tipler";
import { BosDurum, HataDurumu, Yukleniyor, zamanMetni } from "../bilesenler/durumlar";
import { GorevHaritasi } from "../bilesenler/GorevHaritasi";

const DURUM_ETIKETLERI: Record<BulguDurumu, string> = {
  candidate: "Aday",
  confirmed: "Doğrulandı",
  dismissed: "Elendi",
};

export function BulguPaneli({ gorevId, rol }: { gorevId: number; rol: Rol | null }) {
  const sorguIstemcisi = useQueryClient();
  const yazabilir = yazabilirMi(rol);

  const [baslik, setBaslik] = useState("");
  const [kaynak, setKaynak] = useState<KonumKaynagi>("none");
  const [enlem, setEnlem] = useState("");
  const [boylam, setBoylam] = useState("");
  const [esik, setEsik] = useState(50);

  const bulguSorgusu = useQuery({
    queryKey: sorguAnahtarlari.bulgular(gorevId),
    queryFn: () => bulgulariGetir(gorevId),
  });

  const kumeSorgusu = useQuery({
    queryKey: sorguAnahtarlari.kumeler(gorevId),
    queryFn: () => kumeleriGetir(gorevId),
  });

  function tazele() {
    sorguIstemcisi.invalidateQueries({ queryKey: sorguAnahtarlari.bulgular(gorevId) });
    sorguIstemcisi.invalidateQueries({ queryKey: sorguAnahtarlari.kumeler(gorevId) });
    sorguIstemcisi.invalidateQueries({
      queryKey: sorguAnahtarlari.denetimiGecersizKil(gorevId),
    });
  }

  const olusturma = useMutation({
    mutationFn: () =>
      bulguOlustur(gorevId, {
        title: baslik.trim(),
        location_source: kaynak,
        latitude: kaynak === "none" ? null : Number(enlem),
        longitude: kaynak === "none" ? null : Number(boylam),
      }),
    onSuccess: () => {
      setBaslik("");
      setEnlem("");
      setBoylam("");
      setKaynak("none");
      tazele();
    },
  });

  const silme = useMutation({
    mutationFn: (bulguId: number) => bulguSil(bulguId),
    onSuccess: tazele,
  });

  const kumeleme = useMutation({
    mutationFn: () => kumelemeCalistir(gorevId, esik),
    onSuccess: tazele,
  });

  const bulgular = bulguSorgusu.data?.results ?? [];
  const kumeler = kumeSorgusu.data?.clusters ?? [];
  const konumGerekli = kaynak !== "none";
  const koordinatGecerli =
    !konumGerekli ||
    (enlem !== "" &&
      boylam !== "" &&
      Math.abs(Number(enlem)) <= 90 &&
      Math.abs(Number(boylam)) <= 180);

  return (
    <>
      <GorevHaritasi bulgular={bulgular} kumeler={kumeler} />

      <div className="kart">
        <div className="kart-basligi">
          <h2>Bulgular</h2>
          {bulguSorgusu.isSuccess && (
            <span className="sonuk kucuk">{bulguSorgusu.data.count} kayıt</span>
          )}
        </div>

        {bulguSorgusu.isPending && <Yukleniyor metin="Bulgular yükleniyor…" />}
        {bulguSorgusu.isError && (
          <HataDurumu
            mesaj={hataMetni(bulguSorgusu.error)}
            yenidenDene={() => bulguSorgusu.refetch()}
          />
        )}
        {bulguSorgusu.isSuccess && bulgular.length === 0 && (
          <BosDurum metin="Bu görevde henüz bulgu yok." />
        )}

        {bulgular.length > 0 && (
          <div className="tablo-sarmal">
            <table>
              <caption className="gorsel-gizli">
                Bulgular: başlık, durum, konum kaynağı, koordinat ve küme
              </caption>
              <thead>
                <tr>
                  <th scope="col">Başlık</th>
                  <th scope="col">Durum</th>
                  <th scope="col">Konum kaynağı</th>
                  <th scope="col">Koordinat</th>
                  <th scope="col">Küme</th>
                  <th scope="col">Eklenme</th>
                  {yazabilir && <th scope="col">İşlem</th>}
                </tr>
              </thead>
              <tbody>
                {bulgular.map((bulgu) => (
                  <tr key={bulgu.id} data-testid={`bulgu-satiri-${bulgu.id}`}>
                    <td>
                      {bulgu.title || `#${bulgu.id}`}
                      {bulgu.is_demo && (
                        <div className="rozet isleniyor" style={{ marginTop: "0.2rem" }}>
                          DEMO — gerçek GPS değil
                        </div>
                      )}
                    </td>
                    <td className="kucuk">{DURUM_ETIKETLERI[bulgu.status]}</td>
                    <td className="kucuk">
                      {KONUM_KAYNAK_ETIKETLERI[bulgu.location_source]}
                    </td>
                    <td className="kucuk tek-aralik">
                      {bulgu.latitude !== null && bulgu.longitude !== null
                        ? `${bulgu.latitude.toFixed(5)}, ${bulgu.longitude.toFixed(5)}`
                        : "Konum bilgisi mevcut değil"}
                    </td>
                    <td className="kucuk">
                      {bulgu.cluster_id !== null
                        ? `${bulgu.cluster_key} #${bulgu.cluster_id}`
                        : "—"}
                    </td>
                    <td className="kucuk sonuk">{zamanMetni(bulgu.created_at)}</td>
                    {yazabilir && (
                      <td>
                        <button
                          type="button"
                          className="tehlikeli"
                          disabled={silme.isPending}
                          onClick={() => silme.mutate(bulgu.id)}
                        >
                          Sil
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="kart">
        <h2>Kümeleme</h2>
        {kumeleme.isError && (
          <div className="bildirim hata" role="alert">
            {hataMetni(kumeleme.error)}
          </div>
        )}
        <div className="satir">
          <div className="alan" style={{ flex: "0 1 200px", marginBottom: 0 }}>
            <label htmlFor="kumelemeEsigi">Eşik (metre)</label>
            <input
              id="kumelemeEsigi"
              type="number"
              min={1}
              max={100000}
              value={esik}
              disabled={!yazabilir}
              onChange={(olay) => setEsik(Number(olay.target.value))}
            />
          </div>
          {yazabilir && (
            <button
              type="button"
              onClick={() => {
                if (kumeleme.isPending) return;
                kumeleme.mutate();
              }}
              disabled={kumeleme.isPending}
            >
              {kumeleme.isPending ? "Çalışıyor…" : "Kümelemeyi çalıştır"}
            </button>
          )}
        </div>
        <p className="yardim-metni">
          Eşik bir <strong>karar</strong>dır, ölçüm değil: hiçbir alan
          ölçümünden türetilmemiştir. Birbirine eşik kadar yakın bulgular aynı
          kümeye girer ve bu ilişki <strong>zincirleme yayılır</strong> — A ile
          B, B ile C eşik içindeyse A ile C arası eşikten uzak olsa bile üçü
          aynı kümede olur. Yani eşik, kümenin çapı değildir. Demo ve gerçek
          konumlar ayrı kümelenir; konumu olmayan bulgular kümelenmez.
        </p>
      </div>

      {yazabilir ? (
        <div className="kart">
          <h2>Bulgu ekle</h2>
          {olusturma.isError && (
            <div className="bildirim hata" role="alert">
              {hataMetni(olusturma.error)}
            </div>
          )}
          <form
            onSubmit={(olay) => {
              olay.preventDefault();
              if (olusturma.isPending || !koordinatGecerli) return;
              olusturma.mutate();
            }}
          >
            <div className="alan">
              <label htmlFor="bulguBasligi">Başlık</label>
              <input
                id="bulguBasligi"
                type="text"
                maxLength={200}
                value={baslik}
                onChange={(olay) => setBaslik(olay.target.value)}
              />
            </div>

            <div className="alan">
              <label htmlFor="bulguKaynagi">Konum kaynağı</label>
              <select
                id="bulguKaynagi"
                value={kaynak}
                onChange={(olay) => setKaynak(olay.target.value as KonumKaynagi)}
                aria-describedby="bulguKaynakYardim"
              >
                {SECILEBILIR_KAYNAKLAR.map((secenek) => (
                  <option key={secenek} value={secenek}>
                    {KONUM_KAYNAK_ETIKETLERI[secenek]}
                  </option>
                ))}
              </select>
              <div id="bulguKaynakYardim" className="yardim-metni">
                Ölçülmüş kaynaklar (EXIF, uçuş günlüğü) elle seçilemez; onlar
                ancak alım hattından gelirse kaydedilir. Elle girdiğiniz
                koordinat <strong>beyan</strong>, demo koordinat ise{" "}
                <strong>sentetik</strong> olarak işaretlenir ve haritada öyle
                gösterilir.
              </div>
            </div>

            {konumGerekli && (
              <div className="satir">
                <div className="alan" style={{ flex: "1 1 160px" }}>
                  <label htmlFor="bulguEnlem">Enlem (−90 … 90)</label>
                  <input
                    id="bulguEnlem"
                    type="number"
                    step="any"
                    min={-90}
                    max={90}
                    value={enlem}
                    onChange={(olay) => setEnlem(olay.target.value)}
                  />
                </div>
                <div className="alan" style={{ flex: "1 1 160px" }}>
                  <label htmlFor="bulguBoylam">Boylam (−180 … 180)</label>
                  <input
                    id="bulguBoylam"
                    type="number"
                    step="any"
                    min={-180}
                    max={180}
                    value={boylam}
                    onChange={(olay) => setBoylam(olay.target.value)}
                  />
                </div>
              </div>
            )}

            <button
              type="submit"
              className="birincil"
              disabled={olusturma.isPending || !koordinatGecerli}
            >
              {olusturma.isPending ? "Ekleniyor…" : "Bulgu ekle"}
            </button>
            {!koordinatGecerli && (
              <div className="yardim-metni">
                Enlem −90 ile 90, boylam −180 ile 180 arasında olmalı ve ikisi
                birlikte girilmeli.
              </div>
            )}
          </form>
        </div>
      ) : (
        <div className="kart">
          <p className="salt-okunur-notu" data-testid="bulgu-salt-okunur">
            Bu görevde salt okunur yetkiniz var; bulgu ekleyemez veya
            silemezsiniz.
          </p>
        </div>
      )}
    </>
  );
}
