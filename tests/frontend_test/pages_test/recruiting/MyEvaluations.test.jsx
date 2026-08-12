import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { toast } from "sonner";
import MyEvaluations from "@/pages/Recruiting/MyEvaluations";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
// Bazel-sandbox module resolution: `vi.mock("sonner", factory)` doesn't
// intercept the module the component resolved at import time. Spy on the
// real toast instead, matching the rest of the recruiting page tests.
vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

beforeEach(() => vi.clearAllMocks());

/** Render MyEvaluations inside a memory router with a stub detail route. */
const renderPage = () => {
  const router = createMemoryRouter(
    [
      { path: "/recruiting/my-evaluations", element: <MyEvaluations /> },
      {
        path: "/recruiting/applications/:applicationId",
        element: <p>DETAIL PAGE</p>,
      },
    ],
    { initialEntries: ["/recruiting/my-evaluations"] },
  );
  return render(<RouterProvider router={router} />);
};

describe("MyEvaluations page", () => {
  // This page is the interviewer's whole entry point, and an empty one is what
  // they see before anyone has assigned them anything. "You have no assigned
  // evaluations" reads as "nothing is expected of me", when the truth is that
  // a named other person has to act first.
  it("explains an empty queue rather than only stating it is empty", async () => {
    api.listMyEvaluations.mockResolvedValue({ data: [] });
    renderPage();

    expect(
      await screen.findByText(
        "Interviews you've been assigned to appear here.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "A recruiter assigns you to an interview session from their applications board.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("You can't add yourself — ask the posting's recruiter."),
    ).toBeInTheDocument();
  });

  it("explains the No longer assigned badge", async () => {
    api.listMyEvaluations.mockResolvedValue({
      data: [
        {
          applicationId: 9,
          applicantName: "Dana",
          jobTitle: "Backend Engineer",
          stage: "tech",
          round: 1,
          isConfirmed: false,
          isCurrent: false,
        },
      ],
    });
    renderPage();

    (await screen.findByText("No longer assigned")).focus();

    expect(
      await screen.findByText(
        "This session was reassigned to someone else, so it is read-only for you.",
      ),
    ).toBeInTheDocument();
  });

  it("lists each evaluation's job, applicant, stage, and confirmation status, and navigates to the detail page on click", async () => {
    const user = userEvent.setup();
    api.listMyEvaluations.mockResolvedValue({
      data: [
        {
          applicationId: 7,
          jobTitle: "Backend Engineer",
          applicantName: "Ada Lovelace",
          stage: "recruiter_screening",
          round: 1,
          isConfirmed: false,
          isCurrent: true,
        },
        {
          applicationId: 8,
          jobTitle: "Frontend Engineer",
          applicantName: "Grace Hopper",
          stage: "tech",
          round: 2,
          isConfirmed: true,
          isCurrent: true,
        },
      ],
    });
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument(),
    );
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(
      screen.getByText("Recruiter screening — Session 1"),
    ).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();

    expect(screen.getByText("Grace Hopper")).toBeInTheDocument();
    expect(screen.getByText("Frontend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Tech — Session 2")).toBeInTheDocument();
    expect(screen.getByText("Confirmed")).toBeInTheDocument();

    await user.click(screen.getByText("Ada Lovelace"));
    expect(screen.getByText("DETAIL PAGE")).toBeInTheDocument();
  });

  it("shows two rounds of the same application/stage as distinct rows", async () => {
    api.listMyEvaluations.mockResolvedValue({
      data: [
        {
          applicationId: 9,
          jobTitle: "Backend Engineer",
          applicantName: "Ada Lovelace",
          stage: "tech",
          round: 1,
          isConfirmed: true,
          isCurrent: true,
        },
        {
          applicationId: 9,
          jobTitle: "Backend Engineer",
          applicantName: "Ada Lovelace",
          stage: "tech",
          round: 2,
          isConfirmed: false,
          isCurrent: true,
        },
      ],
    });
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Tech — Session 1")).toBeInTheDocument(),
    );
    expect(screen.getByText("Tech — Session 2")).toBeInTheDocument();
    expect(screen.getByText("Confirmed")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("shows an inline error with Retry and recovers", async () => {
    const user = userEvent.setup();
    api.listMyEvaluations
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValue({
        data: [
          {
            applicationId: 7,
            jobTitle: "Backend Engineer",
            applicantName: "Ada Lovelace",
            stage: "recruiter_screening",
            round: 1,
            isConfirmed: false,
            isCurrent: true,
          },
        ],
      });
    renderPage();
    await waitFor(() =>
      expect(
        screen.getByText("Couldn't load your evaluations."),
      ).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() =>
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument(),
    );
  });

  it("renders a stale-but-confirmed row as non-clickable with a 'No longer assigned' badge", async () => {
    const user = userEvent.setup();
    api.listMyEvaluations.mockResolvedValue({
      data: [
        {
          applicationId: 7,
          jobTitle: "Backend Engineer",
          applicantName: "Ada Lovelace",
          stage: "tech",
          round: 1,
          isConfirmed: true,
          isCurrent: false,
        },
      ],
    });
    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Ada Lovelace")).toBeInTheDocument(),
    );
    expect(screen.getByText("No longer assigned")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();

    await user.click(screen.getByText("Ada Lovelace"));
    expect(screen.queryByText("DETAIL PAGE")).not.toBeInTheDocument();
  });
});
