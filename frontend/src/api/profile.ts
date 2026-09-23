/**
 * Profile API (04 §19–§22) — the onboarding wizard's persistence layer.
 *
 * Field names byte-exact to CandidatePrivateSerializer / the create serializer.
 * Recorded divergences from the 05 §7.3 mockups (9.2 finding): there is NO
 * `role` field on CandidateProfile (the mockup's "Role / Designation" input has
 * no API target), hiring types are PRIME/DIGITAL/NINJA/OTHER (no "BPS"), and
 * `region` is free text.
 */
import { apiGet, apiPatch, apiPost } from "@/api/client";
import { ApiError } from "@/api/errors";
import type { CandidateStatus } from "@/types/user";

export type HiringType = "PRIME" | "DIGITAL" | "NINJA" | "OTHER";

export const HIRING_TYPES: readonly HiringType[] = ["PRIME", "DIGITAL", "NINJA", "OTHER"] as const;

export interface CandidateProfilePrivate {
  id: string;
  display_name: string;
  public_identity_mode: "ANONYMOUS" | "DISPLAY_NAME";
  batch: string;
  hiring_type: HiringType;
  region: string;
  interview_center: string;
  interview_date: string | null;
  joining_location: string;
  current_status: CandidateStatus;
  offer_letter_date: string | null;
  expected_joining_date: string | null;
  created_at: string;
  updated_at: string;
}

/** The wizard's step-1 fields (04 §20's create body; PATCH accepts the same set). */
export interface ProfileWritePayload {
  display_name: string;
  public_identity_mode: "ANONYMOUS" | "DISPLAY_NAME";
  batch: string;
  hiring_type: HiringType;
  region: string;
  offer_letter_date: string;
}

/** 404 shape of `GET /profile/` when no profile exists yet (the wizard's first visit). */
export class ProfileNotFoundError extends Error {
  readonly code = "PROFILE_NOT_FOUND";
}

export async function getProfile(): Promise<CandidateProfilePrivate> {
  try {
    return await apiGet<CandidateProfilePrivate>("/profile/");
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      throw new ProfileNotFoundError("No profile yet.");
    }
    throw error;
  }
}

/** Create (first save) or update (resumed wizard / edit) — chosen by profile existence. */
export function saveProfileStep1(
  payload: ProfileWritePayload,
  existing: CandidateProfilePrivate | null,
): Promise<CandidateProfilePrivate> {
  if (existing === null) {
    return apiPost<CandidateProfilePrivate>("/profile/", payload);
  }
  return apiPatch<CandidateProfilePrivate>("/profile/", payload);
}

/**
 * Step-2 status update: PATCH /profile/ with the `current_status` side-channel —
 * the view routes it through transition_status (4.1's walk-the-chain), so a
 * backwards or blocked transition fails server-side with a typed error and the
 * wizard surfaces it rather than pre-validating chains client-side.
 */
export function saveCurrentStatus(
  status: CandidateStatus,
): Promise<CandidateProfilePrivate> {
  return apiPatch<CandidateProfilePrivate>("/profile/", { current_status: status });
}
