import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { toast } from "sonner";
import BoardPage from "@/pages/Recruiting/board/BoardPage";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");
// Bazel-sandbox module resolution: `vi.mock("sonner", factory)` doesn't
// intercept the module the component resolved at import time. Spy on the
// real toast instead, matching the rest of the recruiting page tests.
vi.spyOn(toast, "success").mockImplementation(() => {});
vi.spyOn(toast, "error").mockImplementation(() => {});

beforeEach(() => vi.clearAllMocks());

/** Render BoardPage inside a memory router. */
const renderPage = () => {
  const router = createMemoryRouter(
    [{ path: "/recruiting/board", element: <BoardPage /> }],
    { initialEntries: ["/recruiting/board"] },
  );
  return render(<RouterProvider router={router} />);
};

const jobA = {
  id: 1,
  title: "Backend Engineer",
  kind: "employment",
  stages: ["recruiter_screening", "tech"],
};

const jobB = {
  id: 2,
  title: "Mentor",
  kind: "activity",
  stages: ["board_review"],
};

describe("BoardPage", () => {
  it("shows the empty state when the caller owns no jobs", async () => {
    api.listBoardJobs.mockResolvedValue({ data: [] });
    renderPage();
    await waitFor(() =>
      expect(
        screen.getByText("You don't own any postings."),
      ).toBeInTheDocument(),
    );
    expect(api.getJobBoard).not.toHaveBeenCalled();
  });

  it("shows an inline error with Retry and recovers", async () => {
    const user = userEvent.setup();
    api.listBoardJobs
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({ data: {} });
    renderPage();
    await waitFor(() =>
      expect(screen.getByText(/Couldn't load/)).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() =>
      expect(screen.getByText("Backend Engineer")).toBeInTheDocument(),
    );
  });

  it("shows an inline error with Retry for a failed board fetch and recovers", async () => {
    const user = userEvent.setup();
    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard
      .mockRejectedValueOnce(new Error("board boom"))
      .mockResolvedValue({ data: { recruiter_screening: [] } });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Couldn't load the board.")).toBeInTheDocument(),
    );
    expect(api.getJobBoard).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() =>
      expect(screen.getByText("Recruiter screening")).toBeInTheDocument(),
    );
    expect(api.getJobBoard).toHaveBeenCalledTimes(2);
  });

  it("auto-selects the first job, renders lanes from stages plus terminal lanes, and places cards in the right lanes", async () => {
    api.listBoardJobs.mockResolvedValue({ data: [jobA, jobB] });
    api.getJobBoard.mockResolvedValue({
      data: {
        recruiter_screening: [
          {
            id: 101,
            applicantName: "Alice Smith",
            applicantEmail: "alice@example.com",
            stage: "recruiter_screening",
            subStatus: "pending",
            tags: null,
            appliedAt: "2026-06-01T00:00:00Z",
          },
        ],
        hired: [
          {
            id: 102,
            applicantName: "Bob Jones",
            applicantEmail: "bob@example.com",
            stage: "hired",
            subStatus: null,
            tags: { coldFreeze: true },
            appliedAt: "2026-06-02T00:00:00Z",
          },
        ],
      },
    });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Recruiter screening")).toBeInTheDocument(),
    );
    // job.stages labels
    expect(screen.getByText("Tech")).toBeInTheDocument();
    // always-appended terminal lanes
    expect(screen.getByText("Hired")).toBeInTheDocument();
    expect(screen.getByText("Rejected")).toBeInTheDocument();

    // card placed in its lane
    const screeningLane = screen.getByTestId("lane-recruiter_screening");
    expect(within(screeningLane).getByText("Alice Smith")).toBeInTheDocument();

    const hiredLane = screen.getByTestId("lane-hired");
    expect(within(hiredLane).getByText("Bob Jones")).toBeInTheDocument();
    expect(within(hiredLane).getByText("Cold freeze")).toBeInTheDocument();

    // empty lane message
    const techLane = screen.getByTestId("lane-tech");
    expect(within(techLane).getByText("No applicants")).toBeInTheDocument();

    // count badges
    expect(within(screeningLane).getByText("1")).toBeInTheDocument();

    expect(api.getJobBoard).toHaveBeenCalledWith(1);
  });

  it("switches jobs and refetches the board", async () => {
    const user = userEvent.setup();
    api.listBoardJobs.mockResolvedValue({ data: [jobA, jobB] });
    api.getJobBoard.mockImplementation((jobId) =>
      jobId === 1
        ? Promise.resolve({ data: { recruiter_screening: [] } })
        : Promise.resolve({ data: { board_review: [] } }),
    );

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Recruiter screening")).toBeInTheDocument(),
    );
    expect(api.getJobBoard).toHaveBeenCalledWith(1);

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByText("Mentor"));

    await waitFor(() => expect(api.getJobBoard).toHaveBeenCalledWith(2));
    await waitFor(() =>
      expect(screen.getByText("Board review")).toBeInTheDocument(),
    );
  });

  it("does not show a sub-status badge in terminal lanes and shows one in pipeline lanes", async () => {
    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({
      data: {
        recruiter_screening: [
          {
            id: 101,
            applicantName: "Alice Smith",
            applicantEmail: "alice@example.com",
            stage: "recruiter_screening",
            subStatus: "in_progress",
            tags: null,
            appliedAt: "2026-06-01T00:00:00Z",
          },
        ],
        rejected: [
          {
            id: 103,
            applicantName: "Cara Lee",
            applicantEmail: "cara@example.com",
            stage: "rejected",
            // Non-null on purpose: proves the badge is hidden by the
            // showStatus={false} gating for terminal lanes, not merely
            // because there's nothing to show.
            subStatus: "closed_out",
            tags: null,
            appliedAt: "2026-06-03T00:00:00Z",
          },
        ],
      },
    });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Alice Smith")).toBeInTheDocument(),
    );
    expect(screen.getByText("in_progress")).toBeInTheDocument();
    expect(screen.getByText("Cara Lee")).toBeInTheDocument();
    // Cara has a subStatus, but it must not render in a terminal lane.
    const rejectedLane = screen.getByTestId("lane-rejected");
    expect(
      within(rejectedLane).queryByText("closed_out"),
    ).not.toBeInTheDocument();
  });

  it("renders no tag chips when tags is absent, and renders the blacklisted chip when set", async () => {
    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({
      data: {
        recruiter_screening: [
          {
            id: 104,
            applicantName: "Dana White",
            applicantEmail: "dana@example.com",
            stage: "recruiter_screening",
            subStatus: "pending",
            tags: null,
            appliedAt: "2026-06-04T00:00:00Z",
          },
        ],
        hired: [
          {
            id: 105,
            applicantName: "Evan Ng",
            applicantEmail: "evan@example.com",
            stage: "hired",
            subStatus: null,
            tags: { blacklisted: true },
            appliedAt: "2026-06-05T00:00:00Z",
          },
        ],
      },
    });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Dana White")).toBeInTheDocument(),
    );
    const screeningLane = screen.getByTestId("lane-recruiter_screening");
    expect(
      within(screeningLane).queryByText("Cold freeze"),
    ).not.toBeInTheDocument();
    expect(
      within(screeningLane).queryByText("Blacklisted"),
    ).not.toBeInTheDocument();

    const hiredLane = screen.getByTestId("lane-hired");
    expect(within(hiredLane).getByText("Blacklisted")).toBeInTheDocument();
  });

  it("opens the detail dialog via onOpen when a card is clicked", async () => {
    const user = userEvent.setup();
    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({
      data: {
        recruiter_screening: [
          {
            id: 101,
            applicantName: "Alice Smith",
            applicantEmail: "alice@example.com",
            stage: "recruiter_screening",
            subStatus: "pending",
            tags: null,
            appliedAt: "2026-06-01T00:00:00Z",
          },
        ],
      },
    });
    api.getApplicationDetail.mockResolvedValue({
      data: {
        application: {
          id: 101,
          jobId: 1,
          userId: 5,
          stage: "recruiter_screening",
          subStatus: "pending",
          tags: null,
          current: {
            version: 1,
            isFrozen: false,
            submission: {
              personal: {},
              education: [],
              experience: [],
              answers: {},
            },
          },
          editable: false,
        },
        applicantName: "Alice Smith",
        applicantEmail: "alice@example.com",
        resumeAvailable: false,
        formSchema: null,
      },
    });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Alice Smith")).toBeInTheDocument(),
    );
    // Whole card is a button, wired to onOpen -> the dialog fetches and
    // shows this application's detail.
    await user.click(screen.getByRole("button", { name: /Alice Smith/ }));

    await waitFor(() =>
      expect(api.getApplicationDetail).toHaveBeenCalledWith(101),
    );
    await waitFor(() =>
      expect(screen.getByText("alice@example.com")).toBeInTheDocument(),
    );
  });
});
