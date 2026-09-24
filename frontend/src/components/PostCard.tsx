/**
 * The §7.6 post card, in the spec's order: a top row carrying the category
 * badge and "Posted 2 hours ago", the title, the body, the §6.5 identity row
 * (IdentityPill consumes the redaction-safe author shape — including the
 * `batch • hiring_type • region` cohort caption), and a bottom **action row**:
 * `[▲ Upvote | 42]  💬 18 Comments  🔗 Share  ⚑ Report`.
 *
 * Per plan Task 8.2 the report/share affordances must never be silently dead:
 * - **Share** is implemented (copy the post's link), because the feed is public
 *   and URL-stateful — this is the honest reading of the spec's Share action.
 * - **Report** stays visible and disabled *with its reason* in the title;
 *   reporting belongs to the moderation surface (9.4/8.1).
 *
 * Tombstoned cards render the API's masked copy with voting and sharing closed.
 */
import { Link } from "react-router-dom";

import type { PostCard as PostCardData } from "@/api/community";
import { Badge } from "@/components/Badge";
import { IdentityPill } from "@/components/IdentityPill";
import { useToast } from "@/components/Toast";
import { UpvotePill, type CommitVote } from "@/components/UpvotePill";
import { timeAgo } from "@/utils/date";

export interface PostCardProps {
  post: PostCardData;
  /** Committed vote state for this card (owned by the feed). */
  voted: boolean;
  /**
   * Committed vote COUNT for this card, also owned by the feed. It must be the
   * store's value, not `post.vote_count` (which is the list fetch's stale
   * snapshot): dropping it made a *successful* vote visibly revert to the
   * pre-vote number the moment the optimistic overlay cleared.
   */
  count: number;
  onRequestVote: (postId: string, next: boolean) => Promise<{ has_voted?: boolean; vote_count?: number } | void>;
  onCommitVote: (postId: string, commit: CommitVote) => void;
}

const ACTION_CLASSES =
  "inline-flex min-h-[32px] items-center gap-1 rounded-lg px-2 text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:text-slate-400 dark:hover:bg-slate-700 dark:hover:text-slate-200";

export function PostCard({
  post,
  voted,
  count,
  onRequestVote,
  onCommitVote,
}: PostCardProps): React.ReactElement {
  const { toast } = useToast();
  const tombstone = post.is_deleted;

  async function handleShare(): Promise<void> {
    const url = `${window.location.origin}/community/posts/${post.id}`;
    try {
      await navigator.clipboard.writeText(url);
      toast({ message: "Post link copied to your clipboard.", variant: "success" });
    } catch {
      toast({
        message: "Could not copy the link. Copy it from the address bar instead.",
        variant: "error",
      });
    }
  }

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4 sm:p-5 dark:border-slate-800 dark:bg-slate-800">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge.category code={post.category} />
          {post.is_pinned && (
            <span className="text-[11px] font-medium text-brand-600 dark:text-brand-400">📌 Pinned</span>
          )}
          {tombstone && (
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">[removed]</span>
          )}
        </div>
        <span className="text-xs text-slate-500 dark:text-slate-400">
          Posted {timeAgo(post.created_at)}
        </span>
      </div>

      <h3 className="mt-2 text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-100">
        {tombstone ? (
          post.title
        ) : (
          <Link to={`/community/posts/${post.id}`} className="hover:text-brand-600 dark:hover:text-brand-400">
            {post.title}
          </Link>
        )}
      </h3>
      <p className="mt-1 line-clamp-3 text-sm text-slate-600 dark:text-slate-300">{post.body}</p>

      <div className="mt-3">
        <IdentityPill author={post.author} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 dark:border-slate-700">
        <UpvotePill
          voted={voted}
          count={count}
          disabled={tombstone || post.is_locked}
          disabledReason={
            tombstone
              ? "This post has been removed; voting is closed."
              : post.is_locked
                ? "This thread is locked; voting is closed."
                : undefined
          }
          request={(next) => onRequestVote(post.id, next)}
          onCommit={(commit) => onCommitVote(post.id, commit)}
        />
        <span
          className="text-xs text-slate-500 dark:text-slate-400"
          title={tombstone ? "Comments are closed on removed posts." : undefined}
        >
          💬 {post.comment_count} Comment{post.comment_count === 1 ? "" : "s"}
        </span>
        <button
          type="button"
          onClick={() => void handleShare()}
          disabled={tombstone}
          title={tombstone ? "Removed posts cannot be shared." : "Copy this post's link."}
          className={`${ACTION_CLASSES}${tombstone ? " cursor-not-allowed opacity-50" : ""}`}
        >
          <span aria-hidden="true">🔗</span> Share
        </button>
        <button
          type="button"
          disabled
          title="Reporting arrives with the moderation surface (Phase 9.4)."
          className={`${ACTION_CLASSES} cursor-not-allowed opacity-60`}
        >
          <span aria-hidden="true">⚑</span> Report
        </button>
      </div>
    </article>
  );
}
