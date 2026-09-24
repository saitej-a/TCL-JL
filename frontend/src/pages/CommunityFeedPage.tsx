/**
 * The §7.6 community feed: header + create CTA, debounced (300ms) search,
 * category pills, sort tabs, pinned announcement, cards with optimistic
 * votes, pagination, and honest empty/error states. Filter state lives in
 * the URL (tab/category/search) so a filtered feed is linkable — the feed is
 * public since D1.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  listCommunityPosts,
  unvoteCommunityPost,
  voteCommunityPost,
  type PostCard as PostCardData,
} from "@/api/community";
import { listAnnouncements, type AnnouncementPublic } from "@/api/announcements";
import { getDashboard } from "@/api/dashboard";
import { CategoryTabs, FEED_TABS, type FeedTab } from "@/components/CategoryTabs";
import { EmptyState } from "@/components/EmptyState";
import { PostCard } from "@/components/PostCard";
import { RailStatusSummary } from "@/components/RailStatusSummary";
import { SkeletonCard } from "@/components/Skeleton";
import { useAuth } from "@/context/AuthContext";
import { RailPortal } from "@/layouts/AppShell";
import { TYPOGRAPHY } from "@/theme/tokens";
import type { CandidateStatus } from "@/types/user";
import { timeAgo } from "@/utils/date";

const PAGE_SIZE = 20;
const SEARCH_DEBOUNCE_MS = 300;

const VALID_TABS = new Set(FEED_TABS.map((entry) => entry.value));

interface VoteState {
  voted: boolean;
  count: number;
}

/** §7.6's rail fills the shell's slot with §7.4's status summary. */
interface RailState {
  status: CandidateStatus;
  completion: number;
  unread: number;
}

