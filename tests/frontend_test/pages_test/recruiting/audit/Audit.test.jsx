import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Audit from "@/pages/Recruiting/audit/Audit";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");

const OVERVIEW = {
  openPositionsCount: 2,
  jobs: [
    {
      id: 1,
      title: "Backend Engineer",
      status: "published",
      kind: "employment",
    },
    {
      id: 2,
      title: "Frontend Engineer",
      status: "published",
      kind: "employment",
    },
    { id: 3, title: "Old Posting", status: "closed", kind: "employment" },
    { id: 4, title: "Mentor", status: "published", kind: "activity" },
  ],
  stageBreakdown: [
    {
      jobId: 1,
      jobTitle: "Backend Engineer",
      stage: "recruiter_screening",
      count: 3,
    },
    { jobId: 1, jobTitle: "Backend Engineer", stage: "hired", count: 1 },
    { jobId: 2, jobTitle: "Frontend Engineer", stage: "tech", count: 2 },
    { jobId: 4, jobTitle: "Mentor", stage: "hired", count: 5 },
  ],
  dailyTrend: [
    { jobId: 1, jobTitle: "Backend Engineer", date: "2026-06-01", count: 2 },
    { jobId: 1, jobTitle: "Backend Engineer", date: "2026-06-02", count: 1 },
  ],
};

describe("Audit", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getAuditOverview.mockResolvedValue({ data: OVERVIEW });
  });

  it("shows the open-positions KPI independent of filters", async () => {
    render(<Audit />);
    await waitFor(() =>
      expect(screen.getByText(/Open positions: 2/)).toBeInTheDocument(),
    );
  });

  it("fetches on load with a default 30-day range", async () => {
    render(<Audit />);
    await waitFor(() => expect(api.getAuditOverview).toHaveBeenCalled());
    const call = api.getAuditOverview.mock.calls[0][0];
    expect(call.startDate).toEqual(expect.any(String));
    expect(call.endDate).toEqual(expect.any(String));
    // The first call is an unfiltered discovery fetch (job statuses are
    // only known once its response arrives); the published-only default
    // selection is derived client-side from that response and is verified
    // via checkbox state in the "lists every job..." test below.
    expect(call.jobIds).toEqual([]);
  });

  it("lists every job in the selector regardless of status, checked state matching defaults", async () => {
    render(<Audit />);
    await waitFor(() => expect(api.getAuditOverview).toHaveBeenCalled());
    expect(
      screen.getByRole("checkbox", { name: "Backend Engineer" }),
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Frontend Engineer" }),
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: "Old Posting" }),
    ).not.toBeChecked();
  });

  it("re-fetches with the updated job selection when a checkbox is toggled", async () => {
    const user = userEvent.setup();
    render(<Audit />);
    await waitFor(() => expect(api.getAuditOverview).toHaveBeenCalledTimes(1));

    await user.click(screen.getByRole("checkbox", { name: "Old Posting" }));

    await waitFor(() => expect(api.getAuditOverview).toHaveBeenCalledTimes(2));
    const lastCall =
      api.getAuditOverview.mock.calls[
        api.getAuditOverview.mock.calls.length - 1
      ][0];
    expect(lastCall.jobIds.sort()).toEqual([1, 2, 3, 4]);
  });

  it("renders separate employment and activity job x stage tables with exact counts", async () => {
    render(<Audit />);
    // Waiting only for the API call to have fired (as the sibling tests do)
    // races the mocked response's resolution -- the tables themselves don't
    // exist until the response lands and the component re-renders out of
    // its loading state. findAllByRole polls until they actually appear.
    const [employmentTable, activityTable] =
      await screen.findAllByRole("table");

    expect(
      within(employmentTable).getByText("Backend Engineer"),
    ).toBeInTheDocument();
    expect(
      within(employmentTable).getByText("Recruiter screening"),
    ).toBeInTheDocument();
    expect(within(employmentTable).getByText("3")).toBeInTheDocument();
    expect(within(employmentTable).getByText("Hired")).toBeInTheDocument();
    expect(within(employmentTable).getByText("1")).toBeInTheDocument();
    expect(
      within(employmentTable).queryByText("Mentor"),
    ).not.toBeInTheDocument();

    // The activity section presents `hired` as "Admitted" and never lists
    // employment postings.
    expect(within(activityTable).getByText("Mentor")).toBeInTheDocument();
    expect(within(activityTable).getByText("Admitted")).toBeInTheDocument();
    expect(within(activityTable).getByText("5")).toBeInTheDocument();
    expect(within(activityTable).queryByText("Hired")).not.toBeInTheDocument();
    expect(
      within(activityTable).queryByText("Backend Engineer"),
    ).not.toBeInTheDocument();
  });

  it("renders one stage breakdown chart per posting kind", async () => {
    render(<Audit />);
    // Waiting only for the API call to have fired (as some sibling tests do)
    // races the mocked response's resolution -- the charts themselves don't
    // exist until the response lands and the component re-renders out of
    // its loading state (same class of race already fixed for the table
    // assertion above). findByRole polls until each chart actually appears.
    //
    // Recharts renders SVG <rect> elements per bar segment inside the
    // chart's data-slot="chart" container — assert the containers render
    // rather than asserting on SVG internals, which is brittle.
    expect(
      await screen.findByRole("img", {
        name: /stage breakdown chart — employment/i,
      }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole("img", {
        name: /stage breakdown chart — activity/i,
      }),
    ).toBeInTheDocument();
  });
});
