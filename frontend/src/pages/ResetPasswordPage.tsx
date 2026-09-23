/**
 * The §7.2.6 reset-password screen: new password + confirm against the
 * :token, success routes to /login.
 */
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { confirmPasswordReset } from "@/api/auth";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { AuthCard, AuthField, ErrorStrip } from "@/pages/authCard";

export function ResetPasswordPage() {
  const { token = "" } = useParams();
  const navigate = useNavigate();

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const mismatch = confirm !== "" && confirm !== password;
  const tooShort = password !== "" && password.length < 8;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (mismatch || tooShort || password === "") {
      setErrorMessage(
        mismatch
          ? "Passwords do not match."
          : "Password must be at least 8 characters.",
      );
      return;
    }
    setSubmitting(true);
    setErrorMessage(null);
    try {
      await confirmPasswordReset({ token, new_password: password, new_password_confirm: confirm });
      navigate("/login", { replace: true });
    } catch (error) {
      const apiError = error as { code?: string; message?: string };
      if (apiError?.code === "TOKEN_INVALID" || /expired|invalid/i.test(apiError?.message ?? "")) {
        setErrorMessage("This reset link is invalid or has expired. Request a new one.");
      } else {
        setErrorMessage(apiError?.message ?? "Could not reset the password. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthCard title="Choose a new password" subtitle="Pick a new password for your account.">
      <form onSubmit={handleSubmit} noValidate>
        <div className="space-y-4">
          <AuthField label="New password" htmlFor="reset-password" hint="At least 8 characters.">
            <Input
              id="reset-password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </AuthField>
          <AuthField label="Confirm new password" htmlFor="reset-confirm">
            <Input
              id="reset-confirm"
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
          <Button type="submit" variant="primary" fullWidth loading={submitting} disabled={mismatch}>
            Reset password
          </Button>
        </div>
      </form>
      <p className="text-center text-sm">
        <Link to="/login" className="font-medium text-brand-600 hover:underline dark:text-brand-400">
          ← Back to sign in
        </Link>
      </p>
    </AuthCard>
  );
}
