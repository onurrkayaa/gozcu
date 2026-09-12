/**
 * Backend uçlarının tek tek karşılıkları.
 *
 * Yollar reports/hafta5_api_sozlesmesi.csv ile birebir aynıdır. Bileşenler
 * fetch çağırmaz; yalnızca buradaki fonksiyonları kullanır.
 */

import { apiIstegi, istekYap } from "./istemci";
import type {
  Gorev,
  Kare,
  KareYuklemeSonucu,
  Kosu,
  ModelSurumu,
  SayfaliYanit,
  TaramaBaslatmaGovdesi,
  TaramaBaslatmaYaniti,
  Tespit,
  TokenCifti,
} from "./tipler";

// --- Kimlik ---------------------------------------------------------------

export function girisYap(kullaniciAdi: string, parola: string): Promise<TokenCifti> {
  return apiIstegi<TokenCifti>("/api/auth/token/", {
    yontem: "POST",
    govde: { username: kullaniciAdi, password: parola },
    kimlikDogrulamasiz: true,
  });
}

// --- Görevler -------------------------------------------------------------

export function gorevleriGetir(sayfa = 1): Promise<SayfaliYanit<Gorev>> {
  return apiIstegi<SayfaliYanit<Gorev>>(`/api/missions/?page=${sayfa}`);
}

export function gorevGetir(gorevId: number): Promise<Gorev> {
  return apiIstegi<Gorev>(`/api/missions/${gorevId}/`);
}

export function gorevOlustur(ad: string, aciklama: string): Promise<Gorev> {
  return apiIstegi<Gorev>("/api/missions/", {
    yontem: "POST",
    govde: { name: ad, description: aciklama },
  });
}

// --- Kareler --------------------------------------------------------------

export function kareleriGetir(gorevId: number, sayfa = 1): Promise<SayfaliYanit<Kare>> {
  return apiIstegi<SayfaliYanit<Kare>>(`/api/missions/${gorevId}/frames/?page=${sayfa}`);
}

/**
 * TEK dosya yükler.
 *
 * Backend tek istekte birden çok dosya kabul eder, ama dosyalardan biri
 * bozuksa TÜM istek 400 döner (core/views.py: MissionFrameListCreateView.post
 * ValidationError atıyor). Kullanıcıya dosya bazında sonuç gösterebilmek için
 * arayüz dosyaları tek tek gönderir: biri düşerse diğerleri yüklenmiş kalır.
 */
export async function kareYukle(gorevId: number, dosya: File): Promise<KareYuklemeSonucu> {
  const form = new FormData();
  form.append("images", dosya);
  const sonuc = await apiIstegi<KareYuklemeSonucu[]>(`/api/missions/${gorevId}/frames/`, {
    yontem: "POST",
    formVerisi: form,
  });
  return sonuc[0];
}

/**
 * Kare görüntüsünü blob olarak indirir.
 *
 * Token Authorization başlığında gider; URL'ye KONULMAZ. Çağıran, dönen
 * nesne URL'sini işi bitince URL.revokeObjectURL ile bırakmalıdır.
 */
export async function kareGoruntusunuGetir(
  kareId: number,
  signal?: AbortSignal,
): Promise<Blob> {
  const yanit = await istekYap(`/api/frames/${kareId}/image/`, { signal });
  return yanit.blob();
}

// --- Modeller -------------------------------------------------------------

export function modelleriGetir(): Promise<SayfaliYanit<ModelSurumu>> {
  return apiIstegi<SayfaliYanit<ModelSurumu>>("/api/models/");
}

// --- Koşular --------------------------------------------------------------

export function kosulariGetir(gorevId: number): Promise<SayfaliYanit<Kosu>> {
  return apiIstegi<SayfaliYanit<Kosu>>(`/api/missions/${gorevId}/runs/`);
}

export function kosuGetir(kosuId: number): Promise<Kosu> {
  return apiIstegi<Kosu>(`/api/runs/${kosuId}/`);
}

export function taramaBaslat(
  gorevId: number,
  govde: TaramaBaslatmaGovdesi,
): Promise<TaramaBaslatmaYaniti> {
  return apiIstegi<TaramaBaslatmaYaniti>(`/api/missions/${gorevId}/runs/`, {
    yontem: "POST",
    govde,
  });
}

// --- Tespitler ------------------------------------------------------------

/**
 * Koşunun tespitleri.
 *
 * minSkor, GÖRÜNTÜLEME eşiğidir: modeli yeniden çalıştırmaz, yalnızca
 * okunacak kayıtları süzer. Backend kutuları sabit bir tabanla
 * (DETECTION_STORE_FLOOR = 0,05) sakladığı için tek bir taramadan farklı
 * eşikler sorulabilir.
 */
export function tespitleriGetir(
  kosuId: number,
  secenekler: { kareId?: number; minSkor?: number; sayfa?: number } = {},
): Promise<SayfaliYanit<Tespit>> {
  const parametreler = new URLSearchParams();
  if (secenekler.kareId !== undefined) parametreler.set("frame_id", String(secenekler.kareId));
  if (secenekler.minSkor !== undefined) parametreler.set("min_score", String(secenekler.minSkor));
  parametreler.set("page", String(secenekler.sayfa ?? 1));
  return apiIstegi<SayfaliYanit<Tespit>>(`/api/runs/${kosuId}/detections/?${parametreler}`);
}
