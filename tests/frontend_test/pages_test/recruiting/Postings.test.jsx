import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import Postings from "@/pages/Recruiting/Postings";
import * as api from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

vi.mock("@/api/recruitingApi");
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/context/auth/AuthContext", () => ({
  useAuth: () => ({ user: { userId: 1 } }),
}));

const approvers = [
  { userId: 2, name: "Bob", email: "bob@x.com" },
  { userId: 3, name: "Cara", email: "cara@x.com" },
];

/** Render Postings inside a MemoryRouter at the postings list path.
 * Returns both the render result and a handle to the router so tests can
 * inspect router.state.location after navigation. */
const renderPostings = () => {
  const router = createMemoryRouter(
    [
      { path: ROUTE_PATHS.RECRUITING_POSTINGS, element: <Postings /> },
      {
        path: ROUTE_PATHS.RECRUITING_POSTING_NEW,
        element: <div data-testid="new-posting-page" />,
      },
      {
        path: "/recruiting/postings/:id/edit",
        element: <div data-testid="edit-posting-page" />,
      },
    ],
    { initialEntries: [ROUTE_PATHS.RECRUITING_POSTINGS] },
  );
  const result = render(<RouterProvider router={router} />);
  return { ...result, router };
};

beforeEach(() => {
  vi.clearAllMocks();
  api.listJobs.mockResolvedValue({
    data: [{ id: 1, title: "SWE", kind: "employment", status: "draft" }],
  });
  api.listApprovers.mockResolvedValue({ data: approvers });
  api.closeJob.mockResolvedValue({ data: {} });
  api.requestClose.mockResolvedValue({ data: {} });
  api.requestReopen.mockResolvedValue({ data: {} });
  api.deleteJob.mockResolvedValue({ data: {} });
  api.listInterviewPool.mockResolvedValue({ data: [] });
  api.listJobOwners.mockResolvedValue({ data: [] });
});

describe("Postings page", () => {
  it("loads and lists jobs on mount", async () => {
    renderPostings();
    expect(await screen.findByText("SWE")).toBeInTheDocument();
    expect(api.listJobs).toHaveBeenCalled();
  });

  it("loads approvers on mount so assignee names are ready without opening the dialog", async () => {
    api.listJobs.mockResolvedValue({
      data: [
        {
          id: 1,
          title: "SWE",
          kind: "employment",
          status: "pending_review",
          reviewerId: 2,
        },
      ],
    });
    renderPostings();
    expect(await screen.findByText("Assigned to: Bob")).toBeInTheDocument();
  });

  it("New posting button navigates to the new-posting route", async () => {
    const { router } = renderPostings();
    await screen.findByText("SWE");
    fireEvent.click(screen.getByRole("button", { name: "New posting" }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        ROUTE_PATHS.RECRUITING_POSTING_NEW,
      ),
    );
  });

  it("shows the How it works guide with author statuses", async () => {
    renderPostings();
    await screen.findByText("SWE");
    fireEvent.click(screen.getByRole("button", { name: "How it works" }));
    expect(
      await screen.findByRole("heading", { name: "How postings work" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Revision pending review")).toBeInTheDocument();
  });

  it("Edit button navigates to the edit route for that job", async () => {
    const { router } = renderPostings();
    await screen.findByText("SWE");
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    await waitFor(() =>
      expect(router.state.location.pathname).toBe(
        ROUTE_PATHS.RECRUITING_POSTING_EDIT(1),
      ),
    );
  });

  it("closes a draft job directly then refetches", async () => {
    renderPostings();
    await screen.findByText("SWE");
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    await waitFor(() => expect(api.closeJob).toHaveBeenCalledWith(1));
    expect(api.listJobs).toHaveBeenCalledTimes(2);
  });

  it("disables Close while it's in flight, to prevent a double-submit", async () => {
    let resolveClose;
    api.closeJob.mockReturnValue(
      new Promise((resolve) => {
        resolveClose = resolve;
      }),
    );
    renderPostings();
    await screen.findByText("SWE");
    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(screen.getByRole("button", { name: "Close" })).toBeDisabled();

    resolveClose({ data: {} });
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Close" })).not.toBeDisabled(),
    );
  });

  it("clicking Request close on a published job opens review dialog with title 'Request close', submits requestClose then refetches", async () => {
    api.listJobs.mockResolvedValue({
      data: [
        {
          id: 2,
          title: "PM",
          kind: "employment",
          status: "published",
        },
      ],
    });
    api.requestClose.mockResolvedValue({ data: {} });

    renderPostings();
    await screen.findByText("PM");

    fireEvent.click(screen.getByRole("button", { name: "Request close" }));
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Request close" }),
      ).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByLabelText("Reviewer"), {
      target: { value: "2" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));

    await waitFor(() =>
      expect(api.requestClose).toHaveBeenCalledWith(2, {
        reviewerId: 2,
        message: null,
      }),
    );
    expect(api.listJobs).toHaveBeenCalledTimes(2);
  });

  it("disables Submit while a review action is in flight, to prevent a double-submit", async () => {
    let resolveRequestClose;
    api.requestClose.mockReturnValue(
      new Promise((resolve) => {
        resolveRequestClose = resolve;
      }),
    );
    api.listJobs.mockResolvedValue({
      data: [{ id: 2, title: "PM", kind: "employment", status: "published" }],
    });

    renderPostings();
    await screen.findByText("PM");

    fireEvent.click(screen.getByRole("button", { name: "Request close" }));
    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: "Request close" }),
      ).toBeInTheDocument(),
    );
    fireEvent.change(screen.getByLabelText("Reviewer"), {
      target: { value: "2" },
    });

    const submitButton = screen.getByRole("button", { name: "Submit" });
    fireEvent.click(submitButton);
    expect(submitButton).toBeDisabled();
    fireEvent.click(submitButton);
    expect(api.requestClose).toHaveBeenCalledTimes(1);

    resolveRequestClose({ data: {} });
    await waitFor(() => expect(api.listJobs).toHaveBeenCalledTimes(2));
    expect(
      screen.queryByRole("heading", { name: "Request close" }),
    ).not.toBeInTheDocument();
  });

  it("clicking Delete on a never-published closed job shows confirm dialog, confirming calls deleteJob then refetches", async () => {
    api.listJobs.mockResolvedValue({
      data: [
        {
          id: 3,
          title: "Old Draft",
          kind: "employment",
          status: "closed",
          wasPublished: false,
        },
      ],
    });
    api.deleteJob.mockResolvedValue({ data: {} });

    renderPostings();
    await screen.findByText("Old Draft");

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(
      await screen.findByText(/Delete this posting\?/i),
    ).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "Delete", hidden: false }),
    );

    await waitFor(() => expect(api.deleteJob).toHaveBeenCalledWith(3));
    expect(api.listJobs).toHaveBeenCalledTimes(2);
  });

  it("View swaps to a full-page preview and Back returns to the list", async () => {
    renderPostings();
    await screen.findByText("SWE");
    fireEvent.click(screen.getByRole("button", { name: "View" }));
    // full-page preview: Back button present, list chrome gone
    await waitFor(() => expect(api.listInterviewPool).toHaveBeenCalled());
    expect(screen.getByRole("button", { name: /Back/ })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "New posting" }),
    ).not.toBeInTheDocument();
    // Back returns to the list
    fireEvent.click(screen.getByRole("button", { name: /Back/ }));
    expect(
      await screen.findByRole("button", { name: "New posting" }),
    ).toBeInTheDocument();
  });
});
