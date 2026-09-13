"""demo_kur komutunun davranis testleri.

Demo, projeyi ilk kez acan kisinin gordugu ilk sey; bozuk bir demo calismayan
bir proje izlenimi verir. Bu testler demo zincirinin kuruldugunu, ikinci kez
calistirildiginda kayitlari ikiye katlamadigini ve uretilen verinin sentetik
oldugunun her katmanda yazili kaldigini dogrular.

Gercek ONNX modeli ve HERIDAL veri kumesi GEREKMEZ: testler sentetik modu
kullanir, tarama Celery'siz (eager) kosar.
"""
import io

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

from core.demo import TANITIM_GOREV_ADI
from core.models import AuditLog, Detection, Finding, Frame, InferenceRun, Mission, Review


@pytest.fixture
def demo_kur(db, celery_eager, django_capture_on_commit_callbacks):
    """Komutu sentetik modda, tek kare ile calistirir."""

    def _calistir(**ek):
        secenekler = {
            "kaynak": "sentetik",
            "kare": 1,
            "parola": "test-parolasi-123",
            # Komut ciktisi test raporunu doldurmasin.
            "stdout": io.StringIO(),
        }
        secenekler.update(ek)
        with django_capture_on_commit_callbacks(execute=True):
            call_command("demo_kur", **secenekler)
        return Mission.objects.get(name=TANITIM_GOREV_ADI)

    return _calistir


class TestZincirKuruluyor:
    def test_gorev_kare_kosu_tespit_inceleme_bulgu_olusuyor(self, demo_kur):
        gorev = demo_kur()
        assert Frame.objects.filter(mission=gorev).count() == 1
        kosu = InferenceRun.objects.get(mission=gorev)
        assert kosu.status == InferenceRun.Status.DONE
        assert Detection.objects.filter(inference_run=kosu).exists()
        assert Review.objects.filter(detection__inference_run=kosu).exists()
        assert Finding.objects.filter(mission=gorev).exists()

    def test_iki_rol_de_uye_ekleniyor(self, demo_kur):
        gorev = demo_kur()
        roller = dict(gorev.members.values_list("user__username", "role"))
        assert roller["demo"] == "owner"
        assert roller["demo_izleyici"] == "viewer"

    def test_denetim_kaydi_yaziliyor(self, demo_kur):
        gorev = demo_kur()
        eylemler = set(
            AuditLog.objects.filter(mission=gorev).values_list("action", flat=True)
        )
        assert AuditLog.Action.RUN_STARTED in eylemler
        assert AuditLog.Action.REVIEW_CREATED in eylemler
        assert AuditLog.Action.FINDING_CREATED in eylemler
        assert AuditLog.Action.CLUSTER_RUN in eylemler


class TestIdempotanslik:
    def test_ikinci_kosu_kayitlari_ikiye_katlamiyor(self, demo_kur):
        ilk = demo_kur()
        ilk_sayimlar = (
            Frame.objects.filter(mission=ilk).count(),
            Finding.objects.filter(mission=ilk).count(),
        )
        ikinci = demo_kur()
        assert ikinci.pk == ilk.pk
        assert (
            Frame.objects.filter(mission=ikinci).count(),
            Finding.objects.filter(mission=ikinci).count(),
        ) == ilk_sayimlar

    def test_sil_yalnizca_demo_gorevini_kaldiriyor(self, demo_kur, db):
        Kullanici = get_user_model()
        baskasi = Kullanici.objects.create_user("baska", password="x-123456789")
        gercek = Mission.objects.create(name="Gercek gorev", created_by=baskasi)
        demo_kur()

        call_command("demo_kur", sil=True, stdout=io.StringIO())

        assert not Mission.objects.filter(name=TANITIM_GOREV_ADI).exists()
        assert Mission.objects.filter(pk=gercek.pk).exists()


class TestSentetikligiGizlemiyor:
    def test_gorev_aciklamasi_sentetik_oldugunu_yaziyor(self, demo_kur):
        gorev = demo_kur()
        assert "sentetik" in gorev.description.lower()
        assert "DEĞİLDİR" in gorev.description or "değildir" in gorev.description

    def test_gorev_adi_konumlarin_sentetik_oldugunu_soyluyor(self, demo_kur):
        assert "sentetik" in demo_kur().name.lower()

    def test_konumlar_demo_kaynagiyla_isaretli(self, demo_kur):
        gorev = demo_kur()
        kaynaklar = set(
            Finding.objects.filter(mission=gorev).values_list("location_source", flat=True)
        )
        assert kaynaklar <= {Finding.LocationSource.DEMO, Finding.LocationSource.NONE}
        assert Finding.LocationSource.DEMO in kaynaklar

    def test_konumsuz_bulgu_sifir_sifira_cevrilmiyor(self, demo_kur):
        gorev = demo_kur()
        konumsuz = Finding.objects.filter(mission=gorev, location__isnull=True)
        assert konumsuz.exists()

    def test_kareler_gercek_gps_tasimiyor(self, demo_kur):
        gorev = demo_kur()
        for kare in Frame.objects.filter(mission=gorev):
            assert kare.latitude is None
            assert kare.longitude is None


class TestParolaKorumasi:
    def test_debug_kapaliyken_varsayilan_parola_reddediliyor(
        self, db, settings, monkeypatch
    ):
        """Parola verilmemisse komut varsayilana duser; DEBUG kapaliyken bu
        kabul EDILMEZ, cunku bilinen bir parola uretim benzeri bir kuruluma
        girmis olur."""
        settings.DEBUG = False
        monkeypatch.delenv("DEMO_PAROLA", raising=False)
        with pytest.raises(CommandError, match="varsayilan demo parolasi"):
            call_command("demo_kur", kaynak="sentetik", kare=1, stdout=io.StringIO())

    def test_gercek_mod_model_yoksa_acik_hata_veriyor(self, db, settings):
        settings.ONNX_MODEL_PATH = ""
        with pytest.raises(CommandError, match="ONNX"):
            call_command(
                "demo_kur", kaynak="gercek", parola="test-parolasi-123",
                stdout=io.StringIO(),
            )
