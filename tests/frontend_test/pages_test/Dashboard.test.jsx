import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useState } from "react";
import "@testing-library/jest-dom/vitest";

import Dashboard from "@/pages/Dashboard";
import DateRangePicker from "@/components/common/DateRangePicker";

import { Group } from "@/constants/Groups";
import { LdapStatus } from "@/constants/LdapStatus";
import { getSummary, getLdapsAndDisplayNames } from "@/api/dashboardApi";
import { getCookie, extractCloudflareUserName } from "@/utils/auth";

vi.mock("@/components/common/DateRangePicker", () => {
  return {
    default: vi.fn(({ onChange, defaultStartDate, defaultEndDate }) => {
      const [startDate, setStartDate] = useState(defaultStartDate);
      const [endDate, setEndDate] = useState(defaultEndDate);

      const handleDateChange = (newDate) => {
        const updatedStartDate = newDate.startDate ?? startDate;
        const updatedEndDate = newDate.endDate ?? endDate;

        setStartDate(updatedStartDate);
        setEndDate(updatedEndDate);

        onChange({ startDate: updatedStartDate, endDate: updatedEndDate });
      };

      return (
        <div data-testid="mock-date-range-picker">
          <input
            data-testid="start-date-input"
            defaultValue={startDate}
            onChange={(e) => handleDateChange({ startDate: e.target.value })}
          />
          <input
            data-testid="end-date-input"
            defaultValue={endDate}
            onChange={(e) => handleDateChange({ endDate: e.target.value })}
          />
        </div>
      );
    }),
  };
});

vi.mock("@/components/common/Card", () => ({
  default: ({ title, value }) => (
    <div data-testid={`card-${title.replace(/\s/g, "-")}`}>
      <h3>{title}</h3>
      <p>{value}</p>
    </div>
  ),
}));

