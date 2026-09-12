import { useContext } from "react";

import { OturumBaglami } from "./OturumBaglami";
import type { OturumDurumu } from "./OturumBaglami";

/**
 * Oturum durumunu okur.
 *
 * Ad "use" ile başlar: React'in kanca kuralları (rules-of-hooks) özel
 * kancaların bu önekle adlandırılmasını şart koşar, arayüzün Türkçe olması
 * bu kuralı değiştirmez.
 */
export function useOturum(): OturumDurumu {
  const baglam = useContext(OturumBaglami);
  if (!baglam) {
    throw new Error("useOturum yalnızca OturumSaglayici içinde kullanılabilir.");
  }
  return baglam;
}
