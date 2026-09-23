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
import { listMyTimelineEvents, type TimelineEventPrivate } from "@/api/timeline";
import { Badge } from "@/components/Badge";
import { EmptyState } from "@/components/EmptyState";
import { Skeleton, SkeletonCard } from "@/components/Skeleton";
import { MilestoneStepper } from "@/components/MilestoneStepper";
import { useAuth } from "@/context/AuthContext";
import { RailPortal } from "@/layouts/AppShell";
import { TYPOGRAPHY } from "@/theme/tokens";
import { daysSince, timeAgo } from "@/utils/date";

const CARD =
  "rounded-xl border border-slate-200 bg-white p-4 sm:p-5 dark:border-slate-800 dark:bg-slate-800";

interface DashboardData {
  dashboard: DashboardPayload;
  events: TimelineEventPrivate[];
  posts: PostCard[];
}

/** The right-rail status summary (rail chrome stays in AppShell). */
function RailStatusSummary({ data }: { data: DashboardData | null }) {
  return (
    <div className={CARD}>
      <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
        My Status Summary
      </p>
      {data === null ? (
        <Skeleton className="mt-2 h-4 w-32" />
      ) : (
        <>
          <div className="mt-2">
            <Badge.status value={data.dashboard.profile.current_status} />
          </div>
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            Profile {data.dashboard.profile.completion_percentage}% complete
          </p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            {data.dashboard.community.unread_notifications} unread notification
            {data.dashboard.community.unread_notifications === 1 ? "" : "s"}
          </p>
        </>
      )}
    </div>
  );
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
  return (
    <div className={CARD}>
      <p className={TYPOGRAPHY.subheadLabel}>How you compare</p>
      <p className="mt-2 text-2xl font-bold text-slate-900 dark:text-slate-100">
        {analytics.community_waiting_count}
      </p>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        candidates currently waiting, community-wide
      </p>
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
  return (
    <div className={CARD}>
      <p className={TYPOGRAPHY.subheadLabel}>Community pulse</p>
      <ul className="mt-2 space-y-1 text-sm text-slate-600 dark:text-slate-300">
        <li>{distribution.JOINING_LETTER_RECEIVED} candidates reported receiving their joining letter</li>
        <li>{distribution.JOINED} candidates reported joining</li>
        <li>
          {data.dashboard.community.unread_notifications} unread notification
          {data.dashboard.community.unread_notifications === 1 ? "" : "s"} for you
        </li>
      </ul>
    </div>
  );
}

export function DashboardPage(): React.ReactElement {
  const { user } = useAuth();
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
  const waitingSince = latest !== null ? daysSince(latest.event_date) : null;

  return (
    <>
      <RailPortal>
        <RailStatusSummary data={data} />
      </RailPortal>

      <main className="mx-auto max-w-5xl space-y-4 p-4 lg:p-8">
        {/* Welcome header (§7.4) */}
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className={TYPOGRAPHY.pageTitle}>
              Hello, {user?.email.split("@")[0] ?? "Candidate"}!
            </h1>
            <div className="mt-2 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
              <span>Status:</span>
              {data !== null ? (
                <>
                  <Badge.status value={data.dashboard.profile.current_status} />
                  {waitingSince !== null && <span>· {waitingSince} days since your last update</span>}
                </>
              ) : (
                <Skeleton className="h-4 w-28" />
              )}
            </div>
          </div>
          <Link
            to="/timeline"
            className="flex min-h-[40px] items-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white shadow-sm hover:bg-brand-700"
          >
            Update Timeline
          </Link>
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
              View all →
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
              {data.posts.map((post) => (
                <li key={post.id} className="py-3 first:pt-0 last:pb-0">
                  <Link to={`/community/posts/${post.id}`} className="block">
                    <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{post.title}</p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                      Posted {timeAgo(post.created_at)} · {post.vote_count} votes · {post.comment_count} comments
                    </p>
                  </Link>
                </li>
              ))}
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
