/**
 * Community API (04 §31–§37, §43) — 9.3 Task 5 foundation.
 *
 * Shapes mirror the shipped serializers exactly (apps/community/serializers.py):
 * the feed card is PostCardSerializer's 13 fields, the author sub-object is the
 * redaction boundary (display_name + cohort fields + avatar_seed, never email),
 * and the vote result carries `has_voted` (9.3 D3) so optimistic state can
 * reconcile against the server. Anonymous reads work: the client attaches a
 * Bearer only when a token exists, and D1 opened GET to visitors.
 */
import { apiDelete, apiGet, apiPost } from "@/api/client";
import type { Paginated } from "@/types/api";
import type { PostCategory } from "@/content/postCategories";

/** 04 §31's author shape (the privacy redaction boundary). */
export interface PostAuthor {
  id: string;
  display_name: string;
  batch: string;
  hiring_type: string;
  region: string;
  avatar_seed: number;
}

/** PostCardSerializer (04 §31) — tombstones render via masked title/body. */
export interface PostCard {
  id: string;
  author: PostAuthor;
  title: string;
  body: string;
  category: PostCategory;
  is_pinned: boolean;
  is_locked: boolean;
  is_deleted: boolean;
  vote_count: number;
  comment_count: number;
  has_voted: boolean;
  created_at: string;
  updated_at: string;
}

/** §31's tab parameter (the feed's two orders). */
export type PostTab = "newest" | "trending";

export interface PostListParams {
  tab?: PostTab;
  category?: string;
  search?: string;
  /** §31's whitelist: created_at | vote_count | comment_count (leading `-` allowed). */
  ordering?: string;
  page?: number;
}

/** VoteSerializer (04 §43 + 9.3 D3's has_voted). */
export interface VoteResult {
  id: string;
  vote_count: number;
  has_voted: boolean;
  is_pinned: boolean;
  is_locked: boolean;
}

export interface PostCreatePayload {
  title: string;
  body: string;
  category: string;
}

export function listCommunityPosts(
  params: PostListParams = {},
): Promise<Paginated<PostCard>> {
  return apiGet<Paginated<PostCard>>("/community/posts/", { ...params });
}

export function getCommunityPost(id: string): Promise<PostCard> {
  return apiGet<PostCard>(`/community/posts/${id}/`);
}

export function createCommunityPost(
  payload: PostCreatePayload,
): Promise<PostCard> {
  return apiPost<PostCard>("/community/posts/", payload);
}

export function voteCommunityPost(id: string): Promise<VoteResult> {
  return apiPost<VoteResult>(`/community/posts/${id}/vote/`);
}

/** DELETE /vote/ answers 204 with no body. */
export async function unvoteCommunityPost(id: string): Promise<void> {
  await apiDelete<unknown>(`/community/posts/${id}/vote/`);
}
