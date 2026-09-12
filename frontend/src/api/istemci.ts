/**
 * Merkezi HTTP katmanı.
 *
 * Sorumlulukları:
 *  - API taban adresini tek yerden vermek
 *  - Authorization başlığını eklemek
 *  - 401'de KONTROLLÜ token yenilemesi yapmak (tek uçuşta)
 *  - Backend hata gövdelerini kullanıcıya gösterilebilir Türkçe metne çevirmek
 *
 * Ham JSON hiçbir zaman kullanıcıya gösterilmez; ApiHatasi.mesaj alanı
 * arayüzde gösterilecek metindir.
 */

import { tokenDeposu } from "../kimlik/tokenDeposu";

/**
 * Taban adres. Geliştirmede boş bırakılır ve Vite proxy'si /api'yi backend'e
 * taşır (aynı kaynak, CORS gerekmez). Üretim derlemesinde VITE_API_TABAN
 * verilir.
 */
export const API_TABAN = (import.meta.env?.VITE_API_TABAN ?? "").replace(/\/$/, "");

export class ApiHatasi extends Error {
  readonly durumKodu: number;
  /** Alan bazında doğrulama hataları (varsa): { name: ["..."] } */
  readonly alanHatalari: Record<string, string[]>;

  constructor(mesaj: string, durumKodu: number, alanHatalari: Record<string, string[]> = {}) {
    super(mesaj);
    this.name = "ApiHatasi";
    this.durumKodu = durumKodu;
    this.alanHatalari = alanHatalari;
  }

  get kimlikGecersiz(): boolean {
    return this.durumKodu === 401;
  }
}

/** Oturum düştüğünde haberdar olmak isteyen katman (OturumSaglayici) buraya abone olur. */
type OturumDustuDinleyici = () => void;
let oturumDustuDinleyicisi: OturumDustuDinleyici | null = null;

export function oturumDustugundeCalistir(dinleyici: OturumDustuDinleyici | null): void {
  oturumDustuDinleyicisi = dinleyici;
}

function oturumDustu(): void {
  tokenDeposu.temizle();
  oturumDustuDinleyicisi?.();
}

const GENEL_HATA_METINLERI: Record<number, string> = {
  400: "Gönderilen bilgiler geçerli değil.",
  401: "Oturumunuzun süresi doldu. Lütfen yeniden giriş yapın.",
  403: "Bu işlem için yetkiniz yok.",
  404: "Aradığınız kayıt bulunamadı.",
  500: "Sunucuda beklenmeyen bir hata oluştu.",
  502: "Sunucuya ulaşılamıyor.",
  503: "Servis şu anda kullanılamıyor.",
};

/**
 * DRF hata gövdesini okunabilir tek bir cümleye indirger.
 *
 * DRF üç biçim üretebilir:
 *   { "detail": "..." }
 *   { "alan": ["mesaj", ...] }
 *   { "alan": "mesaj" }
 */
function hatayiCozumle(
  govde: unknown,
  durumKodu: number,
): { mesaj: string; alanHatalari: Record<string, string[]> } {
  const yedek = GENEL_HATA_METINLERI[durumKodu] ?? "İstek tamamlanamadı.";

  if (!govde || typeof govde !== "object") {
    return { mesaj: yedek, alanHatalari: {} };
  }

  const kayit = govde as Record<string, unknown>;

  // 404'ün gövdesi Django'nun kendi İngilizce metnidir ("No Mission matches
  // the given query.") ve son kullanıcıya gösterilecek bir içerik değildir.
  // Üstelik bir kaydın var olup olmadığını da ima eder. Bu yüzden 404'te
  // backend metnini DEĞİL kendi mesajımızı kullanıyoruz.
  if (durumKodu === 404) {
    return { mesaj: GENEL_HATA_METINLERI[404], alanHatalari: {} };
  }

  if (typeof kayit.detail === "string") {
    return { mesaj: kayit.detail, alanHatalari: {} };
  }

  const alanHatalari: Record<string, string[]> = {};
  const parcalar: string[] = [];
  for (const [alan, deger] of Object.entries(kayit)) {
    const mesajlar = Array.isArray(deger)
      ? deger.map(String)
      : typeof deger === "string"
        ? [deger]
        : [];
    if (mesajlar.length > 0) {
      alanHatalari[alan] = mesajlar;
      parcalar.push(mesajlar.join(" "));
    }
  }

  return {
    mesaj: parcalar.length > 0 ? parcalar.join(" ") : yedek,
    alanHatalari,
  };
}

