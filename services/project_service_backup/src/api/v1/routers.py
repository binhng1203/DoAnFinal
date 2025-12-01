from django.urls import path
from src.apps.management.views import (
    ProjectListCreateView, 
    ProjectDetailView, 
    JoinProjectView,
    ProjectMemberView,      
    ProjectMemberDetailView,
    TestSuiteListCreateView, 
    TestSuiteDetailView,
    TestCaseListCreateView,
    TestCaseDetailView
)

urlpatterns = [
    path('projects', ProjectListCreateView.as_view(), name='project-list-create'),
    path('projects/join', JoinProjectView.as_view(), name='project-join'),
    path('projects/<str:project_id>', ProjectDetailView.as_view(), name='project-detail'),

    path('projects/<str:project_id>/members', ProjectMemberView.as_view(), name='project-members'),
    path('projects/<str:project_id>/members/<uuid:user_id>', ProjectMemberDetailView.as_view(), name='project-member-remove'),

    path('projects/<str:project_id>/suites', TestSuiteListCreateView.as_view(), name='suite-list-create'),
    path('suites/<uuid:suite_id>', TestSuiteDetailView.as_view(), name='suite-detail'),

    path('suites/<uuid:suite_id>/cases', TestCaseListCreateView.as_view(), name='case-list-create'),
    path('cases/<uuid:case_id>', TestCaseDetailView.as_view(), name='case-detail'),
]