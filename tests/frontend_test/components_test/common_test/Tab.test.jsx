import { vi, describe, it, expect, beforeEach, afterEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import Tab from "@/components/common/Tab.jsx";
import {
  DataSourceNames,
  ChatProvider,
  JiraIssueStatus,
} from "@/constants/Groups"; // Ensure these paths are correct in your project
import { CalendarReportTable } from "@/components/common/CalendarReportTable";
import { ChatReportTable } from "@/components/common/ChatReportTable";
import JiraReportTable from "@/components/common/JiraReportTable";
import GerritReportTable from "@/components/common/GerritReportTable";

// Mock the child report components
// We use vi.fn() to allow checking calls and props later.
vi.mock("@/components/common/CalendarReportTable", () => ({
  CalendarReportTable: vi.fn((props) => (
    <div data-testid="CalendarReportTable-mock">
      {JSON.stringify(props, null, 2)}
    </div>
  )),
}));

vi.mock("@/components/common/ChatReportTable", () => ({
  ChatReportTable: vi.fn((props) => (
    <div data-testid="ChatReportTable-mock">
      {JSON.stringify(props, null, 2)}
    </div>
  )),
}));

vi.mock("@/components/common/JiraReportTable", () => ({
  default: vi.fn((props) => (
    <div data-testid="JiraReportTable-mock">
      {JSON.stringify(props, null, 2)}
    </div>
  )),
}));

vi.mock("@/components/common/GerritReportTable", () => ({
  default: vi.fn((props) => (
    <div data-testid="GerritReportTable-mock">
      {JSON.stringify(props, null, 2)}
    </div>
  )),
}));

describe("Tab Component", () => {
  // Common search parameters for testing
  const commonSearchParams = {
    ldaps: ["ldap1", "ldap2"],
    startDate: "2023-01-01",
    endDate: "2023-01-31",
  };

  beforeEach(() => {
    // Clear all mock calls before each test
    vi.clearAllMocks();
  });

  afterEach(() => {
    // Clean up the DOM after each test run
    cleanup();
  });

  it("should not render tabs (no committedSearchParams)", () => {
    render(<Tab committedSearchParams={null} />);

    // No report tabs should be rendered
    expect(
      screen.queryByRole("tab", { name: DataSourceNames.CHAT }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("tab", { name: DataSourceNames.JIRA }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("tab", { name: DataSourceNames.CALENDAR }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("tab", { name: DataSourceNames.GERRIT }),
    ).not.toBeInTheDocument();

    // No report tables should be rendered
    expect(
      screen.queryByTestId("ChatReportTable-mock"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("JiraReportTable-mock"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("CalendarReportTable-mock"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("GerritReportTable-mock"),
    ).not.toBeInTheDocument();
  });

  it("should not render any report table if essential commonParams are missing", async () => {
    const committedSearchParamsMissingLdaps = {
      ldaps: [], // Missing ldaps
      startDate: "2023-01-01",
      endDate: "2023-01-31",
      selectedDataSources: {
        [DataSourceNames.CHAT]: [
          { provider: ChatProvider.Google, id: "g1", name: "G1" },
        ],
      },
    };

    render(<Tab committedSearchParams={committedSearchParamsMissingLdaps} />);

    expect(
      screen.queryByRole("tab", { name: DataSourceNames.CHAT }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("ChatReportTable-mock"),
    ).not.toBeInTheDocument();

    cleanup();

    const committedSearchParamsMissingStartDate = {
      ldaps: ["ldap1"],
      startDate: "", // Missing startDate
      endDate: "2023-01-31",
      selectedDataSources: {
        [DataSourceNames.JIRA]: ["j1"],
      },
    };

    render(
      <Tab committedSearchParams={committedSearchParamsMissingStartDate} />,
    );

    expect(
      screen.queryByRole("tab", { name: DataSourceNames.JIRA }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("JiraReportTable-mock"),
    ).not.toBeInTheDocument();
  });

  it("should render tabs and activate Chat when all sources are selected", async () => {
    const committedSearchParams = {
      ...commonSearchParams,
      selectedDataSources: {
        [DataSourceNames.CHAT]: [
          {
            provider: ChatProvider.Google,
            id: "google-space-1",
            name: "Google Space 1",
          },
        ],
        [DataSourceNames.JIRA]: ["jira-project-1"],
        [DataSourceNames.CALENDAR]: ["calendar-id-1"],
        [DataSourceNames.GERRIT]: {
          projectList: ["mock/project-name"],
          includeAllProjects: false,
        },
      },
    };

    render(<Tab committedSearchParams={committedSearchParams} />);

    // All tabs should be enabled
    expect(
      screen.getByRole("tab", { name: DataSourceNames.CHAT }),
    ).not.toBeDisabled();
    expect(
      screen.getByRole("tab", { name: DataSourceNames.JIRA }),
    ).not.toBeDisabled();
    expect(
      screen.getByRole("tab", { name: DataSourceNames.CALENDAR }),
    ).not.toBeDisabled();
    expect(
      screen.getByRole("tab", { name: DataSourceNames.GERRIT }),
    ).not.toBeDisabled();

    // Chat tab should be active by default
    expect(screen.getByRole("tab", { name: DataSourceNames.CHAT })).toHaveClass(
      "active",
    );

    // ChatReportTable should be rendered with correct props
    await waitFor(() => {
      expect(ChatReportTable).toHaveBeenCalledTimes(1);
      const props = ChatReportTable.mock.calls[0][0];
      expect(props.chatReportProps.searchParams).toEqual({
        ...commonSearchParams,
        chatProviderList: [
          {
            provider: ChatProvider.Google,
            googleChatSpaceIds: ["google-space-1"],
          },
        ],
      });
      expect(props.chatReportProps.googleChatSpaceMap).toEqual({
        "google-space-1": "Google Space 1",
      });
      expect(props.chatReportProps.microsoftChatSpaceName).toBe("");
    });

    // Other report tables should not be rendered
    expect(
      screen.queryByTestId("JiraReportTable-mock"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("CalendarReportTable-mock"),
    ).not.toBeInTheDocument();
  });

  it("should switch to Jira tab when Chat is clicked and render JiraReportTable", async () => {
    const committedSearchParams = {
      ...commonSearchParams,
      selectedDataSources: {
        [DataSourceNames.CHAT]: [
          {
            provider: ChatProvider.Google,
            id: "google-space-1",
            name: "Google Space 1",
          },
        ],
        [DataSourceNames.JIRA]: ["jira-project-1"],
        [DataSourceNames.CALENDAR]: ["calendar-id-1"],
      },
    };

    render(<Tab committedSearchParams={committedSearchParams} />);

    // Initially Chat is active
    expect(screen.getByRole("tab", { name: DataSourceNames.CHAT })).toHaveClass(
      "active",
    );
    await waitFor(() => {
      expect(ChatReportTable).toHaveBeenCalledTimes(1);
    });

    // Click on Jira tab
    fireEvent.click(screen.getByRole("tab", { name: DataSourceNames.JIRA }));

    // Jira tab should become active
    expect(screen.getByRole("tab", { name: DataSourceNames.JIRA })).toHaveClass(
      "active",
    );
    expect(
      screen.getByRole("tab", { name: DataSourceNames.CHAT }),
    ).not.toHaveClass("active");

    // JiraReportTable should be rendered with correct props
    await waitFor(() => {
      expect(JiraReportTable).toHaveBeenCalledTimes(1);
      const props = JiraReportTable.mock.calls[0][0];
      expect(props.jiraReportProps.searchParams).toEqual({
        ...commonSearchParams,
        projectIds: ["jira-project-1"],
        statusList: [JiraIssueStatus.DONE],
      });
    });

    // ChatReportTable should not be in the document
    expect(
      screen.queryByTestId("ChatReportTable-mock"),
    ).not.toBeInTheDocument();
  });

  it("should switch to Calendar tab when Calendar is clicked and render CalendarReportTable", async () => {
    const committedSearchParams = {
      ...commonSearchParams,
      selectedDataSources: {
        [DataSourceNames.CHAT]: [
          {
            provider: ChatProvider.Google,
            id: "google-space-1",
            name: "Google Space 1",
          },
        ],
        [DataSourceNames.JIRA]: ["jira-project-1"],
        [DataSourceNames.CALENDAR]: ["calendar-id-1"],
      },
    };

    render(<Tab committedSearchParams={committedSearchParams} />);

    // Initially Chat is active
    expect(screen.getByRole("tab", { name: DataSourceNames.CHAT })).toHaveClass(
      "active",
    );
    await waitFor(() => {
      expect(ChatReportTable).toHaveBeenCalledTimes(1);
    });

    // Click on Calendar tab
    fireEvent.click(
      screen.getByRole("tab", { name: DataSourceNames.CALENDAR }),
    );

    // Calendar tab should become active
    expect(
      screen.getByRole("tab", { name: DataSourceNames.CALENDAR }),
    ).toHaveClass("active");
    expect(
      screen.getByRole("tab", { name: DataSourceNames.CHAT }),
    ).not.toHaveClass("active");

    // CalendarReportTable should be rendered with correct props
    await waitFor(() => {
      expect(CalendarReportTable).toHaveBeenCalledTimes(1);
      const props = CalendarReportTable.mock.calls[0][0];
      expect(props.googleCalendarReportProps.searchParams).toEqual({
        ...commonSearchParams,
        calendarIds: ["calendar-id-1"],
      });
    });

    // ChatReportTable should not be in the document
    expect(
      screen.queryByTestId("ChatReportTable-mock"),
    ).not.toBeInTheDocument();
  });

  it("should disable a tab if its data source is not selected", async () => {
    const committedSearchParams = {
      ...commonSearchParams,
      selectedDataSources: {
        [DataSourceNames.CHAT]: [
          {
            provider: ChatProvider.Google,
            id: "google-space-1",
            name: "Google Space 1",
          },
        ],
        // JIRA is missing, CALENDAR is present
        [DataSourceNames.CALENDAR]: ["calendar-id-1"],
      },
    };

    render(<Tab committedSearchParams={committedSearchParams} />);

    expect(
      screen.getByRole("tab", { name: DataSourceNames.CHAT }),
    ).not.toBeDisabled();
    expect(
      screen.getByRole("tab", { name: DataSourceNames.JIRA }),
    ).toBeDisabled();
    expect(
      screen.getByRole("tab", { name: DataSourceNames.CALENDAR }),
    ).not.toBeDisabled();

    // Attempting to click a disabled tab should not change the active tab
    fireEvent.click(screen.getByRole("tab", { name: DataSourceNames.JIRA }));
    expect(screen.getByRole("tab", { name: DataSourceNames.CHAT })).toHaveClass(
      "active",
    ); // Still active
  });

  it("should switch active tab if current active tab becomes invalid due to committedSearchParams change", async () => {
    const initialSearchParams = {
      ...commonSearchParams,
      selectedDataSources: {
        [DataSourceNames.CHAT]: [
          {
            provider: ChatProvider.Google,
            id: "google-space-1",
            name: "Google Space 1",
          },
        ],
        [DataSourceNames.JIRA]: ["jira-project-1"],
      },
    };

    const { rerender } = render(
      <Tab committedSearchParams={initialSearchParams} />,
    );

    // Initially, Chat is active
    expect(screen.getByRole("tab", { name: DataSourceNames.CHAT })).toHaveClass(
      "active",
    );
    await waitFor(() => {
      expect(ChatReportTable).toHaveBeenCalledTimes(1);
    });

    // Update committedSearchParams: Chat is no longer selected, Jira is still selected
    const updatedSearchParams = {
      ...commonSearchParams,
      selectedDataSources: {
        [DataSourceNames.JIRA]: ["jira-project-1"],
        [DataSourceNames.CALENDAR]: ["calendar-id-1"],
      },
    };

    rerender(<Tab committedSearchParams={updatedSearchParams} />);

    // Expect Jira to become active because Chat is no longer valid and Jira is the first valid one.
    await waitFor(() => {
      expect(
        screen.getByRole("tab", { name: DataSourceNames.JIRA }),
      ).toHaveClass("active");
      expect(
        screen.getByRole("tab", { name: DataSourceNames.CHAT }),
      ).not.toHaveClass("active");
      expect(JiraReportTable).toHaveBeenCalledTimes(1); // Jira table should now be rendered
      expect(ChatReportTable).toHaveBeenCalledTimes(1); // Chat table was called once initially, should not be called again
    });
  });

  it("should default to the first tab (Chat) if no data sources are valid", async () => {
    const initialSearchParams = {
      ...commonSearchParams,
      selectedDataSources: {
        [DataSourceNames.JIRA]: ["jira-project-1"],
      },
    };

    const { rerender } = render(
      <Tab committedSearchParams={initialSearchParams} />,
    );

    // Initially, Jira will be active (as it's the first valid one if Chat is not provided or invalid)
    // Let's explicitly activate Jira first to test the scenario
    fireEvent.click(screen.getByRole("tab", { name: DataSourceNames.JIRA }));
    await waitFor(() => {
      expect(
        screen.getByRole("tab", { name: DataSourceNames.JIRA }),
      ).toHaveClass("active");
      expect(JiraReportTable).toHaveBeenCalledTimes(1);
    });
    vi.clearAllMocks(); // Clear calls before the next rerender

    // Update committedSearchParams: no data sources are selected
    const updatedSearchParams = {
      ...commonSearchParams,
      selectedDataSources: {
        [DataSourceNames.CHAT]: [],
        [DataSourceNames.JIRA]: [],
        [DataSourceNames.CALENDAR]: [],
      },
    };

    rerender(<Tab committedSearchParams={updatedSearchParams} />);

    // Chat tab (index 0) should become active and disabled
    await waitFor(() => {
      expect(
        screen.getByRole("tab", { name: DataSourceNames.CHAT }),
      ).toHaveClass("active");
      expect(
        screen.getByRole("tab", { name: DataSourceNames.CHAT }),
      ).toBeDisabled();
      expect(
        screen.getByRole("tab", { name: DataSourceNames.JIRA }),
      ).toBeDisabled();
      expect(
        screen.getByRole("tab", { name: DataSourceNames.CALENDAR }),
      ).toBeDisabled();
    });

    // No report table should be rendered
    expect(
      screen.queryByTestId("ChatReportTable-mock"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("JiraReportTable-mock"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("CalendarReportTable-mock"),
    ).not.toBeInTheDocument();
  });

  it("should pass correct props to ChatReportTable with Google and Microsoft chat providers", async () => {
    const committedSearchParams = {
      ...commonSearchParams,
      selectedDataSources: {
        [DataSourceNames.CHAT]: [
          {
            provider: ChatProvider.Google,
            id: "google-space-1",
            name: "Google Space One",
          },
          {
            provider: ChatProvider.Google,
            id: "google-space-2",
            name: "Google Space Two",
          },
          {
            provider: ChatProvider.Microsoft,
            id: "ms-chat-1",
            name: "Microsoft Teams Chat",
          },
        ],
      },
    };

    render(<Tab committedSearchParams={committedSearchParams} />);

    fireEvent.click(screen.getByRole("tab", { name: DataSourceNames.CHAT }));

    await waitFor(() => {
      expect(ChatReportTable).toHaveBeenCalledTimes(1);
      const props = ChatReportTable.mock.calls[0][0];
      expect(props.chatReportProps.searchParams.chatProviderList).toEqual([
        {
          provider: ChatProvider.Microsoft,
        },
        {
          provider: ChatProvider.Google,
          googleChatSpaceIds: ["google-space-1", "google-space-2"],
        },
      ]);
      expect(props.chatReportProps.googleChatSpaceMap).toEqual({
        "google-space-1": "Google Space One",
        "google-space-2": "Google Space Two",
      });
      expect(props.chatReportProps.microsoftChatSpaceName).toBe(
        "Microsoft Teams Chat",
      );
    });
  });

  it("should not render ChatReportTable if chatConfig is empty", async () => {
    const committedSearchParams = {
      ...commonSearchParams,
      selectedDataSources: {
        [DataSourceNames.CHAT]: [],
      },
    };

    render(<Tab committedSearchParams={committedSearchParams} />);

    // Chat tab should be disabled
    expect(
      screen.getByRole("tab", { name: DataSourceNames.CHAT }),
    ).toBeDisabled();

    // No ChatReportTable should be rendered
    expect(
      screen.queryByTestId("ChatReportTable-mock"),
    ).not.toBeInTheDocument();
  });

  it("should not render JiraReportTable if jiraConfig is empty", async () => {
    const committedSearchParams = {
      ...commonSearchParams,
      selectedDataSources: {
        [DataSourceNames.JIRA]: [],
      },
    };

    render(<Tab committedSearchParams={committedSearchParams} />);

    // Jira tab should be disabled
    expect(
      screen.getByRole("tab", { name: DataSourceNames.JIRA }),
    ).toBeDisabled();

    // No JiraReportTable should be rendered
    expect(
      screen.queryByTestId("JiraReportTable-mock"),
    ).not.toBeInTheDocument();
  });

  it("should not render CalendarReportTable if calendarConfig is empty", async () => {
    const committedSearchParams = {
      ...commonSearchParams,
      selectedDataSources: {
        [DataSourceNames.CALENDAR]: [],
      },
    };

    render(<Tab committedSearchParams={committedSearchParams} />);

    // Calendar tab should be disabled
    expect(
      screen.getByRole("tab", { name: DataSourceNames.CALENDAR }),
    ).toBeDisabled();

    // No CalendarReportTable should be rendered
    expect(
      screen.queryByTestId("CalendarReportTable-mock"),
    ).not.toBeInTheDocument();
  });

  it("should pass all three Jira issue statuses when endDate is today", async () => {
    const today = new Date().toISOString().split("T")[0]; // "YYYY-MM-DD" format

    const committedSearchParamsToday = {
      ...commonSearchParams,
      endDate: today,
      selectedDataSources: {
        [DataSourceNames.JIRA]: ["jira-project-1"],
      },
    };

    render(<Tab committedSearchParams={committedSearchParamsToday} />);

    fireEvent.click(screen.getByRole("tab", { name: DataSourceNames.JIRA }));

    await waitFor(() => {
      expect(JiraReportTable).toHaveBeenCalledTimes(1);
      const props = JiraReportTable.mock.calls[0][0];
      expect(props.jiraReportProps.searchParams).toEqual({
        ldaps: ["ldap1", "ldap2"],
        startDate: "2023-01-01",
        endDate: today,
        projectIds: ["jira-project-1"],
        statusList: [
          JiraIssueStatus.DONE,
          JiraIssueStatus.IN_PROGRESS,
          JiraIssueStatus.TODO,
        ],
      });
    });
  });
});
