"""Mevcut gorev sahiplerini uyelik tablosuna tasir.

Hafta 6'ya kadar erisim Mission.created_by uzerinden calisiyordu. Uyelik
tablosu devreye girince o alan tek basina yetki tasimiyor; bu migration
olmadan mevcut butun gorevler sahipleri dahil HERKESE kapanirdi.

Mission.created_by silinmiyor: gecmis kayitlarin kim tarafindan acildigini
aciklamaya devam ediyor. Burada yapilan, ayni bilgiyi yetki tablosuna da
yazmak.

Geri alinabilir: geri yon yalnizca bu migration'in urettigi owner kayitlarini
siler, elle eklenmis uyeliklere dokunmaz.
"""
from django.db import migrations


def ileri(apps, schema_editor):
    Mission = apps.get_model("core", "Mission")
    MissionMember = apps.get_model("core", "MissionMember")

    eklenecek = []
    for mission in Mission.objects.all().iterator():
        if mission.created_by_id is None:
            continue
        # get_or_create yerine once var mi diye bakiyoruz: migration
        # tekrarlanabilir olmali, ikinci kosuda tekillik kisitina carpmamali.
        if MissionMember.objects.filter(
            mission_id=mission.pk, user_id=mission.created_by_id
        ).exists():
            continue
        eklenecek.append(
            MissionMember(
                mission_id=mission.pk,
                user_id=mission.created_by_id,
                role="owner",
                added_by_id=mission.created_by_id,
            )
        )

    MissionMember.objects.bulk_create(eklenecek, batch_size=500)


def geri(apps, schema_editor):
    Mission = apps.get_model("core", "Mission")
    MissionMember = apps.get_model("core", "MissionMember")

    for mission in Mission.objects.all().iterator():
        if mission.created_by_id is None:
            continue
        MissionMember.objects.filter(
            mission_id=mission.pk, user_id=mission.created_by_id, role="owner"
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_review_finding_auditlog_missionmember_and_more"),
    ]

    operations = [
        migrations.RunPython(ileri, geri),
    ]
