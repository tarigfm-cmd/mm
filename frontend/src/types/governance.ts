// Governance TypeScript types — mirrors backend app/schemas/governance.py and import_schema.py

// ── Content types & enums ──────────────────────────────────────────────────

export type ContentStatus =
  | 'draft'
  | 'imported'
  | 'pending_review'
  | 'clinically_approved'
  | 'published'
  | 'unpublished'
  | 'needs_update'
  | 'retired'

export type ContentType =
  | 'case'
  | 'simulation'
  | 'osce_station'
  | 'prescription_screening'
  | 'drill'
  | 'game'
  | 'evidence_source'
  | 'taxonomy_node'

export type RegionCode = 'UK' | 'US' | 'GCC' | 'AU'

export type ReviewDecision =
  | 'approved'
  | 'approved_with_conditions'
  | 'rejected'
  | 'needs_revision'

export type EvidenceStatus =
  | 'active'
  | 'needs_review'
  | 'superseded'
  | 'region_specific'
  | 'retired'

// ── Content Items ──────────────────────────────────────────────────────────

export interface ContentItemListItem {
  id: string
  title: string
  content_type: string
  domain: string | null
  specialty: string | null
  difficulty: string | null
  status: string
  region_scope: string[] | null
  external_id: string | null
  current_version_id: string | null
  created_at: string
  updated_at: string
}

export interface ContentItemRead extends ContentItemListItem {
  external_id: string | null
  created_by: string | null
  retired_at: string | null
}

export interface ContentItemListResponse {
  items: ContentItemListItem[]
  total: number
  page: number
  per_page: number
  pages: number
}

export interface ContentItemCreate {
  title: string
  content_type: string
  domain?: string
  specialty?: string
  difficulty?: string
  region_scope?: string[]
  external_id?: string
}

// ── Content Versions ───────────────────────────────────────────────────────

export interface ContentVersionRead {
  id: string
  content_item_id: string
  version_number: number
  payload_json: Record<string, unknown> | null
  evidence_ids: string[] | null
  localization_notes: string | null
  change_summary: string | null
  created_by: string | null
  created_at: string
  is_current: boolean
  source_file_name: string | null
  source_row_number: number | null
  content_hash: string | null
}

// ── Clinical Reviews ───────────────────────────────────────────────────────

export interface ClinicalReviewRead {
  id: string
  content_item_id: string
  content_version_id: string | null
  reviewer_user_id: string | null
  reviewer_role: string | null
  reviewer_team_name: string | null
  external_reviewer_reference: string | null
  approval_batch_id: string | null
  review_decision: string
  review_scope: string | null
  clinical_accuracy_score: number | null
  safety_score: number | null
  localization_score: number | null
  comments: string | null
  signed_off_at: string | null
  review_due_at: string | null
  created_at: string
}

export interface ClinicalReviewCreate {
  content_version_id?: string
  reviewer_role?: string
  reviewer_team_name?: string
  external_reviewer_reference?: string
  approval_batch_id?: string
  review_decision: ReviewDecision
  review_scope?: string
  clinical_accuracy_score?: number
  safety_score?: number
  localization_score?: number
  comments?: string
  signed_off_at?: string
  review_due_at?: string
}

// ── Approval Batches ───────────────────────────────────────────────────────

export interface ApprovalBatchRead {
  id: string
  batch_name: string
  source_package_name: string | null
  approved_by_team_name: string
  approval_statement: string | null
  approved_at: string
  approved_by_user_id: string | null
  region_scope: string[] | null
  content_count: number | null
  evidence_scope: string | null
  notes: string | null
  signed_manifest_hash: string | null
  created_at: string
}

export interface ApprovalBatchCreate {
  batch_name: string
  source_package_name?: string
  approved_by_team_name: string
  approval_statement?: string
  approved_at: string
  region_scope?: string[]
  content_count?: number
  evidence_scope?: string
  notes?: string
  signed_manifest_hash?: string
}

// ── Publishing ─────────────────────────────────────────────────────────────

