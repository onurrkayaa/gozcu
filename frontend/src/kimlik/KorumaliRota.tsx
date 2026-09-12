import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";

import { useOturum } from "./useOturum";

/**
 * Giriş yapılmamışsa giriş ekranına yönlendirir.
 *
 * Gidilmek istenen adres state'te taşınır; giriş sonrası kullanıcı aynı yere
 * döner, başa atılmaz.
 */
export function KorumaliRota({ children }: { children: ReactNode }) {
  const { girisYapildiMi } = useOturum();
  const konum = useLocation();

  if (!girisYapildiMi) {
    return <Navigate to="/giris" replace state={{ nereden: konum.pathname }} />;
  }
  return <>{children}</>;
}
