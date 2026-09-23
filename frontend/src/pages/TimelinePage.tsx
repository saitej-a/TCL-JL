/**
 * The §7.5 personal timeline (9.3 Task 7): the vertical roadmap, the
 * add/edit modal, and the mutation wiring. The candidate's status badge
 * mirrors the server's forward-only sync (a mapped event advances
 * `current_status`; deletion never recalculates it).
 *
 * Destructive actions get a §6.6 confirm dialog, never an instant delete;
 * success and failure surface as §6.7.1 toasts; the server's validation
 * message renders inline in the modal, verbatim.
 */
import { useCallback, useEffect, useState } from "react";

import {
  deleteTimelineEvent,
  listMyTimelineEvents,
  updateTimelineEvent,
  createTimelineEvent,
  type TimelineEventCreatePayload,
  type TimelineEventPrivate,
  type TimelineEventType,
} from "@/api/timeline";
import { getProfile } from "@/api/profile";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { Modal } from "@/components/Modal";
import { Skeleton, SkeletonCard } from "@/components/Skeleton";
import { TimelineEventModal } from "@/components/TimelineEventModal";
import { TimelineRoadmap } from "@/components/TimelineRoadmap";
import { useToast } from "@/components/Toast";
import { Badge } from "@/components/Badge";
import { TYPOGRAPHY } from "@/theme/tokens";

interface ModalState {
  /** Add mode when null, edit mode otherwise. */
  event: TimelineEventPrivate | null;
  /** Pre-set event type for quick actions ("Mark as Received" / "Set Date"). */
  presetType?: TimelineEventType;
}

export function TimelinePage(): React.ReactElement {
  const { toast } = useToast();
  const [events, setEvents] = useState<TimelineEventPrivate[] | null>(null);
  const [currentStatus, setCurrentStatus] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [modal, setModal] = useState<ModalState | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<TimelineEventPrivate | null>(null);
  const [deleting, setDeleting] = useState(false);

  const refresh = useCallback(async (): Promise<TimelineEventPrivate[]> => {
    const page = await listMyTimelineEvents();
    setEvents(page.results);
    return page.results;
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([refresh(), getProfile().then((profile) => profile.current_status)])
      .then(([, status]) => {
        if (!cancelled) setCurrentStatus(status);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  async function refreshStatus(): Promise<void> {
    const profile = await getProfile();
    setCurrentStatus(profile.current_status);
  }

  async function handleSubmit(payload: TimelineEventCreatePayload): Promise<void> {
    if (modal?.event === null || modal.event === undefined) {
      await createTimelineEvent(payload);
      await Promise.all([refresh(), refreshStatus()]);
      toast({ message: "Milestone event added.", variant: "success" });
    } else {
      await updateTimelineEvent(modal.event.id, payload);
      await Promise.all([refresh(), refreshStatus()]);
      toast({ message: "Milestone event updated.", variant: "success" });
    }
    setModalOpen(false);
    setModal(null);
  }

  async function handleDelete(): Promise<void> {
    if (pendingDelete === null) return;
    setDeleting(true);
    try {
      await deleteTimelineEvent(pendingDelete.id);
      await refresh();
      toast({ message: "Milestone event deleted. Your status history is unchanged.", variant: "success" });
    } catch {
      toast({ message: "Could not delete the event. Please try again.", variant: "error" });
    } finally {
      setDeleting(false);
      setPendingDelete(null);
    }
  }

  const unverifiedCount = (events ?? []).filter((event) => !event.is_verified).length;

  return (
    <main className="mx-auto max-w-3xl space-y-4 p-4 lg:p-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className={TYPOGRAPHY.pageTitle}>My recruitment timeline</h1>
          <div className="mt-2 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <span>Current status:</span>
            {currentStatus !== null && (
              <Badge.status value={currentStatus as import("@/types/user").CandidateStatus} />
            )}
          </div>
        </div>
        <Button
          onClick={() => {
            setModal({ event: null });
            setModalOpen(true);
          }}
        >
          + Add Milestone Event
        </Button>
      </header>

      {unverifiedCount > 0 && (
        <div
          role="status"
          className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200"
        >
          {unverifiedCount} of your events {unverifiedCount === 1 ? "is" : "are"} awaiting
          verification. They still count toward your record.
        </div>
      )}

      {failed ? (
        <EmptyState
          headline="Your timeline could not be loaded"
          support="Check your connection and try again."
          actionLabel="Retry"
          onAction={() => window.location.reload()}
        />
      ) : events === null ? (
        <div className="space-y-4" aria-busy="true">
          <Skeleton className="h-10 w-full" />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : (
        <TimelineRoadmap
          events={events}
          onEdit={(event) => {
            setModal({ event: event });
            setModalOpen(true);
          }}
          onDelete={(event) => setPendingDelete(event)}
          onQuickAction={(type) => {
            setModal({ event: null, presetType: type });
            setModalOpen(true);
          }}
        />
      )}

      <TimelineEventModal
        open={modalOpen}
        event={
          modal?.event !== null && modal?.event !== undefined
            ? {
                id: modal.event.id,
                event_type: modal.event.event_type,
                event_date: modal.event.event_date,
                description: modal.event.description,
              }
            : null
        }
        presetType={modal?.presetType}
        onClose={() => {
          setModalOpen(false);
          setModal(null);
        }}
        onSubmit={(payload) => handleSubmit(payload)}
      />

      <Modal
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title="Delete this event?"
      >
        <p className="text-sm text-slate-600 dark:text-slate-300">
          This permanently removes the milestone from your record. Your current status never
          moves backwards, but the event itself cannot be recovered.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="secondary" onClick={() => setPendingDelete(null)}>
            Cancel
          </Button>
          <Button variant="danger" loading={deleting} onClick={() => void handleDelete()}>
            Delete event
          </Button>
        </div>
      </Modal>
    </main>
  );
}
