# Content Governance — Architecture & API Reference

## Overview

The content governance layer manages the full lifecycle of educational pharmacy content: creation, clinical review, regional publication, and learner failure analytics. It is designed around immutable version snapshots, multi-region publishing rules, and complete audit trails.

## Data Model

```
content_items                         (parent record per piece of content)
├── id (UUID PK)
├── title / content_type / domain / specialty / difficulty
├── region_scope (JSON list of region codes)
├── status (draft → pending_review → clinically_approved → published ↔ unpublished)
├── current_version_id → content_versions.id  (SET NULL, use_alter deferred FK)
├── external_id (for bulk import traceability)
├── created_by → users.id
└── created_at / updated_at / retired_at

content_versions                      (immutable snapshot per edit)
├── id (UUID PK)
├── content_item_id → content_items.id (CASCADE)
├── version_number (auto-incremented)
├── payload_json (full content payload)
├── evidence_ids (JSON list — references to evidence_sources)
├── change_summary / localization_notes
├── content_hash (SHA-256 of payload_json)
├── is_current (only one version per item is current)
├── source_file_name / source_row_number (for bulk import traceability)
└── created_by → users.id

evidence_sources                      (tracked external clinical evidence)
├── id (UUID PK)
├── title / organization / source_type / url
├── region (UK / US / GCC / AU)
├── publication_date / last_checked_at / next_review_due_at
├── evidence_status (active / needs_review / superseded / region_specific / retired)
└── created_at / updated_at

approval_batches                      (bulk external-reviewer sign-offs)
├── id (UUID PK)
├── batch_name / source_package_name / approved_by_team_name
├── approval_statement / approved_at
├── approved_by_user_id → users.id
├── region_scope (JSON) / content_count / signed_manifest_hash
└── created_at

clinical_reviews                      (per-item pharmacist sign-off)
├── id (UUID PK)
├── content_item_id → content_items.id (CASCADE)
├── content_version_id → content_versions.id (SET NULL)
├── reviewer_user_id → users.id (SET NULL)
├── approval_batch_id → approval_batches.id (SET NULL)
├── review_decision (approved / approved_with_conditions / rejected / needs_revision)
├── clinical_accuracy_score / safety_score / localization_score (0–1 float)
├── reviewer_role / reviewer_team_name / external_reviewer_reference
├── review_scope / comments
└── signed_off_at / review_due_at / created_at

region_publishing_rules               (per-region content type requirements)
├── id (UUID PK)
├── region_code / content_type / domain
├── allowed_statuses / required_review_roles (JSON)
├── required_evidence_region
├── requires_local_disclaimer / requires_protocol_note
└── is_active / created_at / updated_at

publication_records                   (track where/when content was published)
├── id (UUID PK)
├── content_item_id → content_items.id (CASCADE)
├── content_version_id → content_versions.id (CASCADE)
├── region_code
├── published_by / published_at
├── unpublished_by / unpublished_at
├── publication_status (published / unpublished / rolled_back)
├── reason
└── rollback_from_publication_id → publication_records.id (self-referential)

learner_failure_analytics             (content-version-aware outcome tracking)
├── id (UUID PK)
├── content_item_id → content_items.id (CASCADE)
├── content_version_id → content_versions.id (SET NULL)
├── user_id → users.id (SET NULL)
├── organization_id → organizations.id (SET NULL)
├── region_code / attempt_type / score
├── failed_red_flag / failed_counseling_point / failed_interaction_detection
├── failed_referral_decision / failed_dose_calculation / failed_documentation
├── time_to_decision_seconds
└── created_at
```

## Content Status Lifecycle

```
draft ──────────────────── (add version) ──► pending_review
pending_review ─────────── (clinical review: approved) ──► clinically_approved
clinically_approved ─────── (publish) ──► published
published ────────────────── (unpublish) ──► unpublished
published / unpublished ──── (retire) ──► retired
Any status ────────────────── (new version) ──► pending_review (re-review required)
```

**Publish prerequisites:**
1. Item must have a `current_version_id` (at least one version created)
2. Item must have at least one `ClinicalReview` with `review_decision` in `{approved, approved_with_conditions}`

## Supported Content Types

| Key | Description |
|-----|-------------|
| `case` | Clinical case study |
| `simulation` | Interactive OTC triage simulation |
| `osce_station` | OSCE examination station |
| `prescription_screening` | Rx screening workflow |
| `drill` | Rapid drill / flashcard set |
| `game` | Gamified learning activity |
| `evidence_source` | Evidence reference record |
| `taxonomy_node` | Curriculum hierarchy node |

