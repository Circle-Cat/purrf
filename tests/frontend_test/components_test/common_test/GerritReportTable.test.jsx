import {
  render,
  screen,
  waitFor,
  fireEvent,
  within,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/components/common/GerritReportTable.css", () => ({}));

vi.mock("@/api/dataSearchApi", () => ({
  getGerritStats: vi.fn(),
}));

vi.mock("@/components/common/Table", () => ({
  __esModule: true,
  default: ({ columns, data, onSort }) => (
    <table aria-label="gerrit-table">
      <thead>
        <tr>
          {columns.map((c) => (
            <th key={c.accessor}>
              <button type="button" onClick={() => onSort(c.accessor)}>
                {c.header}
              </button>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((row, idx) => (
          <tr key={idx}>
            {columns.map((c) => (
              <td key={c.accessor} data-col={c.accessor}>
                {row[c.accessor]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  ),
}));

import { getGerritStats } from "@/api/dataSearchApi";
import GerritReportTable from "@/components/common/GerritReportTable";

describe("GerritReportTable", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows 'No data.' and does not call API when inputs are not ready", async () => {
    render(
      <GerritReportTable
        gerritReportProps={{
          searchParams: {
            ldaps: [],
            startDate: "",
            endDate: "",
            project: "",
            includeAllProjects: "",
          },
        }}
      />,
    );

    expect(await screen.findByText(/No data\./i)).toBeInTheDocument();
    expect(getGerritStats).not.toHaveBeenCalled();
  });

  it("calls API when ready and renders rows (dict payload in resp.data)", async () => {
    getGerritStats.mockResolvedValueOnce({
      data: {
        alice: {
          cl_merged: 12,
          cl_under_review: 3,
          loc_merged: 1234,
          cl_abandoned: 1,
          cl_reviewed: 8,
        },
        bob: {
          cl_merged: 4,
          cl_under_review: 7,
          loc_merged: 56789,
          cl_abandoned: 0,
          cl_reviewed: 2,
        },
      },
    });

    render(
      <GerritReportTable
        gerritReportProps={{
          searchParams: {
            ldaps: ["alice", "bob"],
            startDate: "2025-09-01",
            endDate: "2025-09-21",
            project: [""],
            includeAllProjects: true,
          },
        }}
      />,
    );

    expect(screen.getByText(/Loading Gerrit stats/i)).toBeInTheDocument();

    const table = await screen.findByRole("table", { name: /gerrit-table/i });
    expect(table).toBeInTheDocument();

    expect(getGerritStats).toHaveBeenCalledTimes(1);
    expect(getGerritStats).toHaveBeenCalledWith({
      ldaps: ["alice", "bob"],
      startDate: "2025-09-01",
      endDate: "2025-09-21",
      project: [""],
      includeAllProjects: true,
    });

    // Spot-check formatted number appears (locale-safe matcher)
    expect(
      screen.getAllByText(/1,?234/).length > 0 ||
        screen.getAllByText("1234").length > 0,
    ).toBe(true);
  });

  it("accepts { data: { alice: {...}, bob: {...} } } and renders rows", async () => {
    getGerritStats.mockResolvedValueOnce({
      data: {
        alice: {
          cl_merged: 1,
          cl_under_review: 0,
          loc_merged: 10,
          cl_abandoned: 0,
          cl_reviewed: 2,
        },
        bob: {
          cl_merged: 5,
          cl_under_review: 1,
          loc_merged: 2000,
          cl_abandoned: 0,
          cl_reviewed: 3,
        },
      },
    });

    render(
      <GerritReportTable
        gerritReportProps={{
          searchParams: {
            ldaps: ["alice", "bob"],
            startDate: "2025-09-01",
            endDate: "2025-09-21",
            project: ["purrf/backend"],
            includeAllProjects: true,
          },
        }}
      />,
    );

    const table = await screen.findByRole("table", { name: /gerrit-table/i });
    const rows = within(table).getAllByRole("row").slice(1);

    const row1 = within(rows[0]).getAllByRole("cell");
    const row2 = within(rows[1]).getAllByRole("cell");

    expect(row1[0]).toHaveTextContent(/(alice|bob)/i);
    expect(row2[0]).toHaveTextContent(/(alice|bob)/i);

    // Spot-check formatted numbers exist
    expect(
      screen.getAllByText(/2,?000/).length > 0 ||
        screen.getAllByText("2000").length > 0,
    ).toBe(true);
  });

  it("surfaces backend error message", async () => {
    getGerritStats.mockRejectedValueOnce({
      response: { data: { message: "Backend exploded" } },
    });

    render(
      <GerritReportTable
        gerritReportProps={{
          searchParams: {
            ldaps: ["alice"],
            startDate: "2025-09-01",
            endDate: "2025-09-21",
            project: [""],
            includeAllProjects: true,
          },
        }}
      />,
    );

    const err = await screen.findByText(/Backend exploded/i);
    expect(err).toBeInTheDocument();
  });

  it("sorts when header buttons are clicked (ascending then descending)", async () => {
    getGerritStats.mockResolvedValueOnce({
      data: {
        charlie: {
          cl_merged: 7,
          cl_under_review: 0,
          loc_merged: 99,
          cl_abandoned: 0,
          cl_reviewed: 1,
        },
        alice: {
          cl_merged: 12,
          cl_under_review: 0,
          loc_merged: 100,
          cl_abandoned: 0,
          cl_reviewed: 1,
        },
        bob: {
          cl_merged: 4,
          cl_under_review: 0,
          loc_merged: 101,
          cl_abandoned: 0,
          cl_reviewed: 1,
        },
      },
    });

    render(
      <GerritReportTable
        gerritReportProps={{
          searchParams: {
            ldaps: ["alice", "bob", "charlie"],
            startDate: "2025-09-01",
            endDate: "2025-09-21",
            project: [""],
            includeAllProjects: true,
          },
        }}
      />,
    );

    const table = await screen.findByRole("table", { name: /gerrit-table/i });

    // ASC by CL MERGED
    const clMergedHeaderBtn = screen.getByRole("button", {
      name: /CL MERGED/i,
    });
    fireEvent.click(clMergedHeaderBtn);

    await waitFor(() => {
      const bodyRows = within(table).getAllByRole("row").slice(1);
      const firstRow = within(bodyRows[0]).getAllByRole("cell");
      expect(firstRow[0]).toHaveTextContent("bob"); // 4 is smallest
    });

    // DESC by CL MERGED
    fireEvent.click(clMergedHeaderBtn);

    await waitFor(() => {
      const bodyRows = within(table).getAllByRole("row").slice(1);
      const firstRow = within(bodyRows[0]).getAllByRole("cell");
      expect(firstRow[0]).toHaveTextContent("alice"); // 12 is largest
    });
  });

  it("handles 'No data.' state when fetch returns empty", async () => {
    getGerritStats.mockResolvedValueOnce({ data: {} });

    render(
      <GerritReportTable
        gerritReportProps={{
          searchParams: {
            ldaps: ["nobody"],
            startDate: "2025-09-01",
            endDate: "2025-09-21",
            project: [""],
            includeAllProjects: true,
          },
        }}
      />,
    );

    const noData = await screen.findByText(/No data\./i);
    expect(noData).toBeInTheDocument();
  });
});
