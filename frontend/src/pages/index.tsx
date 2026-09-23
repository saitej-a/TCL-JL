/**
 * Stub pages (Task 3): one placeholder per 05 §3.1 route so the SPA boots
 * end-to-end and every 9.2–9.4 sub-phase has a file to fill in. No view
 * logic, no data fetching — a title, a skeleton cluster, and an empty state
 * for the list routes.
 *
 * 9.2: LandingPage and OnboardingPage now live in their own files; the stubs
 * below remain for the routes later sub-phases own.
 */
import type { ReactElement } from "react";

import { SkeletonCard, Skeleton as SkeletonLine } from "@/components/Skeleton";
import { LandingPage } from "@/pages/LandingPage";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
import { ForgotPasswordPage } from "@/pages/ForgotPasswordPage";
import { VerifyEmailPendingPage } from "@/pages/VerifyEmailPendingPage";
import { VerifyEmailActionPage } from "@/pages/VerifyEmailActionPage";
import { ResetPasswordPage } from "@/pages/ResetPasswordPage";
import { OnboardingPage } from "@/pages/OnboardingPage";

export { LandingPage };
export { LoginPage };
export { RegisterPage };
export { ForgotPasswordPage };
export { VerifyEmailPendingPage };
export { VerifyEmailActionPage };
export { ResetPasswordPage };
export { OnboardingPage };

function StubPage({
  title,
  list = false,
}: {
  title: string;
  list?: boolean;
}): ReactElement {
  return (
    <main className="p-6 max-w-3xl mx-auto space-y-4">
      <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">{title}</h1>
      <SkeletonLine />
      {list ? (
        <>
          <SkeletonCard />
          <SkeletonCard />
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Nothing here yet.
          </p>
        </>
      ) : (
        <SkeletonCard />
      )}
    </main>
  );
}

// 05 §3 sitemap — public / informational
export function AboutPage(): ReactElement {
  return <StubPage title="About" />;
}
export function PrivacyPage(): ReactElement {
  return <StubPage title="Privacy Policy" />;
}
export function TermsPage(): ReactElement {
  return <StubPage title="Terms of Service" />;
}

// Auth surfaces (PublicOnly) — the real 9.2 screens are re-exported above.

// Authenticated surfaces (RequireAuth)
export function DashboardPage(): ReactElement {
  return <StubPage title="Dashboard" />;
}
export function TimelinePage(): ReactElement {
  return <StubPage title="Your timeline" />;
}
export function NotificationsPage(): ReactElement {
  return <StubPage title="Notifications" list />;
}
export function CreatePostPage(): ReactElement {
  return <StubPage title="Create a post" />;
}

// Public reads
export function CommunityFeedPage(): ReactElement {
  return <StubPage title="Community" list />;
}
export function PostDetailPage(): ReactElement {
  return <StubPage title="Post" list />;
}
export function AnalyticsPage(): ReactElement {
  return <StubPage title="Community analytics" />;
}

// Settings (+ children as 9.2 placeholders)
export function SettingsPage(): ReactElement {
  return <StubPage title="Settings" />;
}
export function SettingsProfilePage(): ReactElement {
  return <StubPage title="Profile information" />;
}
export function SettingsPrivacyPage(): ReactElement {
  return <StubPage title="Identity mode" />;
}
export function SettingsSecurityPage(): ReactElement {
  return <StubPage title="Password" />;
}
export function SettingsDevicesPage(): ReactElement {
  return <StubPage title="Devices" />;
}
export function SettingsDangerPage(): ReactElement {
  return <StubPage title="Delete account" />;
}

// Staff-only enforcement stays server-side (04 §113)
export function AdminReportsPage(): ReactElement {
  return <StubPage title="Moderation reports" list />;
}
export function AdminAnnouncementsPage(): ReactElement {
  return <StubPage title="Announcements" list />;
}

export function NotFoundPage(): ReactElement {
  return (
    <main className="p-6 max-w-3xl mx-auto space-y-4">
      <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Page not found</h1>
      <p className="text-sm text-slate-500 dark:text-slate-400">
        The page you are looking for does not exist or may have moved.
      </p>
    </main>
  );
}
