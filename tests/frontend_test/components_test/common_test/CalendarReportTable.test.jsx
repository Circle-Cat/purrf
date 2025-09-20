import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { CalendarReportTable } from "@/components/common/CalendarReportTable";
import { getGoogleCalendarEvents } from "@/api/dataSearchApi";

vi.mock("@/api/dataSearchApi", () => ({
  getGoogleCalendarEvents: vi.fn(),
}));

vi.mock("@/components/common/Table", () => ({
  default: vi.fn((props) => (
    <div data-testid="mock-table">
      <div data-testid="table-columns">
        {JSON.stringify(props.columns.map((col) => col.header))}
      </div>
      <div data-testid="table-data">
        {JSON.stringify(props.data.map((row) => row.ldap))}
      </div>
      {props.columns.map(
        (col) =>
          col.sortable && (
            <button
              key={col.accessor}
              data-testid={`sort-button-${col.accessor}`}
              onClick={() => props.onSort(col.accessor)}
            >
              Sort by {col.header}
            </button>
          ),
      )}
      <div data-testid="sort-config">{`${props.sortColumn}-${props.sortDirection}`}</div>
    </div>
  )),
}));

let toLocaleDateStringSpy;
let toLocaleTimeStringSpy;

const mockDatePrototypes = (dateMap, timeMap) => {
  toLocaleDateStringSpy = vi
    .spyOn(Date.prototype, "toLocaleDateString")
    // eslint-disable-next-line no-unused-vars
    .mockImplementation(function (_locale, _options) {
      const dateKey = this.toISOString().split("T")[0];
      return dateMap[dateKey] || new Date(this).toISOString().split("T")[0];
    });

  toLocaleTimeStringSpy = vi
    .spyOn(Date.prototype, "toLocaleTimeString")
    // eslint-disable-next-line no-unused-vars
    .mockImplementation(function (_locale, _options) {
      const timeKey = this.toISOString().substring(0, 16);
      return timeMap[timeKey] || new Date(this).toISOString().substring(11, 16);
    });
};

const restoreDatePrototypes = () => {
  toLocaleDateStringSpy?.mockRestore();
  toLocaleTimeStringSpy?.mockRestore();
};

