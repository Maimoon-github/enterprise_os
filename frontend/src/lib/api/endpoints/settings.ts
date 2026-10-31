import { apiClient } from "../client";
import {
  SettingsResponse,
  PlatformConnectionResponse,
  PlatformConnectionUpdate,
  PlatformConnectionTestResult,
  UserPreferencesResponse,
  UserPreferencesUpdate,
  AnalyticsChannelState,
} from "@marketing-os/contracts";

export const settingsApi = {
  getSettings: () => apiClient<SettingsResponse>("/settings"),

  listPlatforms: () => apiClient<PlatformConnectionResponse[]>("/settings/platforms"),

  configurePlatform: (platform: string, data: PlatformConnectionUpdate) =>
    apiClient<PlatformConnectionResponse>(`/settings/platforms/${platform}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  testPlatform: (platform: string) =>
    apiClient<PlatformConnectionTestResult>(`/settings/platforms/${platform}/test`, {
      method: "POST",
    }),

  disconnectPlatform: (platform: string) =>
    apiClient<void>(`/settings/platforms/${platform}`, {
      method: "DELETE",
    }),

  getPreferences: () => apiClient<UserPreferencesResponse>("/settings/preferences"),

  updatePreferences: (data: UserPreferencesUpdate) =>
    apiClient<UserPreferencesResponse>("/settings/preferences", {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  getAnalyticsChannels: () => apiClient<AnalyticsChannelState[]>("/analytics/channels"),
};
