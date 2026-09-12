/**
 * Backend uçlarının tek tek karşılıkları.
 *
 * Yollar reports/hafta5_api_sozlesmesi.csv ile birebir aynıdır. Bileşenler
 * fetch çağırmaz; yalnızca buradaki fonksiyonları kullanır.
 */

import { apiIstegi, istekYap } from "./istemci";
import type {
  Bulgu,
  BulguDurumu,
  DenetimKaydi,
  Gorev,
  Inceleme,
  Karar,
  KonumKaynagi,
  KumeYaniti,
  Rol,
  Uyelik,
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

// --- Hafta 6 --------------------------------------------------------------

export function uyeleriGetir(gorevId: number): Promise<SayfaliYanit<Uyelik>> {
  return apiIstegi<SayfaliYanit<Uyelik>>(`/api/missions/${gorevId}/members/`);
}

export function uyeEkle(gorevId: number, kullaniciAdi: string, rol: Rol): Promise<Uyelik> {
  return apiIstegi<Uyelik>(`/api/missions/${gorevId}/members/`, {
    yontem: "POST",
    govde: { username: kullaniciAdi, role: rol },
  });
}

export function uyeRolunuGuncelle(
  gorevId: number,
  uyelikId: number,
  rol: Rol,
): Promise<Uyelik> {
  return apiIstegi<Uyelik>(`/api/missions/${gorevId}/members/${uyelikId}/`, {
    yontem: "PATCH",
    govde: { role: rol },
  });
}

export function uyeCikar(gorevId: number, uyelikId: number): Promise<void> {
  return apiIstegi<void>(`/api/missions/${gorevId}/members/${uyelikId}/`, {
    yontem: "DELETE",
  });
}

export function kosuIncelemeleriniGetir(kosuId: number): Promise<SayfaliYanit<Inceleme>> {
  return apiIstegi<SayfaliYanit<Inceleme>>(`/api/runs/${kosuId}/reviews/`);
}

export function incelemeYaz(
  tespitId: number,
  karar: Karar,
  not: string,
): Promise<Inceleme> {
  return apiIstegi<Inceleme>(`/api/detections/${tespitId}/reviews/`, {
    yontem: "PUT",
    govde: { decision: karar, note: not },
  });
}

export function bulgulariGetir(gorevId: number): Promise<SayfaliYanit<Bulgu>> {
  return apiIstegi<SayfaliYanit<Bulgu>>(`/api/missions/${gorevId}/findings/`);
}

export interface BulguGovdesi {
  title?: string;
  note?: string;
  status?: BulguDurumu;
  latitude?: number | null;
  longitude?: number | null;
  location_source: KonumKaynagi;
  location_note?: string;
  detection?: number | null;
}

export function bulguOlustur(gorevId: number, govde: BulguGovdesi): Promise<Bulgu> {
  return apiIstegi<Bulgu>(`/api/missions/${gorevId}/findings/`, {
    yontem: "POST",
    govde,
  });
}

export function bulguGuncelle(bulguId: number, govde: BulguGovdesi): Promise<Bulgu> {
  return apiIstegi<Bulgu>(`/api/findings/${bulguId}/`, { yontem: "PATCH", govde });
}

export function bulguSil(bulguId: number): Promise<void> {
  return apiIstegi<void>(`/api/findings/${bulguId}/`, { yontem: "DELETE" });
}

export function kumeleriGetir(gorevId: number): Promise<KumeYaniti> {
  return apiIstegi<KumeYaniti>(`/api/missions/${gorevId}/clusters/`);
}

export function kumelemeCalistir(
  gorevId: number,
  esikMetre: number,
): Promise<KumeYaniti & { kume_sayisi: number; kumelenen_bulgu: number }> {
  return apiIstegi(`/api/missions/${gorevId}/clusters/`, {
    yontem: "POST",
    govde: { esik_metre: esikMetre },
  });
}

export function denetimKayitlariniGetir(
  gorevId: number,
  sayfa = 1,
): Promise<SayfaliYanit<DenetimKaydi>> {
  return apiIstegi<SayfaliYanit<DenetimKaydi>>(
    `/api/missions/${gorevId}/audit/?page=${sayfa}`,
  );
}
