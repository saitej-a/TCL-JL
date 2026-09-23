/**
 * The §7.2.1 login screen. Error mapping per 04 §10 / apps/accounts/exceptions:
 * INVALID_CREDENTIALS (inline strip), RATE_LIMITED (Retry-After countdown),
 * ACCOUNT_SUSPENDED (distinct copy). Unverified accounts land on
 * /verify-email-pending instead of the dashboard.
 */
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { useAuth } from "@/context/AuthContext";
import type { ApiError } from "@/api/errors";
import {
  AuthCard,
  AuthField,
  ErrorStrip,
} from "@/pages/authCard";

const INVALID_CREDENTIALS_TEXT = "Invalid email or password.";
const SUSPENDED_TEXT =
  "This account has been suspended. Contact support if you believe this is a mistake.";

function rateLimitText(retryAfter: number): string {
  return `Too many attempts. Try again in ${retryAfter} second${retryAfter === 1 ? "" : "s"}.`;
}

export function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [retrySeconds, setRetrySeconds] = useState<number | null>(null);

  // RATE_LIMITED: tick the countdown down to zero, then re-enable submit.
  useEffect(() => {
    if (retrySeconds === null || retrySeconds <= 0) return;
    const timer = window.setTimeout(() => setRetrySeconds((s) => (s === null ? null : s - 1)), 1000);
    return () => window.clearTimeout(timer);
  }, [retrySeconds]);

  const next = searchParams.get("next") ?? "/dashboard";

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting || retrySeconds !== null) return;
    setSubmitting(true);
    setErrorMessage(null);
    try {
      const loggedIn = await login(email, password);
      // §7.2: unverified accounts never reach the dashboard.
      if (!loggedIn.is_verified) {
        navigate("/verify-email-pending", { replace: true });
        return;
      }
      navigate(next.startsWith("/") ? next : "/dashboard", { replace: true });
    } catch (error) {
      const apiError = error as ApiError;
      if (apiError?.code === "RATE_LIMITED") {
        setRetrySeconds(apiError.retryAfter ?? 30);
        setErrorMessage(rateLimitText(apiError.retryAfter ?? 30));
      } else if (apiError?.code === "ACCOUNT_SUSPENDED") {
        setErrorMessage(SUSPENDED_TEXT);
      } else {
        setErrorMessage(INVALID_CREDENTIALS_TEXT);
      }
    } finally {
      setSubmitting(false);
    }
  }

  const locked = retrySeconds !== null && retrySeconds > 0;

  return (
    <AuthCard title="Welcome back" subtitle="Sign in to track your joining journey.">
      <form onSubmit={handleSubmit} noValidate>
        <div className="space-y-4">
          <AuthField label="Email address" htmlFor="login-email">
            <Input
              id="login-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </AuthField>
          <AuthField label="Password" htmlFor="login-password">
            <Input
              id="login-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </AuthField>
          <p className="text-right text-sm">
            <Link
              to="/forgot-password"
              className="font-medium text-brand-600 hover:underline dark:text-brand-400"
            >
              Forgot password?
            </Link>
          </p>
          {errorMessage !== null && <ErrorStrip message={errorMessage} />}
          <Button type="submit" variant="primary" fullWidth loading={submitting} disabled={locked}>
            {locked ? `Wait ${retrySeconds}s` : "Sign in"}
          </Button>
        </div>
      </form>
      <div className="flex items-center gap-3" aria-hidden="true">
        <span className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
        <span className="text-xs uppercase tracking-wider text-slate-400">or</span>
        <span className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
      </div>
      <Link
        to="/register"
        className="flex min-h-[44px] items-center justify-center rounded-lg border border-slate-200 px-4 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
      >
        Create an account
      </Link>
      {user !== null && <span className="hidden">{user.email}</span>}
    </AuthCard>
  );
}
