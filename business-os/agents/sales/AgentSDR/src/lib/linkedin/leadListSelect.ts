/** Fields needed for leads table rows (not detail panel). */
export const leadTableSelect = {
  id: true,
  linkedinUrl: true,
  name: true,
  profilePictureUrl: true,
  headline: true,
  location: true,
  status: true,
  createdAt: true,
  updatedAt: true,
  linkedInAccount: {
    select: { username: true, name: true, profilePictureUrl: true },
  },
  campaign: { select: { id: true, name: true } },
} as const;
