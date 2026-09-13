import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

import { etiketlemeEklentisi } from "./arastirma/etiketlemeEklentisi";

// API taban adresi iki yoldan verilebilir:
//   1. VITE_API_TABAN ortam degiskeni (uretim derlemesi icin)
//   2. Asagidaki gelistirme proxy'si (varsayilan, ayar gerektirmez)
// Proxy sayesinde tarayici ayni kaynaktan konusur; CORS ayari gerekmez.
const API_HEDEF = process.env.VITE_API_PROXY_HEDEF ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react(), etiketlemeEklentisi()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: API_HEDEF, changeOrigin: true },
    },
  },
  // Üretim derlemesini yerelde denerken de aynı proxy gerekiyor; aksi halde
  // `vite preview` /api isteklerini kendi sunucusunda arar ve 404 döner.
  preview: {
    port: 4173,
    proxy: {
      "/api": { target: API_HEDEF, changeOrigin: true },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/kurulum.ts"],
    css: false,
  },
});
