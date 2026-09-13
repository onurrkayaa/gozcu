/**
 * Kör etiketleme aracının giriş noktası.
 *
 * Operatör uygulamasından AYRI bir HTML girişidir: ortak kabuk, oturum ve
 * yönlendirme kullanılmaz. Üretim derlemesi yalnızca index.html'i paketlediği
 * için bu sayfa dağıtıma girmez.
 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { EtiketlemeAraci } from "./EtiketlemeAraci";
import "./etiketleme.css";

createRoot(document.getElementById("kok")!).render(
  <StrictMode>
    <main className="arastirma-kabuk">
      <h1>Kör yanlış pozitif bağlam etiketlemesi</h1>
      <p className="arastirma-bilgi">
        Yerel araştırma aracı. Üretim arayüzünün parçası değildir ve operatör
        oturumuyla ilgisi yoktur.
      </p>
      <EtiketlemeAraci />
    </main>
  </StrictMode>,
);
