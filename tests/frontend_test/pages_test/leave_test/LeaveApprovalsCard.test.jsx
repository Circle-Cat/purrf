import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import LeaveApprovalsCard from "@/pages/PersonalDashboard/components/LeaveApprovalsCard";

const renderWithRouter = (props) => {
  const router = createMemoryRouter(
    [
      { path: "/dashboard/me", element: <LeaveApprovalsCard {...props} /> },
      { path: "/leave/approvals", element: <p>Approvals page</p> },
    ],
    { initialEntries: ["/dashboard/me"] },
  );
  return render(<RouterProvider router={router} />);
};

describe("LeaveApprovalsCard", () => {
  it("puts the count on the dashboard, not one navigation away", () => {
    renderWithRouter({ pendingCount: 3 });

    expect(screen.getByText(/3 requests are waiting/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Review (3)" }),
    ).toBeInTheDocument();
  });

  it("says one request in the singular", () => {
    renderWithRouter({ pendingCount: 1 });

    expect(screen.getByText(/1 request is waiting/i)).toBeInTheDocument();
  });

  it("still offers the way in when nothing is waiting", () => {
    // An approver who has decided everything still needs to get at what they
    // decided, so an empty queue keeps the entry point rather than hiding it.
    renderWithRouter({ pendingCount: 0 });

    expect(screen.getByText(/nothing is waiting on you/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Review" })).toBeInTheDocument();
  });

  it("opens the approvals page", () => {
    renderWithRouter({ pendingCount: 2 });

    fireEvent.click(screen.getByRole("button", { name: "Review (2)" }));

    expect(screen.getByText("Approvals page")).toBeInTheDocument();
  });
});
