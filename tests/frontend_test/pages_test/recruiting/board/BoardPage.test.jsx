import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within, act } from "@testing-library/react";
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

// Set by the test that spies on Element.prototype.scrollIntoView, so the
// shared afterEach below can restore it even if that test fails before
// reaching its own cleanup — vi.clearAllMocks() only clears call history, not
// installed mock implementations, so a leaked spy would otherwise silence
// scrollIntoView for every test that runs after it in this file.
let scrollIntoViewSpy;

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.useRealTimers();
  scrollIntoViewSpy?.mockRestore();
  scrollIntoViewSpy = undefined;
});

/** Render BoardPage inside a memory router with a stub detail route.
 * Returns the router too, so tests can assert on the resulting URL. */
const renderPage = (search = "") => {
  const router = createMemoryRouter(
    [
      { path: "/recruiting/board", element: <BoardPage /> },
      {
        path: "/recruiting/applications/:applicationId",
        element: <p>DETAIL PAGE</p>,
      },
    ],
    { initialEntries: [`/recruiting/board${search}`] },
  );
  return { ...render(<RouterProvider router={router} />), router };
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
    const secondPage = [
      makeCard(20),
      makeCard(21),
      makeCard(22),
      makeCard(23),
      makeCard(24),
    ];

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
    expect(within(rejectedLane).getByText("Load more")).toBeInTheDocument();
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
    expect(within(rejectedLane).getAllByText("Rejected Person 20").length).toBe(
      1,
    );
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
    expect(within(rejectedLane).getByText("Load more")).toBeInTheDocument();
  });

  it("opens the job named by ?jobId= instead of the first one", async () => {
    api.listBoardJobs.mockResolvedValue({ data: [jobA, jobB] });
    api.getJobBoard.mockResolvedValue({
      data: {
        stages: { board_review: { items: [], total: 0, has_more: false } },
      },
    });

    renderPage("?jobId=2");

    await waitFor(() => expect(api.getJobBoard).toHaveBeenCalledWith(2));
    // Mutation check: jobA is first in the list, so a board that ignored the
    // param would have fetched 1 and rendered jobA's lanes.
    expect(api.getJobBoard).not.toHaveBeenCalledWith(1);
    // `findBy`, not `getBy`: the waitFor above only proves the fetch was
    // *called*. Its resolution, the state update and the re-render land a tick
    // later, so a synchronous query here races the render and fails under load.
    expect(await screen.findByText("Board review")).toBeInTheDocument();
  });

  it("falls back to the first job and rewrites the URL when ?jobId= names a job the caller doesn't own", async () => {
    api.listBoardJobs.mockResolvedValue({ data: [jobA, jobB] });
    // Mirrors the backend: paging a board you don't own raises. The gate is
    // what keeps this rejection unreachable — without it, getJobBoard(999)
    // fires, rejects, and loadBoard surfaces it as an error toast.
    api.getJobBoard.mockImplementation((jobId) =>
      jobId === 1
        ? Promise.resolve({
            data: {
              stages: {
                recruiter_screening: { items: [], total: 0, has_more: false },
              },
            },
          })
        : Promise.reject(new Error("you are not an owner of this job")),
    );

    // 999 is a stale link, or a posting this caller was removed from.
    const { router } = renderPage("?jobId=999&focus=101");

    await waitFor(() => expect(api.getJobBoard).toHaveBeenCalledWith(1));
    expect(router.state.location.search).toBe("?jobId=1");
    // The focus id belonged to the job we couldn't honour, so it goes too.
    expect(router.state.location.search).not.toContain("focus");
    expect(api.getJobBoard).not.toHaveBeenCalledWith(999);
    // Mutation check: switch the correction to a push and this still reads
    // "?jobId=1" above, but browser-back would land back on the board
    // instead of leaving it — nothing links to the board with ?jobId=, so
    // every param-less arrival would stack a history entry.
    expect(router.state.historyAction).toBe("REPLACE");
    // The fallback must be quiet: no error toast for a stale or foreign id.
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("falls back to the first job when ?jobId= isn't a number", async () => {
    api.listBoardJobs.mockResolvedValue({ data: [jobA, jobB] });
    api.getJobBoard.mockResolvedValue({
      data: {
        stages: {
          recruiter_screening: { items: [], total: 0, has_more: false },
        },
      },
    });

    const { router } = renderPage("?jobId=abc");

    await waitFor(() => expect(api.getJobBoard).toHaveBeenCalledWith(1));
    expect(router.state.location.search).toBe("?jobId=1");
  });

  it("writes the chosen job into the URL when the switcher changes, without stacking history entries", async () => {
    const user = userEvent.setup();
    api.listBoardJobs.mockResolvedValue({ data: [jobA, jobB] });
    api.getJobBoard.mockResolvedValue({ data: { stages: {} } });

    // Start already reconciled, so the only history action under test is the
    // switcher's own write.
    const { router } = renderPage("?jobId=1");

    await waitFor(() => expect(api.getJobBoard).toHaveBeenCalledWith(1));
    expect(router.state.historyAction).toBe("POP");

    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByText("Mentor"));

    await waitFor(() => expect(router.state.location.search).toBe("?jobId=2"));
    // `replace: true` reuses the history entry rather than pushing a new one,
    // so browser-back leaves the board instead of walking job selections.
    // Mutation check: drop `replace` and this reads "PUSH".
    expect(router.state.historyAction).toBe("REPLACE");
  });

  it("scrolls the focused card into view, rings it, and strips focus from the URL", async () => {
    // jsdom's shim is a bare no-op (setupTests.js), so spy on the prototype to
    // see WHICH element the board asked to scroll to. A plain `function` (not
    // an arrow) is required: `this` is the element the method was called on,
    // and vitest 1.6.1's mock objects expose no `contexts` array to read it
    // from afterwards.
    const scrolled = [];
    scrollIntoViewSpy = vi
      .spyOn(Element.prototype, "scrollIntoView")
      .mockImplementation(function captureTarget() {
        scrolled.push(this);
      });

    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({
      data: {
        stages: {
          rejected: {
            items: [
              {
                id: 777,
                applicantName: "Just Rejected",
                applicantEmail: "jr@example.com",
                stage: "rejected",
                subStatus: null,
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

    const { router } = renderPage("?jobId=1&focus=777");

    const card = await screen.findByRole("button", { name: /Just Rejected/ });
    await waitFor(() => expect(scrolled).toHaveLength(1));
    // The focused card itself, not merely "something scrolled".
    expect(scrolled[0]).toBe(card);
    await waitFor(() => expect(card.className).toContain("ring-2"));
    // Stripped so a refresh doesn't repeat the hunt, and via `replace` so it
    // doesn't add a history entry.
    await waitFor(() => expect(router.state.location.search).toBe("?jobId=1"));
  });

  it("pages a terminal lane to find a focused card that isn't on the first page", async () => {
    const makeCard = (id) => ({
      id,
      applicantName: `Rejected Person ${id}`,
      applicantEmail: `rejected${id}@example.com`,
      stage: "rejected",
      subStatus: null,
      tags: null,
      appliedAt: "2026-06-01T00:00:00Z",
    });

    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({
      data: {
        stages: {
          rejected: {
            items: Array.from({ length: 20 }, (_, i) => makeCard(i + 1)),
            total: 25,
            has_more: true,
          },
        },
      },
    });
    // The focused applicant sits at position 21 — the un-backfilled
    // stage_entered_at rows crowd the top of the lane.
    api.getJobBoardStagePage.mockResolvedValue({
      data: { items: [makeCard(21)], total: 25, has_more: false },
    });

    renderPage("?jobId=1&focus=21");

    await waitFor(() =>
      expect(api.getJobBoardStagePage).toHaveBeenCalledWith(1, {
        stage: "rejected",
        limit: 20,
        offset: 20,
      }),
    );
    const card = await screen.findByRole("button", {
      name: /Rejected Person 21/,
    });
    await waitFor(() => expect(card.className).toContain("ring-2"));
  });

  it("gives up quietly and doesn't retry when a focus-hunt page request fails", async () => {
    const makeCard = (id) => ({
      id,
      applicantName: `Rejected Person ${id}`,
      applicantEmail: `rejected${id}@example.com`,
      stage: "rejected",
      subStatus: null,
      tags: null,
      appliedAt: "2026-06-01T00:00:00Z",
    });

    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({
      data: {
        stages: {
          rejected: {
            items: Array.from({ length: 20 }, (_, i) => makeCard(i + 1)),
            total: 25,
            has_more: true,
          },
        },
      },
    });
    api.getJobBoardStagePage.mockRejectedValue(new Error("page boom"));

    const { router } = renderPage("?jobId=1&focus=21");

    await waitFor(() =>
      expect(api.getJobBoardStagePage).toHaveBeenCalledTimes(1),
    );
    await waitFor(() => expect(router.state.location.search).toBe("?jobId=1"));
    // Give it a chance to have retried before asserting it didn't.
    expect(api.getJobBoardStagePage).toHaveBeenCalledTimes(1);
    // A background hunt failing is not something the owner asked for, so it
    // must not toast — contrast the "Load more" click cases, which do.
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("gives up quietly after the paging cap when the focused card never turns up", async () => {
    const makeCard = (id) => ({
      id,
      applicantName: `Rejected Person ${id}`,
      applicantEmail: `rejected${id}@example.com`,
      stage: "rejected",
      subStatus: null,
      tags: null,
      appliedAt: "2026-06-01T00:00:00Z",
    });

    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({
      data: {
        stages: {
          rejected: {
            items: Array.from({ length: 20 }, (_, i) => makeCard(i + 1)),
            total: 500,
            has_more: true,
          },
        },
      },
    });
    // Always another page, never the id we're looking for.
    api.getJobBoardStagePage.mockImplementation((_jobId, { offset }) =>
      Promise.resolve({
        data: {
          items: Array.from({ length: 20 }, (_, i) => makeCard(offset + i + 1)),
          total: 500,
          has_more: true,
        },
      }),
    );

    const { router } = renderPage("?jobId=1&focus=99999");

    // Bounded: 5 rounds of paging, then it stops rather than walking a lane
    // of unknown length.
    await waitFor(() =>
      expect(api.getJobBoardStagePage).toHaveBeenCalledTimes(5),
    );
    await waitFor(() => expect(router.state.location.search).toBe("?jobId=1"));
    expect(api.getJobBoardStagePage).toHaveBeenCalledTimes(5);
    // Giving up is silent — the job is selected, which was the main win.
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("drops the highlight after its window closes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({
      data: {
        stages: {
          rejected: {
            items: [
              {
                id: 777,
                applicantName: "Just Rejected",
                applicantEmail: "jr@example.com",
                stage: "rejected",
                subStatus: null,
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

    renderPage("?jobId=1&focus=777");

    const card = await screen.findByRole("button", { name: /Just Rejected/ });
    await waitFor(() => expect(card.className).toContain("ring-2"));

    // Wrapped in act: the highlight is dropped by a setTimeout, so advancing
    // the clock is what triggers the state update. Without act React logs
    // "An update to BoardPage inside a test was not wrapped in act(...)".
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3100);
    });

    await waitFor(() => expect(card.className).not.toContain("ring-2"));
  });

  it("renders the applicant search once the jobs have loaded", async () => {
    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({ data: {} });
    renderPage();

    expect(
      await screen.findByPlaceholderText("Search by name or email"),
    ).toBeInTheDocument();
  });

  it("scopes the focus hunt to the lanes, not a search result row sharing the same data-application-id", async () => {
    // ApplicantSearch's rows carry the same `data-application-id` attribute
    // as cards, and sit earlier in the DOM. A document-wide lookup would
    // match this row instead of the real card. The board fetch is held open
    // so the search row can be placed on screen (the search box is mounted
    // as soon as jobs load, independent of the board) before the focus-hunt
    // effect ever runs against a resolved board.
    const scrolled = [];
    scrollIntoViewSpy = vi
      .spyOn(Element.prototype, "scrollIntoView")
      .mockImplementation(function captureTarget() {
        scrolled.push(this);
      });

    const user = userEvent.setup();
    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    let resolveBoard;
    api.getJobBoard.mockReturnValue(
      new Promise((resolve) => {
        resolveBoard = resolve;
      }),
    );
    api.searchBoardApplicants.mockResolvedValue({
      data: {
        hits: [
          {
            applicationId: 777,
            applicantName: "Just Rejected",
            applicantEmail: "jr@example.com",
            jobId: 1,
            jobTitle: "Backend Engineer",
            jobKind: "employment",
            stage: "rejected",
            appliedAt: "2026-06-01T00:00:00Z",
          },
        ],
        truncated: false,
      },
    });

    renderPage("?jobId=1&focus=777");

    // Put a search result row bearing the same data-application-id on
    // screen while the board (and therefore the focus hunt) is still
    // pending.
    await user.type(
      await screen.findByPlaceholderText("Search by name or email"),
      "just",
    );
    await user.click(screen.getByRole("button", { name: "Search" }));
    const searchRow = await screen.findByRole("option");
    expect(searchRow).toHaveAttribute("data-application-id", "777");

    // Now let the board (and the real card) land, with the search row
    // already in the DOM ahead of it.
    resolveBoard({
      data: {
        stages: {
          rejected: {
            items: [
              {
                id: 777,
                applicantName: "Just Rejected",
                applicantEmail: "jr@example.com",
                stage: "rejected",
                subStatus: null,
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

    const card = await screen.findByRole("button", { name: /Just Rejected/ });

    await waitFor(() => expect(scrolled).toHaveLength(1));
    // The real card, not the earlier-in-the-DOM search row, is what got
    // scrolled and rung.
    expect(scrolled[0]).toBe(card);
    expect(scrolled[0]).not.toBe(searchRow);
    await waitFor(() => expect(card.className).toContain("ring-2"));
    expect(searchRow.className).not.toContain("ring-2");
  });

  it("navigates to the detail page when a search hit is chosen", async () => {
    const user = userEvent.setup();
    api.listBoardJobs.mockResolvedValue({ data: [jobA] });
    api.getJobBoard.mockResolvedValue({ data: {} });
    api.searchBoardApplicants.mockResolvedValue({
      data: {
        hits: [
          {
            applicationId: 77,
            applicantName: "Zhang Wei",
            applicantEmail: "zw@example.com",
            jobId: 1,
            jobTitle: "Backend Engineer",
            jobKind: "employment",
            stage: "tech",
            appliedAt: "2026-01-01T00:00:00Z",
          },
        ],
        truncated: false,
      },
    });
    const { router } = renderPage();

    await user.type(
      await screen.findByPlaceholderText("Search by name or email"),
      "zhang",
    );
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.click(await screen.findByRole("option"));

    await waitFor(() => {
      expect(router.state.location.pathname).toBe(
        "/recruiting/applications/77",
      );
    });
  });
});
