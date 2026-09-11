"""Sistem ilk acilista kullanilabilir olsun diye sahte model surumu.

Hafta 2'de gercek agirlik yok; fake-v0 boru hattini uctan uca calistirmaya
yeter. Hafta 4'te gercek model ayri bir ModelVersion kaydi olarak eklenecek,
bu kayit gecmis kosulari aciklamak icin yerinde kalacak.
"""
from django.db import migrations

FAKE_ADI = "fake-v0"


def ileri(apps, schema_editor):
    ModelVersion = apps.get_model("core", "ModelVersion")
    ModelVersion.objects.update_or_create(
        name=FAKE_ADI,
        defaults={
            "weights_path": "",
            "framework": "fake",
            "input_size": 512,
            "tile_size": 512,
            "overlap_ratio": 0.2,
            "notes": (
                "Sahte dedektor. Gercek model yok; karo basina rastgele 0-3 kutu "
                "uretir ve kutulari frame sha256'sindan tohumlar, yani ayni kare "
                "her zaman ayni sonucu verir. Boru hattini modelin yavasligindan "
                "bagimsiz dogrulamak icin."
            ),
        },
    )


def geri(apps, schema_editor):
    ModelVersion = apps.get_model("core", "ModelVersion")
    # Bu surumle kosu yapilmissa silme: InferenceRun.model_version PROTECT.
    ModelVersion.objects.filter(name=FAKE_ADI, runs__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(ileri, geri),
    ]
