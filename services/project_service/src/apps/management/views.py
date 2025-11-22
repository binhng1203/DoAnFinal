from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction

from .models import Project, ProjectMember
from .serializers import ProjectSerializer, ProjectUpdateSerializer, JoinProjectSerializer
from .permissions import IsProjectAdmin, IsProjectMember
from django.shortcuts import get_object_or_404
from .serializers import ProjectMemberSerializer, AddMemberSerializer

from .models import TestSuite 
from .serializers import TestSuiteSerializer, TestSuiteListSerializer

from .models import TestCase, TestSuite 
from .serializers import TestCaseSerializer

# API 1 & 2: List Projects & Create Project
class ProjectListCreateView(generics.ListCreateAPIView):
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # BR4.1, 4.2: Chỉ lấy các dự án mà user hiện tại là thành viên 
        return Project.objects.filter(
            members__user_id=self.request.user.user_id
        ).order_by('-created_at')

# API 3: Retrieve, Update, Destroy Project
class ProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Project.objects.all()
    lookup_field = 'project_id'
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return ProjectUpdateSerializer
        return ProjectSerializer

    def get_permissions(self):
        # BR3.1, BR2.1: Chỉ Admin mới được Sửa/Xóa 
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [permissions.IsAuthenticated(), IsProjectAdmin()]
        # Xem chi tiết thì chỉ cần là Member
        return [permissions.IsAuthenticated(), IsProjectMember()]

# API 4: Join Project
class JoinProjectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = JoinProjectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        project_id = serializer.validated_data['project_id']
        user_id = request.user.user_id

        # BR8.1: Kiểm tra Project tồn tại 
        try:
            project = Project.objects.get(project_id=project_id)
        except Project.DoesNotExist:
            return Response({"detail": "Dự án không tồn tại"}, status=status.HTTP_404_NOT_FOUND)

        # BR8.2: Kiểm tra đã là thành viên chưa 
        if ProjectMember.objects.filter(project=project, user_id=user_id).exists():
             return Response({"detail": "Bạn đã là thành viên của dự án này"}, status=status.HTTP_400_BAD_REQUEST)

        # BR8.3: Thêm vào bảng members với role mặc định 
        ProjectMember.objects.create(
            project=project,
            user_id=user_id,
            project_role=ProjectMember.Role.MEMBER
        )
        
        return Response({"detail": "Tham gia dự án thành công"}, status=status.HTTP_200_OK)
    
# API 5 & 7: Quản lý danh sách thành viên (Lấy danh sách & Thêm mới)
class ProjectMemberView(generics.ListCreateAPIView):
    serializer_class = ProjectMemberSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # PS_07 / BR7.1: Lấy danh sách thành viên của project_id trên URL
        project_id = self.kwargs['project_id']
        
        # Kiểm tra user hiện tại có phải là thành viên của dự án này không?
        # Nếu không phải thành viên -> Không cho xem danh sách
        if not ProjectMember.objects.filter(project_id=project_id, user_id=self.request.user.user_id).exists():
            return ProjectMember.objects.none()

        # BR7.3: Sắp xếp Admin lên đầu, sau đó đến người mới nhất
        return ProjectMember.objects.filter(project_id=project_id).order_by('project_role', '-joined_at')

    def post(self, request, project_id):
        # PS_05: Thêm thành viên vào dự án
        project = get_object_or_404(Project, project_id=project_id)

        # BR5.1: Kiểm tra quyền Admin
        # (Logic kiểm tra này có thể tách ra Permission Class riêng như IsProjectAdmin ở trên để clean code hơn)
        requester_role = ProjectMember.objects.filter(
            project=project, 
            user_id=request.user.user_id
        ).values_list('project_role', flat=True).first()

        if requester_role != ProjectMember.Role.ADMIN:
            return Response({"detail": "Chỉ Project Admin mới được thêm thành viên."}, status=status.HTTP_403_FORBIDDEN)

        # Validate dữ liệu đầu vào
        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        new_user_id = serializer.validated_data['user_id']
        new_role = serializer.validated_data['role']

        # BR5.2: Kiểm tra thành viên đã tồn tại chưa
        if ProjectMember.objects.filter(project=project, user_id=new_user_id).exists():
            return Response({"detail": "Người dùng này đã là thành viên của dự án."}, status=status.HTTP_400_BAD_REQUEST)

        # BR5.3: Tạo thành viên mới
        ProjectMember.objects.create(
            project=project,
            user_id=new_user_id,
            project_role=new_role
        )

        return Response({"detail": "Thêm thành viên thành công."}, status=status.HTTP_201_CREATED)


