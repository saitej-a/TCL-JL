/**
 * Backend vocabulary unions (Task 2's types file, consumed by Task 1's maps).
 *
 * These are typed to the SHIPPED backend contracts, not to the spec tables:
 * - `PostCategory` mirrors `config/settings/base.py` POST_CATEGORIES (12 keys,
 *   read at call time — a settings-added category must extend this union
 *   deliberately, which is the compile error that keeps the badge map honest).
 * - `CandidateStatus` mirrors `apps/candidates/models.py` Status (11 choices).
 *
 * Recorded divergence (Task 1/9.1 finding): 05 §4.1.4's badge matrix lists 10
 * rows — its `OFFER` is the API's `OFFER_LETTER`, and `LOCATION`/`DOCUMENTS`
 * have no spec row (they use the GENERAL slate treatment as the fallback).
 */

export type PostCategory =
  | "GENERAL"
  | "JOINING_LETTER"
  | "OFFER_LETTER"
  | "JOINING_DATE"
  | "LOCATION"
  | "INTERVIEW"
  | "DOCUMENTS"
  | "DISCUSSION"
  | "TCS_PROCESS"
  | "HELP"
  | "ANNOUNCEMENT"
  | "OTHER";

export const POST_CATEGORIES = [
  "GENERAL",
  "JOINING_LETTER",
  "OFFER_LETTER",
  "JOINING_DATE",
  "LOCATION",
  "INTERVIEW",
  "DOCUMENTS",
  "DISCUSSION",
  "TCS_PROCESS",
  "HELP",
  "ANNOUNCEMENT",
  "OTHER",
] as const satisfies readonly PostCategory[];

export type CandidateStatus =
  | "REGISTERED"
  | "INTERVIEWED"
  | "SELECTED"
  | "OFFER_RECEIVED"
  | "READINESS_SURVEY"
  | "WAITING_FOR_JOINING_LETTER"
  | "JOINING_LETTER_RECEIVED"
  | "JOINING_DATE_RECEIVED"
  | "JOINED"
  | "WITHDRAWN"
  | "OTHER";

export const CANDIDATE_STATUSES = [
  "REGISTERED",
  "INTERVIEWED",
  "SELECTED",
  "OFFER_RECEIVED",
  "READINESS_SURVEY",
  "WAITING_FOR_JOINING_LETTER",
  "JOINING_LETTER_RECEIVED",
  "JOINING_DATE_RECEIVED",
  "JOINED",
  "WITHDRAWN",
  "OTHER",
] as const satisfies readonly CandidateStatus[];

/**
 * The self payload exactly as `UserPrivateSerializer` ships it (04 §18):
 * `{id, email, is_verified, created_at, profile_completed}`.
 *
 * Known backend defect (recorded in STATE.md Pending Todos): the API still
 * hardcodes `profile_completed` to `false` — the 3.1 stub never changed. The
 * type stays honest to the wire; 9.2's onboarding gate must not trust it
 * until the backend fix lands.
 */
export interface UserPrivate {
  id: string;
  email: string;
  is_verified: boolean;
  created_at: string;
  profile_completed: boolean;
}

/**
 * The public author payload (`AuthorPublicSerializer`):
 * `{id, display_name, batch, hiring_type, region}`.
 *
 * `display_name` collapses to the literal "Anonymous Candidate" sentinel for
 * both anonymous profiles and profile-less users (recorded coupling). No
 * `avatar_seed` field ships despite the plan assuming one — IdentityPill
 * derives the pastel from `display_name` instead, keeping determinism without
 * inventing API fields.
 */
export interface PublicAuthor {
  id: string;
  display_name: string;
  batch: string | null;
  hiring_type: string | null;
  region: string | null;
  /** Planned-but-unsaf 04 field; tolerated as optional if the API adds it. */
  avatar_seed?: number;
}

/** The login response (FamilyTokenObtainPairSerializer): both tokens + user. */
export interface LoginResponse {
  access: string;
  refresh: string;
  user: UserPrivate;
}

/** The refresh response (FamilyTokenRefreshSerializer): BOTH rotated tokens. */
export interface TokenRefreshResponse {
  access: string;
  refresh: string;
}
