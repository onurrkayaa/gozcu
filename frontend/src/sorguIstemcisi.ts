import { QueryClient } from "@tanstack/react-query";

import { ApiHatasi } from "./api/istemci";

/**
 * Ortak sorgu istemcisi ayarları.
 *
 * 401 ve 404 YENİDEN DENENMEZ: ilkinde istemci katmanı zaten token yenilemesi
 * yapıp bir kez tekrar denedi, ikincisinde kayıt yok. Tekrar denemek yalnızca
 * kullanıcıyı bekletir.
 */
export function sorguIstemcisiOlustur(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (denemeSayisi, hata) => {
          if (hata instanceof ApiHatasi && [401, 403, 404].includes(hata.durumKodu)) {
            return false;
          }
          return denemeSayisi < 2;
        },
        staleTime: 10_000,
        refetchOnWindowFocus: false,
      },
      mutations: { retry: false },
    },
  });
}
