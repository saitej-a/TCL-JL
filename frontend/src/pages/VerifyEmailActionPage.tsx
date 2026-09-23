/**
 * The §7.2.4 verification action screen: visiting /verify-email/:token calls
 * the verify endpoint once and renders exactly one of the three outcomes.
 */
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { verifyEmail } from "@/api/auth";
import { Button } from "@/components/Button";
import { AuthCard, ErrorStrip, SuccessStrip } from "@/pages/authCard";

type Outcome = "verifying" | "success" | "failure";

export function VerifyEmailActionPage() {
  const { token = "" } = useParams();
  const [outcome, setOutcome] = useState<Outcome>("verifying");
  const attempted = useRef(false);

  useEffect(() => {
    if (attempted.current || token === "") return;
    attempted.current = true;
    verifyEmail(token)
      .then(() => setOutcome("success"))
      .catch(() => setOutcome("failure"));
  }, [token]);

  return (
    <AuthCard
      title="Verifying your email"
      subtitle="One moment while we confirm your verification link."
    >
      <div className="space-y-4">
        {outcome === "verifying" && (
          <p className="text-sm text-slate-500 dark:text-slate-400" role="status">
            Verifying…
          </p>
        )}
        {outcome === "success" && (
          <>
            <SuccessStrip message="Your email is verified. You can sign in now." />
            <Link
              to="/login"
              className="flex min-h-[44px] items-center justify-center rounded-lg bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700"
            >
              Sign in
            </Link>
          </>
        )}
        {outcome === "failure" && (
          <>
            <ErrorStrip message="This verification link is invalid or has expired." />
            <Button
              type="button"
              variant="outline"
              fullWidth
              onClick={() => {
                window.location.href = "/verify-email-pending";
              }}
            >
              Request a new email
            </Button>
            <Link
              to="/login"
              className="block text-center text-sm font-medium text-brand-600 hover:underline dark:text-brand-400"
            >
              Back to sign in
            </Link>
          </>
        )}
      </div>
    </AuthCard>
  );
}
