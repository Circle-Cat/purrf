import React from "react";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Routes, Route } from "react-router-dom";

import RecruitingApply from "@/pages/RecruitingApply";

// ── recruitingApi mock ────────────────────────────────────────────────────────
vi.mock("@/api/recruitingApi", () => ({
  getJob: vi.fn(),
  submitApplication: vi.fn(),
  getJobs: vi.fn(),
  createJob: vi.fn(),
  updateJob: vi.fn(),
  publishJob: vi.fn(),
  closeJob: vi.fn(),
  getBoard: vi.fn(),
  viewApplication: vi.fn(),
  advanceApplication: vi.fn(),
}));

// ── profileApi mock ───────────────────────────────────────────────────────────
vi.mock("@/api/profileApi", () => ({
  getMyProfile: vi.fn(),
  updateMyProfile: vi.fn(),
}));

// ── ExperienceEditModal mock ──────────────────────────────────────────────────
vi.mock("@/pages/Profile/modals/ExperienceEditModal", () => ({
  default: vi.fn(({ isOpen, onClose, onSave }) =>
    isOpen ? (
      <div data-testid="experience-modal">
        <button onClick={onClose}>Close Experience</button>
        <button onClick={() => onSave({ workHistory: [] })}>Save Experience</button>
      </div>
    ) : null,
  ),
}));

import { getJob, submitApplication } from "@/api/recruitingApi";
import { getMyProfile, updateMyProfile } from "@/api/profileApi";
import { toast } from "sonner";

// ── sonner spy ────────────────────────────────────────────────────────────────
vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Render the apply page at /recruiting/apply/7 via MemoryRouter + Routes. */
function renderApply() {
  return render(
    <MemoryRouter initialEntries={["/recruiting/apply/7"]}>
      <Routes>
        <Route
          path="/recruiting/apply/:jobId"
          element={<RecruitingApply />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

const SAMPLE_JOB = {
  id: 7,
  title: "Senior Mentor Position",
  description: "Join our mentorship programme.",
  kind: "activity",
  mentorshipRole: "mentor",
  status: "published",
  formSchema: {
    type: "object",
    properties: {
      motivation: { type: "string", title: "Why do you want to join?" },
    },
    required: ["motivation"],
  },
};

const EMPTY_PROFILE = {
  data: {
    profile: {
      user: { id: 1, primaryEmail: "test@example.com" },
      workHistory: [],
      education: [],
      training: [],
    },
  },
};

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("RecruitingApply", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getJob.mockResolvedValue({ data: SAMPLE_JOB });
    getMyProfile.mockResolvedValue(EMPTY_PROFILE);
    updateMyProfile.mockResolvedValue(EMPTY_PROFILE);
    submitApplication.mockResolvedValue({ data: { id: 100 } });
  });

  // ── Rendering ──────────────────────────────────────────────────────────────

  it("renders the job title after loading", async () => {
    renderApply();
    await waitFor(() => {
      expect(screen.getByText("Senior Mentor Position")).toBeInTheDocument();
    });
    expect(getJob).toHaveBeenCalledWith("7");
  });

  it("renders the job description", async () => {
    renderApply();
    await waitFor(() => {
      expect(
        screen.getByText("Join our mentorship programme."),
      ).toBeInTheDocument();
    });
  });

  it("renders the JsonSchemaForm field from the job's formSchema", async () => {
    renderApply();
    await waitFor(() => {
      expect(
        screen.getByLabelText("Why do you want to join?"),
      ).toBeInTheDocument();
    });
  });

  it("renders an 'Edit experience' button", async () => {
    renderApply();
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /edit experience/i }),
      ).toBeInTheDocument();
    });
  });

  // ── Validation blocks submit ───────────────────────────────────────────────

  it("does NOT call submitApplication when a required field is empty", async () => {
    renderApply();
    await waitFor(() => {
      expect(screen.getByText("Senior Mentor Position")).toBeInTheDocument();
    });

    // Don't fill in the required "motivation" field — click submit directly
    const submitBtn = screen.getByRole("button", { name: /submit application/i });
    fireEvent.click(submitBtn);

    // submitApplication must not have been called
    expect(submitApplication).not.toHaveBeenCalled();
  });

  it("shows a validation error message when a required field is empty", async () => {
    renderApply();
    await waitFor(() => {
      expect(screen.getByText("Senior Mentor Position")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /submit application/i }));

    await waitFor(() => {
      expect(screen.getByText(/required/i)).toBeInTheDocument();
    });
  });

  // ── Successful submit ──────────────────────────────────────────────────────

  it("calls submitApplication with jobId and answers when required fields are filled", async () => {
    renderApply();
    await waitFor(() => {
      expect(screen.getByText("Senior Mentor Position")).toBeInTheDocument();
    });

    // Fill the required field
    const motivationInput = screen.getByLabelText("Why do you want to join?");
    fireEvent.change(motivationInput, {
      target: { value: "I am passionate about mentorship." },
    });

    const submitBtn = screen.getByRole("button", { name: /submit application/i });
    await act(async () => {
      fireEvent.click(submitBtn);
    });

    await waitFor(() => {
      expect(submitApplication).toHaveBeenCalledWith("7", {
        motivation: "I am passionate about mentorship.",
      });
    });
  });

  it("shows a success toast after successful submission", async () => {
    renderApply();
    await waitFor(() => {
      expect(screen.getByText("Senior Mentor Position")).toBeInTheDocument();
    });

    const motivationInput = screen.getByLabelText("Why do you want to join?");
    fireEvent.change(motivationInput, {
      target: { value: "I love helping others." },
    });

    const submitBtn = screen.getByRole("button", { name: /submit application/i });
    await act(async () => {
      fireEvent.click(submitBtn);
    });

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalled();
    });
  });

  // ── Experience modal ───────────────────────────────────────────────────────

  it("opens the ExperienceEditModal when 'Edit experience' is clicked", async () => {
    renderApply();
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /edit experience/i }),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /edit experience/i }));

    expect(screen.getByTestId("experience-modal")).toBeInTheDocument();
  });

  it("calls updateMyProfile when ExperienceEditModal saves", async () => {
    renderApply();
    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: /edit experience/i }),
      ).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /edit experience/i }));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save experience/i }));
    });

    expect(updateMyProfile).toHaveBeenCalled();
  });
});
