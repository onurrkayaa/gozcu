/**
 * Durum gösterimleri: yükleniyor, boş, hata + yeniden dene, rozetler.
 *
 * Bunlar tek yerde durur ki her ekranda aynı davranışı göstersinler ve
 * "sessizce boş ekran" durumu oluşmasın.
 */

import type { KareDurumu, KosuDurumu } from "../api/tipler";

export function Yukleniyor({ metin = "Yükleniyor…" }: { metin?: string }) {
  // role="status": ekran okuyucu yüklemeyi duyurur.
  return (
    <div className="bildirim bos" role="status">
      {metin}
    </div>
  );
}

export function BosDurum({ metin }: { metin: string }) {
  return <div className="bildirim bos">{metin}</div>;
}

export function HataDurumu({
  mesaj,
  yenidenDene,
}: {
  mesaj: string;
  yenidenDene?: () => void;
}) {
  return (
    <div className="bildirim hata" role="alert">
      <div>{mesaj}</div>
      {yenidenDene && (
        <button type="button" onClick={yenidenDene} style={{ marginTop: "0.6rem" }}>
          Yeniden dene
        </button>
      )}
    </div>
  );
}

/**
 * Backend enum değeri -> Türkçe etiket + rozet sınıfı.
 *
 * Anahtarlar backend enum'larıyla birebir aynıdır (core/models.py). Değer
 * çevrilmez, yalnızca gösterim etiketi eklenir.
 */
const KARE_DURUM_METINLERI: Record<KareDurumu, { etiket: string; sinif: string; isaret: string }> = {
  pending: { etiket: "Bekliyor", sinif: "bekliyor", isaret: "○" },
  queued: { etiket: "Kuyrukta", sinif: "kuyrukta", isaret: "◔" },
  processing: { etiket: "İşleniyor", sinif: "isleniyor", isaret: "◑" },
  done: { etiket: "Tamam", sinif: "tamam", isaret: "●" },
  failed: { etiket: "Başarısız", sinif: "basarisiz", isaret: "✕" },
};

const KOSU_DURUM_METINLERI: Record<KosuDurumu, { etiket: string; sinif: string; isaret: string }> = {
  pending: { etiket: "Bekliyor", sinif: "bekliyor", isaret: "○" },
  running: { etiket: "Çalışıyor", sinif: "isleniyor", isaret: "◑" },
  done: { etiket: "Tamamlandı", sinif: "tamam", isaret: "●" },
  failed: { etiket: "Başarısız", sinif: "basarisiz", isaret: "✕" },
};

export function KareDurumRozeti({ durum }: { durum: KareDurumu }) {
  const bilgi = KARE_DURUM_METINLERI[durum];
  if (!bilgi) return <span className="rozet bekliyor">{durum}</span>;
  return (
    <span className={`rozet ${bilgi.sinif}`}>
      {/* İşaret renkten bağımsız ikinci bir ayırt edici; renk tek başına
          durum taşımasın diye var. aria-hidden çünkü etiket zaten okunuyor. */}
      <span className="isaret" aria-hidden="true">
        {bilgi.isaret}
      </span>
      {bilgi.etiket}
    </span>
  );
}

export function KosuDurumRozeti({ durum }: { durum: KosuDurumu }) {
  const bilgi = KOSU_DURUM_METINLERI[durum];
  if (!bilgi) return <span className="rozet bekliyor">{durum}</span>;
  return (
    <span className={`rozet ${bilgi.sinif}`}>
      <span className="isaret" aria-hidden="true">
        {bilgi.isaret}
      </span>
      {bilgi.etiket}
    </span>
  );
}

export function kareDurumEtiketi(durum: KareDurumu): string {
  return KARE_DURUM_METINLERI[durum]?.etiket ?? durum;
}

export function kosuDurumEtiketi(durum: KosuDurumu): string {
  return KOSU_DURUM_METINLERI[durum]?.etiket ?? durum;
}

/** Tarihi yerel biçimde gösterir; geçersizse çizgi. */
export function zamanMetni(ham: string | null): string {
  if (!ham) return "—";
  const tarih = new Date(ham);
  if (Number.isNaN(tarih.getTime())) return "—";
  return tarih.toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" });
}
