from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import RentalNeed


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