import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import {
  createMemoryRouter,
  RouterProvider,
  useParams,
} from "react-router-dom";
import Postings from "@/pages/Recruiting/Postings";
import * as api from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { PERMISSIONS } from "@/constants/Permissions";

vi.mock("@/api/recruitingApi");
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
const mockUseAuth = vi.fn();
vi.mock("@/context/auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

describe("Postings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      user: { userId: 5 },
      permissions: [PERMISSIONS.RECRUITING_JOB_WRITE],
    });
    api.listJobs.mockResolvedValue({
      data: [
        {
          id: 1,
          title: "Backend Engineer",
          kind: "employment",
          status: "draft",
          pipelineConfig: { ownerIds: [5] },
        },
      ],
    });
    api.listApprovers.mockResolvedValue({ data: [] });
    api.listJobOwners.mockResolvedValue({
      data: [{ userId: 5, name: "Alice", email: "a@x.com" }],
    });
    api.listMyReviews.mockResolvedValue({ data: [] });
  });

  const renderPage = () => {
    const router = createMemoryRouter(
      [
        { path: ROUTE_PATHS.RECRUITING_POSTINGS, element: <Postings /> },
        {
          path: ROUTE_PATHS.RECRUITING_POSTING_DETAIL(":id"),
          element: <p>detail page</p>,
        },
      ],
      { initialEntries: [ROUTE_PATHS.RECRUITING_POSTINGS] },
    );
    return render(<RouterProvider router={router} />);
  };

  it("renders the Recruiter cue from listJobOwners", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Recruiter: Alice")).toBeInTheDocument(),
    );
  });

  it("navigates to the detail page on row click", async () => {
    renderPage();
    await waitFor(() => screen.getByText("Backend Engineer"));
    fireEvent.click(screen.getByText("Backend Engineer"));
    await waitFor(() =>
      expect(screen.getByText("detail page")).toBeInTheDocument(),
    );
  });

  it("filters to only the current user's own postings when toggled", async () => {
    renderPage();
    await waitFor(() => screen.getByText("Backend Engineer"));
    fireEvent.click(
      screen.getByRole("checkbox", { name: "I'm the recruiter" }),
    );
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument(); // user 5 is an owner

    fireEvent.click(
      screen.getByRole("checkbox", { name: "I'm the recruiter" }),
    );
  });

  it("New posting button navigates to the new-posting route", async () => {
    const router = createMemoryRouter(
      [
        { path: ROUTE_PATHS.RECRUITING_POSTINGS, element: <Postings /> },
        {
          path: ROUTE_PATHS.RECRUITING_POSTING_NEW,
          element: <p>new posting page</p>,
        },
      ],
      { initialEntries: [ROUTE_PATHS.RECRUITING_POSTINGS] },
    );
    render(<RouterProvider router={router} />);
    await waitFor(() => screen.getByText("Backend Engineer"));
    fireEvent.click(screen.getByRole("button", { name: "New posting" }));
    await waitFor(() =>
      expect(screen.getByText("new posting page")).toBeInTheDocument(),
    );
  });

  // Starting a new posting has nothing to do with the list, so it stays
  // reachable without scrolling past however many postings there are.
  it("renders New posting in the header, above the postings list", async () => {
    renderPage();
    const row = await waitFor(() => screen.getByText("Backend Engineer"));
    const newPosting = screen.getByRole("button", { name: "New posting" });
    expect(
      row.compareDocumentPosition(newPosting) &
        Node.DOCUMENT_POSITION_PRECEDING,
    ).toBeTruthy();
  });

  it("disables New posting when the user lacks recruiting.job.write", async () => {
    mockUseAuth.mockReturnValue({ user: { userId: 5 }, permissions: [] });
    renderPage();
    await waitFor(() => screen.getByText("Backend Engineer"));
    expect(screen.getByRole("button", { name: "New posting" })).toBeDisabled();
  });

  it("does not show the Backend Engineer posting when I'm the recruiter excludes the current user", async () => {
    api.listJobs.mockResolvedValue({
      data: [
        {
          id: 1,
          title: "Backend Engineer",
          kind: "employment",
          status: "draft",
          pipelineConfig: { ownerIds: [99] },
        },
      ],
    });
    renderPage();
    await waitFor(() => screen.getByText("Backend Engineer"));
    fireEvent.click(
      screen.getByRole("checkbox", { name: "I'm the recruiter" }),
    );
    await waitFor(() =>
      expect(screen.queryByText("Backend Engineer")).not.toBeInTheDocument(),
    );
  });

  describe("review card", () => {
    const DetailPage = () => <p>detail page {useParams().id}</p>;

    // A different job from the one in the postings list, so opening it
    // proves the card navigates by the review's own jobId.
    const pendingReview = {
      reviewId: 3,
      jobId: 7,
      jobTitle: "Data Analyst",
      kind: "initial",
    };

    const renderWithDetail = () => {
      const router = createMemoryRouter(
        [
          { path: ROUTE_PATHS.RECRUITING_POSTINGS, element: <Postings /> },
          {
            path: ROUTE_PATHS.RECRUITING_POSTING_DETAIL(":id"),
            element: <DetailPage />,
          },
        ],
        { initialEntries: [ROUTE_PATHS.RECRUITING_POSTINGS] },
      );
      return render(<RouterProvider router={router} />);
    };

    it("shows an approver the postings waiting on them and opens one", async () => {
      mockUseAuth.mockReturnValue({
        user: { userId: 5 },
        permissions: [PERMISSIONS.RECRUITING_JOB_APPROVE],
      });
      api.listMyReviews.mockResolvedValue({ data: [pendingReview] });
      renderWithDetail();

      expect(await screen.findByText("Pending approvals")).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "Review" }));
      await waitFor(() =>
        expect(screen.getByText("detail page 7")).toBeInTheDocument(),
      );
    });

    it("hides the card when nothing is waiting on the approver", async () => {
      mockUseAuth.mockReturnValue({
        user: { userId: 5 },
        permissions: [PERMISSIONS.RECRUITING_JOB_APPROVE],
      });
      renderPage();
      await waitFor(() => screen.getByText("Backend Engineer"));
      expect(api.listMyReviews).toHaveBeenCalled();
      expect(screen.queryByText("Pending approvals")).not.toBeInTheDocument();
    });

    // The reviews route 403s without job.approve.
    it("does not fetch reviews for a viewer without job.approve", async () => {
      renderPage();
      await waitFor(() => screen.getByText("Backend Engineer"));
      expect(api.listMyReviews).not.toHaveBeenCalled();
    });
  });
});
