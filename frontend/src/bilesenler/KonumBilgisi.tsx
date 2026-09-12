import type { Kare } from "../api/tipler";

/**
 * Karenin konum durumu.
 *
 * Politika reports/hafta5_gps_kaynak_karari.csv ile belirlendi: taranan 1579
 * HERIDAL görüntüsünün hiçbirinde EXIF yok, dolayısıyla enlem/boylam da yok.
 * Bu yüzden arayüz koordinat ÜRETMEZ; yalnızca kayıtta gerçekten varsa
 * gösterir, yoksa yokluğunu açıkça söyler.
 *
 * Dosya sırasından, karo satır/sütunundan veya görüntü pikselinden koordinat
 * TÜRETİLMEZ. Böyle bir değer ölçüm değil uydurma olurdu ve arama ekibini
 * yanlış noktaya yönlendirirdi.
 */
export function KonumBilgisi({ kare }: { kare: Kare | null }) {
  if (!kare) {
    return <div className="konum-kutusu">Konum bilgisi mevcut değil.</div>;
  }

  const enlem = kare.latitude;
  const boylam = kare.longitude;

  if (enlem === null || boylam === null) {
    return (
      <div className="konum-kutusu">
        <strong>Konum bilgisi mevcut değil.</strong>
        <div className="kucuk" style={{ marginTop: "0.3rem" }}>
          Bu görüntüde EXIF GPS verisi yok. Kullanılan veri kümesindeki
          görüntülerin konum etiketleri kaynağında silinmiştir; arayüz koordinat
          üretmez.
        </div>
      </div>
    );
  }

  return (
    <div className="konum-kutusu">
      <strong>Kayıtlı konum</strong>
      <div className="tek-aralik kucuk" style={{ marginTop: "0.3rem" }}>
        {enlem.toFixed(6)}, {boylam.toFixed(6)}
        {kare.altitude_m !== null && <> · {kare.altitude_m.toFixed(1)} m</>}
      </div>
      <div className="kucuk" style={{ marginTop: "0.3rem" }}>
        Kaynak: görüntünün EXIF GPS alanı.
      </div>
    </div>
  );
}
