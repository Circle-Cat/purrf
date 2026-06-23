import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter } from "react-router-dom";

import RecruitingScreeningIndex from "@/pages/RecruitingScreeningIndex";
import { useAuth } from "@/context/auth";
import { getJobs } from "@/api/recruitingApi";

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

const PUBLISHED_JOB_1 = {
  id: 7,
  title: "Mentor Opening Alpha",
  mentorshipRole: "mentor",
  kind: "activity",
  status: "published",
};

const PUBLISHED_JOB_2 = {
  id: 12,
  title: "Mentee Opening Beta",
  mentorshipRole: "mentee",
  kind: "employment",
  status: "published",
};

/**
 * Render the index page inside a MemoryRouter so NavLink/Link work.
 */
function renderIndex() {
  return render(
    <MemoryRouter>
      <RecruitingScreeningIndex />
    </MemoryRouter>,
  );
}

// ── Tests ──────────────────────────────────────────────────────────────────────

describe("RecruitingScreeningIndex", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({
      permissions: ["recruiting.application.read"],
    });
    getJobs.mockResolvedValue({ data: [PUBLISHED_JOB_1, PUBLISHED_JOB_2] });
  });

  it("renders both job titles after fetching published postings", async () => {
    renderIndex();
    await waitFor(() => {
      expect(screen.getByText("Mentor Opening Alpha")).toBeInTheDocument();
      expect(screen.getByText("Mentee Opening Beta")).toBeInTheDocument();
    });
    expect(getJobs).toHaveBeenCalledTimes(1);
  });

  it("each job card links to /recruiting/screening/<id>", async () => {
    renderIndex();
    await waitFor(() => {
      expect(screen.getByText("Mentor Opening Alpha")).toBeInTheDocument();
    });

    const link1 = screen.getByRole("link", { name: /mentor opening alpha/i });
    const link2 = screen.getByRole("link", { name: /mentee opening beta/i });

    expect(link1).toHaveAttribute("href", "/recruiting/screening/7");
    expect(link2).toHaveAttribute("href", "/recruiting/screening/12");
  });

  it("shows empty-state message when no postings are returned", async () => {
    getJobs.mockResolvedValue({ data: [] });
    renderIndex();
    await waitFor(() => {
      expect(screen.getByText(/no published postings/i)).toBeInTheDocument();
    });
  });

  it("displays loading state before data arrives", () => {
    // getJobs never resolves during this synchronous check
    getJobs.mockReturnValue(new Promise(() => {}));
    renderIndex();
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
});
