import secrets
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _


# --- HÀM SINH ID MỚI ---
def generate_project_id():
    # Chỉ dùng chữ in hoa và số, bỏ các ký tự dễ nhầm (0, O, I, L, 1)
    # Tổng không gian mẫu: 32^8 ~ 1000 tỷ tổ hợp -> Khá an toàn
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return ''.join(secrets.choice(alphabet) for _ in range(8))


class Project(models.Model):
    project_id = models.CharField(
        primary_key=True,
        default=generate_project_id, # Dùng hàm tự viết
        max_length=8,
        editable=False
    )
    name = models.CharField(max_length=255, null=False)
    description = models.TextField(blank=True, null=True)
    repo_url = models.TextField(blank=True, null=True)
    created_by_user_id = models.UUIDField(null=False) # Logical FK to core.users
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Định nghĩa rõ bảng nằm trong schema management
        db_table = '"management"."projects"'
        ordering = ['-created_at']

class ProjectMember(models.Model):
    class Role(models.TextChoices):
        ADMIN = 'Project Admin', _('Project Admin')
        MEMBER = 'Member', _('Member')

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='members')
    user_id = models.UUIDField(null=False) # Logical FK to core.users
    project_role = models.CharField(
        max_length=30, 
        choices=Role.choices, 
        default=Role.MEMBER
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = '"management"."project_members"'
        unique_together = ('project', 'user_id') # BR: Mỗi user 1 vai trò/dự án

class TestSuite(models.Model):
    suite_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='suites')
    # Self-referencing ForeignKey cho cấu trúc cây thư mục
    parent_suite = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='child_suites')
    name = models.CharField(max_length=255, null=False)

    class Meta:
        db_table = '"management"."test_suites"'
        # BR9.1: Suitename unique? Tài liệu nói unique trong bảng management.test_suites
        # Nhưng thực tế nên là unique theo Project hoặc theo Parent Suite sẽ hợp lý hơn.
        # Tạm thời follow sát tài liệu:
        # unique_together = ('project', 'name') 

class TestCase(models.Model):
    class Priority(models.TextChoices):
        HIGH = 'High', _('High')
        MEDIUM = 'Medium', _('Medium')
        LOW = 'Low', _('Low')

    class Type(models.TextChoices):
        MANUAL = 'manual', _('Manual')
        AUTOMATED = 'automated', _('Automated')

    case_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    suite = models.ForeignKey(TestSuite, on_delete=models.CASCADE, related_name='test_cases')
    name = models.CharField(max_length=255, null=False)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.MANUAL)
    description = models.TextField(blank=True, null=True)
    assignee_user_id = models.UUIDField(null=True, blank=True) # Logical FK

    class Meta:
        db_table = '"management"."test_cases"'