from django.contrib import admin
from .models import RentalNeed, RentalNeedResponse


@admin.register(RentalNeed)
class RentalNeedAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "requester",
        "location",
        "start_time",
        "end_time",
        "status",
        "created_at",
    )

    list_filter = ("status", "category")
    search_fields = ("title", "description", "location", "requester__email")


@admin.register(RentalNeedResponse)
class RentalNeedResponseAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "rental_need",
        "provider",
        "order",
        "created_at",
    )

    search_fields = (
        "provider__email",
        "rental_need__title",
    )