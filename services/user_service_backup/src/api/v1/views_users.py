from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from src.api.v1.serializers import UserMeSerializer, UserMeUpdateSerializer

class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserMeSerializer(request.user).data)

    def put(self, request):
        s = UserMeUpdateSerializer(instance=request.user, data=request.data, partial=False)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(UserMeSerializer(request.user).data, status=status.HTTP_200_OK)

