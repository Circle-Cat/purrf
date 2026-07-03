import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import ApplicantDetailDialog from "@/pages/Recruiting/board/ApplicantDetailDialog";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
// Bazel-sandbox module resolution: `vi.mock("sonner", factory)` doesn't
// intercept the module the component resolved at import time. Spy on the
// real toast instead, matching the rest of the recruiting page tests.
vi.spyOn(toast, "error").mockImplementation(() => {});

beforeEach(() => {
  vi.clearAllMocks();
  api.resumeUrl.mockImplementation(
    (id) => `/api/recruiting/applications/${id}/resume`,
  );
});

const baseDetail = {
  application: {
    id: 101,
    jobId: 1,
    userId: 5,
    stage: "recruiter_screening",
    subStatus: "pending",
    tags: null,
    current: {
      version: 1,
      isFrozen: false,
      submission: {
        personal: {
          firstName: "Alice",
          lastName: "Smith",
          linkedin: "https://linkedin.com/in/alice",
          timezone: "America/New_York",
        },
        education: [
          {
            institution: "State University",
            degree: "BS",
            field: "CS",
            startMonth: "August",
            startYear: "2016",
            endMonth: "May",
            endYear: "2020",
            isCurrentlyWorking: false,
          },
        ],
        experience: [
          {
            company: "Acme Corp",
            title: "Engineer",
            startMonth: "June",
            startYear: "2020",
            isCurrentlyWorking: true,
          },
        ],
        answers: { q1: "Yes", q2: "Remote" },
      },
      resumeObjectKey: "obj-key",
      resumeSha256: "abc",
      submittedAt: "2026-06-01T00:00:00Z",
    },
    editable: false,
  },
  applicantName: "Alice Smith",
  applicantEmail: "alice@example.com",
  resumeAvailable: true,
  formSchema: {
    questions: [
      { id: "q1", label: "Are you authorized to work?" },
      // q2 intentionally absent -> falls back to raw id "q2"
    ],
  },
};

/** Render the dialog already open with a given application id. */
const renderDialog = (props = {}) => {
  const onOpenChange = vi.fn();
  const onChanged = vi.fn();
  render(
    <ApplicantDetailDialog
      applicationId={101}
      open
      onOpenChange={onOpenChange}
      onChanged={onChanged}
      {...props}
    />,
  );
  return { onOpenChange, onChanged };
};

