from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    MissionFrameListCreateView,
    MissionListCreateView,
    MissionRunCreateView,
    ModelVersionListView,
    RunDetailView,
    RunDetectionListView,
    health,
)

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
    path(
        "missions/<int:mission_id>/runs/",
        MissionRunCreateView.as_view(),
        name="mission-runs",
    ),
    path("runs/<int:pk>/", RunDetailView.as_view(), name="run-detail"),
    path(
        "runs/<int:run_id>/detections/",
        RunDetectionListView.as_view(),
        name="run-detections",
    ),
    path("models/", ModelVersionListView.as_view(), name="model-list"),
]
