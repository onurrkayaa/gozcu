from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    FrameImageView,
    MissionDetailView,
    MissionFrameListCreateView,
    MissionListCreateView,
    MissionRunListCreateView,
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
    path("missions/<int:pk>/", MissionDetailView.as_view(), name="mission-detail"),
    path(
        "missions/<int:mission_id>/frames/",
        MissionFrameListCreateView.as_view(),
        name="mission-frames",
    ),
    path(
        "missions/<int:mission_id>/runs/",
        MissionRunListCreateView.as_view(),
        name="mission-runs",
    ),
    path(
        "frames/<int:frame_id>/image/",
        FrameImageView.as_view(),
        name="frame-image",
    ),
    path("runs/<int:pk>/", RunDetailView.as_view(), name="run-detail"),
    path(
        "runs/<int:run_id>/detections/",
        RunDetectionListView.as_view(),
        name="run-detections",
    ),
    path("models/", ModelVersionListView.as_view(), name="model-list"),
]
