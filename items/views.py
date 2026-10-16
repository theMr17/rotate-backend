from django.db.models import Q
from django.db.models.deletion import ProtectedError

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .models import Item
from .permissions import IsOwnerOrReadOnly
from .serializers import ItemSerializer


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedOrReadOnly])
def item_list(request):
    # GET /api/items/
    if request.method == "GET":

        # Public catalogue: show available listings by default.
        if request.query_params.get("mine", "").lower() == "true":
            if not request.user.is_authenticated:
                return Response(
                    {"detail": "Authentication required to view your listings."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            items = Item.objects.filter(owner=request.user)
        else:
            items = Item.objects.filter(status="AVAILABLE")

        # Optional category filter:
        # /api/items/?category=Electronics
        category = request.query_params.get("category")
        if category:
            items = items.filter(category__iexact=category)

        # Optional title/description search:
        # /api/items/?search=camera
        search = request.query_params.get("search")
        if search:
            items = items.filter(
                Q(title__icontains=search)
                | Q(description__icontains=search)
            )

        serializer = ItemSerializer(items, many=True)
        return Response(serializer.data)

    # POST /api/items/
    serializer = ItemSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    item = serializer.save(owner=request.user)

    return Response(
        ItemSerializer(item).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticatedOrReadOnly])
def item_detail(request, id):

    try:
        item = Item.objects.get(id=id)
    except Item.DoesNotExist:
        return Response(
            {"detail": "Item not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Only the owner may modify or delete the listing.
    permission = IsOwnerOrReadOnly()

    if not permission.has_object_permission(request, None, item):
        return Response(
            {"detail": "You do not have permission to modify this item."},
            status=status.HTTP_403_FORBIDDEN,
        )

    # GET /api/items/<id>/
    if request.method == "GET":
        serializer = ItemSerializer(item)
        return Response(serializer.data)

    # PATCH /api/items/<id>/
    if request.method == "PATCH":
        serializer = ItemSerializer(
            item,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        serializer.save()

        return Response(serializer.data)

    # DELETE /api/items/<id>/
    if request.method == "DELETE":
        try:
            item.delete()
        except ProtectedError:
            return Response(
                {
                    "detail": (
                        "This item has associated rental orders and cannot "
                        "be deleted. Mark it UNAVAILABLE instead."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)