from django.contrib import admin

from .models import ReliabilityStats, Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'reviewer', 'reviewee', 'reviewee_role', 'rating', 'created_at')
    list_filter = ('reviewee_role', 'rating')
    search_fields = ('reviewer__email', 'reviewee__email', 'comment')
    raw_id_fields = ('order', 'reviewer', 'reviewee')


@admin.register(ReliabilityStats)
class ReliabilityStatsAdmin(admin.ModelAdmin):
    list_display = ('user', 'score', 'rentals_counted', 'late_returns', 'late_cancellations', 'updated_at')
    search_fields = ('user__email',)
    raw_id_fields = ('user',)
