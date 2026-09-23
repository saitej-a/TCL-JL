import type { PublicAuthor } from "@/types/user";

/** The literal sentinel `AuthorPublicSerializer` emits for anonymous/blank identities. */
export const ANONYMOUS_SENTINEL = "Anonymous Candidate";

/** §6.5's deterministic pastel pairs — indexed by a stable hash of the name. */
const PASTELS = [
  "bg-indigo-100 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300",
  "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300",
  "bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300",
  "bg-sky-100 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300",
  "bg-rose-100 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300",
  "bg-teal-100 text-teal-700 dark:bg-teal-950/60 dark:text-teal-300",
] as const;

/** Deterministic 0..(n-1) index from the display name (or explicit seed when the API ships one). */
function pastelIndex(seedSource: string, seed?: number): number {
  if (seed !== undefined) {
    return Math.abs(seed) % PASTELS.length;
  }
  let hash = 0;
  for (let i = 0; i < seedSource.length; i += 1) {
    hash = (hash * 31 + seedSource.charCodeAt(i)) | 0;
  }
  return Math.abs(hash) % PASTELS.length;
}

function initialsOf(displayName: string): string {
  const parts = displayName.trim().split(/\s+/).filter(Boolean);
  const first = parts[0]?.charAt(0) ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1]?.charAt(0) ?? "") : "";
  return `${first}${last}`.toUpperCase() || "?";
}

interface IdentityPillProps {
  author: PublicAuthor;
  className?: string;
}

/**
 * §6.5's identity presentation: a 36px avatar circle plus the cohort tagline
 * (`batch • hiring_type • region`, null-safe). Anonymous identities render
 * the mask glyph on a deterministic pastel; display names render two-letter
 * initials. NEVER renders an email or a real full name (privacy-first).
 */
export function IdentityPill({ author, className = "" }: IdentityPillProps) {
  const isAnonymous = author.display_name === ANONYMOUS_SENTINEL;
  const pastel = PASTELS[pastelIndex(author.display_name, author.avatar_seed)];

  const cohortParts = [author.batch, author.hiring_type, author.region].filter(
    (part): part is string => part !== null && part !== "",
  );
  const tagline = cohortParts.join(" • ");

  return (
    <div className={`flex items-center gap-3 ${className}`.trim()} data-testid="identity-pill">
      <div
        className={`w-9 h-9 rounded-full flex items-center justify-center font-semibold text-xs ${pastel}`}
        aria-hidden={isAnonymous ? undefined : "true"}
      >
        {isAnonymous ? "🎭" : initialsOf(author.display_name)}
      </div>
      <div className="flex flex-col min-w-0">
        <span className="text-sm font-medium text-slate-900 dark:text-slate-100 truncate">
          {author.display_name}
        </span>
        {tagline !== "" && (
          <span className="text-xs text-slate-500 dark:text-slate-400 truncate">{tagline}</span>
        )}
      </div>
    </div>
  );
}
