/**
 * The §7.5 add/edit timeline modal. The write body stays exactly
 * {event_type, event_date, description} — `auto_update_status` is
 * server-hardcoded (4.2 R4) and is never sent. A mapped event advances
 * `current_status` server-side (4.1's walk-the-chain), which the auto-status
 * note states in the UI.
 *
 * Validation is surfaced, not pre-empted: a date the server rejects
 * (e.g. the 730-day horizon, or a future JOINING_LETTER) renders the
 * server's message inline next to the field, verbatim.
 */
import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "@/api/errors";
import type { TimelineEventType } from "@/api/timeline";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { Modal } from "@/components/Modal";
import { Textarea } from "@/components/Textarea";
import { TYPOGRAPHY } from "@/theme/tokens";

export const EVENT_TYPE_OPTIONS: readonly { value: TimelineEventType; label: string }[] = [
  { value: "INTERVIEW", label: "Technical & HR Interview" },
  { value: "SELECTION", label: "Selection Communicated" },
  { value: "OFFER_LETTER", label: "Offer Letter Issued" },
  { value: "READINESS_SURVEY", label: "Joining Readiness Survey Submitted" },
  { value: "JOINING_LETTER", label: "Joining Letter" },
  { value: "JOINING_DATE", label: "Joining Date & Onboarding" },
  { value: "JOINED", label: "Joined TCS" },
  { value: "OTHER", label: "Other" },
] as const;

export interface TimelineEventModalProps {
  open: boolean;
  /** Add mode when null, edit mode otherwise. */
  event: { id: string; event_type: TimelineEventType; event_date: string; description: string } | null;
  /** Pre-selected type for §7.5's quick actions ("Mark as Received" / "Set Date"). */
  presetType?: TimelineEventType;
  onClose: () => void;
  onSubmit: (payload: { event_type: TimelineEventType; event_date: string; description: string }) => Promise<void>;
}

export function TimelineEventModal({ open, event, presetType, onClose, onSubmit }: TimelineEventModalProps): React.ReactElement {
  const [eventType, setEventType] = useState<TimelineEventType>("OTHER");
  const [eventDate, setEventDate] = useState("");
  const [description, setDescription] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setEventType(event?.event_type ?? presetType ?? "OTHER");
      setEventDate(event?.event_date ?? new Date().toISOString().slice(0, 10));
      setDescription(event?.description ?? "");
      setFieldError(null);
      setFormError(null);
      setSaving(false);
    }
  }, [open, event, presetType]);

  async function handleSubmit(formEvent: FormEvent): Promise<void> {
    formEvent.preventDefault();
    setSaving(true);
    setFieldError(null);
    setFormError(null);
    try {
      await onSubmit({ event_type: eventType, event_date: eventDate, description: description });
    } catch (error) {
      if (error instanceof ApiError) {
        // DRF's raw field-errors shape lands in `details` (errors.ts): render
        // the first message for the field it names; anything else is form-wide.
        const details = error.details;
        if (details !== null && typeof details === "object" && !Array.isArray(details)) {
          const record = details as Record<string, unknown>;
          const dateMessages = record["event_date"];
          if (Array.isArray(dateMessages) && dateMessages.length > 0) {
            setFieldError(String(dateMessages[0]));
          } else {
            const first = Object.values(record)[0];
            if (first !== undefined) {
              setFormError(Array.isArray(first) ? String(first[0]) : String(first));
            }
          }
        } else {
          setFormError(error.message);
        }
      } else {
        setFormError("Something went wrong. Please try again.");
      }
      setSaving(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={event === null ? "Add Timeline Milestone Event" : "Edit Timeline Milestone Event"}>
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
        <label className="block">
          <span className={TYPOGRAPHY.subheadLabel}>Event Milestone Type *</span>
          <select
            value={eventType}
            onChange={(e) => setEventType(e.target.value as TimelineEventType)}
            required
            className="mt-1 h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm dark:border-slate-600 dark:bg-slate-900"
          >
            {EVENT_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label} ({option.value})
              </option>
            ))}
          </select>
        </label>

        <Input
          label="Date Occurred *"
          type="date"
          value={eventDate}
          onChange={(e) => setEventDate(e.target.value)}
          required
          errorText={fieldError ?? undefined}
        />

        <Textarea
          label="Description / Notes (Optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={500}
        />

        <p className="text-[11px] text-slate-500 dark:text-slate-400">
          Saving a milestone event automatically advances your current status to match (server-side). Your status never moves backwards.
        </p>

        {formError !== null && (
          <p role="alert" className="text-sm text-rose-600 dark:text-rose-400">
            {formError}
          </p>
        )}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={saving}>
            {event === null ? "Add Event" : "Save Changes"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
