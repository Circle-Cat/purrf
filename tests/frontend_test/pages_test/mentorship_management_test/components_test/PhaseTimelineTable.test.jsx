import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import PhaseTimelineTable from "@/pages/MentorshipManagement/components/PhaseTimelineTable";
import { TIMELINE_PHASES } from "@/pages/MentorshipManagement/utils/roundForm";

const emptyForm = Object.fromEntries(
  TIMELINE_PHASES.flatMap(({ adminAction, participantDeadlines }) => [
    [adminAction.key, null],
    ...participantDeadlines.map((f) => [f.key, null]),
  ]),
);

const renderTable = (props = {}) =>
  render(
    <PhaseTimelineTable
      form={emptyForm}
      errors={{}}
      setField={vi.fn(() => vi.fn())}
      minDate={new Date(2024, 0, 1)}
      {...props}
    />,
  );

describe("PhaseTimelineTable", () => {
  it("renders all phase names", () => {
    renderTable();
    TIMELINE_PHASES.forEach(({ phase }) => {
      expect(screen.getByText(phase)).toBeInTheDocument();
    });
  });

  it("renders column headers", () => {
    renderTable();
    expect(screen.getByText("Admin Action")).toBeInTheDocument();
    expect(screen.getByText("Participant Deadline")).toBeInTheDocument();
  });

  it("renders all field labels", () => {
    renderTable();
    TIMELINE_PHASES.forEach(({ adminAction, participantDeadlines }) => {
      expect(screen.getByText(adminAction.label)).toBeInTheDocument();
      participantDeadlines.forEach(({ label }) => {
        expect(screen.getByText(label)).toBeInTheDocument();
      });
    });
  });

  it("passes error to the correct field", () => {
    renderTable({ errors: { promotionStartAt: "This field is required." } });
    expect(screen.getByText("This field is required.")).toBeInTheDocument();
  });
});
