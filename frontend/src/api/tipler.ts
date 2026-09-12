/**
 * Backend sözleşmesinin TypeScript karşılığı.
 *
 * Buradaki her alan gerçek serializer çıktısından alınmıştır; uydurma alan
 * yoktur. Karşılığı: reports/hafta5_api_sozlesmesi.csv ve
 * backend/core/serializers.py.
 *
 * Durum değerleri backend enum'larıyla BİREBİR aynıdır (core/models.py:
 * Frame.Status, InferenceRun.Status). Arayüzde gösterilecek Türkçe metinler
 * ayrı bir eşlemede durur; enum değerinin kendisi çevrilmez.
 */

/** core/models.py: Frame.Status */
export const KARE_DURUMLARI = [
  "pending",
  "queued",
  "processing",
  "done",
  "failed",
] as const;
export type KareDurumu = (typeof KARE_DURUMLARI)[number];

/** core/models.py: InferenceRun.Status */
export const KOSU_DURUMLARI = ["pending", "running", "done", "failed"] as const;
export type KosuDurumu = (typeof KOSU_DURUMLARI)[number];

/**
 * Koşu bittiğinde artık yoklama yapılmayacak durumlar.
 *
 * finalize_run, kareler kısmen başarısız olsa bile koşuyu "done" yapar; bu
 * yüzden "failed" tek başına kısmi başarısızlık anlamına GELMEZ, koşunun
 * tamamının düştüğü anlamına gelir.
 */
export const TERMINAL_KOSU_DURUMLARI: readonly KosuDurumu[] = ["done", "failed"];

export function kosuTerminalMi(durum: KosuDurumu): boolean {
  return TERMINAL_KOSU_DURUMLARI.includes(durum);
}

/** DRF PageNumberPagination; PAGE_SIZE = 20 */
export interface SayfaliYanit<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface TokenCifti {
  access: string;
  refresh: string;
}

/** /api/auth/token/refresh/ YALNIZCA access döner; refresh döndürülmez. */
export interface YenilemeYaniti {
  access: string;
}

/** Görevin kare sayımları. Sıfır olan durum da anahtar olarak bulunur. */
export type KareSayimlari = Record<KareDurumu, number>;

export interface KosuOzeti {
  id: number;
  status: KosuDurumu;
  model_version: number;
  model_version_name: string;
  conf_threshold: number;
  frames_total: number;
  frames_done: number;
  frames_failed: number;
  started_at: string;
  finished_at: string | null;
}

export interface Gorev {
  id: number;
  name: string;
  description: string;
  created_by: number;
  created_at: string;
  updated_at: string;
  frame_count: number;
  frame_counts: KareSayimlari;
  latest_run: KosuOzeti | null;
}

export interface Kare {
  id: number;
  mission: number;
  /**
   * MEDIA_URL adresi. Kimlik doğrulaması OLMADAN servis edildiği için arayüz
   * bunu KULLANMAZ; görüntü /api/frames/{id}/image/ ucundan Authorization
   * başlığıyla okunur.
   */
  image: string;
  original_filename: string;
  sha256: string;
  width: number;
  height: number;
  /** HERIDAL görüntülerinde EXIF silinmiş olduğu için bu üçü daima null. */
  captured_at: string | null;
  latitude: number | null;
  longitude: number | null;
  altitude_m: number | null;
  status: KareDurumu;
  created_at: string;
}

export interface ModelSurumu {
  id: number;
  name: string;
  /** "onnx" gerçek model, "fake" sahte dedektör (core/detector.py). */
  framework: string;
  input_size: number;
  tile_size: number;
  overlap_ratio: number;
  notes: string;
  created_at: string;
}

export interface Kosu {
  id: number;
  mission: number;
  model_version: number;
  model_version_name: string;
  status: KosuDurumu;
  conf_threshold: number;
  iou_threshold: number;
  tile_size: number;
  overlap_ratio: number;
  frames_total: number;
  frames_done: number;
  frames_failed: number;
  started_at: string;
  finished_at: string | null;
}

/**
 * Tespit kutusu.
 *
 * KOORDİNAT UZAYI: x1/y1/x2/y2 ORİJİNAL görüntü pikselidir (karo düzlemi
 * değil) ve tam sayıdır. Backend bunları frame.width/height ile sınırlar.
 */
export interface Tespit {
  id: number;
  inference_run: number;
  frame: number;
  score: number;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  tile_row: number | null;
  tile_col: number | null;
  created_at: string;
}

/** POST /api/missions/{id}/frames/ yanıtındaki dosya başına sonuç. */
export interface KareYuklemeSonucu {
  id: number;
  filename: string;
  /** Aynı görevde aynı sha256: yeni kayıt açılmadı, mevcut kayıt döndü. */
  duplicate: boolean;
  width: number;
  height: number;
}

/** POST /api/missions/{id}/runs/ -- 202 yanıtı. */
export interface TaramaBaslatmaYaniti {
  run_id: number;
  status: KosuDurumu;
  frames_total: number;
}

export interface TaramaBaslatmaGovdesi {
  model_version_id: number;
  conf_threshold?: number;
  iou_threshold?: number;
  tile_size?: number;
  overlap_ratio?: number;
}