vi.mock("@/components/common/Table", () => ({
  default: ({ columns, data, onSort, sortColumn, sortDirection }) => (
    <table data-testid="mock-table">
      <thead>
        <tr>
          {columns.map((col) => (
            <th
              key={col.accessor}
              data-testid={`table-header-${col.accessor}`}
              onClick={() => onSort(col.accessor)}
            >
              {col.header}
              {sortColumn === col.accessor && (
                <span>{sortDirection === "asc" ? " ▲" : " ▼"}</span>
              )}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.map((item, index) => (
          <tr key={index}>
            {columns.map((col) => (
              <td key={col.accessor}>{item[col.accessor]}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  ),
}));

vi.mock("@/api/dashboardApi", () => ({
  getSummary: vi.fn(),
  getLdapsAndDisplayNames: vi.fn(),
}));

vi.mock("@/utils/auth", () => ({
  getCookie: vi.fn(),
  extractCloudflareUserName: vi.fn(),
}));

const MOCK_TODAY = new Date("2024-02-15");
const MOCK_FIRST_OF_MONTH = new Date("2024-02-01");
const formatDate = (date) => date.toISOString().split("T")[0];

const mockSummaryData = [
  {
    ldap: "test.user1",
    jira_issue_done: 5,
    cl_merged: 10,
    loc_merged: 100,
    meeting_hours: 50,
    chat_count: 200,
  },
  {
    ldap: "test.user2",
    jira_issue_done: 2,
    cl_merged: 20,
    loc_merged: 200,
    meeting_hours: 20,
    chat_count: 150,
  },
  {
    ldap: "test.user3",
    jira_issue_done: 8,
    cl_merged: 5,
    loc_merged: 50,
    meeting_hours: 10,
    chat_count: 50,
  },
];

const mockLdapsData = {
  [Group.Interns]: {
    [LdapStatus.Active]: {
      "test.user1": "Test User1",
    },
  },
  [Group.Employees]: {
    [LdapStatus.Active]: {
      "test.user2": "Test User2",
    },
    [LdapStatus.Terminated]: {
      "test.user3": "Test User3",
    },
  },
};

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    const date = new Date(MOCK_TODAY);
    vi.setSystemTime(date);
    // Reset mocks for auth functions before each test
    getCookie.mockClear();
    extractCloudflareUserName.mockClear();
    getSummary.mockResolvedValue({ data: [] }); // Default mock to prevent unwanted errors
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
    afterEach(cleanup);
  });

  it("fetches and displays summary and table data correctly on search", async () => {
    getSummary.mockResolvedValue({ data: mockSummaryData });
    getLdapsAndDisplayNames.mockResolvedValue({ data: mockLdapsData });

    render(<Dashboard />);

    await vi.waitFor(() => {
      expect(getSummary).toHaveBeenCalled();
      expect(getLdapsAndDisplayNames).toHaveBeenCalled();
    });

    await vi.waitFor(() => {
      expect(screen.getByText("3")).toBeInTheDocument(); // totalMembers from mockLdapsData
      expect(screen.getByText("15")).toBeInTheDocument(); // 5+2+8
      expect(screen.getByText("35")).toBeInTheDocument(); // 10+20+5
      expect(screen.getByText("350")).toBeInTheDocument(); // 100+200+50
      expect(screen.getByText("80")).toBeInTheDocument(); // 50+20+10
      expect(screen.getByText("400")).toBeInTheDocument(); // 200+150+50
    });

    await vi.waitFor(() => {
      expect(screen.getByText("test.user1")).toBeInTheDocument();
      expect(screen.getByText("test.user2")).toBeInTheDocument();
      expect(screen.getByText("test.user3")).toBeInTheDocument();
    });
  });

  it("handles empty API results gracefully", async () => {
    getSummary.mockResolvedValue({ data: [] });
    getLdapsAndDisplayNames.mockResolvedValue({ data: {} });

    render(<Dashboard />);

    await vi.waitFor(() => {
      expect(getSummary).toHaveBeenCalled();
      expect(getLdapsAndDisplayNames).toHaveBeenCalled();
    });

    await vi.waitFor(() => {
      expect(screen.getByTestId("card-Members")).toHaveTextContent("0");
      expect(screen.getByTestId("card-Jira-Tickets-(Done)")).toHaveTextContent(
        "0",
      );
      expect(screen.getByTestId("card-Merged-CLs")).toHaveTextContent("0");
      expect(screen.getByTestId("card-Merged-LOC")).toHaveTextContent("0");
      expect(screen.getByTestId("card-Meeting-Hours")).toHaveTextContent("0");
      expect(screen.getByTestId("card-Chat-Messages-Sent")).toHaveTextContent(
        "0",
      );
    });

    const tableBody = screen.getByTestId("mock-table").querySelector("tbody");
    expect(tableBody).toBeEmptyDOMElement();
  });

  it("handles API fetch error", async () => {
    const consoleErrorSpy = vi.spyOn(console, "log");
    getSummary.mockRejectedValue(new Error("API Error"));

    render(<Dashboard />);

    await vi.waitFor(() => {
      expect(getSummary).toHaveBeenCalled();
      expect(getLdapsAndDisplayNames).toHaveBeenCalled();
    });

    await vi.waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalledWith(expect.any(Error));
    });

    expect(screen.getByText("Members").nextSibling).toHaveTextContent("0");
  });

  it("sorts table data correctly by numeric column (jiraTicketsDone) in ascending and descending order", async () => {
    getSummary.mockResolvedValue({ data: mockSummaryData });
    getLdapsAndDisplayNames.mockResolvedValue({ data: mockLdapsData });

    render(<Dashboard />);

    await vi.waitFor(() => {
      expect(screen.getByText("test.user1")).toBeInTheDocument();
    });

    const jiraHeader = screen.getByTestId("table-header-jiraTicketsDone");

    let tableRows = screen
      .getByTestId("mock-table")
      .querySelectorAll("tbody tr td:first-child");
    expect(tableRows[0]).toHaveTextContent("test.user1");
    expect(tableRows[1]).toHaveTextContent("test.user2");
    expect(tableRows[2]).toHaveTextContent("test.user3");

    fireEvent.click(jiraHeader);
    tableRows = screen
      .getByTestId("mock-table")
      .querySelectorAll("tbody tr td:first-child");
    expect(tableRows[0]).toHaveTextContent("test.user2"); // 2 tickets
    expect(tableRows[1]).toHaveTextContent("test.user1"); // 5 tickets
    expect(tableRows[2]).toHaveTextContent("test.user3"); // 8 tickets

    fireEvent.click(jiraHeader);
    tableRows = screen
      .getByTestId("mock-table")
      .querySelectorAll("tbody tr td:first-child");
    expect(tableRows[0]).toHaveTextContent("test.user3"); // 8 tickets
    expect(tableRows[1]).toHaveTextContent("test.user1"); // 5 tickets
    expect(tableRows[2]).toHaveTextContent("test.user2"); // 2 tickets
  });

  it("sorts table data correctly by string column (ldap) in ascending and descending order", async () => {
    getSummary.mockResolvedValue({ data: mockSummaryData });
    getLdapsAndDisplayNames.mockResolvedValue({ data: mockLdapsData });

    render(<Dashboard />);
    await vi.waitFor(() => {
      expect(screen.getByText("test.user1")).toBeInTheDocument();
    });

    const ldapHeader = screen.getByTestId("table-header-ldap");

    // Click to sort ascending
    fireEvent.click(ldapHeader);
    const tableRowsAsc = screen
      .getByTestId("mock-table")
      .querySelectorAll("tbody tr td:first-child");
    expect(tableRowsAsc[0]).toHaveTextContent("test.user1");
    expect(tableRowsAsc[1]).toHaveTextContent("test.user2");
    expect(tableRowsAsc[2]).toHaveTextContent("test.user3");

    // Click again to sort descending
    fireEvent.click(ldapHeader);
    const tableRowsDesc = screen
      .getByTestId("mock-table")
      .querySelectorAll("tbody tr td:first-child");
    expect(tableRowsDesc[0]).toHaveTextContent("test.user3");
    expect(tableRowsDesc[1]).toHaveTextContent("test.user2");
    expect(tableRowsDesc[2]).toHaveTextContent("test.user1");
  });

  it("renders with correct initial state and default values", () => {
    getSummary.mockResolvedValue({ data: mockSummaryData });
    getLdapsAndDisplayNames.mockResolvedValue({ data: mockLdapsData });

    render(<Dashboard />);

    expect(screen.getByText("Welcome")).toBeInTheDocument();

    expect(DateRangePicker).toHaveBeenCalledWith(
      expect.objectContaining({
        defaultStartDate: formatDate(MOCK_FIRST_OF_MONTH),
        defaultEndDate: formatDate(MOCK_TODAY),
        onChange: expect.any(Function),
      }),
      undefined,
    );

    expect(screen.getByLabelText(Group.Interns)).toBeChecked();
    expect(screen.getByLabelText(Group.Employees)).toBeChecked();
    expect(screen.getByLabelText(Group.Volunteers)).not.toBeChecked();
    expect(
      screen.getByLabelText("Include Terminated Members"),
    ).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
  });

  it("updates group selection when checkboxes are clicked", () => {
    render(<Dashboard />);

    const internsCheckbox = screen.getByLabelText(Group.Interns);
    const employeesCheckbox = screen.getByLabelText(Group.Employees);
    const volunteersCheckbox = screen.getByLabelText(Group.Volunteers);

    fireEvent.click(internsCheckbox);
    fireEvent.click(employeesCheckbox);
    fireEvent.click(volunteersCheckbox);

    expect(internsCheckbox).not.toBeChecked();
    expect(employeesCheckbox).not.toBeChecked();
    expect(volunteersCheckbox).toBeChecked();
  });

  it("toggles 'Include Terminated Members' checkbox on click", () => {
    render(<Dashboard />);
    const terminatedCheckbox = screen.getByLabelText(
      "Include Terminated Members",
    );

    fireEvent.click(terminatedCheckbox);
    expect(terminatedCheckbox).toBeChecked();

    fireEvent.click(terminatedCheckbox);
    expect(terminatedCheckbox).not.toBeChecked();
  });

  it("calls search handler with default filter state when search button is clicked", () => {
    render(<Dashboard />);

    const searchButton = screen.getByRole("button", { name: "Search" });
    fireEvent.click(searchButton);

    expect(getSummary).toHaveBeenCalled();
  });

  it("updates date range via DateRangePicker and calls search with updated dates", () => {
    getSummary.mockResolvedValue({ data: "mocked data" });

    render(<Dashboard />);

    const startDateInput = screen.getByTestId("start-date-input");
    const endDateInput = screen.getByTestId("end-date-input");
    const searchButton = screen.getByRole("button", { name: "Search" });

    const newStartDate = "2023-12-01";
    const newEndDate = "2023-12-31";

    fireEvent.change(startDateInput, { target: { value: newStartDate } });
    fireEvent.change(endDateInput, { target: { value: newEndDate } });
    fireEvent.click(searchButton);

    expect(getSummary).toHaveBeenCalledWith({
      startDate: newStartDate,
      endDate: newEndDate,
      groups: [Group.Interns, Group.Employees],
      includeTerminated: false,
    });
  });

  it("calls search handler with updated filter state after user interaction", () => {
    getSummary.mockResolvedValue({ data: "mocked data" });

    render(<Dashboard />);

    fireEvent.click(screen.getByLabelText(Group.Volunteers));
    fireEvent.click(screen.getByLabelText("Include Terminated Members"));

    fireEvent.click(screen.getByRole("button", { name: "Search" }));

    expect(getSummary).toHaveBeenCalledWith({
      startDate: formatDate(MOCK_FIRST_OF_MONTH),
      endDate: formatDate(MOCK_TODAY),
      groups: [Group.Interns, Group.Employees, Group.Volunteers],
      includeTerminated: true,
    });
  });

  it("fetches summary data on initial render with default filters", async () => {
    getSummary.mockResolvedValue({ data: "mocked data" });
    render(<Dashboard />);

    expect(getSummary).toHaveBeenCalledWith(
      expect.objectContaining({
        startDate: formatDate(MOCK_FIRST_OF_MONTH),
        endDate: formatDate(MOCK_TODAY),
        groups: [Group.Interns, Group.Employees],
        includeTerminated: false,
      }),
    );
  });

  it("shows an error when no any groups are selected", async () => {
    render(<Dashboard />);

    const checkboxes = screen.getAllByRole("checkbox");

    checkboxes.forEach((checkbox) => {
      if (checkbox.checked) {
        fireEvent.click(checkbox);
      }
    });

    const searchButton = screen.getByRole("button", { name: /search/i });
    await fireEvent.click(searchButton);

    await vi.waitFor(() => {
      expect(screen.getByText(/Groups are required/i)).toBeInTheDocument();
    });
  });

  it("removes error message when a group is selected", async () => {
    render(<Dashboard />);

    const checkboxes = screen.getAllByRole("checkbox");
    checkboxes.forEach((checkbox) => {
      if (checkbox.checked) {
        fireEvent.click(checkbox);
      }
    });

    const groupCheckbox = screen.getByLabelText(/interns/i);
    await fireEvent.click(groupCheckbox);

    await vi.waitFor(() => {
      expect(
        screen.queryByText(/Groups are required/i),
      ).not.toBeInTheDocument();
    });
  });

  it("allows searching when at least one required group is selected", async () => {
    getSummary.mockResolvedValue({ data: mockSummaryData });
    getLdapsAndDisplayNames.mockResolvedValue({ data: mockLdapsData });

    render(<Dashboard />);

    const checkboxes = screen.getAllByRole("checkbox");

    checkboxes.forEach((checkbox) => {
      if (checkbox.checked) {
        fireEvent.click(checkbox);
      }
    });

    const internsCheckbox = screen.getByLabelText(/interns/i);
    await fireEvent.click(internsCheckbox);

    const searchButton = screen.getByRole("button", { name: /search/i });
    await fireEvent.click(searchButton);

    expect(getSummary).toHaveBeenCalledWith({
      startDate: expect.any(String),
      endDate: expect.any(String),
      groups: expect.arrayContaining(["interns"]),
      includeTerminated: false,
    });

    await vi.waitFor(() => {
      expect(screen.getByText("test.user1")).toBeInTheDocument();
      expect(screen.getByText("test.user2")).toBeInTheDocument();
      expect(screen.getByText("test.user3")).toBeInTheDocument();
    });
  });

  describe("User Welcome Message", () => {
    it("should display the username when the Cloudflare JWT cookie is present", async () => {
      const mockJwt = "mock.jwt.token";
      const mockUsername = "testuser";

      getCookie.mockReturnValue(mockJwt);
      extractCloudflareUserName.mockReturnValue(mockUsername);

      render(<Dashboard />);

      await vi.waitFor(() => {
        expect(getCookie).toHaveBeenCalledWith("CF_Authorization");
        expect(extractCloudflareUserName).toHaveBeenCalledWith(mockJwt);
        expect(
          screen.getByText(`Welcome, ${mockUsername}`),
        ).toBeInTheDocument();
      });
    });

    it("should display a generic welcome message if the cookie is not present", async () => {
      getCookie.mockReturnValue(null);

      render(<Dashboard />);

      await vi.waitFor(() => {
        expect(getCookie).toHaveBeenCalledWith("CF_Authorization");
        expect(extractCloudflareUserName).not.toHaveBeenCalled();
        expect(
          screen.getByRole("heading", { name: /Welcome/ }),
        ).toHaveTextContent("Welcome");
        expect(screen.queryByText(/Welcome \S+/)).toBeNull();
      });
    });

    it("correctly sums and displays floating-point meeting hours", async () => {
      const mockDecimalSummaryData = [
        {
          ldap: "test.user1",
          jira_issue_done: 1,
          cl_merged: 1,
          loc_merged: 1,
          meeting_hours: 0.65,
          chat_count: 1,
        },
        {
          ldap: "test.user2",
          jira_issue_done: 1,
          cl_merged: 1,
          loc_merged: 1,
          meeting_hours: 0.71,
          chat_count: 1,
        },
        {
          ldap: "test.user3",
          jira_issue_done: 1,
          cl_merged: 1,
          loc_merged: 1,
          meeting_hours: 0.82,
          chat_count: 1,
        },
      ];

      getSummary.mockResolvedValue({ data: mockDecimalSummaryData });
      getLdapsAndDisplayNames.mockResolvedValue({ data: mockLdapsData });

      render(<Dashboard />);

      await vi.waitFor(() => {
        const meetingHoursCard = screen.getByTestId("card-Meeting-Hours");

        expect(meetingHoursCard).toHaveTextContent("2.18");

        expect(meetingHoursCard).not.toHaveTextContent("2.17999");
      });
    });
  });
});
