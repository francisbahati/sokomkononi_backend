from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .fimipay import create_order, get_order_status
from .serializers import CreateOrderSerializer, OrderStatusSerializer


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def create_order_view(request):
    serializer = CreateOrderSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = create_order(**serializer.validated_data)
    return Response(data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def order_status_view(request):
    serializer = OrderStatusSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = get_order_status(serializer.validated_data["order_id"])
    return Response(data)
