export type ClientLeadFilters = {
  status?: string;
  search?: string;
  accountId?: string;
};

type LeadForFilter = {
  status: string;
  linkedinUrl: string;
  name: string | null;
  headline: string | null;
  location: string | null;
  linkedinAccountId?: string | null;
};

export const filterLeadsClient = <T extends LeadForFilter>(
  leads: T[],
  filters: ClientLeadFilters
): T[] => {
  const q = filters.search?.trim().toLowerCase() ?? "";
  return leads.filter((lead) => {
    if (filters.status && lead.status !== filters.status) return false;
    if (filters.accountId && lead.linkedinAccountId !== filters.accountId) return false;
    if (q) {
      const hay = [lead.name, lead.headline, lead.linkedinUrl, lead.location]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
};
