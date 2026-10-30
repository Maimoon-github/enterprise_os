export interface UserModel {
  id: string;
  email: string;
  full_name?: string | null;
  role: "admin" | "editor" | "operator" | "viewer" | string;
  is_active: boolean;
  created_at: string;
}

export interface BrandModel {
  id: string;
  name: string;
  slug: string;
  voice_guidelines?: string | null;
  target_segments?: string[];
  default_platforms: string[];
  created_at: string;
}

export interface CampaignModel {
  id: string;
  brand_id: string;
  name: string;
  status: "draft" | "active" | "completed" | "archived" | string;
  objective: string;
  blueprint?: Record<string, unknown> | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RunModel {
  id: string;
  thread_id: string;
  campaign_id: string;
  status: "running" | "completed" | "interrupted" | "failed" | string;
  trigger_type: string;
  current_node?: string | null;
  error_message?: string | null;
  token_usage?: Record<string, unknown>;
  created_at: string;
  finished_at?: string | null;
}

export interface ApprovalModel {
  id: string;
  run_id: string;
  thread_id: string;
  status: "pending" | "approved" | "rejected" | string;
  step_name: string;
  payload: Record<string, unknown>;
  decision_notes?: string | null;
  reviewed_by?: string | null;
  created_at: string;
  resolved_at?: string | null;
}

export interface MediaAssetModel {
  id: string;
  brand_id: string;
  campaign_id?: string | null;
  minio_bucket: string;
  minio_key: string;
  content_hash: string;
  mime_type: string;
  width?: number | null;
  height?: number | null;
  aspect_ratio?: string | null;
  prompt_lineage?: string | null;
  created_at: string;
}

export interface ScheduleModel {
  id: string;
  campaign_id: string;
  platform: string;
  cron_expression?: string | null;
  scheduled_utc?: string | null;
  status: "scheduled" | "active" | "paused" | "published" | string;
  idempotency_key: string;
  created_at: string;
}

export interface BeatScheduleModel {
  name: string;
  task: string;
  schedule: string;
  queue: string;
  status: string;
}

export interface SandboxStatusModel {
  engine: string;
  image: string;
  memory_limit: string;
  cpu_limit: string;
  network_default: string;
  security_opt: string;
  cap_drop: string;
  mount_mode: string;
  podman_installed: boolean;
}

export interface WorkerQueueMetricModel {
  queue: string;
  routing_key: string;
  worker_concurrency: number;
  active_tasks: number;
}

export interface AnalyticsEventModel {
  id: string;
  brand_id: string;
  platform: string;
  external_post_id: string;
  metric_type: string;
  metric_value: number;
  recorded_at: string;
}

export interface SkillModel {
  name: string;
  path?: string | null;
  description: string;
  compatibility?: string | null;
  allowed_tools: string[];
  tier: string;
  status: string;
  valid: boolean;
  lines_count: number;
  token_estimate: number;
  tier3_resources: string[];
}

export interface SkillDetailModel extends SkillModel {
  content: string;
  tier2_body: string;
}
