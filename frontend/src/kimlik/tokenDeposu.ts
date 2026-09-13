/**
 * Token saklama.
 *
 * GÜVENLİK SINIRI (bilinçli seçim, gizlenmiyor):
 *
 * Backend JWT'yi Authorization başlığında bekler (DRF SimpleJWT) ve HTTP-only
 * çerez desteği YOKTUR -- oturum çerezi üreten bir uç mevcut değil. Bu yüzden
 * token'ı tarayıcıda bir yerde tutmak zorundayız ve seçenek localStorage ile
 * bellek arasında kalıyor:
 *
 *   - Yalnızca bellek: XSS'e karşı belirgin şekilde daha iyi DEĞİL (saldırgan
 *     zaten çalışan sayfadan istek atabilir), ama her sayfa yenilemesinde
 *     oturum kapanır. Operatör için kullanılamaz.
 *   - localStorage: sayfa yenilemesinde oturum sürer; bedeli, XSS açığı olursa
 *     token'ın okunabilmesidir.
 *
 * Bu prototipte localStorage seçildi ve risk docs/GUVENLIK.md içinde yazılıdır.
 * HTTP-only çerez desteği eklenirse değişmesi gereken tek yer burasıdır.
 *
 * Token URL'ye, log'a veya Git'e YAZILMAZ.
 */

const ERISIM_ANAHTARI = "gozcu.erisim";
const YENILEME_ANAHTARI = "gozcu.yenileme";

function guvenliOku(anahtar: string): string | null {
  try {
    return window.localStorage.getItem(anahtar);
  } catch {
    // Gizli sekme veya site verisi engelliyse erişim istisna atabilir.
    return null;
  }
}

function guvenliYaz(anahtar: string, deger: string | null): void {
  try {
    if (deger === null) {
      window.localStorage.removeItem(anahtar);
    } else {
      window.localStorage.setItem(anahtar, deger);
    }
  } catch {
    // Yazılamazsa oturum bu sekmede sürer, yenilemede kapanır. Çökmemeli.
  }
}

export const tokenDeposu = {
  erisimTokeni: (): string | null => guvenliOku(ERISIM_ANAHTARI),
  yenilemeTokeni: (): string | null => guvenliOku(YENILEME_ANAHTARI),

  yaz(erisim: string, yenileme: string): void {
    guvenliYaz(ERISIM_ANAHTARI, erisim);
    guvenliYaz(YENILEME_ANAHTARI, yenileme);
  },

  /** Yenileme sonrası: backend YALNIZCA access döner, refresh değişmez. */
  erisimiGuncelle(erisim: string): void {
    guvenliYaz(ERISIM_ANAHTARI, erisim);
  },

  temizle(): void {
    guvenliYaz(ERISIM_ANAHTARI, null);
    guvenliYaz(YENILEME_ANAHTARI, null);
  },
};
