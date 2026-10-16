from decimal import Decimal

from rest_framework import serializers

from .models import Item


class ItemSerializer(serializers.ModelSerializer):
    hourly_rate = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    deposit_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        default=Decimal("0.00"),
    )

    class Meta:
        model = Item
        fields = [
            "id",
            "owner",
            "title",
            "description",
            "category",
            "hourly_rate",
            "deposit_amount",
            "condition",
            "status",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "owner",
            "created_at",
            "updated_at",
        ]