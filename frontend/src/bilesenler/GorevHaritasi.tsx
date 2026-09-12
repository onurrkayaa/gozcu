/**
 * Görev haritası (Leaflet).
 *
 * En önemli davranış, harita göstermek DEĞİL, ne zaman GÖSTERMEMEK gerektiğini
 * bilmek. Gösterilecek konum yoksa boş bir dünya haritası çizmiyoruz: boş
 * harita, kullanıcıya "konum verisi var ama bu görevde işaret yok" izlenimi
 * verir. Onun yerine neden konum olmadığını yazıyoruz.
 *
 * Demo konumlar, gerçek konumlardan hem metinle hem görsel olarak ayrılır ve
 * uyarı harita üstünde KALICI durur; kaydırıldığında veya ekran görüntüsü
 * alındığında kaybolmaz.
 */

import { useEffect, useMemo, useState } from "react";
import { MapContainer, Marker, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

import type { Bulgu, Kume } from "../api/tipler";
import { KONUM_KAYNAK_ETIKETLERI } from "../api/tipler";

/**
 * Leaflet'in varsayılan işaretçi ikonu, paket içindeki görsellere göreli
 * yollarla bakar. Vite derlemesinde o yollar taşındığı için üretim
 * derlemesinde ikon kaybolur — bilinen bir tuzak. Bunun yerine ikonları
 * kendimiz çiziyoruz: dış dosya yok, derleme sonrası kırılacak yol yok.
 */
function isaretIkonu(demo: boolean, uyeSayisi: number): L.DivIcon {
  const renk = demo ? "#e8b04b" : "#4da3ff";
  const kenar = demo ? "dashed" : "solid";
  const cap = uyeSayisi > 1 ? 34 : 24;
  return L.divIcon({
    className: "gozcu-isaret",
    html: `<div style="
      width:${cap}px;height:${cap}px;border-radius:50%;
      background:${demo ? "rgba(232,176,75,0.35)" : "rgba(77,163,255,0.35)"};
      border:3px ${kenar} ${renk};
      display:flex;align-items:center;justify-content:center;
      color:#fff;font-weight:700;font-size:12px;
      box-shadow:0 0 0 2px rgba(0,0,0,0.45);
    ">${uyeSayisi > 1 ? uyeSayisi : ""}</div>`,
    iconSize: [cap, cap],
    iconAnchor: [cap / 2, cap / 2],
  });
}

/** Harita sınırlarını mevcut noktalara uydurur. */
function SinirlariUydur({ noktalar }: { noktalar: [number, number][] }) {
  const harita = useMap();

  useEffect(() => {
    if (noktalar.length === 0) return;
    if (noktalar.length === 1) {
      // Tek noktada fitBounds sonsuza yakın yakınlaşır; sabit bir ölçek
      // kullanıp kullanıcıyı çevresini göremeyecek kadar içeri sokmuyoruz.
      harita.setView(noktalar[0], 15);
      return;
    }
    harita.fitBounds(L.latLngBounds(noktalar), { padding: [40, 40], maxZoom: 16 });
  }, [harita, noktalar]);

  // Harita gizli bir kapsayıcıda açıldıysa (sekme, katlanmış panel) boyutunu
  // yanlış hesaplar; görünür olduğunda yeniden ölçmesi gerekir.
  useEffect(() => {
    const zamanlayici = window.setTimeout(() => harita.invalidateSize(), 200);
    const yenidenOlc = () => harita.invalidateSize();
    window.addEventListener("resize", yenidenOlc);
    return () => {
      window.clearTimeout(zamanlayici);
      window.removeEventListener("resize", yenidenOlc);
    };
  }, [harita]);

  return null;
}

interface Ozellikler {
  bulgular: Bulgu[];
  kumeler: Kume[];
  bulguSecildi?: (bulguId: number) => void;
}

export function GorevHaritasi({ bulgular, kumeler, bulguSecildi }: Ozellikler) {
  const [dosemeHatasi, setDosemeHatasi] = useState(false);
  const konumlu = useMemo(
    () => bulgular.filter((b) => b.latitude !== null && b.longitude !== null),
    [bulgular],
  );
  const demoVar = konumlu.some((b) => b.is_demo);
  const noktalar = useMemo<[number, number][]>(
    () => konumlu.map((b) => [b.latitude as number, b.longitude as number]),
    [konumlu],
  );

  const kumeSozlugu = useMemo(() => {
    const sozluk = new Map<string, Kume>();
    for (const kume of kumeler) {
      sozluk.set(`${kume.cluster_key}#${kume.cluster_id}`, kume);
    }
    return sozluk;
  }, [kumeler]);

  if (konumlu.length === 0) {
    return (
      <div className="kart" data-testid="harita-bos-durum">
        <h2>Harita</h2>
        <div className="konum-kutusu">
          <strong>Bu görevde konum bilgisi mevcut değil.</strong>
          <div className="kucuk" style={{ marginTop: "0.4rem" }}>
            Bu görevdeki bulguların hiçbirinde koordinat yok. Kullanılan veri
            kümesindeki görüntülerin konum etiketleri kaynağında silinmiş
            durumda; arayüz koordinat üretmez. Tespit kutuları görüntü
            pikselidir ve haritaya yerleştirilemez — piksel ile dünya koordinatı
            arasında dönüşüm için kameranın konumu, irtifası ve yönelimi
            gerekir, bunların hiçbiri kayıtlarda yok.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="kart">
      <h2>Harita</h2>

      {demoVar && (
        <div className="bildirim demo-uyarisi" role="alert" data-testid="demo-uyarisi">
          <strong>Demo konumları — gerçek GPS verisi değildir.</strong>
          <div className="kucuk" style={{ marginTop: "0.3rem" }}>
            Bu haritadaki kesikli çerçeveli işaretler gösterim amacıyla
            üretilmiş sentetik koordinatlardır. Gerçek bir ölçüm, gerçek bir
            uçuş rotası veya gerçek bir olay yeri göstermezler.
          </div>
        </div>
      )}

      {dosemeHatasi && (
        <div className="bildirim hata" role="status">
          Harita karoları yüklenemedi. İşaret konumları aşağıdaki listede
          okunabilir; harita görüntüsü olmadan da bulgular kaybolmaz.
        </div>
      )}

      <div className="harita-kabi" data-testid="harita-kabi">
        <MapContainer
          center={[noktalar[0][0], noktalar[0][1]]}
          zoom={14}
          scrollWheelZoom
          keyboard
          style={{ height: "100%", width: "100%" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> katkıda bulunanları'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            eventHandlers={{ tileerror: () => setDosemeHatasi(true) }}
          />
          <SinirlariUydur noktalar={noktalar} />

          {konumlu.map((bulgu) => {
            const kume =
              bulgu.cluster_id !== null
                ? kumeSozlugu.get(`${bulgu.cluster_key}#${bulgu.cluster_id}`)
                : undefined;
            return (
              <Marker
                key={bulgu.id}
                position={[bulgu.latitude as number, bulgu.longitude as number]}
                icon={isaretIkonu(bulgu.is_demo, kume?.uye_sayisi ?? 1)}
                eventHandlers={{ click: () => bulguSecildi?.(bulgu.id) }}
              >
                <Popup>
                  <div className="harita-balon">
                    <strong>{bulgu.title || `Bulgu #${bulgu.id}`}</strong>
                    {bulgu.is_demo && (
                      <div className="balon-demo">
                        DEMO — gerçek GPS değildir
                      </div>
                    )}
                    <dl>
                      <dt>Konum kaynağı</dt>
                      <dd>{KONUM_KAYNAK_ETIKETLERI[bulgu.location_source]}</dd>
                      <dt>Durum</dt>
                      <dd>{bulgu.status}</dd>
                      <dt>Koordinat</dt>
                      <dd>
                        {(bulgu.latitude as number).toFixed(5)},{" "}
                        {(bulgu.longitude as number).toFixed(5)}
                      </dd>
                      {kume && (
                        <>
                          <dt>Küme</dt>
                          <dd>
                            {kume.cluster_key} #{kume.cluster_id} · {kume.uye_sayisi}{" "}
                            bulgu
                          </dd>
                        </>
                      )}
                      {bulgu.created_by && (
                        <>
                          <dt>Ekleyen</dt>
                          <dd>{bulgu.created_by.username}</dd>
                        </>
                      )}
                    </dl>
                    {bulgu.note && <p className="kucuk">{bulgu.note}</p>}
                  </div>
                </Popup>
              </Marker>
            );
          })}
        </MapContainer>
      </div>

      <p className="yardim-metni">
        {konumlu.length} konumlu bulgu gösteriliyor.
        {bulgular.length - konumlu.length > 0 && (
          <> {bulgular.length - konumlu.length} bulgunun konumu yok ve haritada
          gösterilmiyor.</>
        )}{" "}
        Küme işaretlerindeki sayı, o kümedeki bulgu adedidir; küme merkezi
        ölçülmüş bir konum değil, üyelerin ortalamasıdır.
      </p>
    </div>
  );
}
