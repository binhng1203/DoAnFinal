from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("src.api.v1.routers")),
    path("healthz", lambda r: HttpResponse("User Service OK")),
]

