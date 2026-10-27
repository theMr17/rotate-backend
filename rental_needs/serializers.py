from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers
from decimal import Decimal
from items.models import Item
from orders.serializers import OrderSerializer

from .models import RentalNeed, RentalNeedResponse


class RentalNeedSerializer(serializers.ModelSerializer):

    # Return the requester's name along with their ID.
    requester_name = serializers.CharField(
        source="requester.name",
        read_only=True,
    )

    budget_per_hour = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = RentalNeed

        fields = [
            "id",
            "requester",
            "requester_name",
            "title",
            "description",
            "category",
            "start_time",
            "end_time",
            "location",
            "budget_per_hour",
            "status",
            "fulfilled_order",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "requester",
            "requester_name",
            "status",
            "fulfilled_order",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):

        # For PATCH, use existing values for fields not supplied.
        start_time = attrs.get(
            "start_time",
            self.instance.start_time if self.instance else None,
        )

        end_time = attrs.get(
            "end_time",
            self.instance.end_time if self.instance else None,
        )

        # Start time must be in the future.
        if start_time and start_time <= timezone.now():
            raise serializers.ValidationError({
                "start_time": "Start time must be in the future."
            })

        # End time must be after start time.
        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError({
                "end_time": "End time must be after start time."
            })

        return attrs

class RentalNeedResponseCreateSerializer(serializers.Serializer):

    item = serializers.PrimaryKeyRelatedField(
        queryset=Item.objects.all()
    )

    hourly_rate = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )

    message = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    def validate_item(self, item):

        user = self.context["request"].user

        if item.owner_id != user.id:
            raise serializers.ValidationError(
                "You can only offer items that you own."
            )

        if item.status != "AVAILABLE":
            raise serializers.ValidationError(
                "This item is not available."
            )

        return item


class RentalNeedResponseReadSerializer(serializers.ModelSerializer):

    provider_name = serializers.CharField(
        source="provider.name",
        read_only=True,
    )

    order = OrderSerializer(read_only=True)

    class Meta:
        model = RentalNeedResponse

        fields = [
            "id",
            "provider",
            "provider_name",
            "order",
            "created_at",
        ]

        read_only_fields = fields


class RentalNeedDetailSerializer(RentalNeedSerializer):

    responses = RentalNeedResponseReadSerializer(
        many=True,
        read_only=True,
    )

    class Meta(RentalNeedSerializer.Meta):
        fields = RentalNeedSerializer.Meta.fields + [
            "responses",
        ]