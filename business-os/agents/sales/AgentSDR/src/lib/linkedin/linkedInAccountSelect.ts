/** LinkedIn account fields for UI lists (excludes heavy profileData JSON). */
export const linkedInAccountListSelect = {
  id: true,
  username: true,
  name: true,
  profilePictureUrl: true,
  headline: true,
  status: true,
  limitReached: true,
  isPremium: true,
  workTimezone: true,
  workStartTime: true,
  workEndTime: true,
  workDays: true,
  nextAllowedRun: true,
} as const;

export const linkedInAccountFilterSelect = {
  id: true,
  username: true,
  name: true,
  profilePictureUrl: true,
} as const;
