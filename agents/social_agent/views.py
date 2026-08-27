"""
social_agent/views.py
Django REST Framework views for campaign execution, human review/resumption, and platform webhooks.
"""
import uuid
import logging
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import RetrieveAPIView, ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.pagination import PageNumberPagination

from social_agent.models import SocialCampaign, AgentAuditLog, ChatSession, ChatMessage
from social_agent.serializers import (
    CampaignCreateSerializer,
    HITLApprovalSerializer,
    CampaignDetailSerializer,
    AgentAuditLogSerializer,
    ChatSessionSerializer,
    ChatMessageSerializer,
    ChatInputSerializer,
)
from social_agent.tasks import run_campaign_workflow_task, resume_hitl_workflow_task
from social_agent.agents.orchestrator import triage_intent

logger = logging.getLogger("social_agent")


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class TriggerCampaignView(APIView):
    """
    POST /api/campaigns/
    Triggers a new multi-agent social media workflow with transaction-safe Celery dispatch.
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = CampaignCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        prompt = validated["prompt"]
        platforms = validated.get("platforms", ["x_twitter", "instagram"])
        title = validated.get("title") or f"Campaign: {prompt[:30]}..."
        thread_id = f"thread_{uuid.uuid4()}"

        with transaction.atomic():
            campaign = SocialCampaign.objects.create(
                title=title,
                raw_prompt=prompt,
                target_platforms=platforms,
                langgraph_thread_id=thread_id,
                status="PENDING"
            )
            # Guarantee DB commit prior to Celery worker pickup to prevent ObjectDoesNotExist race
            transaction.on_commit(lambda: run_campaign_workflow_task.delay(str(campaign.id)))

        logger.info("Created campaign '%s' [Thread: %s]. Enqueued Celery task.", campaign.id, thread_id)
        return Response(
            {
                "status": "initiated",
                "campaign_id": str(campaign.id),
                "thread_id": campaign.langgraph_thread_id,
                "workflow_status": campaign.status
            },
            status=status.HTTP_201_CREATED
        )


class HITLApprovalView(APIView):
    """
    POST /api/campaigns/<uuid:id>/approve/
    Resumes an interrupted workflow at the HITL gate with human review verdict and edits.
    """
    permission_classes = [AllowAny]

    def post(self, request, id, *args, **kwargs):
        campaign = get_object_or_404(SocialCampaign, id=id)

        if campaign.status != "AWAITING_APPROVAL":
            return Response(
                {"error": f"Campaign is not awaiting approval (Current status: '{campaign.status}')."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = HITLApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        approved = data["approved"]
        notes = data.get("notes", "")
        modified_content = data.get("modified_content", {})

        with transaction.atomic():
            campaign.status = "RUNNING"
            campaign.save(update_fields=["status", "updated_at"])
            transaction.on_commit(
                lambda: resume_hitl_workflow_task.delay(
                    str(campaign.id),
                    approved,
                    notes,
                    modified_content
                )
            )

        logger.info("HITL decision submitted for campaign '%s': Approved=%s", campaign.id, approved)
        return Response(
            {
                "status": "resumed",
                "campaign_id": str(campaign.id),
                "decision": "APPROVED" if approved else "REJECTED"
            },
            status=status.HTTP_200_OK
        )


class CampaignDetailView(RetrieveAPIView):
    """
    GET /api/campaigns/<uuid:id>/
    Retrieves campaign status, generated posts, and evaluation metrics with prefetch optimization.
    """
    permission_classes = [AllowAny]
    serializer_class = CampaignDetailSerializer
    lookup_field = "id"

    def get_queryset(self):
        return SocialCampaign.objects.prefetch_related("posts", "audit_logs")


class CampaignAuditLogView(ListAPIView):
    """
    GET /api/campaigns/<uuid:id>/audit/
    Retrieves paginated audit log traces for a specific campaign.
    """
    permission_classes = [AllowAny]
    serializer_class = AgentAuditLogSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        campaign_id = self.kwargs.get("id")
        return AgentAuditLog.objects.filter(campaign_id=campaign_id).order_by("-timestamp")


class PlatformWebhookView(APIView):
    """
    POST /api/webhooks/<str:platform>/
    Ingests asynchronous engagement/mention webhooks from social media platforms.
    """
    permission_classes = [AllowAny]

    def post(self, request, platform, *args, **kwargs):
        logger.info("Received inbound webhook event from platform '%s'", platform)
        return Response({"status": "received", "platform": platform}, status=status.HTTP_200_OK)
from django.views.generic import TemplateView

class DashboardView(TemplateView):
    """
    GET /dashboard/
    Serves the agentic social media control plane frontend.
    """
    template_name = "social_agent/dashboard.html"

class CampaignListView(ListAPIView):
    """
    GET /api/campaigns/
    Retrieves the list of active campaigns for the dashboard.
    """
    permission_classes = [AllowAny]
    serializer_class = CampaignDetailSerializer
    queryset = SocialCampaign.objects.all().order_by("-updated_at")

class ChatSessionListCreateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        sessions = ChatSession.objects.filter(is_active=True)
        serializer = ChatSessionSerializer(sessions, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        thread_id = f"thread_{uuid.uuid4()}"
        session = ChatSession.objects.create(thread_id=thread_id)
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ChatMessageView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, id, *args, **kwargs):
        session = get_object_or_404(ChatSession, id=id)
        messages = session.messages.all().order_by("timestamp")
        serializer = ChatMessageSerializer(messages, many=True)
        return Response(serializer.data)

    def post(self, request, id, *args, **kwargs):
        session = get_object_or_404(ChatSession, id=id)
        serializer = ChatInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        content = serializer.validated_data["content"]
        agent_role = serializer.validated_data.get("agent_role")

        # Save user message
        user_msg = ChatMessage.objects.create(
            session=session,
            role="user",
            content=content,
            metadata={"agent_role": agent_role} if agent_role else {}
        )

        history = session.messages.filter(role__in=["user", "assistant"]).order_by("-timestamp")[:10][::-1]
        model_name = serializer.validated_data.get("model")
        triage_res = triage_intent(content, history[:-1], model_name) # exclude current user message

        if triage_res.get("mode") == "B":
            # Actionable Intention
            prompt = content
            platforms = triage_res.get("platforms", ["x_twitter", "instagram"])
            if not platforms:
                platforms = ["x_twitter", "instagram"]
            
            with transaction.atomic():
                campaign = SocialCampaign.objects.create(
                    title=f"Campaign: {prompt[:20]}",
                    raw_prompt=prompt,
                    target_platforms=platforms,
                    langgraph_thread_id=session.thread_id,
                    status="PENDING"
                )
                transaction.on_commit(lambda: run_campaign_workflow_task.delay(str(campaign.id)))

            assistant_msg = ChatMessage.objects.create(
                session=session,
                role="assistant",
                content=triage_res.get("response", f"Initialized campaign on {', '.join(platforms)}."),
                metadata={
                    "intent": "CAMPAIGN_TRIGGER",
                    "campaign_id": str(campaign.id),
                    "thread_id": session.thread_id,
                    "status": "RUNNING",
                    "target_platforms": platforms
                }
            )
            
            return Response({
                "session_id": str(session.id),
                "message": ChatMessageSerializer(assistant_msg).data
            }, status=status.HTTP_200_OK)
        else:
            # Advisory / Consultative Intent
            assistant_msg = ChatMessage.objects.create(
                session=session,
                role="assistant",
                content=triage_res.get("response", "Consultative response."),
                metadata={"intent": "ADVISORY"}
            )
            return Response({
                "session_id": str(session.id),
                "message": ChatMessageSerializer(assistant_msg).data
            }, status=status.HTTP_200_OK)


import urllib.request
import json

class AvailableModelsView(APIView):
    """
    GET /api/models/
    Retrieves locally available models from Ollama to populate the UI.
    """
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        try:
            url = "http://127.0.0.1:11434/api/tags"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.loads(response.read().decode())
                
            models = [m["name"] for m in data.get("models", []) if "embed" not in m["name"].lower()]
            return Response({"models": models})
        except Exception as e:
            logger.warning("Could not fetch Ollama models: %s", e)
            return Response({"models": ["llama3.3:70b-instruct", "gpt-4"]})
