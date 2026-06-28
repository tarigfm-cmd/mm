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
  external_paypal_plan_id: string | null
}

export interface SubscriptionPlanAdminRead extends SubscriptionPlanRead {
  created_at: string
  updated_at: string
}

export interface SubscriptionPlanUpdate {
  name?: string
  price_monthly_cents?: number
  currency?: string
  is_active?: boolean
  external_paypal_plan_id?: string | null
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

export interface PayPalCheckoutResponse {
  checkout_url: string
  external_subscription_id: string | null
  status: string
  provider: string
}

export interface PayPalPlanStatus {
  plan_code: string
  name: string
  is_active: boolean
  is_paid: boolean
  external_paypal_plan_id_configured: boolean
  checkout_ready: boolean
}

export interface PayPalConfigStatus {
  paypal_env: string
  app_public_url: string
  client_id_configured: boolean
  client_secret_configured: boolean
  webhook_id_configured: boolean
  paypal_configured: boolean
  webhook_url: string
  success_url: string
  cancel_url: string
  plans: PayPalPlanStatus[]
  missing_requirements: string[]
  warnings: string[]
}
