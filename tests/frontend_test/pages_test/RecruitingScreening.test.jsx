import React from "react";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Routes, Route } from "react-router-dom";

import RecruitingScreening from "@/pages/RecruitingScreening";
import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";
import {
  getBoard,
  viewApplication,
  advanceApplication,
} from "@/api/recruitingApi";

// ── API mock ──────────────────────────────────────────────────────────────────
vi.mock("@/api/recruitingApi", () => ({
  getJobs: vi.fn(),
  getJob: vi.fn(),
  createJob: vi.fn(),
  updateJob: vi.fn(),
  publishJob: vi.fn(),
  closeJob: vi.fn(),
  submitApplication: vi.fn(),
  getBoard: vi.fn(),
  viewApplication: vi.fn(),
  advanceApplication: vi.fn(),
}));

// ── Auth mock ─────────────────────────────────────────────────────────────────
vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

// ── Fixtures ──────────────────────────────────────────────────────────────────

const ALL_SCREENING_PERMS = [
  PERMISSIONS.RECRUITING_APPLICATION_READ,
  PERMISSIONS.RECRUITING_APPLICATION_ADVANCE,
];

/** Card that has already been viewed (locked). */
const VIEWED_CARD = {
  id: 10,
  userId: 42,
  jobId: 7,
  roundId: 1,
  stage: "recruiter_screening",
  formAnswers: {},
  snapshot: null,
  isViewed: true,
  freezeUntil: null,
};

/** Unviewed card with a freezeUntil date. */
const FROZEN_CARD = {
  id: 11,
  userId: 99,
  jobId: 7,
  roundId: 1,
  stage: "recruiter_screening",
  formAnswers: {},
  snapshot: null,
  isViewed: false,
  freezeUntil: "2026-07-01T00:00:00.000Z",
};

