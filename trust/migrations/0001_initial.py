import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('orders', '0002_offer'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ReliabilityStats',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('rentals_counted', models.PositiveIntegerField(default=0)),
                ('on_time_returns', models.PositiveIntegerField(default=0)),
                ('late_returns', models.PositiveIntegerField(default=0)),
                ('late_cancellations', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='reliability', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'reliability stats',
                'constraints': [models.CheckConstraint(condition=models.Q(('score__isnull', True), ('score__lte', 100), _connector='OR'), name='reliability_score_0_to_100')],
            },
        ),
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reviewee_role', models.CharField(choices=[('lender', 'Lender'), ('borrower', 'Borrower')], max_length=10)),
                ('rating', models.PositiveSmallIntegerField()),
                ('comment', models.TextField(blank=True, max_length=1000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='orders.order')),
                ('reviewee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews_received', to=settings.AUTH_USER_MODEL)),
                ('reviewer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews_given', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['reviewee', 'reviewee_role'], name='trust_revie_reviewe_a6e289_idx')],
                'constraints': [models.UniqueConstraint(fields=('order', 'reviewer'), name='one_review_per_order_per_reviewer'), models.CheckConstraint(condition=models.Q(('rating__gte', 1), ('rating__lte', 5)), name='review_rating_1_to_5')],
            },
        ),
    ]
