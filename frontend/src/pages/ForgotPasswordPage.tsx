/**
 * The §7.2.5 forgot-password screen. The success copy is enumeration-safe
 * (the same response regardless of whether the email exists).
 */
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { requestPasswordReset } from "@/api/auth";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { AuthCard, AuthField, SuccessStrip } from "@/pages/authCard";

const SENT_TEXT = "If that email exists, a reset link is on its way.";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting || email === "") return;
    setSubmitting(true);
    try {
      await requestPasswordReset(email);
      setSent(true);
    } catch {
      // Enumeration-safe: even on failure, present the same sent state.
      setSent(true);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthCard title="Reset your password" subtitle="Enter the email you registered with and we will send you a reset link.">
      <form onSubmit={handleSubmit} noValidate>
        <div className="space-y-4">
          <AuthField label="Email address" htmlFor="forgot-email">
            <Input
              id="forgot-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </AuthField>
          {sent && <SuccessStrip message={SENT_TEXT} />}
          <Button type="submit" variant="primary" fullWidth loading={submitting}>
            Send reset link
          </Button>
        </div>
      </form>
      <p className="text-center text-sm">
        <Link
          to="/login"
          className="font-medium text-brand-600 hover:underline dark:text-brand-400"
        >
          ← Back to sign in
        </Link>
      </p>
    </AuthCard>
  );
}
