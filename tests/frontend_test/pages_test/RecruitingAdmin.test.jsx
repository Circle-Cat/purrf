import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom/vitest";

import RecruitingAdmin from "@/pages/RecruitingAdmin";
import { useAuth } from "@/context/auth";
import { PERMISSIONS } from "@/constants/Permissions";
import {
  getJobs,
  createJob,
  publishJob,
  closeJob,
} from "@/api/recruitingApi";

// ── API mock ──────────────────────────────────────────────────────────────────
vi.mock("@/api/recruitingApi", () => ({
  getJobs: vi.fn(),
  createJob: vi.fn(),
  updateJob: vi.fn(),
  publishJob: vi.fn(),
  closeJob: vi.fn(),
  getJob: vi.fn(),
  submitApplication: vi.fn(),
  getBoard: vi.fn(),
  viewApplication: vi.fn(),
  advanceApplication: vi.fn(),
}));

// ── Auth mock ─────────────────────────────────────────────────────────────────
vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

// ── FormBuilder mock (prevents heavy internal state / select portal issues) ───
vi.mock("@/components/recruiting/FormBuilder", () => ({
  default: vi.fn(({ onChange }) => (
    <div data-testid="mock-form-builder">
      <button
        type="button"
        onClick={() =>
          onChange({ type: "object", properties: {}, required: [] })
        }
      >
        Trigger Schema Change
      </button>
    </div>
  )),
}));

const ALL_WRITE_PERMS = [
  PERMISSIONS.RECRUITING_JOB_READ,
  PERMISSIONS.RECRUITING_JOB_WRITE,
];

const SAMPLE_PUBLISHED_JOB = {
  id: 1,
  title: "Published Mentor Role",
  mentorshipRole: "mentor",
  kind: "activity",
  status: "published",
};

describe("RecruitingAdmin", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ permissions: ALL_WRITE_PERMS });
    getJobs.mockResolvedValue({ data: [SAMPLE_PUBLISHED_JOB] });
    createJob.mockResolvedValue({
      data: {
        id: 99,
        title: "New Job",
        mentorshipRole: "mentor",
        kind: "activity",
        status: "draft",
        formSchema: { type: "object", properties: {}, required: [] },
      },
    });
    publishJob.mockResolvedValue({ data: {} });
    closeJob.mockResolvedValue({ data: {} });
  });

  // ── Rendering ──────────────────────────────────────────────────────────────

  it("renders published postings from getJobs on mount", async () => {
    render(<RecruitingAdmin />);
    await waitFor(() => {
      expect(screen.getByText("Published Mentor Role")).toBeInTheDocument();
    });
    expect(getJobs).toHaveBeenCalledTimes(1);
  });

  it("shows 'Create posting' button when user has RECRUITING_JOB_WRITE", async () => {
    render(<RecruitingAdmin />);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /create posting/i }),
      ).toBeInTheDocument();
    });
  });

  it("does not show 'Create posting' button when user lacks RECRUITING_JOB_WRITE", async () => {
    useAuth.mockReturnValue({
      permissions: [PERMISSIONS.RECRUITING_JOB_READ],
    });
    render(<RecruitingAdmin />);
    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: /create posting/i }),
      ).not.toBeInTheDocument();
    });
  });

  it("shows empty-state message when no postings exist", async () => {
    getJobs.mockResolvedValue({ data: [] });
    render(<RecruitingAdmin />);
    await waitFor(() => {
      expect(screen.getByText(/no postings/i)).toBeInTheDocument();
    });
  });

  // ── Publish action ─────────────────────────────────────────────────────────

  it("calls publishJob with the posting id when Publish is clicked", async () => {
    render(<RecruitingAdmin />);
    await waitFor(() => {
      expect(screen.getByText("Published Mentor Role")).toBeInTheDocument();
    });

    // Published postings show a Close button, not a Publish button.
    // Inject a draft posting so Publish is rendered.
    const DRAFT_JOB = {
      id: 42,
      title: "Draft Mentee Role",
      mentorshipRole: "mentee",
      kind: "activity",
      status: "draft",
    };
    getJobs.mockResolvedValue({ data: [] });
    createJob.mockResolvedValue({ data: DRAFT_JOB });

    // Open modal, fill title, save → creates draft, Publish appears in list
    fireEvent.click(screen.getByRole("button", { name: /create posting/i }));
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    const titleInput = screen.getByLabelText(/title/i);
    fireEvent.change(titleInput, { target: { value: "Draft Mentee Role" } });

    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));
    await waitFor(() => {
      expect(createJob).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getByText("Draft Mentee Role")).toBeInTheDocument();
    });

    const publishBtn = screen.getByRole("button", { name: /^publish$/i });
    fireEvent.click(publishBtn);
    await waitFor(() => {
      expect(publishJob).toHaveBeenCalledWith(42);
    });
  });

  // ── Create posting ─────────────────────────────────────────────────────────

  it("opens JobModal when 'Create posting' is clicked", async () => {
    render(<RecruitingAdmin />);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /create posting/i }),
      ).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /create posting/i }));
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
  });

  it("calls createJob with title, kind:activity, mentorshipRole, formSchema on save", async () => {
    render(<RecruitingAdmin />);
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /create posting/i }),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /create posting/i }));
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    // Fill title
    const titleInput = screen.getByLabelText(/title/i);
    fireEvent.change(titleInput, { target: { value: "Mentor Opening" } });

    // Save (mentorshipRole defaults to "mentor", formSchema is the empty schema)
    fireEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() => {
      expect(createJob).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Mentor Opening",
          kind: "activity",
          mentorshipRole: "mentor",
          formSchema: expect.any(Object),
        }),
      );
    });
  });

  // ── Close action ───────────────────────────────────────────────────────────

  it("calls closeJob with the posting id when Close is clicked", async () => {
    render(<RecruitingAdmin />);
    await waitFor(() => {
      expect(screen.getByText("Published Mentor Role")).toBeInTheDocument();
    });

    const closeBtn = screen.getByRole("button", { name: /^close posting$/i });
    fireEvent.click(closeBtn);
    await waitFor(() => {
      expect(closeJob).toHaveBeenCalledWith(SAMPLE_PUBLISHED_JOB.id);
    });
  });
});