async function govdeyiOku(yanit: Response): Promise<unknown> {
  const tur = yanit.headers.get("content-type") ?? "";
  if (!tur.includes("application/json")) return null;
  try {
    return await yanit.json();
  } catch {
    return null;
  }
}

/**
 * Aynı anda birden fazla 401 gelirse TEK yenileme isteği atılır.
 *
 * Eşzamanlı istekler bu sözü paylaşır; aksi halde her 401 kendi yenilemesini
 * başlatır, backend'e aynı refresh ile N istek gider ve yarış oluşur.
 */
let ucustakiYenileme: Promise<string | null> | null = null;

async function tokeniYenile(): Promise<string | null> {
  if (ucustakiYenileme) return ucustakiYenileme;

  const yenilemeTokeni = tokenDeposu.yenilemeTokeni();
  if (!yenilemeTokeni) {
    oturumDustu();
    return null;
  }

  ucustakiYenileme = (async () => {
    try {
      const yanit = await fetch(`${API_TABAN}/api/auth/token/refresh/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: yenilemeTokeni }),
      });

      if (!yanit.ok) {
        // Yenileme başarısız: oturum gerçekten bitti.
        oturumDustu();
        return null;
      }

      const govde = (await yanit.json()) as { access?: string };
      if (!govde.access) {
        oturumDustu();
        return null;
      }
      tokenDeposu.erisimiGuncelle(govde.access);
      return govde.access;
    } catch {
      // Ağ hatası oturumu KAPATMAZ; kullanıcı yeniden deneyebilsin.
      return null;
    } finally {
      ucustakiYenileme = null;
    }
  })();

  return ucustakiYenileme;
}

/** Test yalıtımı için: uçuştaki yenileme sözünü sıfırlar. */
export function yenilemeDurumunuSifirla(): void {
  ucustakiYenileme = null;
}

interface IstekSecenekleri {
  yontem?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  govde?: unknown;
  /** FormData gönderilirken Content-Type'ı tarayıcı kendisi koyar. */
  formVerisi?: FormData;
  /** Yenileme uçlarında sonsuz döngüyü engellemek için. */
  kimlikDogrulamasiz?: boolean;
  signal?: AbortSignal;
}

async function hamIstek(yol: string, secenekler: IstekSecenekleri): Promise<Response> {
  const basliklar: Record<string, string> = {};
  const erisim = tokenDeposu.erisimTokeni();

  if (!secenekler.kimlikDogrulamasiz && erisim) {
    basliklar.Authorization = `Bearer ${erisim}`;
  }

  let govde: BodyInit | undefined;
  if (secenekler.formVerisi) {
    govde = secenekler.formVerisi;
  } else if (secenekler.govde !== undefined) {
    basliklar["Content-Type"] = "application/json";
    govde = JSON.stringify(secenekler.govde);
  }

  return fetch(`${API_TABAN}${yol}`, {
    method: secenekler.yontem ?? "GET",
    headers: basliklar,
    body: govde,
    signal: secenekler.signal,
  });
}

/**
 * Yanıtı ham Response olarak döndürür; 401'de bir kez yeniler ve tekrar dener.
 * Görüntü gibi ikili gövdeler için kullanılır.
 */
export async function istekYap(yol: string, secenekler: IstekSecenekleri = {}): Promise<Response> {
  let yanit = await hamIstek(yol, secenekler);

  if (yanit.status === 401 && !secenekler.kimlikDogrulamasiz) {
    const yeniToken = await tokeniYenile();
    if (!yeniToken) {
      throw new ApiHatasi(GENEL_HATA_METINLERI[401], 401);
    }
    yanit = await hamIstek(yol, secenekler);
  }

  if (!yanit.ok) {
    const govde = await govdeyiOku(yanit);
    const { mesaj, alanHatalari } = hatayiCozumle(govde, yanit.status);
    if (yanit.status === 401) oturumDustu();
    throw new ApiHatasi(mesaj, yanit.status, alanHatalari);
  }

  return yanit;
}

/** JSON döndüren uçlar için. 204 gibi gövdesiz yanıtlarda undefined döner. */
export async function apiIstegi<T>(yol: string, secenekler: IstekSecenekleri = {}): Promise<T> {
  const yanit = await istekYap(yol, secenekler);
  if (yanit.status === 204) return undefined as T;
  return (await yanit.json()) as T;
}

/** Ağ hatası dahil her hatayı gösterilebilir bir metne çevirir. */
export function hataMetni(hata: unknown): string {
  if (hata instanceof ApiHatasi) return hata.message;
  if (hata instanceof Error && hata.name === "AbortError") return "İstek iptal edildi.";
  return "Sunucuya ulaşılamadı. Bağlantınızı kontrol edip yeniden deneyin.";
}
