/**
 * The §7.4 dashboard (9.3 Task 6): welcome header, milestone stepper,
 * community benchmark, community pulse, and the newest-discussions block.
 *
 * Two honesty rules govern every block:
 * - **Suppression** (4.2 D2): a suppressed analytics block renders the API's
 *   message and the COMMUNITY_REPORTED attribution — never zeros, never a
 *   blank card. The `DashboardAnalytics` union forces this at compile time.
 * - **D6's labelling**: the discussions block shows the community's newest
 *   posts and says exactly that. §7.4's "in your stream" narrowing is a
 *   recorded divergence (the feed endpoint has no stream filter), so the
 *   heading never implies stream filtering.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getDashboard, type DashboardPayload } from "@/api/dashboard";
import { listCommunityPosts, type PostCard } from "@/api/community";
import {
  listMyTimelineEvents,
  type TimelineEventPrivate,
  type TimelineEventType,
} from "@/api/timeline";
import { Badge } from "@/components/Badge";
import { EmptyState } from "@/components/EmptyState";
import { Skeleton, SkeletonCard } from "@/components/Skeleton";
import { MilestoneStepper } from "@/components/MilestoneStepper";
import { RailStatusSummary } from "@/components/RailStatusSummary";
import { RailPortal } from "@/layouts/AppShell";
import { STATUS_LABELS } from "@/theme/badges";
import { TYPOGRAPHY } from "@/theme/tokens";
import type { CandidateStatus } from "@/types/user";
import { daysSince, formatDateShort, timeAgo } from "@/utils/date";

const CARD =
  "rounded-xl border border-slate-200 bg-white p-4 sm:p-5 dark:border-slate-800 dark:bg-slate-800";

const CTA_PRIMARY =
  "flex min-h-[40px] items-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-brand-700";
const CTA_SECONDARY =
  "flex min-h-[40px] items-center rounded-lg border border-slate-300 px-4 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800";

/**
 * The candidate's own wait (§7.4's "Your wait time"), taken from their record:
 * days since the readiness survey, else since the offer, else since the latest
 * event. Returns null only when the record is empty — never a made-up number.
 */
function ownWaitDays(events: TimelineEventPrivate[]): number | null {
  if (events.length === 0) return null;
  const preference: readonly TimelineEventType[] = [
    "READINESS_SURVEY",
    "OFFER_LETTER",
    "SELECTION",
  ];
  for (const type of preference) {
    const match = events.filter((event) => event.event_type === type);
    if (match.length > 0) {
      const earliest = match.reduce((a, b) => (a.event_date < b.event_date ? a : b));
      return daysSince(earliest.event_date);
    }
  }
  const latest = events.reduce((a, b) => (a.event_date > b.event_date ? a : b));
  return daysSince(latest.event_date);
}

interface DashboardData {
  dashboard: DashboardPayload;
  events: TimelineEventPrivate[];
  posts: PostCard[];
}

/** §7.4's benchmark card, with the suppression discipline enforced by the union. */
function BenchmarkCard({ data }: { data: DashboardData | null }) {
  if (data === null) {
    return (
      <div className={CARD} aria-busy="true">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="mt-3 h-8 w-24" />
      </div>
    );
  }
  const analytics = data.dashboard.analytics;
  if (analytics.suppressed) {
    return (
      <div className={CARD}>
        <p className={TYPOGRAPHY.subheadLabel}>How you compare</p>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{analytics.message}</p>
        <p className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
          Community-reported data.
        </p>
      </div>
    );
  }
  const distribution = analytics.status_distribution;
  const wait = ownWaitDays(data.events);
  return (
    <div className={CARD}>
      <p className={TYPOGRAPHY.subheadLabel}>How you compare</p>
      {/* §7.4's row anatomy; every row is a real payload field. */}
      <ul className="mt-2 space-y-1.5 text-sm text-slate-600 dark:text-slate-300">
        <li className="flex items-baseline justify-between gap-3">
          <span>Candidates currently waiting</span>
          <span className="font-semibold text-slate-900 dark:text-slate-100">
            {analytics.community_waiting_count}
          </span>
        </li>
        <li className="flex items-baseline justify-between gap-3">
          <span>Reported receiving their joining letter</span>
          <span className="font-semibold text-slate-900 dark:text-slate-100">
            {distribution.JOINING_LETTER_RECEIVED}
          </span>
        </li>
        <li className="flex items-baseline justify-between gap-3">
          <span>Reported joining</span>
          <span className="font-semibold text-slate-900 dark:text-slate-100">
            {distribution.JOINED}
          </span>
        </li>
        {wait !== null && (
          <li className="flex items-baseline justify-between gap-3">
            <span>Your wait so far</span>
            <span className="font-semibold text-slate-900 dark:text-slate-100">{wait} days</span>
          </li>
        )}
      </ul>
      <p className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
        Community-reported data ({analytics.data_source.toLowerCase()}).
      </p>
    </div>
  );
}

