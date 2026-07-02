import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { toast } from "sonner";
import JobsBrowse from "@/pages/Recruiting/JobsBrowse";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
// Bazel-sandbox module resolution: `vi.mock("sonner", factory)` doesn't
// intercept the module the component resolved at import time. Spy on the
// real toast instead, matching the rest of the recruiting page tests.
vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

beforeEach(() => vi.clearAllMocks());

/** Render JobsBrowse inside a memory router with a stub detail route. */
const renderPage = () => {
  const router = createMemoryRouter(
    [
      { path: "/recruiting/jobs", element: <JobsBrowse /> },
      { path: "/recruiting/jobs/:jobId", element: <p>DETAIL PAGE</p> },
    ],
    { initialEntries: ["/recruiting/jobs"] },
  );
  return render(<RouterProvider router={router} />);
};

describe("JobsBrowse page", () => {
  it("lists published jobs and navigates to the detail page on click", async () => {
    const user = userEvent.setup();
    api.listPublicJobs.mockResolvedValue({
      data: [{ id: 5, title: "Mentee", kind: "activity", description: "Grow" }],
    });
    renderPage();
    await waitFor(() => expect(screen.getByText("Mentee")).toBeInTheDocument());
    expect(screen.getByText("Grow")).toBeInTheDocument();
    await user.click(screen.getByText("Mentee"));
    expect(screen.getByText("DETAIL PAGE")).toBeInTheDocument();
  });

  it("shows the empty state when no jobs are published", async () => {
    api.listPublicJobs.mockResolvedValue({ data: [] });
    renderPage();
    await waitFor(() =>
      expect(
        screen.getByText("No open positions right now."),
      ).toBeInTheDocument(),
    );
  });

  it("shows an inline error with Retry and recovers", async () => {
    const user = userEvent.setup();
    api.listPublicJobs
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValue({
        data: [{ id: 5, title: "Mentee", kind: "activity" }],
      });
    renderPage();
    await waitFor(() =>
      expect(
        screen.getByText("Couldn't load open positions."),
      ).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.getByText("Mentee")).toBeInTheDocument());
  });
});
