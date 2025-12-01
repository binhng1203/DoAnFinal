from django.urls import path, include
from django.http import HttpResponse

urlpatterns = [
    path('healthz', lambda r: HttpResponse("Project Service OK")),
    # Include router v1
    path('api/v1/', include('src.api.v1.routers')),
]