/** §7.4's community pulse: derived strictly from real payload fields. */
function PulseCard({ data }: { data: DashboardData | null }) {
  if (data === null) {
    return (
      <div className={CARD} aria-busy="true">
        <Skeleton className="h-4 w-36" />
        <Skeleton className="mt-3 h-4 w-48" />
      </div>
    );
  }
  const analytics = data.dashboard.analytics;
  if (analytics.suppressed) {
    // Same discipline as the benchmark: the message, never fabricated numbers.
    return (
      <div className={CARD}>
        <p className={TYPOGRAPHY.subheadLabel}>Community pulse</p>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{analytics.message}</p>
        <p className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
          Community-reported data.
        </p>
      </div>
    );
  }
  const distribution = analytics.status_distribution;
  const rows = (Object.entries(distribution) as [CandidateStatus, number][])
    .filter(([, count]) => count > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4);
  return (
    <div className={CARD}>
      <p className={TYPOGRAPHY.subheadLabel}>Community pulse</p>
      {rows.length === 0 ? (
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
          No community activity has been reported yet.
        </p>
      ) : (
        /* §7.4's fact list, as label/value rows over the real distribution.
           The viewer's own unread count lives in the rail, not here. */
        <ul className="mt-2 space-y-1.5 text-sm text-slate-600 dark:text-slate-300">
          {rows.map(([status, count]) => (
            <li key={status} className="flex items-baseline justify-between gap-3">
              <span>{STATUS_LABELS[status] ?? status}</span>
              <span className="font-semibold text-slate-900 dark:text-slate-100">{count}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">
        Community-reported status counts.
      </p>
    </div>
  );
}

export function DashboardPage(): React.ReactElement {
  const [data, setData] = useState<DashboardData | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getDashboard(),
      listMyTimelineEvents().then((page) => page.results),
      listCommunityPosts({ tab: "newest" }).then((page) => page.results.slice(0, 5)),
    ])
      .then(([dashboard, events, posts]) => {
        if (cancelled) return;
        setData({ dashboard: dashboard, events: events, posts: posts });
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (failed) {
    return (
      <main className="mx-auto max-w-5xl p-4 lg:p-8">
        <EmptyState
          headline="Your dashboard could not be loaded"
          support="Check your connection and try again."
          actionLabel="Retry"
          onAction={() => window.location.reload()}
        />
      </main>
    );
  }

  const latest = data?.dashboard.timeline.latest_event ?? null;
  const since = latest !== null ? formatDateShort(latest.event_date) : null;

  return (
    <>
      <RailPortal>
        <RailStatusSummary
          status={data?.dashboard.profile.current_status ?? null}
          completion={data?.dashboard.profile.completion_percentage ?? null}
          unread={data?.dashboard.community.unread_notifications ?? null}
        />
      </RailPortal>

      <main className="mx-auto max-w-5xl space-y-4 p-4 lg:p-8">
        {/* Welcome header (§7.4) */}
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className={TYPOGRAPHY.pageTitle}>Hello, Candidate!</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
              <span>Status:</span>
              {data !== null ? (
                <>
                  <Badge.status value={data.dashboard.profile.current_status} />
                  {since !== null && <span>(Since {since})</span>}
                </>
              ) : (
                <Skeleton className="h-4 w-28" />
              )}
            </div>
          </div>
          {/* §7.4's header carries BOTH CTAs. */}
          <div className="flex flex-wrap items-center gap-2">
            <Link to="/community/create" className={CTA_SECONDARY}>
              Ask Question
            </Link>
            <Link to="/timeline" className={CTA_PRIMARY}>
              Update Timeline
            </Link>
          </div>
        </header>

        {/* Recruitment progression (§7.4.1) */}
        <section className={CARD} aria-label="Your recruitment progression">
          <p className={TYPOGRAPHY.subheadLabel}>Your recruitment progression</p>
          <div className="mt-3">
            {data === null ? <Skeleton className="h-16 w-full" /> : <MilestoneStepper events={data.events} />}
          </div>
        </section>

        {/* Benchmark + pulse (§7.4.2) */}
        <div className="grid gap-4 sm:grid-cols-2">
          <BenchmarkCard data={data} />
          <PulseCard data={data} />
        </div>

        {/* Latest discussions (§7.4.3, D6 labelling) */}
        <section className={CARD}>
          <div className="flex items-center justify-between">
            <p className={TYPOGRAPHY.subheadLabel}>Latest community discussions</p>
            <Link to="/community" className="text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-300">
              View all community discussions →
            </Link>
          </div>
          {data === null ? (
            <div className="mt-3 space-y-3" aria-busy="true">
              <SkeletonCard />
              <SkeletonCard />
            </div>
          ) : data.posts.length === 0 ? (
            <EmptyState
              headline="No discussions yet"
              support="Be the first to ask a question in the community."
              actionLabel="Ask a question"
            />
          ) : (
            <ul className="mt-3 divide-y divide-slate-200 dark:divide-slate-700">
              {data.posts.map((post) => {
                // §7.4's row caption: cohort • when • who. All three are real
                // `PostCardSerializer` fields (author is redaction-safe).
                const cohort = [post.author.hiring_type, post.author.region]
                  .filter((part) => part !== null && part !== "")
                  .join(" • ");
                return (
                  <li key={post.id} className="flex items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge.category code={post.category} />
                        <span className="text-[11px] text-slate-500 dark:text-slate-400">
                          Posted {timeAgo(post.created_at)}
                        </span>
                      </div>
                      <Link
                        to={`/community/posts/${post.id}`}
                        className="mt-1 block text-sm font-medium text-slate-900 hover:text-brand-600 dark:text-slate-100 dark:hover:text-brand-400"
                      >
                        {post.title}
                      </Link>
                      <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                        {cohort !== "" ? `${cohort} • ` : ""}by {post.author.display_name}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                      <span>{post.vote_count} ▲</span>
                      <span aria-hidden="true">💬</span>
                      <span>{post.comment_count}</span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          <p className="mt-3 text-[11px] text-slate-500 dark:text-slate-400">
            The community's newest posts — every candidate's discussions, not filtered to your stream.
          </p>
        </section>
      </main>
    </>
  );
}
