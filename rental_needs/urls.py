from django.urls import path

from .views import (
    RentalNeedListCreateView,
    RentalNeedDetailView,
    RentalNeedCancelView,
)


urlpatterns = [

    path(
        "rental-needs/",
        RentalNeedListCreateView.as_view(),
        name="rental-need-list-create",
    ),

    path(
        "rental-needs/<int:pk>/",
        RentalNeedDetailView.as_view(),
        name="rental-need-detail",
    ),

    path(
        "rental-needs/<int:pk>/cancel/",
        RentalNeedCancelView.as_view(),
        name="rental-need-cancel",
    ),
]