export function CommunityFeedPage(): React.ReactElement {
  const { status } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  const tabParam = searchParams.get("tab") ?? "newest";
  const tab: FeedTab = VALID_TABS.has(tabParam as FeedTab) ? (tabParam as FeedTab) : "newest";
  const categoryParam = searchParams.get("category");
  const searchParam = searchParams.get("search") ?? "";

  const [searchDraft, setSearchDraft] = useState(searchParam);
  const [posts, setPosts] = useState<PostCardData[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [votes, setVotes] = useState<Record<string, VoteState>>({});
  const [failed, setFailed] = useState(false);
  const [rail, setRail] = useState<RailState | null>(null);
  const [pinned, setPinned] = useState<AnnouncementPublic | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Keep the visible search draft in sync with back/forward navigation.
  useEffect(() => {
    setSearchDraft(searchParam);
  }, [searchParam]);

  const load = useCallback(
    (targetPage: number) => {
      setFailed(false);
      listCommunityPosts({
        tab: tab === "votes" ? "votes" : tab,
        category: categoryParam ?? undefined,
        search: searchParam === "" ? undefined : searchParam,
        page: targetPage,
      })
        .then((result) => {
          setPosts(result.results);
          setTotal(result.count);
          setVotes((current) => {
            const merged = { ...current };
            for (const post of result.results) {
              if (merged[post.id] === undefined) {
                merged[post.id] = { voted: post.has_voted, count: post.vote_count };
              }
            }
            return merged;
          });
        })
        .catch(() => {
          setFailed(true);
          setPosts(null);
        });
    },
    [tab, categoryParam, searchParam],
  );

  useEffect(() => {
    load(page);
  }, [load, page]);

  useEffect(() => {
    let cancelled = false;
    listAnnouncements()
      .then((result) => {
        if (cancelled) return;
        const announcement = result.results.find((item) => item.is_pinned) ?? null;
        setPinned(announcement);
      })
      .catch(() => {
        // The pinned card is a garnish; its failure is silent.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // The rail is a signed-in affordance: the design shows it beside the feed,
  // but a visitor has no status to summarise, so the request is not made at all
  // (the feed stays public and unauthenticated reads stay single-request).
  useEffect(() => {
    if (status !== "authenticated") {
      setRail(null);
      return;
    }
    let cancelled = false;
    getDashboard()
      .then((payload) => {
        if (cancelled) return;
        setRail({
          status: payload.profile.current_status,
          completion: payload.profile.completion_percentage,
          unread: payload.community.unread_notifications,
        });
      })
      .catch(() => {
        // A failed rail read leaves the slot empty; the feed itself is unaffected.
      });
    return () => {
      cancelled = true;
    };
  }, [status]);

  function updateParams(mutate: (params: URLSearchParams) => void): void {
    const next = new URLSearchParams(searchParams);
    mutate(next);
    setSearchParams(next);
    setPage(1);
  }

  function handleSearchDraftChange(value: string): void {
    setSearchDraft(value);
    if (debounceRef.current !== null) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      updateParams((params) => {
        if (value === "") {
          params.delete("search");
        } else {
          params.set("search", value);
        }
      });
    }, SEARCH_DEBOUNCE_MS);
  }

  function handleVote(postId: string, next: boolean) {
    return next ? voteCommunityPost(postId) : unvoteCommunityPost(postId);
  }

  function handleCommitVote(postId: string, commit: VoteState): void {
    setVotes((current) => ({ ...current, [postId]: commit }));
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const firstShown = total === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const lastShown = Math.min(page * PAGE_SIZE, total);
  const loading = posts === null && !failed;
  const createCta = useMemo(
    () => (
      <Link
        to="/community/create"
        className="flex min-h-[40px] items-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-brand-700"
      >
        + Create New Post
      </Link>
    ),
    [],
  );

  return (
    // The shell owns the frame (padding, sidebar, rail) — the page only owns
    // its own vertical rhythm, so it must not add a second max-width/padding.
    <main className="space-y-4">
      {status === "authenticated" && (
        <RailPortal>
          <RailStatusSummary
            status={rail?.status ?? null}
            completion={rail?.completion ?? null}
            unread={rail?.unread ?? null}
          />
        </RailPortal>
      )}

      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className={TYPOGRAPHY.pageTitle}>Community Discussions</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Connect, share updates, and compare notes with fellow candidates.
          </p>
        </div>
        {status === "authenticated" ? (
          createCta
        ) : (
          <Link
            to="/login?next=%2Fcommunity%2Fcreate"
            className="flex min-h-[40px] items-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-brand-700"
          >
            Sign in to post
          </Link>
        )}
      </header>

      {pinned !== null && (
        /* §7.6's pinned announcement card: eyebrow, title, body, and the pinned
           meta line. An announcement is not a post — it carries no votes,
           comments, or author — so none of those are rendered (D9). */
        <aside className="rounded-xl border border-brand-200 bg-brand-50 p-4 sm:p-5 dark:border-brand-800 dark:bg-brand-950/40">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-brand-700 dark:text-brand-300">
            📌 Pinned announcement
          </p>
          <p className="mt-1 text-sm font-semibold text-slate-900 dark:text-slate-100">{pinned.title}</p>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">{pinned.body}</p>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            Pinned{pinned.published_at !== null && <> • {timeAgo(pinned.published_at)}</>}
          </p>
        </aside>
      )}

      {/* §7.6 groups the search field, the pills and the tabs in one bordered
          filter block above the list. */}
      <section className="space-y-3 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-800">
        <div className="relative">
          <span
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            aria-hidden="true"
          >
            🔍
          </span>
          <input
            type="search"
            value={searchDraft}
            onChange={(event) => handleSearchDraftChange(event.target.value)}
            placeholder="Search posts by keyword, location, or batch..."
            aria-label="Search posts"
            className="h-10 w-full rounded-lg border border-slate-300 bg-white pl-9 pr-3 text-sm dark:border-slate-600 dark:bg-slate-900"
          />
        </div>

        <CategoryTabs
          category={categoryParam}
          tab={tab}
          onCategoryChange={(next) =>
            updateParams((params) => {
              if (next === null) {
                params.delete("category");
              } else {
                params.set("category", next);
              }
            })
          }
          onTabChange={(next) =>
            updateParams((params) => {
              params.set("tab", next);
            })
          }
        />
      </section>

      {failed ? (
        <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-200">
          <p>The feed could not be loaded.</p>
          <button
            type="button"
            onClick={() => load(page)}
            className="mt-2 min-h-[36px] rounded-lg border border-rose-300 px-3 text-xs font-semibold text-rose-700 hover:bg-rose-100 dark:border-rose-700 dark:text-rose-200"
          >
            Retry
          </button>
        </div>
      ) : loading ? (
        <div className="space-y-4" aria-busy="true">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : (posts ?? []).length === 0 ? (
        <EmptyState
          headline={
            searchParam === ""
              ? "No discussions found in this category."
              : "No discussions match your search."
          }
          support="Be the first candidate to share an update or question."
          actionLabel="Create Post"
          onAction={() => window.location.assign("/community/create")}
        />
      ) : (
        <>
          <div className="space-y-4">
            {(posts ?? []).map((post) => (
              <PostCard
                key={post.id}
                post={post}
                voted={votes[post.id]?.voted ?? post.has_voted}
                count={votes[post.id]?.count ?? post.vote_count}
                onRequestVote={handleVote}
                onCommitVote={handleCommitVote}
              />
            ))}
          </div>
          {total > 0 && (
            <nav
              className="flex flex-wrap items-center justify-between gap-3"
              aria-label="Feed pagination"
            >
              <span className="text-xs text-slate-500 dark:text-slate-400">
                Showing {firstShown}-{lastShown} of {total} posts
              </span>
              <span className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  className="min-h-[36px] rounded-lg border border-slate-300 px-3 text-sm dark:border-slate-600 disabled:opacity-40"
                >
                  ← Previous
                </button>
                <span className="text-xs text-slate-500 dark:text-slate-400">
                  Page {page} of {pageCount}
                </span>
                <button
                  type="button"
                  disabled={page >= pageCount}
                  onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
                  className="min-h-[36px] rounded-lg border border-slate-300 px-3 text-sm dark:border-slate-600 disabled:opacity-40"
                >
                  Next →
                </button>
              </span>
            </nav>
          )}
        </>
      )}
    </main>
  );
}
