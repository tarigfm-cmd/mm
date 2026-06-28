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

// ---------------------------------------------------------------------------
// Training flow (pre-submission blueprint)
// ---------------------------------------------------------------------------

export interface TrainingFlowStep {
  step_number: number
  step_type: string       // "briefing" | "red_flag_check" | "decision" | "counseling"
  title: string
  instruction: string
  safe_content: Record<string, unknown>
  input_required: boolean
  input_type: string      // "none" | "text" | "action_select" | "checkbox_list"
  options: string[]
}

export interface TrainingFlowResponse {
  content_item_id: string
  content_type: string
  title: string
  total_steps: number
  steps: TrainingFlowStep[]
  scoring_note: string
}

// ---------------------------------------------------------------------------
// Training sessions
// ---------------------------------------------------------------------------

export interface SessionStartResponse {
  session_id: string
  content_item_id: string
  content_version_id: string
  region_code: string
  status: string
  current_step: number
  total_steps: number
  started_at: string
}

export interface SessionSubmitRequest {
  red_flags_selected?: string[]
  action_selected?: string
  counseling_points?: string[]
  documentation_points?: string[]
  answer_text?: string
  confidence?: number
  time_to_decision_seconds?: number
}

export interface DimensionFeedbackItem {
  dimension: string
  status: string   // "passed" | "failed" | "not_assessable"
  feedback: string
}

export interface SessionSubmitResponse {
  session_id: string
  status: string
  score: number | null
  max_score: number
  score_percent: number | null
  failed_dimensions: string[]
  not_assessable_dimensions: string[]
  dimension_feedback: DimensionFeedbackItem[]
  reveal_summary: Record<string, unknown>
  next_recommendation: string
}

// ---------------------------------------------------------------------------
// Phase-1 attempt (kept for compatibility)
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Learner progress
// ---------------------------------------------------------------------------

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

export interface LearnerSessionSummary {
  id: string
  content_item_id: string
  content_title: string | null
  content_type: string | null
  region_code: string
  status: string
  score: number | null
  score_percent: number | null
  started_at: string
  completed_at: string | null
}

export interface LearnerProgressSummary {
  total_attempts: number
  completed_sessions: number
  average_score: number | null
  average_score_percent: number | null
  strongest_dimension: string | null
  weakest_dimension: string | null
  attempts_by_content_type: Record<string, number>
  dimension_breakdown: Record<string, number>
  weakness_breakdown: Record<string, number>
  recent_attempts: LearnerRecentAttempt[]
  recent_sessions: LearnerSessionSummary[]
  recommended_next_content_type: string | null
  recommended_next_domain: string | null
}
