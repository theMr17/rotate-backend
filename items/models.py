from django.db import models

# Create your models here.
class Item(models.Model):
    CONDITION_CHOICES = [ 
        ('NEW', 'New'),
        ('GOOD', 'Good'),
        ('FAIR', 'Fair'),
        ('POOR', 'Poor')
    ]

    STATUS_CHOICES = [
        ("AVAILABLE", "Available"),
        ("UNAVAILABLE", "Unavailable"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="items"
    )

    title = models.CharField(max_length=200)
    description = models.TextField()

    category = models.CharField(max_length=100)

    rate = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    deposit_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    condition = models.CharField(
        max_length=10,
        choices=CONDITION_CHOICES
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="AVAILABLE"
    )

    created_at = models.DateTimeField(auto_now_add = TRUE)
    updated_at = models.DateTimeField(auto_now=TRUE)

    