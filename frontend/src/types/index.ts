// ── Material ───────────────────────────────────────────────────────────────────

export interface Material {
  id: string
  title: string
  description: string | null
  file_name: string
  file_size: number
  file_type: string
  has_content: boolean
  scenario_count: number
  created_at: string
}

export interface MaterialDetail extends Material {
  content_text: string | null
  updated_at: string
}

export interface MaterialListResponse {
  items: Material[]
  total: number
  page: number
  per_page: number
  pages: number
}

// ── Scenario ───────────────────────────────────────────────────────────────────

export type DifficultyLevel = 'beginner' | 'intermediate' | 'advanced'

export interface Scenario {
  id: string
  material_id: string | null
  title: string
  clinical_case: string
  difficulty_level: DifficultyLevel
  specialty: string | null
  key_concepts: string[] | null
  interaction_count: number
  created_at: string
  updated_at: string
}

export interface ScenarioListResponse {
  items: Scenario[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface GenerateScenarioRequest {
  material_id: string
  difficulty_level: DifficultyLevel
  specialty?: string
}

// ── Interaction ────────────────────────────────────────────────────────────────

export interface Interaction {
  id: string
  scenario_id: string
  user_answer: string
  ai_feedback: string
  score: number | null
  key_findings: string[] | null
  next_steps: string[] | null
  strengths: string[] | null
  areas_for_improvement: string[] | null
  created_at: string
}

export interface SubmitAnswerRequest {
  scenario_id: string
  content: string
  session_id?: string
}

export interface ScenarioInteractionsResponse {
  scenario: Scenario
  interactions: Interaction[]
  average_score: number | null
  total_interactions: number
}

// ── Auth ───────────────────────────────────────────────────────────────────────

export interface UserRead {
  id: string
  email: string
  username: string
  full_name: string | null
  is_active: boolean
  is_verified: boolean
  is_superuser: boolean
  created_at: string
  updated_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  username: string
  password: string
  full_name?: string
}

// ── UI state ───────────────────────────────────────────────────────────────────

export interface ApiError {
  detail: string | { msg: string; type: string }[]
}

export interface UploadProgress {
  fileName: string
  progress: number
  status: 'uploading' | 'processing' | 'done' | 'error'
  error?: string
  materialId?: string
}