/** Render the screening page at /recruiting/screening/7. */
function renderScreening() {
  return render(
    <MemoryRouter initialEntries={["/recruiting/screening/7"]}>
      <Routes>
        <Route
          path="/recruiting/screening/:jobId"
          element={<RecruitingScreening />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe("RecruitingScreening", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ permissions: ALL_SCREENING_PERMS });
    getBoard.mockResolvedValue({ data: [VIEWED_CARD, FROZEN_CARD] });
    viewApplication.mockResolvedValue({ data: {} });
    advanceApplication.mockResolvedValue({ data: {} });
  });

  // ── Rendering ──────────────────────────────────────────────────────────────

  it("renders both applicant cards after loading", async () => {
    renderScreening();
    await waitFor(() => {
      expect(screen.getByText(/user.*42/i)).toBeInTheDocument();
      expect(screen.getByText(/user.*99/i)).toBeInTheDocument();
    });
    expect(getBoard).toHaveBeenCalledWith("7");
  });

  it("shows 'Locked' badge on the viewed card", async () => {
    renderScreening();
    await waitFor(() => {
      expect(screen.getByText("Locked")).toBeInTheDocument();
    });
  });

  it("shows 'Unviewed (editable)' badge on the unviewed card", async () => {
    renderScreening();
    await waitFor(() => {
      expect(screen.getByText("Unviewed (editable)")).toBeInTheDocument();
    });
  });

  it("shows a 'Frozen until' badge on the card with a freezeUntil date", async () => {
    renderScreening();
    await waitFor(() => {
      expect(screen.getByText(/frozen until/i)).toBeInTheDocument();
    });
  });

  it("renders three labeled columns: Screening, Hired, Rejected", async () => {
    renderScreening();
    await waitFor(() => {
      expect(screen.getByText("Screening")).toBeInTheDocument();
      expect(screen.getByText("Hired")).toBeInTheDocument();
      expect(screen.getByText("Rejected")).toBeInTheDocument();
    });
  });

  it("denies access and shows no cards when user lacks READ permission", async () => {
    useAuth.mockReturnValue({ permissions: [] });
    renderScreening();
    await waitFor(() => {
      expect(screen.queryByText(/user.*42/i)).not.toBeInTheDocument();
    });
  });

  // ── Open action ────────────────────────────────────────────────────────────

  it("calls viewApplication with card id when Open is clicked", async () => {
    renderScreening();
    await waitFor(() => {
      expect(screen.getByText(/user.*99/i)).toBeInTheDocument();
    });

    // The frozen (unviewed) card has id=11
    const openButtons = screen.getAllByRole("button", { name: /open/i });
    fireEvent.click(openButtons[0]);

    await waitFor(() => {
      expect(viewApplication).toHaveBeenCalled();
    });
  });

  it("flips the card to 'Locked' after Open is clicked", async () => {
    renderScreening();
    await waitFor(() => {
      expect(screen.getByText("Unviewed (editable)")).toBeInTheDocument();
    });

    // openButtons[0] = viewed card (already Locked); openButtons[1] = unviewed card
    const openButtons = screen.getAllByRole("button", { name: /open/i });
    fireEvent.click(openButtons[1]);

    await waitFor(() => {
      // After view, "Unviewed (editable)" should be replaced by another "Locked"
      const lockedBadges = screen.getAllByText("Locked");
      expect(lockedBadges.length).toBeGreaterThan(1);
    });
  });

  // ── Hire action ────────────────────────────────────────────────────────────

  it("calls advanceApplication with id and 'hired' when Hire is clicked", async () => {
    renderScreening();
    await waitFor(() => {
      expect(screen.getByText(/user.*42/i)).toBeInTheDocument();
    });

    const hireButtons = screen.getAllByRole("button", { name: /hire/i });
    fireEvent.click(hireButtons[0]);

    await waitFor(() => {
      expect(advanceApplication).toHaveBeenCalledWith(
        expect.any(Number),
        "hired",
      );
    });
  });

  it("removes card from Screening and places it in Hired after Hire is clicked", async () => {
    renderScreening();
    await waitFor(() => {
      expect(screen.getByText(/user.*42/i)).toBeInTheDocument();
    });

    const screeningCol = screen.getByTestId("column-screening");
    const hiredCol = screen.getByTestId("column-hired");

    // Both cards start in Screening; hire the viewed card (id=10, userId=42)
    const hireButtons = within(screeningCol).getAllByRole("button", {
      name: /hire/i,
    });
    fireEvent.click(hireButtons[0]);

    await waitFor(() => {
      expect(advanceApplication).toHaveBeenCalledWith(
        expect.any(Number),
        "hired",
      );
    });

    // userId=42 must be gone from Screening and present in Hired
    await waitFor(() => {
      expect(
        within(screeningCol).queryByText(/user.*42/i),
      ).not.toBeInTheDocument();
      expect(within(hiredCol).getByText(/user.*42/i)).toBeInTheDocument();
    });
  });

  // ── Reject action ──────────────────────────────────────────────────────────

  it("calls advanceApplication with id and 'rejected' when Reject is clicked", async () => {
    renderScreening();
    await waitFor(() => {
      expect(screen.getByText(/user.*42/i)).toBeInTheDocument();
    });

    const rejectButtons = screen.getAllByRole("button", { name: /reject/i });
    fireEvent.click(rejectButtons[0]);

    await waitFor(() => {
      expect(advanceApplication).toHaveBeenCalledWith(
        expect.any(Number),
        "rejected",
      );
    });
  });

  it("removes card from Screening and places it in Rejected after Reject is clicked", async () => {
    renderScreening();
    await waitFor(() => {
      expect(screen.getByText(/user.*42/i)).toBeInTheDocument();
    });

    const screeningCol = screen.getByTestId("column-screening");
    const rejectedCol = screen.getByTestId("column-rejected");

    // Reject the viewed card (id=10, userId=42)
    const rejectButtons = within(screeningCol).getAllByRole("button", {
      name: /reject/i,
    });
    fireEvent.click(rejectButtons[0]);

    await waitFor(() => {
      expect(advanceApplication).toHaveBeenCalledWith(
        expect.any(Number),
        "rejected",
      );
    });

    // userId=42 must be gone from Screening and present in Rejected
    await waitFor(() => {
      expect(
        within(screeningCol).queryByText(/user.*42/i),
      ).not.toBeInTheDocument();
      expect(within(rejectedCol).getByText(/user.*42/i)).toBeInTheDocument();
    });
  });

  // ── Permission gate ────────────────────────────────────────────────────────

  it("shows cards and Open button but NOT Hire/Reject when user lacks ADVANCE permission", async () => {
    useAuth.mockReturnValue({
      permissions: [PERMISSIONS.RECRUITING_APPLICATION_READ],
    });
    renderScreening();

    await waitFor(() => {
      expect(screen.getByText(/user.*42/i)).toBeInTheDocument();
      expect(screen.getByText(/user.*99/i)).toBeInTheDocument();
    });

    // Open buttons must be present
    expect(
      screen.getAllByRole("button", { name: /open/i }).length,
    ).toBeGreaterThan(0);

    // Hire and Reject buttons must be absent
    expect(
      screen.queryByRole("button", { name: /hire/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /reject/i }),
    ).not.toBeInTheDocument();
  });
});
