from rest_framework import serializers
from .models import Item


class ItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = Item
        fields = [
            "id",
            "owner",
            "title",
            "description",
            "category",
            "rate",
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