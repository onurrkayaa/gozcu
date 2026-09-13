from django.urls import path

from .views import (
    GirisTokenView,
    YenilemeTokenView,
    DetectionReviewView,
    FindingDetailView,
    FrameImageView,
    MissionAuditListView,
    MissionClusterView,
    MissionFindingListCreateView,
    MissionMemberDetailView,
    MissionMemberListCreateView,
    MissionDetailView,
    MissionFrameListCreateView,
    MissionListCreateView,
    MissionRunListCreateView,
    ModelVersionListView,
    RunDetailView,
    RunDetectionListView,
    RunReviewListView,
    health,
)

urlpatterns = [
    path("health/", health, name="health"),
    path("auth/token/", GirisTokenView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", YenilemeTokenView.as_view(), name="token_refresh"),
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
    path(
        "missions/<int:mission_id>/members/",
        MissionMemberListCreateView.as_view(),
        name="mission-members",
    ),
    path(
        "missions/<int:mission_id>/members/<int:member_id>/",
        MissionMemberDetailView.as_view(),
        name="mission-member-detail",
    ),
    path(
        "missions/<int:mission_id>/findings/",
        MissionFindingListCreateView.as_view(),
        name="mission-findings",
    ),
    path("findings/<int:finding_id>/", FindingDetailView.as_view(), name="finding-detail"),
    path(
        "missions/<int:mission_id>/clusters/",
        MissionClusterView.as_view(),
        name="mission-clusters",
    ),
    path(
        "missions/<int:mission_id>/audit/",
        MissionAuditListView.as_view(),
        name="mission-audit",
    ),
    path(
        "detections/<int:detection_id>/reviews/",
        DetectionReviewView.as_view(),
        name="detection-reviews",
    ),
    path("runs/<int:run_id>/reviews/", RunReviewListView.as_view(), name="run-reviews"),
    path("runs/<int:pk>/", RunDetailView.as_view(), name="run-detail"),
    path(
        "runs/<int:run_id>/detections/",
        RunDetectionListView.as_view(),
        name="run-detections",
    ),
    path("models/", ModelVersionListView.as_view(), name="model-list"),
]
