import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import MyReviews from "@/pages/Recruiting/MyReviews";
import * as api from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

vi.mock("@/api/recruitingApi");
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

describe("MyReviews", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listMyReviews.mockResolvedValue({
      data: [
        {
          reviewId: 3,
          jobId: 7,
          jobTitle: "Backend Engineer",
          kind: "initial",
        },
      ],
    });
  });

  it("navigates to the unified detail page when a queue item is opened", async () => {
    const router = createMemoryRouter(
      [
        { path: ROUTE_PATHS.RECRUITING_REVIEWS, element: <MyReviews /> },
        {
          path: ROUTE_PATHS.RECRUITING_POSTING_DETAIL(":id"),
          element: <p>detail page</p>,
        },
      ],
      { initialEntries: [ROUTE_PATHS.RECRUITING_REVIEWS] },
    );
    render(<RouterProvider router={router} />);

    await waitFor(() => screen.getByText("Backend Engineer"));
    fireEvent.click(screen.getByRole("button", { name: "Review" }));

    await waitFor(() =>
      expect(screen.getByText("detail page")).toBeInTheDocument(),
    );
  });

  // The review kinds are explained on the badges themselves now; see
  // ReviewQueue.test.jsx.
  it("shows no How it works button", async () => {
    const router = createMemoryRouter(
      [{ path: ROUTE_PATHS.RECRUITING_REVIEWS, element: <MyReviews /> }],
      { initialEntries: [ROUTE_PATHS.RECRUITING_REVIEWS] },
    );
    render(<RouterProvider router={router} />);
    await screen.findByRole("button", { name: "Review" });
    expect(
      screen.queryByRole("button", { name: "How it works" }),
    ).not.toBeInTheDocument();
  });
});
