/**
 * Görev üyeleri.
 *
 * Owner ekleyip çıkarabilir ve rol değiştirebilir; diğer roller listeyi
 * yalnızca okur. Arayüz yetkiye göre denetimleri gizler, ama karar backend'in:
 * gizlenen bir düğmenin isteği yine de reddedilir.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { hataMetni } from "../api/istemci";
import { sorguAnahtarlari } from "../api/sorguAnahtarlari";
import { uyeCikar, uyeEkle, uyeleriGetir, uyeRolunuGuncelle } from "../api/uclar";
import type { Rol } from "../api/tipler";
import { ROLLER, yonetebilirMi } from "../api/tipler";
import { BosDurum, HataDurumu, Yukleniyor, zamanMetni } from "../bilesenler/durumlar";

const ROL_ETIKETLERI: Record<Rol, string> = {
  owner: "Sahip",
  operator: "Operatör",
  viewer: "İzleyici",
};

const ROL_ACIKLAMALARI: Record<Rol, string> = {
  owner: "Üyeleri ve rolleri yönetir; operatörün yaptığı her şeyi yapabilir.",
  operator: "Kare ekler, tarama başlatır, inceleme ve bulgu yazar.",
  viewer: "Yalnızca okur; hiçbir şey değiştiremez.",
};

export function UyeYonetimi({ gorevId, rol }: { gorevId: number; rol: Rol | null }) {
  const sorguIstemcisi = useQueryClient();
  const [kullaniciAdi, setKullaniciAdi] = useState("");
  const [yeniRol, setYeniRol] = useState<Rol>("viewer");

  const yonetebilir = yonetebilirMi(rol);

  const sorgu = useQuery({
    queryKey: sorguAnahtarlari.uyeler(gorevId),
    queryFn: () => uyeleriGetir(gorevId),
  });

  function tazele() {
    sorguIstemcisi.invalidateQueries({ queryKey: sorguAnahtarlari.uyeler(gorevId) });
    sorguIstemcisi.invalidateQueries({
      queryKey: sorguAnahtarlari.denetimiGecersizKil(gorevId),
    });
  }

  const ekleme = useMutation({
    mutationFn: () => uyeEkle(gorevId, kullaniciAdi.trim(), yeniRol),
    onSuccess: () => {
      setKullaniciAdi("");
      tazele();
    },
  });

  const rolGuncelleme = useMutation({
    mutationFn: ({ uyelikId, rol: hedef }: { uyelikId: number; rol: Rol }) =>
      uyeRolunuGuncelle(gorevId, uyelikId, hedef),
    onSuccess: tazele,
  });

  const cikarma = useMutation({
    mutationFn: (uyelikId: number) => uyeCikar(gorevId, uyelikId),
    onSuccess: tazele,
  });

  const uyeler = sorgu.data?.results ?? [];
  const sahipSayisi = uyeler.filter((u) => u.role === "owner").length;
  const islemHatasi = ekleme.error ?? rolGuncelleme.error ?? cikarma.error;

  return (
    <div className="kart">
      <h2>Görev üyeleri</h2>

      {sorgu.isPending && <Yukleniyor metin="Üyeler yükleniyor…" />}
      {sorgu.isError && (
        <HataDurumu mesaj={hataMetni(sorgu.error)} yenidenDene={() => sorgu.refetch()} />
      )}
      {sorgu.isSuccess && uyeler.length === 0 && <BosDurum metin="Üye yok." />}

      {islemHatasi && (
        <div className="bildirim hata" role="alert">
          {hataMetni(islemHatasi)}
        </div>
      )}

      {uyeler.length > 0 && (
        <div className="tablo-sarmal">
          <table>
            <caption className="gorsel-gizli">
              Görev üyeleri: kullanıcı adı, rol ve eklenme zamanı
            </caption>
            <thead>
              <tr>
                <th scope="col">Kullanıcı</th>
                <th scope="col">Rol</th>
                <th scope="col">Eklenme</th>
                {yonetebilir && <th scope="col">İşlem</th>}
              </tr>
            </thead>
            <tbody>
              {uyeler.map((uyelik) => {
                const sonSahip = uyelik.role === "owner" && sahipSayisi <= 1;
                return (
                  <tr key={uyelik.id}>
                    <td>{uyelik.user.username}</td>
                    <td>
                      {yonetebilir ? (
                        <select
                          aria-label={`${uyelik.user.username} rolü`}
                          value={uyelik.role}
                          disabled={sonSahip || rolGuncelleme.isPending}
                          onChange={(olay) =>
                            rolGuncelleme.mutate({
                              uyelikId: uyelik.id,
                              rol: olay.target.value as Rol,
                            })
                          }
                        >
                          {ROLLER.map((secenek) => (
                            <option key={secenek} value={secenek}>
                              {ROL_ETIKETLERI[secenek]}
                            </option>
                          ))}
                        </select>
                      ) : (
                        ROL_ETIKETLERI[uyelik.role]
                      )}
                      {sonSahip && (
                        <div className="kucuk sonuk">Görevin son sahibi</div>
                      )}
                    </td>
                    <td className="kucuk sonuk">{zamanMetni(uyelik.created_at)}</td>
                    {yonetebilir && (
                      <td>
                        <button
                          type="button"
                          className="tehlikeli"
                          disabled={sonSahip || cikarma.isPending}
                          onClick={() => cikarma.mutate(uyelik.id)}
                        >
                          Çıkar
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {yonetebilir ? (
        <form
          style={{ marginTop: "1rem" }}
          onSubmit={(olay) => {
            olay.preventDefault();
            if (!kullaniciAdi.trim() || ekleme.isPending) return;
            ekleme.mutate();
          }}
        >
          <h3>Üye ekle</h3>
          <div className="satir">
            <div className="alan" style={{ flex: "1 1 200px", marginBottom: 0 }}>
              <label htmlFor="uyeKullaniciAdi">Kullanıcı adı</label>
              <input
                id="uyeKullaniciAdi"
                type="text"
                value={kullaniciAdi}
                onChange={(olay) => setKullaniciAdi(olay.target.value)}
                aria-describedby="uyeEklemeYardim"
              />
            </div>
            <div className="alan" style={{ flex: "0 1 180px", marginBottom: 0 }}>
              <label htmlFor="uyeRolu">Rol</label>
              <select
                id="uyeRolu"
                value={yeniRol}
                onChange={(olay) => setYeniRol(olay.target.value as Rol)}
              >
                {ROLLER.map((secenek) => (
                  <option key={secenek} value={secenek}>
                    {ROL_ETIKETLERI[secenek]}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="submit"
              className="birincil"
              disabled={!kullaniciAdi.trim() || ekleme.isPending}
            >
              {ekleme.isPending ? "Ekleniyor…" : "Ekle"}
            </button>
          </div>
          <div id="uyeEklemeYardim" className="yardim-metni">
            {ROL_ACIKLAMALARI[yeniRol]} Kullanıcının sistemde kayıtlı olması
            gerekir; arayüz kullanıcı listesi göstermez, çünkü görev üyesi
            olmayan kişilerin adlarını listelemek gereksiz bir bilgi paylaşımı
            olurdu.
          </div>
        </form>
      ) : (
        <p className="salt-okunur-notu" data-testid="uye-salt-okunur">
          Üyeleri yalnızca görev sahibi yönetebilir.
        </p>
      )}
    </div>
  );
}
