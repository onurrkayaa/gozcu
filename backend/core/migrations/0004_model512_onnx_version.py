"""Gercek Model-512 ONNX surumu.

Hafta 4: karolanmis 512 px veriyle egitilen yolo11n agirligi ONNX'e aktarildi
(scripts/17_model512_onnx_export.py). Kosu bu kayitla baslatildiginda
core.detector.get_detector gercek ONNX dedektorunu kurar.

weights_path yalnizca hangi yapinin kastedildigini soyler; dosyanin calisma
anindaki yeri ONNX_MODEL_PATH ortam degiskeninden okunur, cunku agirlik depoya
girmez ve konteynerde /models altina baglanir.

Sahte surum (fake-v0) silinmez: gecmis kosulari aciklar ve testlerde
kullanilmaya devam eder.
"""
from django.db import migrations

ONNX_ADI = "model512-onnx"


def ileri(apps, schema_editor):
    ModelVersion = apps.get_model("core", "ModelVersion")
    ModelVersion.objects.update_or_create(
        name=ONNX_ADI,
        defaults={
            "weights_path": "agirliklar/model512_best.onnx",
            "framework": "onnx",
            "input_size": 512,
            "tile_size": 512,
            "overlap_ratio": 0.2,
            "notes": (
                "Model-512 (yolo11n, 512 px karolar, 100 epoch) ONNX disa aktarimi. "
                "Kaynak .pt sha256 66a93278a16e1cf720052dbde975f9c5b13ab3881e2416dd1"
                "bd78d6815fdf3b7, ONNX sha256 361731351703f4581f95871c26583eba760f08"
                "ed26493869cc864c8c57f55dbd; kimlik kaydi reports/model512_onnx_bilgisi.csv. "
                "PyTorch ile ONNX ayni protokolde olculdu ve uc esikte de TP/FN/FP, "
                "recall, FP/goruntu ve precision ayni cikti (reports/pytorch_onnx_metrik.csv). "
                "Dosya yolu ONNX_MODEL_PATH ortam degiskeninden gelir."
            ),
        },
    )


def geri(apps, schema_editor):
    ModelVersion = apps.get_model("core", "ModelVersion")
    # Bu surumle kosu yapilmissa silme: InferenceRun.model_version PROTECT.
    ModelVersion.objects.filter(name=ONNX_ADI, runs__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_fake_model_version"),
    ]

    operations = [
        migrations.RunPython(ileri, geri),
    ]
