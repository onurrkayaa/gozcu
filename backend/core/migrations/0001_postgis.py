from django.contrib.postgres.operations import CreateExtension
from django.db import migrations


class Migration(migrations.Migration):
    """PostGIS eklentisini acar. Cografi alanlar sonraki adimlarda eklenecek."""

    initial = True

    dependencies = []

    operations = [CreateExtension("postgis")]
