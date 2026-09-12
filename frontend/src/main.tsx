import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import { Uygulama } from "./Uygulama";
import { OturumSaglayici } from "./kimlik/OturumBaglami";
import { sorguIstemcisiOlustur } from "./sorguIstemcisi";
import "./stil.css";

const sorguIstemcisi = sorguIstemcisiOlustur();
const kok = document.getElementById("root");
if (!kok) throw new Error("#root bulunamadı.");

createRoot(kok).render(
  <StrictMode>
    <QueryClientProvider client={sorguIstemcisi}>
      <BrowserRouter>
        <OturumSaglayici>
          <Uygulama />
        </OturumSaglayici>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
