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
      {
        path: "/recruiting/jobs",
        element: <p>Open Positions page</p>,
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

  it("shows an empty state that links to Open Positions", () => {
    renderWithRouter({ applications: [], isLoading: false, loadError: false });
    expect(screen.getByText(/no applications yet/i)).toHaveTextContent(
      "No applications yet. Browse Open Positions to apply for a program or a job.",
    );

    fireEvent.click(
      screen.getByRole("link", { name: "Browse Open Positions" }),
    );
    expect(screen.getByText("Open Positions page")).toBeInTheDocument();
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

  describe("next step on a mentorship row", () => {
    /** A row as `/recruiting/my-applications` returns it. */
    const mentorshipRow = (overrides) => ({
      applicationId: 11,
      jobId: 21,
      jobTitle: "Spring Mentee Program",
      jobKind: "activity",
      mentorshipRole: "mentee",
      stage: "applied",
      ...overrides,
    });

    const renderRows = (applications) =>
      renderWithRouter({ applications, isLoading: false, loadError: false });

    it.each(["applied", "recruiter_screening", "board_review"])(
      "says the decision comes by email while %s",
      (stage) => {
        renderRows([mentorshipRow({ stage })]);
        expect(
          screen.getByText("We'll email you the decision"),
        ).toBeInTheDocument();
      },
    );

    it("points an admitted applicant at the Mentorship section as plain text", () => {
      renderRows([mentorshipRow({ stage: "hired" })]);

      const line = screen.getByText("Your next steps are in Mentorship below");
      expect(line.tagName).toBe("P");
      expect(line.closest("li").querySelectorAll("a, button")).toHaveLength(1);
      expect(
        screen.queryByText("We'll email you the decision"),
      ).not.toBeInTheDocument();
    });

    it.each(["rejected", "blacklisted"])(
      "adds nothing to a %s row",
      (stage) => {
        renderRows([mentorshipRow({ stage })]);
        const row = screen.getByText("Spring Mentee Program").closest("li");
        expect(row.querySelectorAll("p")).toHaveLength(0);
      },
    );

    it("adds nothing to an employment row or an activity row with no mentorship role", () => {
      renderRows([
        mentorshipRow({
          applicationId: 12,
          jobId: 22,
          jobTitle: "Backend Engineer",
          jobKind: "employment",
          mentorshipRole: null,
        }),
        mentorshipRow({
          applicationId: 13,
          jobId: 23,
          jobTitle: "Hackathon",
          mentorshipRole: null,
          stage: "hired",
        }),
      ]);
      expect(
        screen.queryByText(/email you|next steps/i),
      ).not.toBeInTheDocument();
    });

    it("gives each mentorship row its own next step", () => {
      renderRows([
        mentorshipRow({ stage: "hired" }),
        mentorshipRow({
          applicationId: 14,
          jobId: 24,
          jobTitle: "Spring Mentor Program",
          mentorshipRole: "mentor",
          stage: "tech",
        }),
      ]);
      const menteeRow = screen.getByText("Spring Mentee Program").closest("li");
      const mentorRow = screen.getByText("Spring Mentor Program").closest("li");
      expect(menteeRow).toHaveTextContent(
        "Your next steps are in Mentorship below",
      );
      expect(mentorRow).toHaveTextContent("We'll email you the decision");
    });
  });
});
