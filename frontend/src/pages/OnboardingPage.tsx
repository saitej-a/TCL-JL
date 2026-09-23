/**
 * The §7.3 three-step onboarding wizard (Stitch steps 1–3 as visual
 * reference). Per-step persistence (the plan's resolution): step 1 saves via
 * POST/PATCH /profile/, step 2 saves `current_status` via PATCH (the
 * walk-the-chain side-channel), step 3 is review + confirm → refreshUser()
 * flips the truthful gate and releases /dashboard.
 *
 * Real API vocabulary (recorded divergences from the mockups): hiring types
 * are PRIME/DIGITAL/NINJA/OTHER — no "BPS"; there is no role field; region is
 * free text; completion requires offer_letter_date.
 */
import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import {
  getProfile,
  saveProfileStep1,
  ProfileNotFoundError,
  type CandidateProfilePrivate,
  type HiringType,
  type ProfileWritePayload,
} from "@/api/profile";
import { Button } from "@/components/Button";
import { Disclaimer } from "@/components/Disclaimer";
import { Input } from "@/components/Input";
import { createTimelineEvent, type TimelineEventType } from "@/api/timeline";
import type { CandidateStatus } from "@/types/user";
import { useAuth } from "@/context/AuthContext";
import { ErrorStrip } from "@/pages/authCard";

/**
 * The status picks the wizard offers, in the 4.1 chain order. Each maps to the
 * timeline event type whose creation walks the chain (multi-hop OK, 4.1 D1);
 * WITHDRAWN/OTHER have no event semantics so the wizard does not offer them —
 * they remain reachable later via Settings (PATCH-only path, 3.2).
 */
const STATUS_PICKS: ReadonlyArray<{ status: CandidateStatus; event: TimelineEventType; label: string }> = [
  { status: "INTERVIEWED", event: "INTERVIEW", label: "Interview completed — I attended the TCS interview" },
  { status: "SELECTED", event: "SELECTION", label: "Selection confirmed — I have been selected" },
  { status: "OFFER_RECEIVED", event: "OFFER_LETTER", label: "Offer received — I have the offer letter, no joining letter yet" },
  { status: "READINESS_SURVEY", event: "READINESS_SURVEY", label: "Readiness survey submitted on the TCS portal" },
  { status: "WAITING_FOR_JOINING_LETTER", event: "JOINING_LETTER", label: "Joining letter received — waiting for the joining date" },
  { status: "JOINING_DATE_RECEIVED", event: "JOINING_DATE", label: "Joining date confirmed — I know my joining date" },
  { status: "JOINED", event: "JOINED", label: "Joined — I have onboarded" },
];

const BATCHES = ["2024", "2025", "2026", "2027"] as const;

const STATUS_LABELS: Record<CandidateStatus, string> = {
  REGISTERED: "Registered",
  INTERVIEWED: "Interviewed",
  SELECTED: "Selected",
  OFFER_RECEIVED: "Offer received — I have the offer letter, no joining letter yet",
  READINESS_SURVEY: "Readiness survey submitted",
  WAITING_FOR_JOINING_LETTER: "Waiting for my joining letter",
  JOINING_LETTER_RECEIVED: "Joining letter received",
  JOINING_DATE_RECEIVED: "Joining date confirmed",
  JOINED: "Joined — I have onboarded",
  WITHDRAWN: "Withdrawn",
  OTHER: "Not sure / other",
};

interface Step1State {
  display_name: string;
  public_identity_mode: "ANONYMOUS" | "DISPLAY_NAME";
  hiring_type: HiringType;
  region: string;
  batch: string;
  offer_letter_date: string;
}

