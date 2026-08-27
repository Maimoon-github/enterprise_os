"""
social_agent/urls.py
REST API URL routing for campaigns, approvals, audit logs, and social webhooks.
"""
from django.urls import path
from social_agent.views import (
    TriggerCampaignView,
    CampaignDetailView,
    HITLApprovalView,
    CampaignAuditLogView,
    PlatformWebhookView,
    DashboardView,
    CampaignListView,
    ChatSessionListCreateView,
    ChatMessageView,
    AvailableModelsView
)

app_name = "social_agent"

urlpatterns = [
    # Frontend Dashboard
    path("", DashboardView.as_view(), name="dashboard"),

    # Campaign Lifecycle Operations
    path("api/campaigns/create/", TriggerCampaignView.as_view(), name="campaign-trigger"),
    path("api/campaigns/", CampaignListView.as_view(), name="campaign-list"),
    path("api/campaigns/<uuid:id>/", CampaignDetailView.as_view(), name="campaign-detail"),
    path("api/campaigns/<uuid:id>/approve/", HITLApprovalView.as_view(), name="campaign-approve"),
    path("api/campaigns/<uuid:id>/audit/", CampaignAuditLogView.as_view(), name="campaign-audit"),

    # Reactive Platform Webhooks
    path("api/webhooks/<str:platform>/", PlatformWebhookView.as_view(), name="platform-webhook"),

    # Chat & Sessions
    path("api/chat/sessions/", ChatSessionListCreateView.as_view(), name="chat-session-list-create"),
    path("api/chat/sessions/<uuid:id>/messages/", ChatMessageView.as_view(), name="chat-message-list"),
    path("api/chat/sessions/<uuid:id>/message/", ChatMessageView.as_view(), name="chat-message-create"),
    
    # Models
    path("api/models/", AvailableModelsView.as_view(), name="available-models"),
]
