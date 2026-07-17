import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { toast } from "sonner";
import MyApplication from "@/pages/Recruiting/MyApplication";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
// Keep this page test focused on MyApplication's own load/gating logic;
// ApplicationForm's submission behavior is covered by its own test suite.
vi.mock("@/pages/Recruiting/ApplicationForm", () => ({
  default: ({ job, existing, seed, seedApplicationId, onSubmitted }) => (
    <div>
      <p>Editing application for {job.title}</p>
      {existing && <p>Existing id {existing.id}</p>}
      {seed && <p>Seeded from prior submission</p>}
      {seedApplicationId != null && (
        <p>Seed application id {seedApplicationId}</p>
      )}
      <button
        type="button"
        onClick={() =>
          onSubmitted({
            id: 9,
            stage: "recruiter_screening",
            editable: true,
            current: { submission: {} },
          })
        }
      >
        Submit application
      </button>
    </div>
  ),
}));

vi.spyOn(toast, "error").mockImplementation(() => {});

const JOB = { id: 5, title: "Mentee", kind: "activity", description: "" };

beforeEach(() => {
  vi.clearAllMocks();
  api.getPublicJob.mockResolvedValue({ data: JOB });
});

/** Render MyApplication inside a MemoryRouter at the given job's application path. */
const renderAt = (jobId) => {
  const router = createMemoryRouter(
    [
      {
        path: "/recruiting/jobs/:jobId/application",
        element: <MyApplication />,
      },
      { path: "/dashboard/me", element: <p>Personal Dashboard</p> },
    ],
    { initialEntries: [`/recruiting/jobs/${jobId}/application`] },
  );
  return render(<RouterProvider router={router} />);
};

