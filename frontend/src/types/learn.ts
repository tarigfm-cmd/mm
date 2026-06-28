// Learner-facing types — no admin/reviewer metadata

export interface LearnableContentItem {
  id: string
  external_id: string | null
  title: string
  content_type: string
  domain: string | null
  specialty: string | null
  difficulty: string | null
  region_scope: string[] | null
  published_at: string
  version_id: string
  version_number: number
}

export interface LearnableContentListResponse {
  items: LearnableContentItem[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface LearnableContentDetail {
  id: string
  external_id: string | null
  title: string
  content_type: string
  domain: string | null
  specialty: string | null
  difficulty: string | null
  region_scope: string[] | null
  published_at: string
  version_id: string
  version_number: number
  safe_payload: Record<string, unknown> | null
  evidence_ids: string[] | null
  localization_notes: string | null
  requires_local_disclaimer: boolean
  requires_protocol_note: boolean
}

export interface LearnerAttemptCreate {
  region_code: string
  attempt_type?: string
  learner_response?: string
  selected_action?: string
  time_to_decision_seconds?: number
  self_confidence?: number
  red_flag_identified?: boolean
  counseling_point_selected?: boolean
  interaction_detected?: boolean
  referral_decision_selected?: boolean
  dose_calculation_answer?: string
  documentation_completed?: boolean
}

export interface LearnerAttemptResult {
  attempt_id: string
  score: number | null
  feedback: string
  failed_dimensions: string[]
  recommended_next_step: string
}

export interface LearnerRecentAttempt {
  id: string
  content_item_id: string
  content_title: string | null
  content_type: string | null
  region_code: string | null
  score: number | null
  attempt_type: string | null
  created_at: string
}

export interface LearnerProgressSummary {
  total_attempts: number
  average_score: number | null
  attempts_by_content_type: Record<string, number>
  weakness_breakdown: Record<string, number>
  recent_attempts: LearnerRecentAttempt[]
}