## Region Codes

`UK`, `US`, `GCC`, `AU`

## Access Control

| Action | Required |
|--------|----------|
| Create / update content items | `is_superuser=True` |
| Create content versions | `is_superuser=True` |
| Rollback to a previous version | `is_superuser=True` |
| Submit clinical reviews | `is_superuser=True` |
| Publish / unpublish | `is_superuser=True` |
| Create approval batches | `is_superuser=True` |
| Create / update evidence sources | `is_superuser=True` |
| View due-for-review evidence | `is_superuser=True` |
| List published content | Any authenticated user |
| View a published item | Any authenticated user |
| View a draft / unpublished item | `is_superuser=True` |
| Record failure analytics | Any authenticated user |
| View analytics endpoints | `is_superuser=True` |

## API Endpoints

### Content Items

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/content/items` | Create a content item (admin) |
| `GET` | `/api/content/items` | List items (admins see all; learners see published only) |
| `GET` | `/api/content/items/{id}` | Get a single item |
| `GET` | `/api/content/published?region=UK` | List published items for a region |

### Content Versions

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/content/items/{id}/versions` | Add a new version (increments version_number) |
| `GET` | `/api/content/items/{id}/versions` | List all versions for an item |
| `POST` | `/api/content/items/{id}/versions/rollback/{version_id}` | Rollback to a prior version |

### Clinical Reviews

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/content/items/{id}/reviews` | Submit a clinical review |
| `GET` | `/api/content/items/{id}/reviews` | List reviews for an item |

### Publishing

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/content/items/{id}/publish` | Publish to a region |
| `POST` | `/api/content/items/{id}/unpublish` | Unpublish from a region |

### Approval Batches

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/content/approval-batches` | Create an approval batch |
| `GET` | `/api/content/approval-batches` | List approval batches |

### Bulk Import (Stubs)

| Method | Path | Status |
|--------|------|--------|
| `POST` | `/api/content/import/preview` | 501 Not Implemented |
| `POST` | `/api/content/import/commit` | 501 Not Implemented |

### Evidence Sources

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/evidence/sources` | Create an evidence source |
| `GET` | `/api/evidence/sources` | List evidence sources (filter by region, status) |
| `PATCH` | `/api/evidence/sources/{id}` | Update evidence source fields |
| `GET` | `/api/evidence/due-for-review` | List sources with overdue review dates |

### Analytics

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/analytics/failures` | Record a learner attempt outcome |
| `GET` | `/api/analytics/failure-hotspots` | Top content items by failure rate |
| `GET` | `/api/analytics/content/{id}/failure-summary` | Per-item failure breakdown by type |
| `GET` | `/api/analytics/organization/{org_id}/weakness-map` | Org-level weakness analysis |

## Audit Events

Every write action emits an `AuditLog` record:

| Action | Trigger |
|--------|---------|
| `content.item_created` | Content item created |
| `content.version_created` | New version added to item |
| `content.version_rollback` | Version rollback performed |
| `content.review_created` | Clinical review submitted |
| `content.published` | Item published to a region |
| `content.unpublished` | Item unpublished from a region |
| `content.approval_batch_created` | Approval batch recorded |
| `content.evidence_source_created` | Evidence source added |
| `content.evidence_source_updated` | Evidence source fields updated |

## Circular FK Design

`content_items.current_version_id → content_versions.id` and `content_versions.content_item_id → content_items.id` form a circular reference.

**Solution:** `use_alter=True` on `ContentItem.current_version_id` — SQLAlchemy creates both tables first (without the deferred FK), then adds the FK via `ALTER TABLE`. In SQLite (test environments) the `ALTER TABLE` step is a no-op; the constraint is only enforced in PostgreSQL (production).

The Alembic migration replicates this by calling `op.create_foreign_key(...)` after both tables are created.

## Security Constraints

- Learners **cannot** see unpublished, draft, or pending-review content
- Organization analytics are scoped by `organization_id` — admins specify the org; the query never crosses org boundaries
- `is_superuser` bypass follows existing platform rules
- No secrets, tokens, or clinical wording is logged — `extra_data` contains only safe metadata (IDs, field names, status strings)
- Clinical content is **never auto-generated** — all content payload comes from the caller (educator/admin); the API does not invoke the AI service for content creation