describe("MyApplication", () => {
  it("renders the ApplicationForm as a new submission when there is no existing application", async () => {
    api.getMyApplication.mockResolvedValue({ data: null });
    renderAt(5);
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /submit application/i }),
      ).toBeInTheDocument(),
    );
    expect(api.getMyApplication).toHaveBeenCalledWith("5");
    expect(screen.queryByText(/existing id/i)).not.toBeInTheDocument();
  });

  it("renders the editable ApplicationForm with the existing draft when editable is true, even at a later stage", async () => {
    api.getMyApplication.mockResolvedValue({
      data: {
        id: 9,
        stage: "recruiter_screening",
        editable: true,
        current: { submission: {} },
      },
    });
    renderAt(5);
    await waitFor(() =>
      expect(screen.getByText("Existing id 9")).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: /submit application/i }),
    ).toBeInTheDocument();
  });

  it("renders a read-only summary with no Submit button when editable is false", async () => {
    api.getMyApplication.mockResolvedValue({
      data: {
        id: 9,
        stage: "recruiter_screening",
        editable: false,
        current: {
          submission: {
            personal: { firstName: "Ann", lastName: "Lee" },
            education: [],
            experience: [],
            answers: {},
          },
        },
      },
    });
    renderAt(5);
    // Exact string: stage labels are sentence case ("Recruiter screening",
    // not "Recruiter Screening").
    await waitFor(() =>
      expect(
        screen.getByText("Status: Recruiter screening"),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: /submit application/i }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/Ann/)).toBeInTheDocument();
  });

  it("shows a Reapply button for a rejected application, and clicking it renders a seeded ApplicationForm", async () => {
    api.getMyApplication.mockResolvedValue({
      data: {
        id: 9,
        stage: "rejected",
        editable: false,
        current: {
          submission: {
            personal: { firstName: "Ann", lastName: "Lee" },
            education: [],
            experience: [],
            answers: {},
          },
        },
      },
    });
    renderAt(5);

    await waitFor(() =>
      expect(screen.getByText("Status: Rejected")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: /reapply/i }));

    await waitFor(() =>
      expect(
        screen.getByText("Seeded from prior submission"),
      ).toBeInTheDocument(),
    );
    expect(screen.queryByText(/existing id/i)).not.toBeInTheDocument();
  });

  it("passes the rejected application's own id as seedApplicationId when reapplying", async () => {
    api.getMyApplication.mockResolvedValue({
      data: {
        id: 9,
        stage: "rejected",
        editable: false,
        current: {
          submission: {
            personal: { firstName: "Ann", lastName: "Lee" },
            education: [],
            experience: [],
            answers: {},
          },
        },
      },
    });
    renderAt(5);

    await waitFor(() =>
      expect(screen.getByText("Status: Rejected")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: /reapply/i }));

    await waitFor(() =>
      expect(screen.getByText("Seed application id 9")).toBeInTheDocument(),
    );
  });

  it("navigates to Personal Dashboard after a fresh submission", async () => {
    api.getMyApplication.mockResolvedValue({ data: null });
    renderAt(5);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /submit application/i }),
      ).toBeInTheDocument(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: /submit application/i }),
    );

    await waitFor(() =>
      expect(screen.getByText("Personal Dashboard")).toBeInTheDocument(),
    );
  });

  it("navigates to Personal Dashboard after a successful reapply submission", async () => {
    api.getMyApplication.mockResolvedValue({
      data: {
        id: 9,
        stage: "rejected",
        editable: false,
        current: { submission: {} },
      },
    });
    renderAt(5);

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /reapply/i }),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: /reapply/i }));

    await waitFor(() =>
      expect(
        screen.getByText("Seeded from prior submission"),
      ).toBeInTheDocument(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: /submit application/i }),
    );

    await waitFor(() =>
      expect(screen.getByText("Personal Dashboard")).toBeInTheDocument(),
    );
  });

  it("does not show a Reapply button for a non-rejected read-only application", async () => {
    api.getMyApplication.mockResolvedValue({
      data: {
        id: 9,
        stage: "hired",
        editable: false,
        current: { submission: {} },
      },
    });
    renderAt(5);
    // Activity posting fixture: `hired` renders as "Admitted".
    await waitFor(() =>
      expect(screen.getByText("Status: Admitted")).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: /reapply/i }),
    ).not.toBeInTheDocument();
  });

  it("renders a read-only summary when editable is false even though the stage string is still applied", async () => {
    // Proves the gate keys off the server's `editable` flag, not the stage
    // string: a stage of "applied" with `editable: false` (e.g. the current
    // submission has been frozen) must NOT render the editable form.
    api.getMyApplication.mockResolvedValue({
      data: {
        id: 9,
        stage: "applied",
        editable: false,
        current: {
          submission: {
            personal: { firstName: "Ann", lastName: "Lee" },
            education: [],
            experience: [],
            answers: {},
          },
        },
      },
    });
    renderAt(5);
    await waitFor(() =>
      expect(screen.getByText("Status: Applied")).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: /submit application/i }),
    ).not.toBeInTheDocument();
  });

  it("shows a status line naming the final stage for a terminal outcome", async () => {
    api.getMyApplication.mockResolvedValue({
      data: {
        id: 9,
        stage: "hired",
        editable: false,
        current: {
          submission: {
            personal: {},
            education: [],
            experience: [],
            answers: {},
          },
        },
      },
    });
    renderAt(5);
    // The job fixture is an activity posting, whose `hired` stage is
    // presented as "Admitted" (display-only rename).
    await waitFor(() =>
      expect(screen.getByText("Status: Admitted")).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: /submit application/i }),
    ).not.toBeInTheDocument();
  });

  it("toasts an error when loading fails", async () => {
    api.getMyApplication.mockRejectedValue(new Error("boom"));
    renderAt(5);
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("boom"));
  });

  it("shows a loading placeholder while the application is being fetched", () => {
    api.getMyApplication.mockReturnValue(new Promise(() => {}));
    renderAt(5);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows an inline error with a Retry button on load failure, and recovers on retry", async () => {
    api.getMyApplication.mockRejectedValueOnce(new Error("boom"));
    api.getMyApplication.mockResolvedValue({
      data: {
        id: 9,
        stage: "applied",
        editable: true,
        current: { submission: {} },
      },
    });
    renderAt(5);
    expect(
      await screen.findByText("Couldn't load your application."),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() =>
      expect(screen.getByText("Existing id 9")).toBeInTheDocument(),
    );
    expect(
      screen.queryByText("Couldn't load your application."),
    ).not.toBeInTheDocument();
  });
});
