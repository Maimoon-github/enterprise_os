export * from "./generated/schema";
import type { components } from "./generated/schema";

export type SchemaMap = components["schemas"];

export type PlatformType =
  | "linkedin"
  | "youtube"
  | "instagram"
  | "threads"
  | "facebook"
  | "x"
  | "pinterest"
  | "google_business_profile";

export type LoginRequest = components["schemas"]["LoginRequest"];
export type RefreshTokenRequest = components["schemas"]["RefreshTokenRequest"];
export type TokenResponse = components["schemas"]["TokenResponse"];
export type UserProfile = components["schemas"]["UserProfile"];
export type UserCreate = components["schemas"]["UserCreate"];
export type AuthProviderStatus = components["schemas"]["AuthProviderStatus"];

export type BrandCreate = components["schemas"]["BrandCreate"];
export type BrandResponse = components["schemas"]["BrandResponse"];

export type CampaignCreate = components["schemas"]["CampaignCreate"];
export type CampaignResponse = components["schemas"]["CampaignResponse"];
export type CampaignUpdate = components["schemas"]["CampaignUpdate"];

export type RunCreate = components["schemas"]["RunCreate"];
export type RunResponse = components["schemas"]["RunResponse"];

export type ApprovalResponse = components["schemas"]["ApprovalResponse"];
export type ApprovalResumeRequest = components["schemas"]["ApprovalResumeRequest"];

export type MediaAssetResponse = components["schemas"]["MediaAssetResponse"];
export type MediaPresignedUrlResponse = components["schemas"]["MediaPresignedUrlResponse"];

export type ScheduleCreate = components["schemas"]["ScheduleCreate"];
export type ScheduleResponse = components["schemas"]["ScheduleResponse"];

export type CrossPlatformKPIs = components["schemas"]["CrossPlatformKPIs"];
export type AnomalyAlert = components["schemas"]["AnomalyAlert"];
export type AnalyticsEventCreate = components["schemas"]["AnalyticsEventCreate"];
export type AnalyticsEventResponse = components["schemas"]["AnalyticsEventResponse"];

export type AgentSummary = components["schemas"]["AgentSummary"];
export type AgentConfigUpdate = components["schemas"]["AgentConfigUpdate"];

export type SkillSummary = components["schemas"]["SkillSummary"];
export type SkillValidateRequest = components["schemas"]["SkillValidateRequest"];
export type SkillValidateResponse = components["schemas"]["SkillValidateResponse"];

export type MCPServerStatus = components["schemas"]["MCPServerStatus"];
export type MCPSyncResponse = components["schemas"]["MCPSyncResponse"];

export type SettingsResponse = components["schemas"]["SettingsResponse"];
export type SettingsUpdateRequest = components["schemas"]["SettingsUpdateRequest"];

export type ChatSessionCreate = components["schemas"]["ChatSessionCreate"];
export type ChatSessionResponse = components["schemas"]["ChatSessionResponse"];
export type ChatSessionDetailResponse = components["schemas"]["ChatSessionDetailResponse"];
export type ChatSessionUpdate = components["schemas"]["ChatSessionUpdate"];
export type ChatMessageCreate = components["schemas"]["ChatMessageCreate"];
export type ChatMessageResponse = components["schemas"]["ChatMessageResponse"];

export type PlatformConnectionResponse = components["schemas"]["PlatformConnectionResponse"];
export type PlatformConnectionUpdate = components["schemas"]["PlatformConnectionUpdate"];
export type PlatformConnectionTestResult = components["schemas"]["PlatformConnectionTestResult"];
export type AnalyticsChannelState = components["schemas"]["AnalyticsChannelState"];
export type UserPreferencesResponse = components["schemas"]["UserPreferencesResponse"];
export type UserPreferencesUpdate = components["schemas"]["UserPreferencesUpdate"];

export type ObservabilityTraceResponse = components["schemas"]["ObservabilityTraceResponse"];
export type ObservabilityStatsResponse = components["schemas"]["ObservabilityStatsResponse"];
export type ObservabilityEvaluationItem = components["schemas"]["ObservabilityEvaluationItem"];
export type ObservabilityEvaluationsResponse = components["schemas"]["ObservabilityEvaluationsResponse"];
export type GoldenRegressionRunResponse = components["schemas"]["GoldenRegressionRunResponse"];
