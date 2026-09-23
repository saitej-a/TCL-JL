/**
 * The §7.2.2 registration screen. Client-side validation is UX only — the
 * server stays the authority. Success → /verify-email-pending (the account is
 * created unverified). Note: display_name is NOT a registration field — it
 * lives on the candidate profile (the wizard's step 1 collects it).
 */
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { register } from "@/api/auth";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import {
  AuthCard,
  AuthField,
  ErrorStrip,
} from "@/pages/authCard";

export function RegisterPage() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mismatch = confirm !== "" && confirm !== password;
  const tooShort = password !== "" && password.length < 8;
  const canSubmit =
    email !== "" && password.length >= 8 && confirm === password && agreed && !submitting;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (mismatch || tooShort) {
      setErrorMessage(
        mismatch ? "Passwords do not match." : "Password must be at least 8 characters.",
      );
      return;
    }
    if (!canSubmit) return;
    setSubmitting(true);
    setErrorMessage(null);
    try {
      await register({ email, password, password_confirm: confirm });
      navigate("/verify-email-pending", { replace: true });
    } catch (error) {
      const apiError = error as { code?: string; message?: string };
      if (apiError?.code === "EMAIL_TAKEN" || /already/i.test(apiError?.message ?? "")) {
        setErrorMessage("An account with this email already exists.");
      } else {
        setErrorMessage(apiError?.message ?? "Registration failed. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthCard title="Create your account" subtitle="Join the community tracking TCS joining timelines.">
      <form onSubmit={handleSubmit} noValidate>
        <div className="space-y-4">
          <AuthField label="Email address" htmlFor="register-email">
            <Input
              id="register-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </AuthField>
          <AuthField
            label="Password"
            htmlFor="register-password"
            hint="Must be at least 8 characters."
          >
            <Input
              id="register-password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </AuthField>
          <AuthField label="Confirm password" htmlFor="register-confirm">
            <Input
              id="register-confirm"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              aria-invalid={mismatch || undefined}
            />
          </AuthField>
          {(mismatch || tooShort || errorMessage !== null) && (
            <ErrorStrip
              message={
                mismatch
                  ? "Passwords do not match."
                  : tooShort
                    ? "Password must be at least 8 characters."
                    : (errorMessage ?? "")
              }
            />
          )}
          <label className="flex items-start gap-2 text-xs text-slate-600 dark:text-slate-300">
            <input
              type="checkbox"
              checked={agreed}
              onChange={(e) => setAgreed(e.target.checked)}
              className="mt-0.5 h-4 w-4"
              data-testid="terms-checkbox"
            />
            <span>
              I agree to the{" "}
              <Link to="/terms" className="text-brand-600 hover:underline dark:text-brand-400">
                Terms
              </Link>{" "}
              and{" "}
              <Link to="/privacy" className="text-brand-600 hover:underline dark:text-brand-400">
                Privacy Policy
              </Link>
            </span>
          </label>
          <Button type="submit" variant="primary" fullWidth loading={submitting} disabled={!canSubmit}>
            Create account
          </Button>
        </div>
      </form>
      <p className="text-center text-sm text-slate-500 dark:text-slate-400">
        Already have an account?{" "}
        <Link to="/login" className="font-medium text-brand-600 hover:underline dark:text-brand-400">
          Sign in
        </Link>
      </p>
    </AuthCard>
  );
}
