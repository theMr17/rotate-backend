from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0004_order_deposit_deducted_order_resolution_note'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='conditionphoto',
            name='image',
        ),
        migrations.AddField(
            model_name='conditionphoto',
            name='image_url',
            field=models.URLField(default='', max_length=500),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='conditionphoto',
            name='image_public_id',
            field=models.CharField(default='', max_length=255),
            preserve_default=False,
        ),
    ]
