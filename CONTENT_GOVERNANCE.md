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
draft ──────────────── (create version) ──► pending_review
imported ────────────── (create version) ──► pending_review
pending_review ────────── (approved review) ──► clinically_approved
clinically_approved ────── (publish) ──► published
published ────────────────── (unpublish) ──► unpublished
published / unpublished ──── (retire) ──► retired  [manual]
published ────────────────── (create version) ──► needs_update
needs_update ─────────────── (approved review, re-publish) ──► published
```

**Status transition rules:**
- Creating a version on a `draft` or `imported` item → `pending_review`
- Creating a version on a `published` item → `needs_update` (signals re-review needed)
- Creating a version on `clinically_approved` → `pending_review` (re-review the new version)
- Rollback to prior version on `published` or `needs_update` → `needs_update`
- Rollback in any other state → `pending_review`
- Attempting to create a version on a `retired` item → 409 Conflict

**Publish prerequisites:**
1. Item must have a `current_version_id` (at least one version created)
2. Item must have at least one `ClinicalReview` with `review_decision` in `{approved, approved_with_conditions}` that targets either the current version or no specific version (`content_version_id IS NULL`)
3. Item must not be blocked by any active `RegionPublishingRule` for the target region

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

Content governance uses **platform-scoped RBAC**: a user needs the required permission in *any* active organization membership. The `is_superuser` flag bypasses all permission checks.

### Permissions (seeded by migration 005)

| Permission | Roles | Description |
|------------|-------|-------------|
| `content.import` | educator, institution_admin, platform_admin | Create content items and initiate bulk import |
| `content.review` | educator, content_reviewer, institution_admin, platform_admin | Submit and read clinical reviews |
| `content.approve` | content_reviewer, institution_admin, platform_admin | Submit approval-batch records |
| `content.publish` | institution_admin, platform_admin | Publish content to regions |
| `content.unpublish` | institution_admin, platform_admin | Unpublish content from regions |
| `content.version.create` | educator, content_reviewer, institution_admin, platform_admin | Create new content versions |
| `content.rollback` | institution_admin, platform_admin | Roll back to a prior version |
| `evidence.manage` | content_reviewer, institution_admin, platform_admin | Create and update evidence sources |
| `analytics.view` | educator, content_reviewer, institution_admin, platform_admin | View platform-level failure analytics |
| `analytics.view_org` | institution_admin, platform_admin | View analytics for a specific organization |

### Route RBAC Mapping

| Action | Permission required |
|--------|---------------------|
| Create content item | `content.import` |
| List / view content items | Any authenticated user |
| Create content version | `content.version.create` |
| List content versions | `content.review` |
| Rollback to prior version | `content.rollback` |
| Submit clinical review | `content.review` |
| List clinical reviews | `content.review` |
| Publish to region | `content.publish` |
| Unpublish from region | `content.unpublish` |
| Create approval batch | `content.approve` |
| List approval batches | `content.review` |
| Create evidence source | `evidence.manage` |
| Update evidence source | `evidence.manage` |
| List evidence sources | Any authenticated user |
| View due-for-review evidence | `evidence.manage` |
| Record failure analytics | Any authenticated user |
| View failure hotspots | `analytics.view` |
| View content failure summary | `analytics.view` |
| View org weakness map | `analytics.view_org` (org-scoped to the requested `org_id`) |

### Dependency Implementations

- `require_content_permission(perm)` — checks that the user has `perm` in **any** active org membership. Used for platform-scoped governance operations where content has no single owning org.
- `has_permission(perm)` — checks that the user has `perm` in the **specific org** given by the `org_id` path parameter. Used for org-level analytics to prevent cross-org data leakage.

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

## Region Publishing Rules

`RegionPublishingRule` records impose region-specific constraints on publication. When a publish request arrives, the system checks for any **active** rule matching `(region_code, content_type)`. If a matching active rule exists:

1. The item's current status must be in the rule's `allowed_statuses` list (if configured).
2. If `required_evidence_region` is set, at least one `active` `EvidenceSource` scoped to that region code must exist in the database.

If a blocking rule is found, the publish request is rejected with HTTP 409.

Rules with `is_active=False` are ignored — useful for drafting rules before enforcement.

## Circular FK Design

`content_items.current_version_id → content_versions.id` and `content_versions.content_item_id → content_items.id` form a circular reference.

**Solution:** `use_alter=True` on `ContentItem.current_version_id` — SQLAlchemy creates both tables first (without the deferred FK), then adds the FK via `ALTER TABLE`. In SQLite (test environments) the `ALTER TABLE` step is a no-op; the constraint is only enforced in PostgreSQL (production).

The Alembic migration replicates this by calling `op.create_foreign_key(...)` after both tables are created.

## Known Limitations

- **Bulk import not implemented.** `POST /api/content/import/preview` and `/commit` return 501. The `external_id`, `source_file_name`, and `source_row_number` fields on models are reserved for the upcoming import pipeline.
- **Evidence region enforcement is coarse.** The publish gate checks that *any* active evidence source exists for `required_evidence_region` — it does not verify that the evidence is linked to the specific content item being published.
- **RegionPublishingRule `required_review_roles`** is stored in JSON but not yet enforced at publish time. The field is reserved for future multi-role review gate logic.
- **`requires_local_disclaimer` / `requires_protocol_note`** are stored but not injected into the published payload — enforcement is deferred to the content rendering layer.
- **`analytics.view_org`** requires the path-param `org_id` to be the same org in which the user holds the permission. Cross-org access by a user with the permission in one org but not another is correctly blocked.
- **No learner-facing published-content API** is implemented yet; learner UI is a future milestone.

## Security Constraints

- Learners **cannot** see unpublished, draft, or pending-review content
- Organization analytics are scoped by `organization_id` — admins specify the org; the query never crosses org boundaries
- `is_superuser` bypass follows existing platform rules
- No secrets, tokens, or clinical wording is logged — `extra_data` contains only safe metadata (IDs, field names, status strings)
- Clinical content is **never auto-generated** — all content payload comes from the caller (educator/admin); the API does not invoke the AI service for content creation
