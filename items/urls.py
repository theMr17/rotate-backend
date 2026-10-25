from django.urls import path

from .views import item_detail, item_list, item_quote


urlpatterns = [
    path("items/", item_list),
    path("items/<int:id>/", item_detail),
    path("items/<int:id>/quote/", item_quote),
]