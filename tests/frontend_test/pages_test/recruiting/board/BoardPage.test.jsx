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

beforeEach(() => {
  vi.clearAllMocks();
});

/** Render BoardPage inside a memory router with a stub detail route. */
const renderPage = () => {
  const router = createMemoryRouter(
    [
      { path: "/recruiting/board", element: <BoardPage /> },
      {
        path: "/recruiting/applications/:applicationId",
        element: <p>DETAIL PAGE</p>,
      },
    ],
    { initialEntries: ["/recruiting/board"] },
  );
  return render(<RouterProvider router={router} />);
};

const jobA = {
  id: 1,
  title: "Backend Engineer",
  kind: "employment",
  stages: [
    { stage: "recruiter_screening", rounds: 1 },
    { stage: "tech", rounds: 1 },
  ],
};

const jobB = {
  id: 2,
  title: "Mentor",
  kind: "activity",
  stages: [{ stage: "board_review", rounds: 1 }],
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
      .mockResolvedValue({
        data: {
          stages: {
            recruiter_screening: { items: [], total: 0, has_more: false },
          },
        },
      });

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
        stages: {
          recruiter_screening: {
            items: [
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
            total: 1,
            has_more: false,
          },
          hired: {
            items: [
              {
                id: 102,
                applicantName: "Bob Jones",
                applicantEmail: "bob@example.com",
                stage: "hired",
                subStatus: null,
                tags: { cold_freeze: { thaw_date: "2099-01-01" } },
                appliedAt: "2026-06-02T00:00:00Z",
              },
            ],
            total: 1,
            has_more: false,
          },
        },
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
    expect(within(hiredLane).getByText(/Cold freeze ·/)).toBeInTheDocument();

    // empty lane message
    const techLane = screen.getByTestId("lane-tech");
    expect(within(techLane).getByText("No applicants")).toBeInTheDocument();

    // count badges
    expect(within(screeningLane).getByText("1")).toBeInTheDocument();

    expect(api.getJobBoard).toHaveBeenCalledWith(1);
  });

  it("always shows an Offer lane between an employment job's pipeline lanes and the terminal lanes, regardless of configured stages", async () => {
    const jobNoStages = {
      id: 5,
      title: "No Stages Job",
      kind: "employment",
      stages: [],
    };
    api.listBoardJobs.mockResolvedValue({ data: [jobNoStages] });
    api.getJobBoard.mockResolvedValue({ data: {} });

    renderPage();

    await waitFor(() => expect(screen.getByText("Offer")).toBeInTheDocument());
    expect(screen.getByText("Hired")).toBeInTheDocument();
    expect(screen.getByText("Rejected")).toBeInTheDocument();

    const laneKeys = screen
      .getAllByTestId(/^lane-/)
      .map((el) => el.getAttribute("data-testid"));
    expect(laneKeys).toEqual(["lane-offer", "lane-hired", "lane-rejected"]);
  });

  it("omits the Offer lane and labels the terminal success lane Admitted for an activity job", async () => {
    api.listBoardJobs.mockResolvedValue({ data: [jobB] });
    api.getJobBoard.mockResolvedValue({ data: {} });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Board review")).toBeInTheDocument(),
    );
    expect(screen.getByText("Admitted")).toBeInTheDocument();
    expect(screen.getByText("Rejected")).toBeInTheDocument();
    expect(screen.queryByText("Offer")).not.toBeInTheDocument();
    expect(screen.queryByText("Hired")).not.toBeInTheDocument();

    // The lane still keys off the stored stage value ("hired") — only the
    // label is renamed.
    const laneKeys = screen
      .getAllByTestId(/^lane-/)
      .map((el) => el.getAttribute("data-testid"));
    expect(laneKeys).toEqual([
      "lane-board_review",
      "lane-hired",
      "lane-rejected",
    ]);
  });

  it("switches jobs and refetches the board", async () => {
    const user = userEvent.setup();
    api.listBoardJobs.mockResolvedValue({ data: [jobA, jobB] });
    api.getJobBoard.mockImplementation((jobId) =>
      jobId === 1
        ? Promise.resolve({
            data: {
              stages: {
                recruiter_screening: {
                  items: [],
                  total: 0,
                  has_more: false,
                },
              },
            },
          })
        : Promise.resolve({
            data: {
              stages: {
                board_review: { items: [], total: 0, has_more: false },
              },
            },
          }),
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

  it("opens the How it works guide with the board's title and steps", async () => {
    const user = userEvent.setup();
    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({
      data: {
        stages: {
          recruiter_screening: { items: [], total: 0, has_more: false },
        },
      },
    });

    renderPage();
    await waitFor(() =>
      expect(screen.getByText("Recruiter screening")).toBeInTheDocument(),
    );

    await user.click(screen.getByRole("button", { name: "How it works" }));

    expect(
      screen.getByRole("heading", { name: "How the board works" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Pick a posting")).toBeInTheDocument();
  });

  it("does not show a sub-status badge in terminal lanes and shows one in pipeline lanes", async () => {
    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({
      data: {
        stages: {
          recruiter_screening: {
            items: [
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
            total: 1,
            has_more: false,
          },
          rejected: {
            items: [
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
            total: 1,
            has_more: false,
          },
        },
      },
    });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Alice Smith")).toBeInTheDocument(),
    );
    expect(screen.getByText("In progress")).toBeInTheDocument();
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
        stages: {
          recruiter_screening: {
            items: [
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
            total: 1,
            has_more: false,
          },
          hired: {
            items: [
              {
                id: 105,
                applicantName: "Evan Ng",
                applicantEmail: "evan@example.com",
                stage: "hired",
                subStatus: null,
                tags: { blacklisted: true },
                isBlocked: true,
                appliedAt: "2026-06-05T00:00:00Z",
              },
            ],
            total: 1,
            has_more: false,
          },
        },
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

  it("navigates to the shared application detail page when a card is clicked", async () => {
    const user = userEvent.setup();
    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({
      data: {
        stages: {
          recruiter_screening: {
            items: [
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
            total: 1,
            has_more: false,
          },
        },
      },
    });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Alice Smith")).toBeInTheDocument(),
    );
    // Whole card is a button, wired to onOpen -> navigates to the shared
    // detail route instead of opening a dialog.
    await user.click(screen.getByRole("button", { name: /Alice Smith/ }));

    await waitFor(() =>
      expect(screen.getByText("DETAIL PAGE")).toBeInTheDocument(),
    );
  });

  it("splits a multi-round stage into one lane per round, buckets cards by round, and badges each round lane with its own count (not the whole-stage total)", async () => {
    const jobC = {
      id: 3,
      title: "Staff Engineer",
      kind: "employment",
      stages: [{ stage: "tech", rounds: 2 }],
    };
    api.listBoardJobs.mockResolvedValue({ data: [jobC] });
    api.getJobBoard.mockResolvedValue({
      data: {
        stages: {
          tech: {
            items: [
              {
                id: 201,
                applicantName: "Round One Person",
                applicantEmail: "r1@example.com",
                stage: "tech",
                subStatus: "pending",
                tags: null,
                appliedAt: "2026-06-01T00:00:00Z",
                round: 1,
              },
              {
                id: 202,
                applicantName: "Round Two Person",
                applicantEmail: "r2@example.com",
                stage: "tech",
                subStatus: "pending",
                tags: null,
                appliedAt: "2026-06-02T00:00:00Z",
                round: 2,
              },
            ],
            total: 2,
            has_more: false,
          },
          // Terminal lane with a total that outruns what's loaded, so the
          // test also proves terminal lanes still badge off `total` (they're
          // paginated, so cards.length would undercount them).
          hired: {
            items: [
              {
                id: 501,
                applicantName: "Hired Person",
                applicantEmail: "hired@example.com",
                stage: "hired",
                subStatus: null,
                tags: null,
                appliedAt: "2026-06-03T00:00:00Z",
              },
            ],
            total: 5,
            has_more: true,
          },
        },
      },
    });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Tech — Round 1")).toBeInTheDocument(),
    );
    expect(screen.getByText("Tech — Round 2")).toBeInTheDocument();

    const round1Lane = screen.getByTestId("lane-tech:1");
    expect(
      within(round1Lane).getByText("Round One Person"),
    ).toBeInTheDocument();
    expect(
      within(round1Lane).queryByText("Round Two Person"),
    ).not.toBeInTheDocument();
    // Each round lane badges its own 1-card round bucket, not the
    // whole-stage total of 2.
    expect(within(round1Lane).getByText("1")).toBeInTheDocument();

    const round2Lane = screen.getByTestId("lane-tech:2");
    expect(
      within(round2Lane).getByText("Round Two Person"),
    ).toBeInTheDocument();
    expect(
      within(round2Lane).queryByText("Round One Person"),
    ).not.toBeInTheDocument();
    expect(within(round2Lane).getByText("1")).toBeInTheDocument();

    // Terminal lane still shows the whole-stage total (5), not the 1 card
    // that happens to be loaded on screen.
    const hiredLane = screen.getByTestId("lane-hired");
    expect(within(hiredLane).getByText("5")).toBeInTheDocument();
  });

  it("falls back applicants above the current max round into the last lane instead of hiding them", async () => {
    const jobD = {
      id: 4,
      title: "Principal Engineer",
      kind: "employment",
      stages: [{ stage: "tech", rounds: 2 }],
    };
    api.listBoardJobs.mockResolvedValue({ data: [jobD] });
    api.getJobBoard.mockResolvedValue({
      data: {
        stages: {
          tech: {
            items: [
              {
                id: 301,
                applicantName: "Round Two Person",
                applicantEmail: "r2@example.com",
                stage: "tech",
                subStatus: "pending",
                tags: null,
                appliedAt: "2026-06-01T00:00:00Z",
                round: 2,
              },
              {
                // Stale: was staged at round 3 before the posting's pipeline
                // config shrank "tech" from 3 rounds down to 2.
                id: 302,
                applicantName: "Stale Round Three Person",
                applicantEmail: "r3@example.com",
                stage: "tech",
                subStatus: "pending",
                tags: null,
                appliedAt: "2026-06-02T00:00:00Z",
                round: 3,
              },
            ],
            total: 2,
            has_more: false,
          },
        },
      },
    });

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Tech — Round 2")).toBeInTheDocument(),
    );
    expect(screen.queryByText("Tech — Round 3")).not.toBeInTheDocument();

    const lastLane = screen.getByTestId("lane-tech:2");
    expect(within(lastLane).getByText("Round Two Person")).toBeInTheDocument();
    expect(
      within(lastLane).getByText("Stale Round Three Person"),
    ).toBeInTheDocument();
  });

  it("shows Load more on a terminal lane and appends deduped cards, dropping an id the first page already rendered", async () => {
    const user = userEvent.setup();
    const makeCard = (id) => ({
      id,
      applicantName: `Rejected Person ${id}`,
      applicantEmail: `rejected${id}@example.com`,
      stage: "rejected",
      subStatus: null,
      tags: null,
      appliedAt: "2026-06-01T00:00:00Z",
    });
    const firstPage = Array.from({ length: 20 }, (_, i) => makeCard(i + 1));
    // Overlaps with the first page on id 20 (e.g. a slow fetch racing an
    // insert ahead of the offset) plus 4 genuinely new ids — this is the
    // case plain concatenation would double-render, but the Set-based
    // dedupe in loadMore must drop.
    const secondPage = [makeCard(20), makeCard(21), makeCard(22), makeCard(23), makeCard(24)];

    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({
      data: {
        stages: {
          rejected: { items: firstPage, total: 24, has_more: true },
        },
      },
    });
    api.getJobBoardStagePage.mockResolvedValue({
      data: { items: secondPage, total: 24, has_more: false },
    });

    renderPage();

    const rejectedLane = await screen.findByTestId("lane-rejected");
    expect(
      within(rejectedLane).getByText("Load more"),
    ).toBeInTheDocument();
    expect(within(rejectedLane).getAllByRole("button").length).toBe(
      firstPage.length + 1, // 20 cards + the Load more button
    );

    await user.click(within(rejectedLane).getByText("Load more"));

    expect(api.getJobBoardStagePage).toHaveBeenCalledWith(1, {
      stage: "rejected",
      limit: 20,
      offset: 20,
    });

    await waitFor(() =>
      expect(
        within(rejectedLane).getByText("Rejected Person 24"),
      ).toBeInTheDocument(),
    );
    // The repeated id 20 renders exactly once, not twice.
    expect(
      within(rejectedLane).getAllByText("Rejected Person 20").length,
    ).toBe(1);
    // 20 original cards + 4 genuinely new ones = 24 unique cards rendered
    // (not 25, which is what concatenation-without-dedupe would produce),
    // and the button is gone.
    expect(within(rejectedLane).getAllByRole("button").length).toBe(24);
    expect(
      within(rejectedLane).queryByText("Load more"),
    ).not.toBeInTheDocument();
  });

  it("guards against a double-click on Load more firing two requests for the same stage", async () => {
    const user = userEvent.setup();
    const makeCard = (id) => ({
      id,
      applicantName: `Rejected Person ${id}`,
      applicantEmail: `rejected${id}@example.com`,
      stage: "rejected",
      subStatus: null,
      tags: null,
      appliedAt: "2026-06-01T00:00:00Z",
    });
    const firstPage = Array.from({ length: 20 }, (_, i) => makeCard(i + 1));
    let resolvePage;
    const pagePromise = new Promise((resolve) => {
      resolvePage = resolve;
    });

    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({
      data: {
        stages: {
          rejected: { items: firstPage, total: 21, has_more: true },
        },
      },
    });
    api.getJobBoardStagePage.mockImplementation(() => pagePromise);

    renderPage();

    const rejectedLane = await screen.findByTestId("lane-rejected");
    const loadMoreButton = within(rejectedLane).getByText("Load more");

    // Two rapid clicks while the first request is still in flight.
    await user.click(loadMoreButton);
    await user.click(loadMoreButton);

    // Only one request fired for the stage, and the button is disabled
    // while its load is pending.
    expect(api.getJobBoardStagePage).toHaveBeenCalledTimes(1);
    expect(loadMoreButton).toBeDisabled();

    resolvePage({
      data: { items: [makeCard(21)], total: 21, has_more: false },
    });

    await waitFor(() =>
      expect(
        within(rejectedLane).getByText("Rejected Person 21"),
      ).toBeInTheDocument(),
    );
    // Load finished, button is gone (has_more is now false) — nothing left
    // stuck disabled.
    expect(
      within(rejectedLane).queryByText("Load more"),
    ).not.toBeInTheDocument();
  });

  it("shows an error toast and keeps existing items when Load more fails", async () => {
    const user = userEvent.setup();
    const makeCard = (id) => ({
      id,
      applicantName: `Rejected Person ${id}`,
      applicantEmail: `rejected${id}@example.com`,
      stage: "rejected",
      subStatus: null,
      tags: null,
      appliedAt: "2026-06-01T00:00:00Z",
    });
    const firstPage = Array.from({ length: 20 }, (_, i) => makeCard(i + 1));

    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({
      data: {
        stages: {
          rejected: { items: firstPage, total: 25, has_more: true },
        },
      },
    });
    api.getJobBoardStagePage.mockRejectedValue(new Error("page boom"));

    renderPage();

    const rejectedLane = await screen.findByTestId("lane-rejected");
    await user.click(within(rejectedLane).getByText("Load more"));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("page boom"));
    // Existing items are left unchanged and the button is still shown.
    expect(within(rejectedLane).getAllByRole("button").length).toBe(21);
    expect(
      within(rejectedLane).getByText("Load more"),
    ).toBeInTheDocument();
  });
});
