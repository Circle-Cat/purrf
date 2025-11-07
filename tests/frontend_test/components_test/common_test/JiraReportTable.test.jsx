import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import "@testing-library/jest-dom/vitest";

import JiraReportTable from "@/components/common/JiraReportTable";
import { getJiraIssueDetails, getJiraIssueBrief } from "@/api/dataSearchApi";

vi.mock("@/api/dataSearchApi", () => ({
  getJiraIssueDetails: vi.fn(),
  getJiraIssueBrief: vi.fn(),
}));

const mockJiraReportProps = {
  searchParams: {
    startDate: "2025-09-01",
    endDate: "2025-09-10",
    projectIds: ["PROJ1", "PROJ2"],
    statusList: ["todo", "done", "in_progress"],
    ldaps: ["user1", "user2"],
  },
  ldapsAndDisplayNames: {
    user1: "Test User 1",
  },
};

const mockJiraReportPropsDoneOnly = {
  searchParams: {
    startDate: "2025-09-01",
    endDate: "2025-09-10",
    projectIds: ["PROJ1", "PROJ2"],
    statusList: ["done"],
    ldaps: ["user1", "user2"],
  },
  ldapsAndDisplayNames: {
    user1: "Test User 1",
  },
};

const mockSummaryData = {
  user1: {
    todo: ["JIRA-101"],
    in_progress: ["JIRA-102"],
    done: ["JIRA-103"],
    done_story_points_total: 5,
  },
  user2: {
    todo: [],
    in_progress: [],
    done: [],
    done_story_points_total: 0,
  },
  time_range: {},
};

const mockDetailedTasks = [
  {
    issue_key: "JIRA-101",
    issue_title: "This is a to-do task",
    story_point: 3,
    finish_date: null,
  },
  {
    issue_key: "JIRA-102",
    issue_title: "This is an in-progress task",
    story_point: 8,
    finish_date: null,
  },
  {
    issue_key: "JIRA-103",
    issue_title: "This is a done task",
    story_point: 5,
    finish_date: "20240726",
  },
];