# API 6: Xóa thành viên
class ProjectMemberDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, project_id, user_id):
        # PS_06: Xoá thành viên
        project = get_object_or_404(Project, project_id=project_id)

        # BR6.1: Người thực hiện phải là Admin
        is_admin = ProjectMember.objects.filter(
            project=project, 
            user_id=request.user.user_id, 
            project_role=ProjectMember.Role.ADMIN
        ).exists()
        
        if not is_admin:
            return Response({"detail": "Quyền bị từ chối."}, status=status.HTTP_403_FORBIDDEN)

        # BR6.2: Không thể tự xóa chính mình
        # Lưu ý: user_id ở URL là kiểu UUID (string), request.user.user_id là UUID object, cần ép kiểu để so sánh
        if str(request.user.user_id) == str(user_id):
            return Response({"detail": "Không thể tự xóa chính mình khỏi dự án."}, status=status.HTTP_400_BAD_REQUEST)

        # BR6.3: Xóa bản ghi trong DB
        deleted_count, _ = ProjectMember.objects.filter(project=project, user_id=user_id).delete()

        if deleted_count == 0:
            return Response({"detail": "Thành viên không tồn tại."}, status=status.HTTP_404_NOT_FOUND)

        # BR6.4: Dữ liệu test case do user tạo vẫn giữ nguyên (đã được xử lý tự động vì Logical FK không có ràng buộc DB)
        return Response(status=status.HTTP_204_NO_CONTENT)
    

    # --- NHÓM API 2: TEST SUITES ---

class TestSuiteListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsProjectMember]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return TestSuiteSerializer
        return TestSuiteListSerializer

    def get_queryset(self):
        # PS_12 / BR12.1: Lấy toàn bộ suite của project
        project_id = self.kwargs['project_id']
        return TestSuite.objects.filter(project_id=project_id)

    def create(self, request, *args, **kwargs):
        # PS_09: Tạo Suite mới
        project_id = self.kwargs['project_id']
        
        # Kiểm tra quyền: Thành viên được tạo suite không? 
        # Tài liệu không nói rõ, giả định Member được tạo (IsProjectMember)
        
        # Truyền project_id vào context cho Serializer validate
        serializer = self.get_serializer(data=request.data, context={'project_id': project_id})
        serializer.is_valid(raise_exception=True)
        
        # Gán project_id trước khi lưu
        serializer.save(project_id=project_id)
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TestSuiteDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = TestSuite.objects.all()
    serializer_class = TestSuiteSerializer
    lookup_field = 'suite_id'
    permission_classes = [permissions.IsAuthenticated, IsProjectMember]

    def get_serializer_context(self):
        # Truyền project_id vào context để validate update (BR10.2)
        context = super().get_serializer_context()
        # Chỉ lấy project_id nếu phương thức là PUT/PATCH (cần validate)
        if self.request.method in ['PUT', 'PATCH']:
            # Lấy object từ URL lookup field
            # Lưu ý: get_object() có thể raise 404, nhưng ở đây là hợp lý
            obj = self.get_object()
            context['project_id'] = obj.project_id
        return context

    def perform_update(self, serializer):
        # PS_10: Cập nhật suite
        # Cần lấy project_id từ instance hiện tại để validate trong serializer
        instance = self.get_object()
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        # PS_11 / BR11.1: Xóa suite (Cascade delete)
        # Django on_delete=models.CASCADE đã tự xử lý việc xóa con cháu & testcase
        return super().destroy(request, *args, **kwargs)
    

# --- NHÓM API 3: TEST CASES ---

class TestCaseListCreateView(generics.ListCreateAPIView):
    serializer_class = TestCaseSerializer
    permission_classes = [permissions.IsAuthenticated, IsProjectMember]

    def get_serializer_context(self):
        # Truyền suite_id vào context để serializer dùng validate assignee
        context = super().get_serializer_context()
        context['suite_id'] = self.kwargs['suite_id']
        return context

    def get_queryset(self):
        # PS_16: Lấy danh sách test case theo suite_id
        suite_id = self.kwargs['suite_id']
        return TestCase.objects.filter(suite_id=suite_id)

    def perform_create(self, serializer):
        # PS_13: Tạo Test Case mới
        suite_id = self.kwargs['suite_id']
        suite = get_object_or_404(TestSuite, suite_id=suite_id)
        
        # BR: Cần kiểm tra xem user hiện tại có thuộc project chứa suite này không
        # (Đã được xử lý bởi permission IsProjectMember nhưng cần check object permission kỹ hơn nếu muốn chặt chẽ)
        
        serializer.save(suite=suite)


class TestCaseDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = TestCase.objects.all()
    serializer_class = TestCaseSerializer
    lookup_field = 'case_id'
    permission_classes = [permissions.IsAuthenticated, IsProjectMember]

    def get_object(self):
        obj = super().get_object()
        # Logic check quyền bổ sung nếu cần thiết (Permission class đã lo phần lớn)
        return obj

    def perform_destroy(self, instance):
        instance.delete()