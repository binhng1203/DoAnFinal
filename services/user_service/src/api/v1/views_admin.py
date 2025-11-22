from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from src.apps.core.models import User, Role, Permission
from src.apps.core.permissions import IsAdminRole
from src.api.v1.serializers import UserListAdminSerializer, RoleSerializer, PermissionSerializer, AssignRoleSerializer
from src.apps.core.services import assign_roles

class AdminUserListView(APIView):
    permission_classes = [IsAdminRole]
    def get(self, request):
        qs = User.objects.all().order_by("-created_at")
        return Response(UserListAdminSerializer(qs, many=True).data)

class AdminAssignRoleView(APIView):
    permission_classes = [IsAdminRole]
    def post(self, request, user_id):
        s = AssignRoleSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        n = assign_roles(user_id, [s.validated_data["role_id"]])
        return Response({"inserted": n}, status=status.HTTP_201_CREATED)

class AdminRolesListView(APIView):
    permission_classes = [IsAdminRole]
    def get(self, request):
        return Response(RoleSerializer(Role.objects.all(), many=True).data)

class AdminPermissionsListView(APIView):
    permission_classes = [IsAdminRole]
    def get(self, request):
        return Response(PermissionSerializer(Permission.objects.all(), many=True).data)

