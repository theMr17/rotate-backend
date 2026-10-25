import secrets

from django.db import migrations, models

ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'


def fill_booking_refs(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    used = set(Order.objects.exclude(booking_ref__isnull=True).values_list('booking_ref', flat=True))
    for order in Order.objects.filter(booking_ref__isnull=True):
        ref = None
        while ref is None or ref in used:
            ref = 'ROT-' + ''.join(secrets.choice(ALPHABET) for _ in range(6))
        used.add(ref)
        order.booking_ref = ref
        order.save(update_fields=['booking_ref'])


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_order_lifecycle_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='rental_fee',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='platform_fee',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='total_due',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        # booking_ref: add nullable, backfill existing orders, then make it required + unique.
        migrations.AddField(
            model_name='order',
            name='booking_ref',
            field=models.CharField(editable=False, max_length=16, null=True),
        ),
        migrations.RunPython(fill_booking_refs, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='order',
            name='booking_ref',
            field=models.CharField(editable=False, max_length=16, unique=True),
        ),
    ]
