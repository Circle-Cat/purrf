import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import Postings from "@/pages/Recruiting/Postings";
import * as api from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

vi.mock("@/api/recruitingApi");
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("@/context/auth/AuthContext", () => ({
  useAuth: () => ({ user: { userId: 5 }, permissions: [] }),
}));

describe("Postings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

  it("renders the Managed by cue from listJobOwners", async () => {
    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Managed by: Alice")).toBeInTheDocument(),
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

  it("filters to only the current user's managed postings when toggled", async () => {
    renderPage();
    await waitFor(() => screen.getByText("Backend Engineer"));
    fireEvent.click(screen.getByRole("checkbox", { name: "My postings" }));
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument(); // user 5 is an owner

    fireEvent.click(screen.getByRole("checkbox", { name: "My postings" }));
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

  it("does not show the Backend Engineer posting when My postings excludes the current user", async () => {
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
    fireEvent.click(screen.getByRole("checkbox", { name: "My postings" }));
    await waitFor(() =>
      expect(screen.queryByText("Backend Engineer")).not.toBeInTheDocument(),
    );
  });
});
