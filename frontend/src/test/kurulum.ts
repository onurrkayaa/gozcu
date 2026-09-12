import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

import { yenilemeDurumunuSifirla } from "../api/istemci";

/**
 * jsdom, URL.createObjectURL / revokeObjectURL uygulamaz. Görüntü katmanı
 * blob'u nesne adresine çevirdiği için testte bunların bir karşılığı gerekir.
 * Serbest bırakma çağrıları da sayılabilsin diye vi.fn kullanılır.
 */
const uretilenAdresler = new Set<string>();

beforeEach(() => {
  window.localStorage.clear();
  yenilemeDurumunuSifirla();

  let sayac = 0;
  URL.createObjectURL = vi.fn(() => {
    sayac += 1;
    const adres = `blob:gozcu-test/${sayac}`;
    uretilenAdresler.add(adres);
    return adres;
  });
  URL.revokeObjectURL = vi.fn((adres: string) => {
    uretilenAdresler.delete(adres);
  });
});

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  uretilenAdresler.clear();
});