function StepIndicator({ step }: { step: 1 | 2 | 3 }) {
  const LABELS = ["Offer details", "Current status", "Review"] as const;
  return (
    <div aria-label={`Step ${step} of 3`} className="space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-brand-600 dark:text-brand-400">
          Step {step} of 3 — {LABELS[step - 1]}
        </p>
        <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
          {step === 1 ? "33" : step === 2 ? "66" : "100"}% completed
        </p>
      </div>
      <div className="flex gap-1.5">
        {([1, 2, 3] as const).map((s) => (
          <span
            key={s}
            className={`h-1.5 flex-1 rounded-full ${s <= step ? "bg-brand-600" : "bg-slate-200 dark:bg-slate-700"}`}
          />
        ))}
      </div>
      <div className="flex justify-between text-[11px] text-slate-400 dark:text-slate-500">
        {LABELS.map((label, i) => (
          <span key={label} className={i + 1 === step ? "font-semibold text-brand-600 dark:text-brand-400" : ""}>
            {i + 1}. {label}
          </span>
        ))}
      </div>
    </div>
  );
}

export function OnboardingPage() {
  const navigate = useNavigate();
  const { refreshUser } = useAuth();

  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [profile, setProfile] = useState<CandidateProfilePrivate | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1 state
  const [s1, setS1] = useState<Step1State>({
    display_name: "",
    public_identity_mode: "DISPLAY_NAME",
    hiring_type: "DIGITAL",
    region: "",
    batch: "2025",
    offer_letter_date: "",
  });
  // Step 2 state: the pick drives both the displayed label and the event written.
  const [status, setStatus] = useState<CandidateStatus>("OFFER_RECEIVED");
  const [statusEvent, setStatusEvent] = useState<TimelineEventType>("OFFER_LETTER");
  const [statusDate, setStatusDate] = useState<string>("");
  // Step 3 state (Stitch step-3 mockup: review rows + accuracy confirmation)
  const [confirmed, setConfirmed] = useState(false);

  // Boot: load any existing profile (resumed wizard) and seed the fields.
  useEffect(() => {
    let cancelled = false;
    getProfile()
      .then((existing) => {
        if (cancelled) return;
        setProfile(existing);
        setS1({
          display_name: existing.display_name,
          public_identity_mode: existing.public_identity_mode,
          hiring_type: existing.hiring_type,
          region: existing.region,
          batch: existing.batch,
          offer_letter_date: existing.offer_letter_date ?? "",
        });
        setStatus(existing.current_status);
        // Resume at the first incomplete step (per-step persistence payoff).
        setStep(existing.offer_letter_date === null ? 1 : existing.current_status === "REGISTERED" ? 2 : 3);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ProfileNotFoundError) {
          setProfile(null); // first visit: step 1
          setLoading(false);
        } else {
          setError("Could not load your profile. Please refresh and try again.");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function persistStep1(event: FormEvent) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setError(null);
    try {
      const payload: ProfileWritePayload = {
        display_name: s1.display_name.trim(),
        public_identity_mode: s1.public_identity_mode,
        batch: s1.batch,
        hiring_type: s1.hiring_type,
        region: s1.region.trim(),
        offer_letter_date: s1.offer_letter_date,
      };
      const saved = await saveProfileStep1(payload, profile);
      setProfile(saved);
      setStep(2);
    } catch (err) {
      const apiError = err as { message?: string };
      setError(apiError?.message ?? "Could not save. Check the fields and try again.");
    } finally {
      setSaving(false);
    }
  }

  async function persistStep2() {
    if (saving || statusDate === "") return;
    setSaving(true);
    setError(null);
    try {
      // The event creation walks the chain hop-by-hop server-side (4.1 D1),
      // advancing current_status legally — a REGISTERED user picking "Offer
      // received" becomes INTERVIEWED → SELECTED → OFFER_RECEIVED in one write.
      await createTimelineEvent({
        event_type: statusEvent,
        event_date: statusDate,
        description: `Recorded during onboarding (${status}).`,
      });
      setStep(3);
    } catch (err) {
      const apiError = err as { message?: string };
      setError(apiError?.message ?? "Could not record that milestone. Check the date and try again.");
    } finally {
      setSaving(false);
    }
  }

  async function finish() {
    if (saving) return;
    setSaving(true);
    try {
      await refreshUser(); // /me/ re-read: the truthful gate releases.
      navigate("/dashboard", { replace: true });
    } catch {
      setError("Could not refresh your session. Please reload.");
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <p className="text-sm text-slate-500 dark:text-slate-400" role="status">
          Loading your profile…
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="rounded-2xl border border-slate-100 bg-white p-8 shadow-xl dark:border-slate-800 dark:bg-slate-800">
        <StepIndicator step={step} />

        {error !== null && (
          <div className="mt-4">
            <ErrorStrip message={error} />
          </div>
        )}

        {step === 1 && (
          <form onSubmit={persistStep1} noValidate>
            <h1 className="mt-4 text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">
              Tell us about your offer
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              This powers your personal timeline. You can change it later in Settings.
            </p>
            <div className="mt-6 space-y-4">
              <div>
                <label
                  htmlFor="ob-display-name"
                  className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-200"
                >
                  Community display name
                </label>
                <Input
                  id="ob-display-name"
                  value={s1.display_name}
                  onChange={(e) => setS1({ ...s1, display_name: e.target.value })}
                  placeholder="How the community sees you"
                  maxLength={50}
                  required
                />
                <label className="mt-2 flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
                  <input
                    type="checkbox"
                    checked={s1.public_identity_mode === "ANONYMOUS"}
                    onChange={(e) =>
                      setS1({
                        ...s1,
                        public_identity_mode: e.target.checked ? "ANONYMOUS" : "DISPLAY_NAME",
                      })
                    }
                  />
                  Stay anonymous (show “Anonymous Candidate” instead of a name)
                </label>
              </div>

              <fieldset>
                <legend className="mb-1.5 text-sm font-medium text-slate-700 dark:text-slate-200">
                  Hiring type
                </legend>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  {(["PRIME", "DIGITAL", "NINJA", "OTHER"] as const).map((ht) => (
                    <label
                      key={ht}
                      className={`flex min-h-[44px] cursor-pointer items-center justify-center rounded-lg border px-3 py-2 text-sm font-medium capitalize ${
                        s1.hiring_type === ht
                          ? "border-brand-600 bg-brand-50 text-brand-700 dark:bg-brand-950/60 dark:text-brand-300"
                          : "border-slate-200 text-slate-600 hover:border-slate-300 dark:border-slate-700 dark:text-slate-300"
                      }`}
                    >
                      <input
                        type="radio"
                        name="hiring_type"
                        value={ht}
                        checked={s1.hiring_type === ht}
                        onChange={() => setS1({ ...s1, hiring_type: ht })}
                        className="sr-only"
                      />
                      {ht.toLowerCase()}
                    </label>
                  ))}
                </div>
              </fieldset>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="ob-region" className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-200">
                    Region of joining
                  </label>
                  <Input
                    id="ob-region"
                    value={s1.region}
                    onChange={(e) => setS1({ ...s1, region: e.target.value })}
                    placeholder="e.g. Hyderabad"
                    required
                  />
                </div>
                <div>
                  <label htmlFor="ob-batch" className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-200">
                    Batch
                  </label>
                  <select
                    id="ob-batch"
                    value={s1.batch}
                    onChange={(e) => setS1({ ...s1, batch: e.target.value })}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                  >
                    {BATCHES.map((b) => (
                      <option key={b} value={b}>
                        {b}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label htmlFor="ob-offer-date" className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-200">
                  Offer letter date
                </label>
                <Input
                  id="ob-offer-date"
                  type="date"
                  value={s1.offer_letter_date}
                  onChange={(e) => setS1({ ...s1, offer_letter_date: e.target.value })}
                  required
                />
              </div>

              <div className="flex items-center justify-between pt-2">
                <span className="text-xs text-slate-500 dark:text-slate-400">Step 1 — your details</span>
                <Button type="submit" variant="primary" loading={saving}>
                  Continue
                </Button>
              </div>
            </div>
          </form>
        )}

        {step === 2 && (
          <div>
            <h1 className="mt-4 text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">
              Where are you in the process?
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Pick the option that matches your latest official communication. It becomes a
              milestone on your timeline.
            </p>
            <div className="mt-6 space-y-2">
              {STATUS_PICKS.map((pick) => (
                <label
                  key={pick.status}
                  className={`flex min-h-[44px] cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-sm ${
                    status === pick.status
                      ? "border-brand-600 bg-brand-50 text-brand-900 dark:bg-brand-950/60 dark:text-brand-200"
                      : "border-slate-200 text-slate-700 hover:border-slate-300 dark:border-slate-700 dark:text-slate-300"
                  }`}
                >
                  <input
                    type="radio"
                    name="current_status"
                    value={pick.status}
                    checked={status === pick.status}
                    onChange={() => {
                      setStatus(pick.status);
                      setStatusEvent(pick.event);
                    }}
                    className="h-4 w-4"
                  />
                  {pick.label}
                </label>
              ))}
              <div>
                <label
                  htmlFor="ob-status-date"
                  className="mb-1.5 block text-sm font-medium text-slate-700 dark:text-slate-200"
                >
                  When did this happen?
                </label>
                <Input
                  id="ob-status-date"
                  type="date"
                  value={statusDate}
                  onChange={(e) => setStatusDate(e.target.value)}
                  required
                />
              </div>
            </div>
            <div className="mt-6 flex items-center justify-between">
              <Button type="button" variant="ghost" onClick={() => setStep(1)}>
                ← Back
              </Button>
              <Button type="button" variant="primary" loading={saving} onClick={persistStep2}>
                Continue
              </Button>
            </div>
            <p className="mt-4 flex items-center gap-2 rounded-xl border border-sky-100 bg-sky-50 px-3 py-2 text-xs text-sky-800 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-300">
              <span aria-hidden="true">ℹ️</span>
              Reporting an accurate status keeps the community timeline trustworthy.
            </p>
          </div>
        )}

        {step === 3 && (
          <div>
            <h1 className="mt-4 text-xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">
              Review your details
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Everything here can be updated later in Settings.
            </p>
            <p className="mt-4 flex items-center gap-2 rounded-xl border border-emerald-200/80 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300">
              <span aria-hidden="true">✓</span>
              Your timeline will start from your offer date.
            </p>
            <dl className="mt-6 divide-y divide-slate-100 rounded-xl border border-slate-200 dark:divide-slate-700 dark:border-slate-700">
              {[
                ["Display name", s1.public_identity_mode === "ANONYMOUS" ? "Anonymous" : s1.display_name, 1],
                ["Hiring type", s1.hiring_type.toLowerCase(), 1],
                ["Region of joining", s1.region, 1],
                ["Batch", s1.batch, 1],
                ["Offer letter date", s1.offer_letter_date, 1],
                ["Current status", STATUS_LABELS[status], 2],
              ].map(([label, value, targetStep]) => (
                <div key={label} className="flex items-center justify-between gap-4 px-4 py-3">
                  <dt className="text-xs font-medium text-slate-500 dark:text-slate-400">{label}</dt>
                  <dd className="flex items-center gap-3">
                    <span className="text-sm font-medium text-slate-800 dark:text-slate-200">{value}</span>
                    <button
                      type="button"
                      onClick={() => setStep(targetStep as 1 | 2)}
                      className="text-xs font-semibold text-brand-600 hover:underline dark:text-brand-400"
                    >
                      Edit
                    </button>
                  </dd>
                </div>
              ))}
            </dl>
            <label className="mt-4 flex items-start gap-2 text-xs text-slate-600 dark:text-slate-300">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
                className="mt-0.5 h-4 w-4"
                data-testid="confirm-accuracy"
              />
              <span>I confirm these details are accurate to the best of my knowledge.</span>
            </label>
            <div className="mt-6 flex items-center justify-between">
              <Button type="button" variant="ghost" onClick={() => setStep(2)}>
                ← Back
              </Button>
              <Button
                type="button"
                variant="primary"
                loading={saving}
                disabled={!confirmed}
                onClick={finish}
              >
                Finish and go to dashboard
              </Button>
            </div>
          </div>
        )}
      </div>
      <div className="mx-auto mt-6 max-w-xl text-center">
        <Disclaimer variant="footer" />
      </div>
    </div>
  );
}