describe("CalendarReportTable", () => {
  const defaultProps = {
    googleCalendarReportProps: {
      searchParams: {
        startDate: "2025-09-01",
        endDate: "2025-09-30",
        calendarIds: ["id1"],
        ldaps: ["ldapA", "ldapB"],
      },
    },
  };

  const mockCalendarEventsData = {
    ldapB: [
      {
        calendar_name: "Calendar X",
        summary: "Event B",
        event_id: "eB",
        attendance: [
          {
            join_time: "2025-09-22T09:00:00Z",
            leave_time: "2025-09-22T10:00:00Z",
          },
        ],
      },
    ],
    ldapA: [
      {
        calendar_name: "Calendar Y",
        summary: "Event C",
        event_id: "eC",
        attendance: [
          {
            join_time: "2025-09-23T11:00:00Z",
            leave_time: "2025-09-23T12:00:00Z",
          },
        ],
      },
      {
        calendar_name: "Calendar Z",
        summary: "Event A",
        event_id: "eA",
        attendance: [
          {
            join_time: "2025-09-20T14:00:00Z",
            leave_time: "2025-09-20T15:00:00Z",
          },
        ],
      },
    ],
  };

  const expectedFlattenedAndUnsorted = [
    {
      ldap: "ldapB",
      calendarName: "Calendar X",
      summary: "Event B",
      date: "09/22/2025",
      joinTime: "09:00 AM",
      leaveTime: "10:00 AM",
      key: "ldapB-eB-0",
    },
    {
      ldap: "ldapA",
      calendarName: "Calendar Y",
      summary: "Event C",
      date: "09/23/2025",
      joinTime: "11:00 AM",
      leaveTime: "12:00 PM",
      key: "ldapA-eC-0",
    },
    {
      ldap: "ldapA",
      calendarName: "Calendar Z",
      summary: "Event A",
      date: "09/20/2025",
      joinTime: "02:00 PM",
      leaveTime: "03:00 PM",
      key: "ldapA-eA-0",
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    mockDatePrototypes(
      {
        "2025-09-20": "09/20/2025",
        "2025-09-22": "09/22/2025",
        "2025-09-23": "09/23/2025",
      },
      {
        "2025-09-20T14:00": "02:00 PM",
        "2025-09-20T15:00": "03:00 PM",
        "2025-09-22T09:00": "09:00 AM",
        "2025-09-22T10:00": "10:00 AM",
        "2025-09-23T11:00": "11:00 AM",
        "2025-09-23T12:00": "12:00 PM",
      },
    );
  });

  afterEach(() => {
    restoreDatePrototypes();
  });

  it("should display loading state initially", () => {
    getGoogleCalendarEvents.mockReturnValue(new Promise(() => {}));
    render(<CalendarReportTable {...defaultProps} />);
    expect(screen.getByText("Loading schedule data...")).toBeInTheDocument();
  });

  it("should display an error message if data fetching fails", async () => {
    const consoleErrorSpy = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    getGoogleCalendarEvents.mockRejectedValue(new Error("API error"));

    render(<CalendarReportTable {...defaultProps} />);

    await waitFor(() => {
      expect(
        screen.getByText(
          "Failed to fetch data. Please check the provided parameters.",
        ),
      ).toBeInTheDocument();
    });
    expect(consoleErrorSpy).toHaveBeenCalledWith(expect.any(Error));

    consoleErrorSpy.mockRestore();
  });

  it('should display "No events found" if no data is returned or flattened', async () => {
    getGoogleCalendarEvents.mockResolvedValue({ data: {} });
    render(<CalendarReportTable {...defaultProps} />);
    await waitFor(() => {
      expect(
        screen.getByText("No events found for the given parameters."),
      ).toBeInTheDocument();
    });
  });

  it("should render the Table component with flattened data on successful fetch", async () => {
    getGoogleCalendarEvents.mockResolvedValue({ data: mockCalendarEventsData });
    render(<CalendarReportTable {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("mock-table")).toBeInTheDocument();
    });

    const expectedHeaders = [
      "LDAP",
      "CALENDAR",
      "EVENTS",
      "DATE",
      "START TIME",
      "END TIME",
    ];
    expect(screen.getByTestId("table-columns")).toHaveTextContent(
      JSON.stringify(expectedHeaders),
    );
    expect(screen.getByTestId("table-data")).toHaveTextContent(
      JSON.stringify(expectedFlattenedAndUnsorted.map((row) => row.ldap)),
    );
    expect(screen.getByTestId("sort-config")).toHaveTextContent("null-asc");
  });

  it("should sort data by LDAP in ascending and descending order", async () => {
    getGoogleCalendarEvents.mockResolvedValue({ data: mockCalendarEventsData });
    render(<CalendarReportTable {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("mock-table")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    const sortByLdapButton = screen.getByTestId("sort-button-ldap");

    expect(screen.getByTestId("table-data")).toHaveTextContent(
      JSON.stringify(["ldapB", "ldapA", "ldapA"]),
    );

    await user.click(sortByLdapButton);

    expect(screen.getByTestId("sort-config")).toHaveTextContent("ldap-asc");
    expect(screen.getByTestId("table-data")).toHaveTextContent(
      JSON.stringify(["ldapA", "ldapA", "ldapB"]),
    );

    await user.click(sortByLdapButton);
    expect(screen.getByTestId("sort-config")).toHaveTextContent("ldap-desc");
    expect(screen.getByTestId("table-data")).toHaveTextContent(
      JSON.stringify(["ldapB", "ldapA", "ldapA"]),
    );
  });

  it("should sort data by DATE in ascending and descending order", async () => {
    getGoogleCalendarEvents.mockResolvedValue({ data: mockCalendarEventsData });
    render(<CalendarReportTable {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByTestId("mock-table")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    const sortByDateButton = screen.getByTestId("sort-button-date");

    expect(screen.getByTestId("table-data")).toHaveTextContent(
      JSON.stringify(["ldapB", "ldapA", "ldapA"]),
    );

    await user.click(sortByDateButton);
    expect(screen.getByTestId("sort-config")).toHaveTextContent("date-asc");
    expect(screen.getByTestId("table-data")).toHaveTextContent(
      JSON.stringify(["ldapA", "ldapB", "ldapA"]),
    );

    await user.click(sortByDateButton);
    expect(screen.getByTestId("sort-config")).toHaveTextContent("date-desc");
    expect(screen.getByTestId("table-data")).toHaveTextContent(
      JSON.stringify(["ldapA", "ldapB", "ldapA"]),
    );
  });
});
