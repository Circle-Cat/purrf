import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { toast } from "sonner";
import JobDetailPage from "@/pages/Recruiting/JobDetailPage";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
// Keep this page test focused on JobDetailPage's own load/gating logic;
// ApplicationForm's submission behavior is covered by its own test suite.
vi.mock("@/pages/Recruiting/ApplicationForm", () => ({
  default: ({ job }) => (
    <div>
      <p>Applying to {job.title}</p>
      <button type="button">Submit application</button>
    </div>
  ),
}));

// Bazel-sandbox module resolution: `vi.mock("sonner", factory)` doesn't
// intercept the module the component resolved at import time. Spy on the
// real toast instead, matching the rest of the recruiting page tests.
vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

beforeEach(() => {
  vi.clearAllMocks();
  api.getPublicJob.mockResolvedValue({
    data: { id: 5, title: "Mentee", kind: "activity", description: "" },
  });
  api.getMyApplication.mockResolvedValue({ data: null });
});

/** Render JobDetailPage inside a MemoryRouter at the given path, with both
 * the detail and apply routes wired (JobDetailPage handles both). */
const renderAt = (path) => {
  const router = createMemoryRouter(
    [
      { path: "/recruiting/jobs/:jobId", element: <JobDetailPage /> },
      { path: "/recruiting/jobs/:jobId/apply", element: <JobDetailPage /> },
      {
        path: "/recruiting/jobs/:jobId/application",
        element: <p>My application</p>,
      },
    ],
    { initialEntries: [path] },
  );
  return { ...render(<RouterProvider router={router} />), router };
};

describe("JobDetailPage", () => {
  it("loads and shows the published job title with an Apply action", async () => {
    renderAt("/recruiting/jobs/5");
    await waitFor(() => expect(screen.getByText("Mentee")).toBeInTheDocument());
    expect(api.getPublicJob).toHaveBeenCalledWith("5");
    expect(screen.getByRole("button", { name: /apply/i })).toBeInTheDocument();
  });

  it("does not check for an existing application on the plain job-detail route", async () => {
    renderAt("/recruiting/jobs/5");
    await waitFor(() => expect(screen.getByText("Mentee")).toBeInTheDocument());
    expect(api.getMyApplication).not.toHaveBeenCalled();
  });

  it("shows the job kind and description alongside the title", async () => {
    api.getPublicJob.mockResolvedValue({
      data: {
        id: 5,
        title: "Mentee",
        kind: "activity",
        description: "Help a mentee grow.",
      },
    });
    renderAt("/recruiting/jobs/5");
    await waitFor(() => expect(screen.getByText("Mentee")).toBeInTheDocument());
    expect(screen.getByText("activity")).toBeInTheDocument();
    expect(screen.getByText("Help a mentee grow.")).toBeInTheDocument();
  });

  it("navigates to the apply route when Apply is clicked", async () => {
    const { router } = renderAt("/recruiting/jobs/5");
    await waitFor(() => expect(screen.getByText("Mentee")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /apply/i }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/recruiting/jobs/5/apply"),
    );
  });

  it("renders the ApplicationForm at the apply route instead of the summary", async () => {
    renderAt("/recruiting/jobs/5/apply");
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /submit application/i }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole("button", { name: /^apply$/i }),
    ).not.toBeInTheDocument();
    expect(api.getMyApplication).toHaveBeenCalledWith("5");
  });

  it("redirects to the my-application route when an application already exists at the apply route", async () => {
    api.getMyApplication.mockResolvedValue({
      data: { id: 7, stage: "applied" },
    });
    const { router } = renderAt("/recruiting/jobs/5/apply");
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        "/recruiting/jobs/5/application",
      ),
    );
    expect(
      screen.queryByRole("button", { name: /submit application/i }),
    ).not.toBeInTheDocument();
  });

  it("shows the ApplicationForm at the apply route when no application exists yet", async () => {
    api.getMyApplication.mockResolvedValue({ data: null });
    renderAt("/recruiting/jobs/5/apply");
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /submit application/i }),
      ).toBeInTheDocument(),
    );
  });

  it("falls back to showing the ApplicationForm when the existing-application check fails", async () => {
    api.getMyApplication.mockRejectedValue(new Error("boom"));
    renderAt("/recruiting/jobs/5/apply");
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /submit application/i }),
      ).toBeInTheDocument(),
    );
  });

  it("toasts an error when the job fails to load", async () => {
    api.getPublicJob.mockRejectedValue(new Error("not found"));
    renderAt("/recruiting/jobs/5");
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("not found"));
  });

  it("shows a loading placeholder while the job is being fetched", () => {
    api.getPublicJob.mockReturnValue(new Promise(() => {}));
    renderAt("/recruiting/jobs/5");
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows an inline error with a Retry button on load failure, and recovers on retry", async () => {
    api.getPublicJob.mockRejectedValueOnce(new Error("not found"));
    renderAt("/recruiting/jobs/5");
    expect(
      await screen.findByText("Couldn't load this job."),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.getByText("Mentee")).toBeInTheDocument());
    expect(api.getPublicJob).toHaveBeenCalledTimes(2);
    expect(
      screen.queryByText("Couldn't load this job."),
    ).not.toBeInTheDocument();
  });
});