describe("ApplicantDetailDialog", () => {
  it("shows a loading state before the detail resolves", () => {
    api.getApplicationDetail.mockReturnValue(new Promise(() => {}));
    renderDialog();
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("renders header info, resume link, and snapshot sections once loaded", async () => {
    api.getApplicationDetail.mockResolvedValue({ data: baseDetail });
    renderDialog();

    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("heading", { name: "Alice Smith" }),
    ).toBeInTheDocument();

    const resumeLink = screen.getByRole("link", { name: /resume/i });
    expect(resumeLink).toHaveAttribute(
      "href",
      "/api/recruiting/applications/101/resume",
    );
    expect(resumeLink).toHaveAttribute("target", "_blank");

    // Personal
    expect(
      screen.getByText(/https:\/\/linkedin\.com\/in\/alice/),
    ).toBeInTheDocument();
    expect(screen.getByText(/America\/New_York/)).toBeInTheDocument();

    // Education / Experience via shared RowList
    expect(screen.getByText(/State University/)).toBeInTheDocument();
    expect(screen.getByText(/Acme Corp/)).toBeInTheDocument();

    // Answers: known question uses its label, removed question falls back to raw id
    expect(
      screen.getByText(/Are you authorized to work\?/),
    ).toBeInTheDocument();
    expect(screen.getByText(/q2/)).toBeInTheDocument();
  });

  it("does not render a resume link when resumeAvailable is false", async () => {
    api.getApplicationDetail.mockResolvedValue({
      data: { ...baseDetail, resumeAvailable: false },
    });
    renderDialog();
    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("link", { name: /resume/i }),
    ).not.toBeInTheDocument();
  });

  it("renders one sub-status button per allowed value for the current stage, with the active one pressed", async () => {
    api.getApplicationDetail.mockResolvedValue({ data: baseDetail });
    renderDialog();

    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument(),
    );

    const pending = screen.getByRole("button", { name: /pending/i });
    const inProgress = screen.getByRole("button", { name: /in progress/i });
    const evaluated = screen.getByRole("button", { name: /evaluated/i });
    expect(pending).toHaveAttribute("aria-pressed", "true");
    expect(inProgress).toHaveAttribute("aria-pressed", "false");
    expect(evaluated).toHaveAttribute("aria-pressed", "false");
    // recruiter_screening has no "scheduling"/"scheduled" values
    expect(
      screen.queryByRole("button", { name: /scheduling/i }),
    ).not.toBeInTheDocument();
  });

  it("renders scheduling/scheduled sub-status buttons for the behavioral stage", async () => {
    api.getApplicationDetail.mockResolvedValue({
      data: {
        ...baseDetail,
        application: {
          ...baseDetail.application,
          stage: "behavioral",
          subStatus: "scheduling",
        },
      },
    });
    renderDialog();

    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: /^scheduling$/i }),
    ).toHaveAttribute("aria-pressed", "true");
    expect(
      screen.getByRole("button", { name: /^scheduled$/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /pending/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /evaluated/i }),
    ).toBeInTheDocument();
  });

  it("renders no sub-status selector for terminal stages", async () => {
    api.getApplicationDetail.mockResolvedValue({
      data: {
        ...baseDetail,
        application: {
          ...baseDetail.application,
          stage: "hired",
          subStatus: null,
        },
      },
    });
    renderDialog();

    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: /pending/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /evaluated/i }),
    ).not.toBeInTheDocument();
  });

  it("clicking a sub-status button calls the API and onChanged", async () => {
    const user = userEvent.setup();
    api.getApplicationDetail.mockResolvedValue({ data: baseDetail });
    api.setApplicationSubStatus.mockResolvedValue({ data: {} });
    const { onChanged } = renderDialog();

    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: /in progress/i }));

    await waitFor(() =>
      expect(api.setApplicationSubStatus).toHaveBeenCalledWith(
        101,
        "in_progress",
      ),
    );
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
  });

  it("toasts an error and does not call onChanged when the sub-status update fails", async () => {
    const user = userEvent.setup();
    api.getApplicationDetail.mockResolvedValue({ data: baseDetail });
    api.setApplicationSubStatus.mockRejectedValue(new Error("boom"));
    const { onChanged } = renderDialog();

    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: /in progress/i }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("boom"));
    expect(onChanged).not.toHaveBeenCalled();
  });

  it("re-fetches the detail each time the dialog opens", async () => {
    api.getApplicationDetail.mockResolvedValue({ data: baseDetail });
    const { rerender } = render(
      <ApplicantDetailDialog
        applicationId={101}
        open={false}
        onOpenChange={() => {}}
        onChanged={() => {}}
      />,
    );
    expect(api.getApplicationDetail).not.toHaveBeenCalled();

    rerender(
      <ApplicantDetailDialog
        applicationId={101}
        open
        onOpenChange={() => {}}
        onChanged={() => {}}
      />,
    );

    await waitFor(() =>
      expect(api.getApplicationDetail).toHaveBeenCalledWith(101),
    );
  });

  it("shows an error with Retry and recovers when getApplicationDetail fails", async () => {
    const user = userEvent.setup();
    api.getApplicationDetail
      .mockRejectedValueOnce(new Error("Network error"))
      .mockResolvedValue({ data: baseDetail });
    renderDialog();

    await waitFor(() =>
      expect(
        screen.getByText("Couldn't load this application."),
      ).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("heading", { name: "Alice Smith" }),
    ).toBeInTheDocument();
  });
});
