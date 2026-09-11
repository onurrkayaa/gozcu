from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import MissionFrameListCreateView, MissionListCreateView, health

urlpatterns = [
    path("health/", health, name="health"),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("missions/", MissionListCreateView.as_view(), name="mission-list"),
    path(
        "missions/<int:mission_id>/frames/",
        MissionFrameListCreateView.as_view(),
        name="mission-frames",
    ),
]