export interface PublicationRecordRead {
  id: string
  content_item_id: string
  content_version_id: string
  region_code: string
  published_by: string | null
  published_at: string
  unpublished_by: string | null
  unpublished_at: string | null
  publication_status: string
  reason: string | null
  rollback_from_publication_id: string | null
  created_at: string
}

// ── Evidence Sources ───────────────────────────────────────────────────────

export interface EvidenceSourceRead {
  id: string
  title: string
  organization: string | null
  source_type: string | null
  url: string | null
  region: string | null
  publication_date: string | null
  last_checked_at: string | null
  next_review_due_at: string | null
  evidence_status: string
  notes: string | null
  created_at: string
  updated_at: string
}

export interface EvidenceSourceCreate {
  title: string
  organization?: string
  source_type?: string
  url?: string
  region?: string
  publication_date?: string
  next_review_due_at?: string
  evidence_status?: string
  notes?: string
}

export interface EvidenceSourceUpdate {
  title?: string
  organization?: string
  source_type?: string
  url?: string
  region?: string
  publication_date?: string
  last_checked_at?: string
  next_review_due_at?: string
  evidence_status?: string
  notes?: string
}

// ── Import Pipeline ────────────────────────────────────────────────────────

export interface FileSummary {
  file_name: string
  content_type: string | null
  total_rows: number
  valid_rows: number
  invalid_rows: number
  skipped_duplicates: number
  is_reference_only: boolean
}

export interface DuplicateSummary {
  duplicate_external_id_in_upload: number
  duplicate_hash_in_upload: number
  existing_external_id_in_db: number
  existing_hash_in_db: number
}

export interface RowError {
  file_name: string
  row_number: number
  external_id: string | null
  error_code: string
  message: string
  severity: string
}

export interface PreviewResult {
  total_rows: number
  valid_rows: number
  invalid_rows: number
  warnings: string[]
  errors_by_file: Record<string, string[]>
  file_summaries: FileSummary[]
  detected_content_types: string[]
  duplicate_summary: DuplicateSummary
  approval_batch_required: boolean
  row_errors: RowError[]
}

export interface CommitResult {
  import_batch_id: string
  created_items: number
  created_versions: number
  created_evidence_sources: number
  created_region_rules: number
  skipped_duplicates: number
  invalid_rows: number
  warnings: string[]
  approval_batch_id: string | null
  row_errors: RowError[]
}

// ── Governance Summary ─────────────────────────────────────────────────────

export interface GovernanceSummary {
  total_items: number
  by_status: Record<string, number>
  by_content_type: Record<string, number>
  evidence_due_count: number
  published_by_region: Record<string, number>
}

// ── Import Batches ─────────────────────────────────────────────────────────

export interface ImportBatchRead {
  id: string
  source_file_name: string
  package_type: string
  status: string
  total_rows: number
  valid_rows: number
  invalid_rows: number
  created_items: number
  created_versions: number
  created_evidence_sources: number
  created_region_rules: number
  skipped_duplicates: number
  approval_batch_id: string | null
  uploaded_by_user_id: string | null
  created_at: string
  committed_at: string | null
}

export interface ImportBatchListResponse {
  items: ImportBatchRead[]
  total: number
}

// ── Region Publishing Rules ────────────────────────────────────────────────

export interface RegionPublishingRuleRead {
  id: string
  region_code: string
  content_type: string | null
  domain: string | null
  allowed_statuses: string[] | null
  required_review_roles: string[] | null
  required_evidence_region: string | null
  requires_local_disclaimer: boolean
  requires_protocol_note: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface RegionPublishingRuleCreate {
  region_code: string
  content_type?: string
  domain?: string
  allowed_statuses?: string[]
  required_review_roles?: string[]
  required_evidence_region?: string
  requires_local_disclaimer?: boolean
  requires_protocol_note?: boolean
  is_active?: boolean
}

export interface RegionPublishingRuleUpdate {
  content_type?: string
  domain?: string
  allowed_statuses?: string[]
  required_review_roles?: string[]
  required_evidence_region?: string
  requires_local_disclaimer?: boolean
  requires_protocol_note?: boolean
  is_active?: boolean
}
