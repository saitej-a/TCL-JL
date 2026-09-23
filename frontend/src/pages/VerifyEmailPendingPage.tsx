/**
 * The §7.2.3 "check your inbox" screen with a resend-with-cooldown button.
 */
import { useEffect, useState } from "react";

import { resendVerification } from "@/api/auth";
import { Button } from "@/components/Button";
import { AuthCard, ErrorStrip, SuccessStrip } from "@/pages/authCard";

const RESEND_SECONDS = 60;

export function VerifyEmailPendingPage() {
  const [email, setEmail] = useState("");
  const [cooldown, setCooldown] = useState(0);
  const [resent, setResent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  async function handleResend() {
    if (sending || cooldown > 0) return;
    const entered = window.prompt("Enter the email you registered with:");
    if (entered === null || entered.trim() === "") return;
    setEmail(entered.trim());
    setSending(true);
    setError(null);
    try {
      await resendVerification(entered.trim());
      setResent(true);
      setCooldown(RESEND_SECONDS);
    } catch (error) {
      const apiError = error as { code?: string };
      if (apiError?.code === "RATE_LIMITED") {
        setError("Please wait before requesting another email.");
        setCooldown(30);
      } else {
        setError("Could not send the email. Please try again.");
      }
    } finally {
      setSending(false);
    }
  }

  return (
    <AuthCard
      title="Verify your email"
      subtitle="We sent a verification link to your inbox. Click it to activate your account."
    >
      <div className="space-y-4">
        {resent && <SuccessStrip message="Verification email sent." />}
        {error !== null && <ErrorStrip message={error} />}
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {email !== "" && <>Requested for {email}. </>}
          Didn't get it? Check your spam folder or resend the email.
        </p>
        <Button
          type="button"
          variant="primary"
          fullWidth
          onClick={handleResend}
          loading={sending}
          disabled={cooldown > 0}
        >
          {cooldown > 0 ? `Resend available in ${cooldown}s` : "Resend verification email"}
        </Button>
      </div>
    </AuthCard>
  );
}
