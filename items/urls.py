from django.urls import path

from .views import item_detail, item_list, item_quote


urlpatterns = [
    path("items/", item_list, name="item-list"),
    path("items/<int:id>/", item_detail, name="item-detail"),
    path("items/<int:id>/quote/", item_quote, name="item-quote"),
]