export interface SubscriptionPlanRead {
  id: string
  code: string
  name: string
  price_monthly_cents: number
  currency: string
  billing_interval: string
  is_active: boolean
  max_training_sessions_per_month: number | null
  max_published_content_access_per_month: number | null
  allows_admin_governance: boolean
  allows_bulk_import: boolean
  allows_institution_dashboard: boolean
  allows_ai_tutor: boolean
  allows_osce: boolean
  allows_games: boolean
}

export interface UserSubscriptionRead {
  id: string
  user_id: string
  plan_id: string
  status: string
  current_period_start: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
  external_provider: string | null
  created_at: string
  updated_at: string
  plan: SubscriptionPlanRead
}

export interface UserSubscriptionWithFallback {
  subscription: UserSubscriptionRead | null
  plan: SubscriptionPlanRead
  is_free_tier: boolean
}

export interface UsageSummary {
  event_type: string
  count: number
  limit: number | null
  period: string
}

export interface MonthlyUsageResponse {
  usage: UsageSummary[]
  period_start: string
}
