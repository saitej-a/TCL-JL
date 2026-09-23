/**
 * The post-category vocabulary (9.3 D7): the ONE frontend module holding the
 * 12 post-category keys — the settings-held `POST_CATEGORIES` union
 * (config/settings/base.py, read at call time). The `PostCategory` union is
 * derived from this array, so every consumer (badge map, feed pills, the
 * create-post form) compiles against the same single list.
 *
 * 04 §31's `/community/posts/categories/` endpoint does not exist yet
 * (recorded in 09.3's Deferred Items), so the key list lives here, duplicated
 * deliberately from the backend, and `postCategories.test.ts` pins the exact
 * set — a backend-side change that adds or renames a key fails loudly here
 * instead of silently dropping a filter pill.
 */

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
] as const;

/** The 04 §31 key union, derived — never re-declared anywhere else. */
export type PostCategory = (typeof POST_CATEGORIES)[number];
