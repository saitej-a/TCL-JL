/**
 * The §7.7 create-post page (9.3 D5): title, body, and a category picker
 * driven by D7's single vocabulary module. Client-side required/length checks
 * pre-validate; the server's two writer rejections render **distinctly**:
 *
 * - `scam_pattern_detected` — the text was blocked by 8.1's scanner. The copy
 *   never implies "try rewording": posting variations of scam text is what
 *   the scanner exists to stop.
 * - `duplicate_post` — 8.1 D6's 60-minute debounce on (title, body) hashes.
 *   The copy names the window so the delay is legible.
 *
 * A 201 navigates back to the feed.
 */
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { createCommunityPost } from "@/api/community";
import { ApiError } from "@/api/errors";
import { getProfile } from "@/api/profile";
import { Button } from "@/components/Button";
import { ANONYMOUS_SENTINEL } from "@/components/IdentityPill";
import { Input } from "@/components/Input";
import { Textarea } from "@/components/Textarea";
import { POST_CATEGORIES } from "@/content/postCategories";
import { CATEGORY_LABELS } from "@/theme/badges";
import { TYPOGRAPHY } from "@/theme/tokens";

const TITLE_MAX = 200;
const BODY_MAX = 5000;

/** §7.7's "Posting as:" preview, built from the viewer's own profile. */
function identityPreviewLabel(profile: {
  display_name: string;
  public_identity_mode: "ANONYMOUS" | "DISPLAY_NAME";
  batch: string;
  hiring_type: string;
  region: string;
}): { handle: string; anonymous: boolean } {
  const anonymous = profile.public_identity_mode === "ANONYMOUS" || profile.display_name.trim() === "";
  const cohort = [profile.batch, profile.hiring_type, profile.region]
    .filter((part) => part !== "")
    .join(" • ");
  const handle = anonymous ? ANONYMOUS_SENTINEL : profile.display_name;
  return { handle: cohort === "" ? handle : `${handle} • ${cohort}`, anonymous: anonymous };
}

const SCAM_COPY =
  "This post was blocked by our anti-scam screening. The text matches patterns we do not allow in the community.";
const DUPLICATE_COPY =
  "You already posted this within the last 60 minutes. Duplicate posts are debounced to keep the feed readable.";

export function CreatePostPage(): React.ReactElement {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [category, setCategory] = useState<string>(POST_CATEGORIES[0] ?? "GENERAL");
  const [clientError, setClientError] = useState<string | null>(null);
  const [blocked, setBlocked] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [identity, setIdentity] = useState<{ handle: string; anonymous: boolean } | null>(null);

  useEffect(() => {
    let cancelled = false;
    getProfile()
      .then((profile) => {
        if (!cancelled) setIdentity(identityPreviewLabel(profile));
      })
      .catch(() => {
        // No profile yet (the wizard's first visit) or the read failed: the
        // preview is a courtesy, so it simply does not render.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setClientError(null);
    setBlocked(null);

    if (title.trim() === "") {
      setClientError("A title is required.");
      return;
    }
    if (title.length > TITLE_MAX) {
      setClientError(`Keep the title under ${TITLE_MAX} characters.`);
      return;
    }
    if (body.trim() === "") {
      setClientError("The post body is required.");
      return;
    }
    if (body.length > BODY_MAX) {
      setClientError(`Keep the body under ${BODY_MAX} characters.`);
      return;
    }

    setSaving(true);
    try {
      await createCommunityPost({ title: title.trim(), body: body.trim(), category: category });
      navigate("/community");
    } catch (error) {
      if (error instanceof ApiError && error.code === "scam_pattern_detected") {
        setBlocked(SCAM_COPY);
      } else if (error instanceof ApiError && error.code === "duplicate_post") {
        setBlocked(DUPLICATE_COPY);
      } else {
        setBlocked("Your post could not be published. Please try again.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl space-y-4 p-4 lg:p-8">
      <h1 className={TYPOGRAPHY.pageTitle}>Create Community Discussion Post</h1>

      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4" noValidate>
        <div>
          <Input
            label="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={TITLE_MAX}
            required
            placeholder="e.g. Anyone from Hyderabad received the JL email today?"
          />
          {/* §7.7's live character counter. */}
          <p className="mt-1 text-right text-[11px] text-slate-500 dark:text-slate-400">
            {title.length} / {TITLE_MAX} characters
          </p>
        </div>
        <div>
          <Textarea
            label="Body"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            maxLength={BODY_MAX}
            required
            rows={8}
            placeholder="Describe your question, update, or experience in detail..."
          />
          <p className="mt-1 text-right text-[11px] text-slate-500 dark:text-slate-400">
            {body.length} / {BODY_MAX} characters
          </p>
        </div>

        {identity !== null && (
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 dark:border-slate-700 dark:bg-slate-800/60">
            <p className={TYPOGRAPHY.subheadLabel}>Posting as</p>
            <p className="mt-1 text-sm text-slate-700 dark:text-slate-200">
              {identity.anonymous && <span aria-hidden="true">🎭 </span>}
              {identity.handle}
            </p>
            {identity.anonymous && (
              <p className="mt-1 text-[11px] text-slate-500 dark:text-slate-400">
                To post with your display name instead, update your privacy settings.
              </p>
            )}
          </div>
        )}

        <fieldset>
          <legend className={TYPOGRAPHY.subheadLabel}>Category</legend>
          <div className="mt-2 flex flex-wrap gap-2">
            {POST_CATEGORIES.map((key) => (
              <button
                key={key}
                type="button"
                aria-pressed={category === key}
                onClick={() => setCategory(key)}
                className={[
                  "min-h-[36px] rounded-full px-3 text-xs font-medium transition-colors",
                  category === key
                    ? "bg-brand-600 text-white"
                    : "border border-slate-300 text-slate-600 hover:border-brand-300 hover:text-brand-600 dark:border-slate-600 dark:text-slate-300",
                ].join(" ")}
              >
                {CATEGORY_LABELS[key]}
              </button>
            ))}
          </div>
        </fieldset>

        {clientError !== null && (
          <p role="alert" className="text-sm text-rose-600 dark:text-rose-400">
            {clientError}
          </p>
        )}
        {blocked !== null && (
          <div
            role="alert"
            className="rounded-lg border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-800 dark:border-rose-700 dark:bg-rose-950/40 dark:text-rose-200"
          >
            {blocked}
          </div>
        )}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={() => navigate("/community")}>
            Cancel
          </Button>
          <Button type="submit" loading={saving}>
            Publish Post
          </Button>
        </div>
      </form>
    </main>
  );
}
