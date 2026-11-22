from rest_framework import serializers

from orders.models import Order

from .models import Review


class ReviewUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    profile_photo_url = serializers.CharField()


class ReviewSerializer(serializers.ModelSerializer):
    reviewer = ReviewUserSerializer(read_only=True)

    class Meta:
        model = Review
        fields = ('id', 'order', 'reviewer', 'reviewee_role', 'rating', 'comment', 'created_at')
        read_only_fields = fields


class ReviewCreateSerializer(serializers.Serializer):
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all())
    rating = serializers.IntegerField(min_value=1, max_value=5)
    comment = serializers.CharField(max_length=1000, required=False, allow_blank=True, default='')
