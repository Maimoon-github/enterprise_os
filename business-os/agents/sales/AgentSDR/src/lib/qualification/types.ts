export type QualificationStatus =
  | "qualified"
  | "not_live"
  | "no_ads" // reserved — ads stage currently deferred
  | "apollo_no_data"
  | "apollo_has_data" // Apollo has people but none with verified emails
  | "pending";

export interface QualificationDebugTrace {
  parentLookup?: {
    request: {
      provider: "azure_openai" | "foundry_openai" | "openrouter";
      endpoint: string;
      model: string;
      instructions: string;
      input: string;
      maxOutputTokens: number;
      tool: string;
      tools: { type: "web_search" }[];
    };
    response?: {
      id?: string;
      status?: string;
      outputText?: string;
      output?: unknown;
      usage?: unknown;
      parsedParentDomain?: string | null;
      webSearchUsed?: boolean;
      webSearchCalls?: unknown[];
    };
    error?: string;
    startedAt: string;
    finishedAt: string;
  };
  apollo?: {
    child?: ApolloLeadDebugTrace;
    parent?: ApolloLeadDebugTrace;
  };
}

export interface ApolloLeadDebugTrace {
  domain: string;
  domains: string[];
  allPeople: ApolloSearchDebugTrace;
  verifiedPeople: ApolloSearchDebugTrace;
}

export interface ApolloSearchDebugTrace {
  label: "all_people" | "verified_people";
  method: "POST";
  url: string;
  query: Record<string, string | string[]>;
  status?: number;
  response?: unknown;
  error?: string;
  totalEntries: number | null;
  startedAt: string;
  finishedAt: string;
}

/** Result of running the simplified pipeline on a single domain. */
export interface QualificationResult {
  domain: string;
  status: QualificationStatus;
  isLive: boolean;
  /** Parent-company rows skip Shopify/liveness and only run Apollo checks. */
  isParentCompany: boolean;
  /** Apollo total_entries with no email filter — tells us if Apollo has any data at all. */
  allLeadCount: number | null;
  /** Apollo total_entries filtered to verified-email people only. */
  verifiedEmployeeCount: number | null;
  /** Annual revenue (clean_domains.annual_sales). Parent rows inherit the child's value. */
  revenue: string | null;
  /** FK to the parent domain's targeted_domains row, once resolved. */
  parentId: string | null;
  /** Resolved parent domain string (denormalised for display). */
  parentDomain: string | null;
  /** True when the resolved parent row already existed before this run. */
  parentPreviouslyAdded: boolean;
  /** Campaign that owns the resolved parent row, when known. */
  parentCampaignId: string | null;
  /** True when status=apollo_no_data and a human must research the parent. */
  parentPending: boolean;
  reason: string | null;
  qualificationDebug: QualificationDebugTrace | null;
}

export interface CampaignFilters {
  countryCode?: string;
  c1?: string;
  c2?: string;
  c3?: string;
  platform?: string;
  app?: string;
  minRevenue?: string;
  maxRevenue?: string;
}

export type CampaignInputMode = "filters" | "manual";

/** "leads": stop once accumulated verified leads reach targetLeadCount.
 *  "domains": stop once targetDomainCount domains have been qualified. */
export type CampaignTargetMode = "leads" | "domains";
