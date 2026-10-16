from django.contrib import admin

from .models import Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "owner",
        "category",
        "hourly_rate",
        "status",
        "created_at",
    )

    list_filter = (
        "category",
        "condition",
        "status",
    )

    search_fields = (
        "title",
        "description",
        "owner__username",
    )