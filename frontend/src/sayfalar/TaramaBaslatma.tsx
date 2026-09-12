import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { hataMetni } from "../api/istemci";
import { sorguAnahtarlari } from "../api/sorguAnahtarlari";
import { modelleriGetir, taramaBaslat } from "../api/uclar";
import type { ModelSurumu } from "../api/tipler";
import { HataDurumu, Yukleniyor } from "../bilesenler/durumlar";

/**
 * Varsayılan model seçimi.
 *
 * Model adı veya kimliği SABİT YAZILMAZ: listeden gerçek bir modele bakılır.
 * Tercih, gerçek dedektörü çalıştıran framework == "onnx" kaydının en
 * yenisidir (core/detector.py bu değere göre gerçek ONNX dedektörünü kurar;
 * "fake" sahte dedektörde kalır). Böyle bir kayıt yoksa listenin ilki seçilir.
 */
export function varsayilanModeliSec(modeller: ModelSurumu[]): ModelSurumu | null {
  if (modeller.length === 0) return null;
  const gercekler = modeller.filter((model) => model.framework === "onnx");
  return gercekler[0] ?? modeller[0];
}

interface Ozellikler {
  gorevId: number;
  kareSayisi: number;
  taramaSuruyor: boolean;
  baslatildi: (kosuId: number) => void;
}

export function TaramaBaslatma({
  gorevId,
  kareSayisi,
  taramaSuruyor,
  baslatildi,
}: Ozellikler) {
  const sorguIstemcisi = useQueryClient();
  const [secilenModelId, setSecilenModelId] = useState<number | null>(null);

  const modelSorgusu = useQuery({
    queryKey: sorguAnahtarlari.modeller,
    queryFn: modelleriGetir,
    // Model listesi nadiren değişir; her odaklanmada yeniden çekmeye gerek yok.
    staleTime: 5 * 60 * 1000,
  });

  const modeller = useMemo(
    () => modelSorgusu.data?.results ?? [],
    [modelSorgusu.data],
  );
  const varsayilan = useMemo(() => varsayilanModeliSec(modeller), [modeller]);
  const etkinModelId = secilenModelId ?? varsayilan?.id ?? null;
  const etkinModel = modeller.find((model) => model.id === etkinModelId) ?? null;

  const baslatma = useMutation({
    mutationFn: () => {
      if (etkinModelId === null) {
        throw new Error("Model seçilmedi.");
      }
      return taramaBaslat(gorevId, { model_version_id: etkinModelId });
    },
    onSuccess: (yanit) => {
      sorguIstemcisi.invalidateQueries({ queryKey: sorguAnahtarlari.kosular(gorevId) });
      sorguIstemcisi.invalidateQueries({ queryKey: sorguAnahtarlari.gorev(gorevId) });
      sorguIstemcisi.invalidateQueries({ queryKey: sorguAnahtarlari.gorevler });
      baslatildi(yanit.run_id);
    },
  });

  if (modelSorgusu.isPending) return <Yukleniyor metin="Modeller yükleniyor…" />;
  if (modelSorgusu.isError) {
    return (
      <HataDurumu
        mesaj={hataMetni(modelSorgusu.error)}
        yenidenDene={() => modelSorgusu.refetch()}
      />
    );
  }

  const kareYok = kareSayisi === 0;
  // Buton üç nedenden kilitlenebilir; hepsinin gerekçesi kullanıcıya yazılır.
  const kilitli =
    baslatma.isPending || taramaSuruyor || kareYok || etkinModelId === null;

  return (
    <div className="kart">
      <h2>Tarama başlat</h2>

      {baslatma.isError && (
        <div className="bildirim hata" role="alert">
          {hataMetni(baslatma.error)}
        </div>
      )}

      <div className="alan">
        <label htmlFor="modelSecimi">Model</label>
        <select
          id="modelSecimi"
          value={etkinModelId ?? ""}
          onChange={(olay) => setSecilenModelId(Number(olay.target.value))}
          disabled={baslatma.isPending || taramaSuruyor}
          aria-describedby="modelYardim"
        >
          {modeller.map((model) => (
            <option key={model.id} value={model.id}>
              {model.name} ({model.framework})
            </option>
          ))}
        </select>
        <div id="modelYardim" className="yardim-metni">
          {etkinModel?.framework === "fake"
            ? "Bu kayıt sahte dedektördür: gerçek model çalıştırmaz, boru hattını sınamak içindir."
            : "Karo boyutu ve örtüşme model kaydından gelir; tarama bu değerlerle çalışır."}
          {etkinModel && (
            <>
              {" "}
              Karo {etkinModel.tile_size} px, örtüşme{" "}
              {(etkinModel.overlap_ratio * 100).toFixed(0)}%.
            </>
          )}
        </div>
      </div>

      <button
        type="button"
        className="birincil"
        onClick={() => {
          // Çift tarama koruması: mutation uçarken veya koşu sürerken basılmaz.
          if (kilitli) return;
          baslatma.mutate();
        }}
        disabled={kilitli}
      >
        {baslatma.isPending ? "Başlatılıyor…" : "Taramayı başlat"}
      </button>

      {kareYok && (
        <div className="yardim-metni">
          Görevde kare yok. Tarama başlatmadan önce en az bir görüntü ekleyin.
        </div>
      )}
      {taramaSuruyor && (
        <div className="yardim-metni">
          Bu görevde bir tarama sürüyor. Bitmesini bekleyin.
        </div>
      )}
    </div>
  );
}
