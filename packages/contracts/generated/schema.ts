/**
 * Auto-generated TypeScript definitions matching the OpenAPI 3.1.0 contract.
 */

export interface CampaignCreate {
  brand_id: string;
  name: string;
  objective: string;
  target_platforms?: string[];
}

export interface CampaignResponse {
  id: string;
  brand_id: string;
  name: string;
  status: "draft" | "planning" | "review" | "approved" | "publishing" | "completed" | "failed";
  objective: string;
  blueprint?: Record<string, unknown> | null;
  created_at: string;
}

export interface RunCreate {
  campaign_id: string;
  user_command?: string | null;
  skills_override?: string[] | null;
}

export interface RunResponse {
  id: string;
  thread_id: string;
  campaign_id: string;
  status: "running" | "interrupted" | "completed" | "failed";
  current_node?: string | null;
  created_at: string;
}

export interface ApprovalResponse {
  id: string;
  run_id: string;
  thread_id: string;
  status: "pending" | "approved" | "rejected";
  step_name: string;
  payload: Record<string, unknown>;
  decision_notes?: string | null;
  created_at: string;
}

export interface ApprovalResumeRequest {
  approved: boolean;
  notes?: string | null;
  modifications?: Record<string, unknown> | null;
}
