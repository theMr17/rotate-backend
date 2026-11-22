import django.contrib.gis.db.models.fields
from django.contrib.postgres.operations import CreateExtension
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0003_alter_user_managers'),
    ]

    operations = [
        # The PostGIS backend also tries this on connect, but only a superuser
        # can do it there. Keeping it here makes the requirement explicit; on
        # managed databases enable the extension once by hand beforehand.
        CreateExtension('postgis'),
        migrations.AddField(
            model_name='user',
            name='home_address_label',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='user',
            name='home_location',
            field=django.contrib.gis.db.models.fields.PointField(blank=True, geography=True, null=True, srid=4326),
        ),
    ]
