import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { hataMetni } from "../api/istemci";
import { sorguAnahtarlari } from "../api/sorguAnahtarlari";
import { kareYukle } from "../api/uclar";

/** Backend Pillow ile açabildiğini kabul eder; arayüz önden bariz olanı eler. */
const KABUL_EDILEN_TURLER = ["image/jpeg", "image/png", "image/tiff", "image/webp"];
const EN_BUYUK_BOYUT = 50 * 1024 * 1024;

type SonucDurumu = "yuklendi" | "zaten_vardi" | "hata";

interface DosyaSonucu {
  ad: string;
  durum: SonucDurumu;
  mesaj: string;
}

function sonucMetni(sonuc: DosyaSonucu): string {
  switch (sonuc.durum) {
    case "yuklendi":
      return "Yüklendi";
    case "zaten_vardi":
      return "Zaten ekliydi";
    default:
      return sonuc.mesaj;
  }
}

export function KareEkleme({ gorevId }: { gorevId: number }) {
  const sorguIstemcisi = useQueryClient();
  const dosyaGirisiRef = useRef<HTMLInputElement>(null);

  const [secilenler, setSecilenler] = useState<File[]>([]);
  const [sonuclar, setSonuclar] = useState<DosyaSonucu[]>([]);
  const [yukleniyor, setYukleniyor] = useState(false);
  const [ilerleme, setIlerleme] = useState(0);

  function dosyalariSec(liste: FileList | null) {
    if (!liste) return;
    setSecilenler(Array.from(liste));
    setSonuclar([]);
  }

  function dosyayiDogrula(dosya: File): string | null {
    // Tür yalnızca uzantıdan değil, tarayıcının bildirdiği MIME türünden de
    // bakılır. Son söz backend'indir: Pillow dosyayı gerçekten açmayı dener.
    if (dosya.type && !KABUL_EDILEN_TURLER.includes(dosya.type)) {
      return "Desteklenmeyen dosya türü. JPEG, PNG, TIFF veya WebP gönderin.";
    }
    if (dosya.size > EN_BUYUK_BOYUT) {
      return "Dosya çok büyük (en fazla 50 MB).";
    }
    if (dosya.size === 0) {
      return "Dosya boş.";
    }
    return null;
  }

  async function yukle() {
    // Çift gönderim koruması.
    if (yukleniyor || secilenler.length === 0) return;

    setYukleniyor(true);
    setSonuclar([]);
    setIlerleme(0);

    const toplananlar: DosyaSonucu[] = [];

    // Dosyalar TEK TEK gönderilir: backend tek istekte bir dosya bozuksa tüm
    // isteği 400 ile reddediyor. Tek tek göndermek kısmi başarıyı korur ve
    // kullanıcıya dosya bazında sonuç göstermeyi mümkün kılar.
    for (const [sira, dosya] of secilenler.entries()) {
      const onHata = dosyayiDogrula(dosya);
      if (onHata) {
        toplananlar.push({ ad: dosya.name, durum: "hata", mesaj: onHata });
      } else {
        try {
          const sonuc = await kareYukle(gorevId, dosya);
          toplananlar.push({
            ad: dosya.name,
            durum: sonuc.duplicate ? "zaten_vardi" : "yuklendi",
            mesaj: "",
          });
        } catch (sebep) {
          toplananlar.push({ ad: dosya.name, durum: "hata", mesaj: hataMetni(sebep) });
        }
      }
      setIlerleme(sira + 1);
      setSonuclar([...toplananlar]);
    }

    setYukleniyor(false);
    setSecilenler([]);
    if (dosyaGirisiRef.current) dosyaGirisiRef.current.value = "";

    sorguIstemcisi.invalidateQueries({
      queryKey: sorguAnahtarlari.kareleriGecersizKil(gorevId),
    });
    sorguIstemcisi.invalidateQueries({ queryKey: sorguAnahtarlari.gorev(gorevId) });
    sorguIstemcisi.invalidateQueries({ queryKey: sorguAnahtarlari.gorevler });
  }

  const basarisizSayisi = sonuclar.filter((s) => s.durum === "hata").length;
  const basariliSayisi = sonuclar.length - basarisizSayisi;

  return (
    <div className="kart">
      <h2>Kare ekle</h2>

      <div className="alan">
        <label htmlFor="kareDosyalari">Görüntü dosyaları</label>
        <input
          id="kareDosyalari"
          ref={dosyaGirisiRef}
          type="file"
          multiple
          accept={KABUL_EDILEN_TURLER.join(",")}
          onChange={(olay) => dosyalariSec(olay.target.files)}
          disabled={yukleniyor}
          aria-describedby="kareDosyalariYardim"
        />
        <div id="kareDosyalariYardim" className="yardim-metni">
          Birden fazla dosya seçebilirsiniz. Aynı görevde daha önce eklenmiş bir
          görüntü yeniden yüklenirse yeni kayıt açılmaz, mevcut kare korunur.
        </div>
      </div>

      {secilenler.length > 0 && (
        <ul className="dosya-listesi">
          {secilenler.map((dosya) => (
            <li key={`${dosya.name}-${dosya.size}`}>
              <span>{dosya.name}</span>
              <span className="sonuk kucuk">
                {(dosya.size / (1024 * 1024)).toFixed(1)} MB
              </span>
            </li>
          ))}
        </ul>
      )}

      <div className="satir" style={{ marginTop: "0.8rem" }}>
        <button
          type="button"
          className="birincil"
          onClick={yukle}
          disabled={yukleniyor || secilenler.length === 0}
        >
          {yukleniyor
            ? `Yükleniyor… (${ilerleme}/${secilenler.length})`
            : `Seçilenleri yükle${secilenler.length > 0 ? ` (${secilenler.length})` : ""}`}
        </button>
      </div>

      {sonuclar.length > 0 && (
        <div style={{ marginTop: "0.9rem" }}>
          {/* Kısmi başarısızlık gizlenmez: kaç dosyanın geçtiği ve kaçının
              düştüğü birlikte yazılır. */}
          <div
            className={`bildirim ${basarisizSayisi > 0 ? "hata" : "basari"}`}
            role="status"
          >
            {basarisizSayisi === 0
              ? `${basariliSayisi} dosya işlendi.`
              : `${basariliSayisi} dosya işlendi, ${basarisizSayisi} dosya eklenemedi.`}
          </div>
          <ul className="dosya-listesi">
            {sonuclar.map((sonuc, sira) => (
              <li key={`${sonuc.ad}-${sira}`}>
                <span>{sonuc.ad}</span>
                <span className={sonuc.durum === "hata" ? "" : "sonuk"}>
                  {sonucMetni(sonuc)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