describe("JiraReportTable", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    getJiraIssueBrief.mockResolvedValue({ data: mockSummaryData });

    getJiraIssueDetails.mockImplementation(({ issueIds }) => {
      const filteredTasks = mockDetailedTasks.filter((task) =>
        issueIds.includes(task.issue_key),
      );
      return Promise.resolve({ data: filteredTasks });
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    console.error.mockRestore();
  });

  it('should render "N/A" when jiraReportProps.searchParams is null', () => {
    render(
      <JiraReportTable
        jiraReportProps={{ searchParams: null, ldapsAndDisplayNames: {} }}
      />,
    );
    expect(screen.getByText("N/A")).toBeInTheDocument();
    expect(getJiraIssueBrief).not.toHaveBeenCalled();
  });

  it("should render nothing if the API returns empty summary data", async () => {
    getJiraIssueBrief.mockResolvedValueOnce({ data: {} });
    const { container } = render(
      <JiraReportTable jiraReportProps={mockJiraReportProps} />,
    );

    await waitFor(() => {
      expect(getJiraIssueBrief).toHaveBeenCalledWith(
        mockJiraReportProps.searchParams,
      );
    });

    expect(
      container.querySelector(".jira-table-container"),
    ).toBeInTheDocument();
    expect(
      container.querySelector(".jira-table-container"),
    ).toBeEmptyDOMElement();
  });

  it("should render user tables with correct names and initial status data", async () => {
    render(<JiraReportTable jiraReportProps={mockJiraReportProps} />);

    await waitFor(() => {
      expect(screen.getByText("user1 (Test User 1)")).toBeInTheDocument();
      expect(screen.getByText("user2")).toBeInTheDocument();
    });

    const user1Table = screen
      .getByText("user1 (Test User 1)")
      .closest(".user-table");
    const user2Table = screen.getByText("user2").closest(".user-table");

    expect(user1Table).toBeInTheDocument();
    expect(user2Table).toBeInTheDocument();

    const user1Scope = within(user1Table);

    const todoRowUser1 = user1Scope.getByText("To Do").closest("tr");
    expect(todoRowUser1).toHaveTextContent("To Do");
    expect(todoRowUser1).toHaveTextContent("1");
    expect(todoRowUser1).toHaveTextContent("-");

    const inProgressRowUser1 = user1Scope
      .getByText("In Progress")
      .closest("tr");
    expect(inProgressRowUser1).toHaveTextContent("In Progress");
    expect(inProgressRowUser1).toHaveTextContent("1");
    expect(inProgressRowUser1).toHaveTextContent("-");

    const doneRowUser1 = user1Scope.getByText("Done").closest("tr");
    expect(doneRowUser1).toHaveTextContent("Done");
    expect(doneRowUser1).toHaveTextContent("1");
    expect(doneRowUser1).toHaveTextContent("5.0");

    const user2Scope = within(user2Table);

    const todoRowUser2 = user2Scope.getByText("To Do").closest("tr");
    expect(todoRowUser2).toHaveTextContent("To Do");
    expect(todoRowUser2).toHaveTextContent("0");
    expect(todoRowUser2).toHaveTextContent("-");

    const inProgressRowUser2 = user2Scope
      .getByText("In Progress")
      .closest("tr");
    expect(inProgressRowUser2).toHaveTextContent("In Progress");
    expect(inProgressRowUser2).toHaveTextContent("0");
    expect(inProgressRowUser2).toHaveTextContent("-");

    const doneRowUser2 = user2Scope.getByText("Done").closest("tr");
    expect(doneRowUser2).toHaveTextContent("Done");
    expect(doneRowUser2).toHaveTextContent("0");
    expect(doneRowUser2).toHaveTextContent("0.0");
  });

  it("should render user tables with correct names and only 'Done' status data", async () => {
    render(<JiraReportTable jiraReportProps={mockJiraReportPropsDoneOnly} />);

    await waitFor(() => {
      expect(screen.getByText("user1 (Test User 1)")).toBeInTheDocument();
      expect(screen.getByText("user2")).toBeInTheDocument();
    });

    const user1Table = screen
      .getByText("user1 (Test User 1)")
      .closest(".user-table");
    const user2Table = screen.getByText("user2").closest(".user-table");

    const user1Scope = within(user1Table);
    const user2Scope = within(user2Table);

    const doneRowUser1 = user1Scope.getByText("Done").closest("tr");
    expect(doneRowUser1).toHaveTextContent("Done");
    expect(doneRowUser1).toHaveTextContent("1");
    expect(doneRowUser1).toHaveTextContent("5.0");

    expect(user1Scope.queryByText("To Do")).not.toBeInTheDocument();
    expect(user1Scope.queryByText("In Progress")).not.toBeInTheDocument();

    const doneRowUser2 = user2Scope.getByText("Done").closest("tr");
    expect(doneRowUser2).toHaveTextContent("Done");
    expect(doneRowUser2).toHaveTextContent("0");
    expect(doneRowUser2).toHaveTextContent("0.0");

    expect(user2Scope.queryByText("To Do")).not.toBeInTheDocument();
    expect(user2Scope.queryByText("In Progress")).not.toBeInTheDocument();
  });

  it("should not fetch details for a status with zero issues", async () => {
    render(<JiraReportTable jiraReportProps={mockJiraReportProps} />);

    await waitFor(() => {
      expect(screen.getByText("user2")).toBeInTheDocument();
    });

    const user2Table = screen.getByText("user2").closest(".user-table");
    const user2Scope = within(user2Table);

    const todoRowUser2 = user2Scope.getByText("To Do").closest("tr");
    expect(todoRowUser2).toBeInTheDocument();
    expect(todoRowUser2).toHaveTextContent("0");

    fireEvent.click(todoRowUser2);

    expect(getJiraIssueDetails).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(user2Scope.getByText("N/A")).toBeInTheDocument();
    });
  });

  it("should fetch and display task details when a status row is clicked", async () => {
    render(<JiraReportTable jiraReportProps={mockJiraReportProps} />);

    await waitFor(() => {
      expect(screen.getByText("user1 (Test User 1)")).toBeInTheDocument();
    });

    const user1Table = screen
      .getByText("user1 (Test User 1)")
      .closest(".user-table");
    const user1Scope = within(user1Table);

    const todoRowUser1 = user1Scope.getByText("To Do").closest("tr");
    fireEvent.click(todoRowUser1);

    await waitFor(() => {
      expect(getJiraIssueDetails).toHaveBeenCalledWith({
        issueIds: ["JIRA-101"],
      });
      expect(user1Scope.getByText("JIRA-101")).toBeInTheDocument();
      expect(user1Scope.getByText("This is a to-do task")).toBeInTheDocument();
      expect(user1Scope.getByText("3")).toBeInTheDocument();
      expect(user1Scope.getAllByText("-")[0]).toBeInTheDocument();
    });

    fireEvent.click(todoRowUser1);
    expect(user1Scope.queryByText("JIRA-101")).not.toBeInTheDocument();

    fireEvent.click(todoRowUser1);
    await waitFor(() => {
      expect(user1Scope.getByText("JIRA-101")).toBeInTheDocument();
    });

    expect(getJiraIssueDetails).toHaveBeenCalledTimes(1);
  });

  it("should handle API errors gracefully when fetching task details", async () => {
    getJiraIssueDetails.mockRejectedValueOnce(new Error("API Error"));

    render(<JiraReportTable jiraReportProps={mockJiraReportProps} />);

    await waitFor(() => {
      expect(screen.getByText("user1 (Test User 1)")).toBeInTheDocument();
    });

    const user1Table = screen
      .getByText("user1 (Test User 1)")
      .closest(".user-table");
    const user1Scope = within(user1Table);

    const todoRowUser1 = user1Scope.getByText("To Do").closest("tr");
    fireEvent.click(todoRowUser1);

    await waitFor(() => {
      expect(console.error).toHaveBeenCalledWith(
        "Failed to fetch jira issue details:",
        expect.any(Error),
      );
    });

    expect(await user1Scope.findByText("N/A")).toBeInTheDocument();
  });

  it("should format and display the finish date correctly", async () => {
    render(<JiraReportTable jiraReportProps={mockJiraReportProps} />);

    await waitFor(() => {
      expect(screen.getByText("user1 (Test User 1)")).toBeInTheDocument();
    });

    const user1Table = screen
      .getByText("user1 (Test User 1)")
      .closest(".user-table");
    const user1Scope = within(user1Table);

    const doneRowUser1 = user1Scope.getByText("Done").closest("tr");
    fireEvent.click(doneRowUser1);

    await waitFor(() => {
      expect(getJiraIssueDetails).toHaveBeenCalledWith({
        issueIds: ["JIRA-103"],
      });
      const dateCell = user1Scope.getByText("2024/07/26");
      expect(dateCell).toBeInTheDocument();
    });
  });
});
