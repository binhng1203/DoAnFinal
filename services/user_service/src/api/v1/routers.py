from django.urls import path
from .views_auth import RegisterView, LoginView
from .views_users import MeView
from .views_admin import (
    AdminUserListView, AdminAssignRoleView, AdminRolesListView, AdminPermissionsListView
)

urlpatterns = [
    path("auth/register", RegisterView.as_view(), name="auth-register"),
    path("auth/login",    LoginView.as_view(),    name="auth-login"),
    path("users/me",      MeView.as_view(),       name="users-me"),

    path("admin/users",                 AdminUserListView.as_view(),       name="admin-users"),
    path("admin/users/<uuid:user_id>/roles", AdminAssignRoleView.as_view(), name="admin-assign-role"),
    path("admin/roles",                 AdminRolesListView.as_view(),      name="admin-roles"),
    path("admin/permissions",           AdminPermissionsListView.as_view(),name="admin-permissions"),
]

