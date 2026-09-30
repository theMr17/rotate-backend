from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Item
from .serializers import ItemSerializer
from .permissions import IsOwnerOrReadOnly


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def item_list(request):

    if request.method == "GET":
        items = Item.objects.all()
        serializer = ItemSerializer(items, many=True)

        return Response(serializer.data)

    elif request.method == "POST":
        serializer = ItemSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(owner=request.user)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_404_BAD_REQUEST
        )


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def item_detail(request, id):

    try:
        item = Item.objects.get(id=id)
    except Item.DoesNotExist:
        return Response(
            {"error": "Item not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    permission = IsOwnerOrReadOnly()

    if not permission.has_object_permission(request, None, item):
        return Response(
            {"error": "You do not have permission to modify this item"},
            status=status.HTTP_403_FORBIDDEN
        )

    if request.method == "GET":
        serializer = ItemSerializer(item)
        return Response(serializer.data)

    elif request.method == "PATCH":
        serializer = ItemSerializer(
            item,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    elif request.method == "DELETE":
        item.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )