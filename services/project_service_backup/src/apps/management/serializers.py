from rest_framework import serializers
from .models import Project, ProjectMember
from .models import TestSuite, TestCase

class ProjectSerializer(serializers.ModelSerializer):
    # Trường role này không có trong bảng Project, ta sẽ tính toán runtime
    role = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ['project_id', 'name', 'description', 'repo_url', 'created_at', 'role']
        read_only_fields = ['project_id', 'created_at', 'role']

    def get_role(self, obj):
        # Lấy user từ context (được truyền vào từ View)
        user = self.context['request'].user
        try:
            member = ProjectMember.objects.get(project=obj, user_id=user.user_id)
            return member.project_role
        except ProjectMember.DoesNotExist:
            return None

    def create(self, validated_data):
        # Lấy user hiện tại làm người tạo
        user = self.context['request'].user
        validated_data['created_by_user_id'] = user.user_id
        
        # 1. Tạo Project
        project = Project.objects.create(**validated_data)
        
        # 2. Tự động add người tạo thành Admin (Theo BR1.4)
        ProjectMember.objects.create(
            project=project,
            user_id=user.user_id,
            project_role=ProjectMember.Role.ADMIN
        )
        return project

class ProjectUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['name', 'description', 'repo_url']
        # name không bắt buộc unique global, nhưng nên check unique trong list dự án của user (tuỳ nghiệp vụ)
        # Theo BR2.2: projectname mới phải là duy nhất (trong hệ thống hoặc scope). 
        # Ở đây ta dùng default validation của Model.

class JoinProjectSerializer(serializers.Serializer):
    project_id = serializers.CharField(max_length=8, min_length=8)

class ProjectMemberSerializer(serializers.ModelSerializer):
    """
    Serializer dùng để hiển thị danh sách thành viên (PS_07)
    """
    class Meta:
        model = ProjectMember
        fields = ['user_id', 'project_role', 'joined_at']
        # Lưu ý: Project Service chỉ chứa user_id. 
        # Frontend sẽ cần gọi User Service hoặc Gateway để lấy tên/avatar từ user_id này.

class AddMemberSerializer(serializers.Serializer):
    """
    Serializer validate dữ liệu đầu vào khi thêm thành viên (PS_05)
    """
    user_id = serializers.UUIDField()
    role = serializers.ChoiceField(choices=ProjectMember.Role.choices, default=ProjectMember.Role.MEMBER)


class TestSuiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestSuite
        fields = ['suite_id', 'project', 'parent_suite', 'name']
        read_only_fields = ['suite_id', 'project']

    def validate(self, data):
        """
        Validate logic nghiệp vụ phức tạp (BR9.2, BR10.2)
        """
        # Lấy thông tin user và project từ context (do View truyền vào)
        project_id = self.context.get('project_id')
        instance = self.instance  # Object hiện tại (nếu đang update)

        # 1. Nếu có gửi lên parent_suite (Di chuyển hoặc Tạo mới vào thư mục con)
        parent_suite = data.get('parent_suite')
        if parent_suite:
            # BR9.2: Kiểm tra Parent Suite phải thuộc cùng Project
            if str(parent_suite.project_id) != str(project_id):
                raise serializers.ValidationError(
                    {"parent_suite": "Thư mục cha không thuộc dự án này."}
                )
            
            # BR10.2: Chặn vòng lặp khi update (Không được chọn chính mình hoặc con cháu làm cha)
            if instance:
                if parent_suite.suite_id == instance.suite_id:
                    raise serializers.ValidationError(
                        {"parent_suite": "Không thể chọn chính thư mục này làm thư mục cha."}
                    )
                # Kiểm tra logic đệ quy: Parent mới không được nằm trong cây con của suite hiện tại
                # (Logic này hơi phức tạp, tạm thời check level 1, nếu cần đệ quy sâu thì dùng CTE query)

        return data

class TestSuiteListSerializer(serializers.ModelSerializer):
    """
    Serializer tối giản để trả về danh sách cho FE dựng Tree (DR12.2)
    """
    parent_suite_id = serializers.PrimaryKeyRelatedField(read_only=True, source='parent_suite')
    
    class Meta:
        model = TestSuite
        fields = ['suite_id', 'name', 'parent_suite_id']


class TestCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestCase
        fields = [
            'case_id', 'suite', 'name', 'priority', 
            'type', 'description', 'assignee_user_id'
        ]
        read_only_fields = ['case_id', 'suite']

    def validate_assignee_user_id(self, value):
        """
        BR13.3: Kiểm tra Assignee có phải là thành viên dự án không?
        """
        if value is None:
            return value

        # Để check member, ta cần biết project_id.
        # Project_id có thể lấy từ suite (đối tượng cha).
        
        # Trường hợp 1: Đang tạo mới (context có suite_id hoặc view truyền vào)
        # Trường hợp 2: Đang update (self.instance có suite)
        
        suite = None
        if self.instance:
            suite = self.instance.suite
        elif 'suite_id' in self.context:
             # Lấy suite từ DB để biết project của nó
             from django.shortcuts import get_object_or_404
             suite = get_object_or_404(TestSuite, suite_id=self.context['suite_id'])
        
        if suite:
            is_member = ProjectMember.objects.filter(
                project_id=suite.project_id,
                user_id=value
            ).exists()
            
            if not is_member:
                raise serializers.ValidationError("Người được gán (Assignee) không phải là thành viên của dự án này.")
        
        return value