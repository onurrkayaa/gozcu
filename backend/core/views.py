from django.db import connection
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Frame, Mission
from .serializers import FrameSerializer, MissionSerializer
from .services import InvalidImageError, ingest_frame


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Uygulama ve veritabani durumu. Kimlik dogrulama gerektirmez."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        return Response(
            {"status": "degraded", "database": "error", "detail": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response({"status": "ok", "database": "ok"})


class MissionListCreateView(generics.ListCreateAPIView):
    serializer_class = MissionSerializer

    def get_queryset(self):
        # Kullanici yalnizca kendi olusturdugu gorevleri gorur.
        return Mission.objects.filter(created_by=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class MissionFrameListCreateView(generics.ListAPIView):
    serializer_class = FrameSerializer
    parser_classes = (MultiPartParser, FormParser)

    def get_mission(self):
        return get_object_or_404(
            Mission, pk=self.kwargs["mission_id"], created_by=self.request.user
        )

    def get_queryset(self):
        queryset = Frame.objects.filter(mission=self.get_mission()).order_by("-created_at")
        wanted = self.request.query_params.get("status")
        if wanted:
            if wanted not in Frame.Status.values:
                raise ValidationError({"status": f"Gecersiz durum: {wanted}"})
            queryset = queryset.filter(status=wanted)
        return queryset

    def post(self, request, *args, **kwargs):
        mission = self.get_mission()
        files = request.FILES.getlist("images")
        if not files:
            raise ValidationError({"images": "En az bir dosya gonderilmeli."})

        results = []
        for uploaded in files:
            try:
                frame, duplicate = ingest_frame(mission, uploaded)
            except InvalidImageError as exc:
                raise ValidationError({"images": f"{uploaded.name}: {exc}"})
            results.append(
                {
                    "id": frame.id,
                    "filename": frame.original_filename,
                    "duplicate": duplicate,
                    "width": frame.width,
                    "height": frame.height,
                }
            )
        return Response(results, status=status.HTTP_201_CREATED)
