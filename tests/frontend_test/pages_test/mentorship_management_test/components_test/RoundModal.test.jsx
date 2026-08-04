import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { toast } from "sonner";
import RoundModal from "@/pages/MentorshipManagement/components/RoundModal";

vi.spyOn(toast, "error").mockImplementation(() => {});

vi.mock("@/pages/MentorshipManagement/components/PhaseTimelineTable", () => ({
  default: vi.fn(() => <div data-testid="mock-phase-timeline-table" />),
}));

// A round with all required timeline fields pre-filled (as UTC ISO strings)
// so that mapRoundToForm produces a form that passes validateForm.
const fullEditRound = {
  id: 1,
  name: "Mentorship 2026 Spring",
  requiredMeetings: 5,
  timeline: {
    promotionStartAt: "2025-12-19T07:59:59Z", // 2025-12-18 PT
    mentorApplicationDeadlineAt: "2025-12-26T07:59:59Z", // 2025-12-25 PT
    menteeApplicationDeadlineAt: "2025-12-26T07:59:59Z", // 2025-12-25 PT
    matchNotificationAt: "2026-02-13T07:59:59Z", // 2026-02-12 PT
    meetingsCompletionDeadlineAt: "2026-05-01T06:59:59Z", // 2026-04-30 PT
  },
};

const renderModal = (props = {}) =>
  render(
    <RoundModal
      open={true}
      round={null}
      onClose={vi.fn()}
      onSave={vi.fn()}
      rounds={[]}
      {...props}
    />,
  );

describe("RoundModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows 'Create New Round' title in create mode", () => {
    renderModal();
    expect(screen.getByText("Create New Round")).toBeInTheDocument();
  });

  it("shows 'Edit Round' title in edit mode", () => {
    renderModal({ round: fullEditRound });
    expect(screen.getByText("Edit Round")).toBeInTheDocument();
  });

  it("pre-fills the name field in edit mode", () => {
    renderModal({ round: fullEditRound });
    expect(
      screen.getByDisplayValue("Mentorship 2026 Spring"),
    ).toBeInTheDocument();
  });

  it("does not show quick fill section in edit mode", () => {
    renderModal({ round: fullEditRound });
    expect(screen.queryByText("Select season")).not.toBeInTheDocument();
    expect(screen.queryByText("Select year")).not.toBeInTheDocument();
  });

  it("shows quick fill section in create mode", () => {
    renderModal();
    expect(screen.getByText("Select season")).toBeInTheDocument();
    expect(screen.getByText("Select year")).toBeInTheDocument();
  });

  it("calls onClose when Cancel is clicked", async () => {
    const onClose = vi.fn();
    renderModal({ onClose });
    await userEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("shows name validation error when submitted with empty name", async () => {
    renderModal();
    await userEvent.click(screen.getByRole("button", { name: /^save$/i }));
    expect(screen.getByText("This field is required.")).toBeInTheDocument();
  });

  it("shows duplicate name error when name matches an existing round", async () => {
    const rounds = [{ id: 99, name: "Mentorship 2026 Spring" }];
    renderModal({ rounds });
    await userEvent.type(screen.getByRole("textbox"), "Mentorship 2026 Spring");
    await userEvent.click(screen.getByRole("button", { name: /^save$/i }));
    expect(screen.getByText(/already exists/i)).toBeInTheDocument();
  });

  it("calls onSave with the form payload on valid submit", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderModal({ round: fullEditRound, onSave });
    await userEvent.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Mentorship 2026 Spring" }),
    );
  });

  it("shows an error toast when onSave rejects", async () => {
    const onSave = vi.fn().mockRejectedValue({ message: "Server error" });
    renderModal({ round: fullEditRound, onSave });
    await userEvent.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Server error"),
    );
  });

  it("shows 'View Round' title in read-only mode", () => {
    renderModal({ round: fullEditRound, readOnly: true });
    expect(screen.getByText("View Round")).toBeInTheDocument();
  });

  it("shows Close instead of Cancel in read-only mode", () => {
    renderModal({ round: fullEditRound, readOnly: true });
    expect(screen.getAllByRole("button", { name: /close/i })).toHaveLength(2);
    expect(
      screen.queryByRole("button", { name: /cancel/i }),
    ).not.toBeInTheDocument();
  });

  it("does not show Save and Reset buttons in read-only mode", () => {
    renderModal({ round: fullEditRound, readOnly: true });
    expect(
      screen.queryByRole("button", { name: /^save$/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /reset/i }),
    ).not.toBeInTheDocument();
  });

  it("disables the name input in read-only mode", () => {
    renderModal({ round: fullEditRound, readOnly: true });
    expect(screen.getByDisplayValue("Mentorship 2026 Spring")).toBeDisabled();
  });
});
