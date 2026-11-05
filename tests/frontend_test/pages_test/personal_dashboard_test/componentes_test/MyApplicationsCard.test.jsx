import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import MyApplicationsCard from "@/pages/PersonalDashboard/components/MyApplicationsCard";

const renderWithRouter = (props) => {
  const router = createMemoryRouter(
    [
      {
        path: "/dashboard/me",
        element: <MyApplicationsCard {...props} />,
      },
      {
        path: "/recruiting/jobs/:jobId/application",
        element: <p>My application page</p>,
      },
    ],
    { initialEntries: ["/dashboard/me"] },
  );
  return render(<RouterProvider router={router} />);
};

describe("MyApplicationsCard", () => {
  it("shows a loading state", () => {
    renderWithRouter({ applications: [], isLoading: true, loadError: false });
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("shows a retryable error state", () => {
    const onRetry = vi.fn();
    renderWithRouter({
      applications: [],
      isLoading: false,
      loadError: true,
      onRetry,
    });
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("shows an empty state when there are no applications", () => {
    renderWithRouter({ applications: [], isLoading: false, loadError: false });
    expect(screen.getByText(/no applications yet/i)).toBeInTheDocument();
  });

  it("lists each application's title and stage", () => {
    renderWithRouter({
      applications: [
        {
          applicationId: 1,
          jobId: 5,
          jobTitle: "CircleCat Mentor",
          jobKind: "activity",
          mentorshipRole: "mentor",
          stage: "hired",
        },
        {
          applicationId: 2,
          jobId: 6,
          jobTitle: "Backend Engineer",
          jobKind: "employment",
          mentorshipRole: null,
          stage: "recruiter_screening",
        },
      ],
      isLoading: false,
      loadError: false,
    });

    expect(screen.getByText("CircleCat Mentor")).toBeInTheDocument();
    // Activity postings present `hired` as "Admitted" (display-only rename).
    expect(screen.getByText("Admitted")).toBeInTheDocument();
    expect(screen.queryByText("Hired")).not.toBeInTheDocument();
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Recruiter screening")).toBeInTheDocument();
  });

  it("navigates to the job's application route when a row is clicked", () => {
    renderWithRouter({
      applications: [
        {
          applicationId: 1,
          jobId: 5,
          jobTitle: "CircleCat Mentor",
          jobKind: "activity",
          mentorshipRole: "mentor",
          stage: "hired",
        },
      ],
      isLoading: false,
      loadError: false,
    });

    fireEvent.click(screen.getByText("CircleCat Mentor"));
    expect(screen.getByText("My application page")).toBeInTheDocument();
  });
});
