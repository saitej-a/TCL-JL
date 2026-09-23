/**
 * MilestoneStepper tests (Task 6): nodes complete only from real events, the
 * final node accepts JOINING_DATE or JOINED, OTHER is never a milestone, and
 * no date is ever invented for a pending node.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MilestoneStepper } from "@/components/MilestoneStepper";
import type { TimelineEventPrivate } from "@/api/timeline";

function event(event_type: TimelineEventPrivate["event_type"], event_date: string): TimelineEventPrivate {
  return {
    id: `evt-${event_type}-${event_date}`,
    event_type: event_type,
    event_date: event_date,
    description: "",
    is_verified: true,
    created_at: `${event_date}T00:00:00Z`,
  };
}

describe("MilestoneStepper", () => {
  it("marks only milestones that have events; pending nodes show no date", () => {
    render(
      <MilestoneStepper
        events={[event("INTERVIEW", "2026-04-23"), event("SELECTION", "2026-05-05")]}
      />,
    );
    const nodes = screen.getAllByRole("listitem");
    expect(nodes).toHaveLength(6);
    expect(screen.getByText("23 Apr 2026")).toBeInTheDocument();
    expect(screen.getByText("05 May 2026")).toBeInTheDocument();
    expect(screen.getAllByText("Pending")).toHaveLength(4);
  });

  it("accepts JOINING_DATE or JOINED for the final node", () => {
    render(<MilestoneStepper events={[event("JOINED", "2026-08-01")]} />);
    expect(screen.getByText("01 Aug 2026")).toBeInTheDocument();
    expect(screen.getAllByText("Pending")).toHaveLength(5);
  });

  it("never treats OTHER as a milestone", () => {
    render(<MilestoneStepper events={[event("OTHER", "2026-03-01")]} />);
    expect(screen.getAllByText("Pending")).toHaveLength(6);
  });
});
