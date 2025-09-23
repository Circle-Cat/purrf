import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ChatReportTable } from "@/components/common/ChatReportTable";
import {
  getMicrosoftChatMessagesCount,
  getGoogleChatMessagesCount,
} from "@/api/dataSearchApi";
import { ChatProvider } from "@/constants/Groups";
import {
  flattenMicrosoftChatData,
  flattenGoogleChatData,
} from "@/utils/flattenScheduleData";
import userEvent from "@testing-library/user-event";
import Table from "@/components/common/Table";

vi.mock("@/api/dataSearchApi", () => ({
  getMicrosoftChatMessagesCount: vi.fn(),
  getGoogleChatMessagesCount: vi.fn(),
}));

vi.mock("@/utils/flattenScheduleData", () => ({
  flattenMicrosoftChatData: vi.fn(),
  flattenGoogleChatData: vi.fn(),
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

describe("ChatReportTable", () => {
  let expectedCombinedData;
  let expectedGoogleChatData;
  const mockProps = {
    chatReportProps: {
      searchParams: {
        startDate: "2025-01-01",
        endDate: "2025-01-31",
        ldaps: ["user1", "user2"],
        chatProviderList: [
          { provider: ChatProvider.Microsoft },
          {
            provider: ChatProvider.Google,
            googleChatSpaceIds: ["space1", "space2"],
          },
        ],
      },
      googleChatSpaceMap: {
        space1: "Project A",
        space2: "Team B",
      },
      microsoftChatSpaceName: "General Chat",
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    getMicrosoftChatMessagesCount.mockResolvedValue({
      data: { result: { user1: 10, user2: 20 } },
    });
    getGoogleChatMessagesCount.mockResolvedValue({
      data: {
        result: {
          user1: { space1: 5, space2: 15 },
          user2: { space1: 8, space2: 12 },
        },
      },
    });
    const mockFlattenedMicrosoftData = [
      { ldap: "user1", chatSpace: "General Chat", counts: 10 },
      { ldap: "user2", chatSpace: "General Chat", counts: 20 },
    ];

    const mockFlattenedGoogleData = [
      { ldap: "user1", chatSpace: "Project A", counts: 5 },
      { ldap: "user1", chatSpace: "Team B", counts: 15 },
      { ldap: "user2", chatSpace: "Project A", counts: 8 },
      { ldap: "user2", chatSpace: "Team B", counts: 12 },
    ];
    flattenMicrosoftChatData.mockReturnValue(mockFlattenedMicrosoftData);
    flattenGoogleChatData.mockReturnValue(mockFlattenedGoogleData);

    expectedCombinedData = [
      ...mockFlattenedMicrosoftData,
      ...mockFlattenedGoogleData,
    ];
    expectedGoogleChatData = mockFlattenedGoogleData;
  });

  it("should display loading message initially", () => {
    getMicrosoftChatMessagesCount.mockReturnValue(new Promise(() => {}));
    getGoogleChatMessagesCount.mockReturnValue(new Promise(() => {}));
    render(<ChatReportTable {...mockProps} />);
    expect(screen.getByText("Loading chat data...")).toBeInTheDocument();
  });

  it("should fetch and display combined data for multiple providers", async () => {
    render(<ChatReportTable {...mockProps} />);

    await waitFor(() => {
      expect(getMicrosoftChatMessagesCount).toHaveBeenCalledWith({
        startDate: "2025-01-01",
        endDate: "2025-01-31",
        ldaps: ["user1", "user2"],
      });
      expect(getGoogleChatMessagesCount).toHaveBeenCalledWith({
        startDate: "2025-01-01",
        endDate: "2025-01-31",
        ldaps: ["user1", "user2"],
        spaceIds: ["space1", "space2"],
      });
      expect(Table).toHaveBeenCalledWith(
        expect.objectContaining({
          columns: expect.any(Array),
          data: expect.arrayContaining(expectedCombinedData),
          onSort: expect.any(Function),
          sortColumn: null,
          sortDirection: "asc",
        }),
        undefined,
      );
    });
  });

  it("should display Google Chat data when Microsoft API failure", async () => {
    getMicrosoftChatMessagesCount.mockRejectedValue(new Error("API Error"));
    render(<ChatReportTable {...mockProps} />);

    await waitFor(() => {
      expect(getGoogleChatMessagesCount).toHaveBeenCalledWith({
        startDate: "2025-01-01",
        endDate: "2025-01-31",
        ldaps: ["user1", "user2"],
        spaceIds: ["space1", "space2"],
      });
      expect(Table).toHaveBeenCalledWith(
        expect.objectContaining({
          columns: expect.any(Array),
          data: expect.arrayContaining(expectedGoogleChatData),
          onSort: expect.any(Function),
          sortColumn: null,
          sortDirection: "asc",
        }),
        undefined,
      );
    });
  });

  it("should display no data message when no chat messages are found", async () => {
    getMicrosoftChatMessagesCount.mockResolvedValue({ data: { result: null } });
    getGoogleChatMessagesCount.mockResolvedValue({ data: { result: null } });
    flattenMicrosoftChatData.mockReturnValue([]);
    flattenGoogleChatData.mockReturnValue([]);

    render(<ChatReportTable {...mockProps} />);

    await waitFor(() => {
      expect(
        screen.getByText("No chat messages found for the given parameters."),
      ).toBeInTheDocument();
    });
    expect(screen.queryByTestId("mock-table")).not.toBeInTheDocument();
  });

  it("should handle sorting when a column header is clicked", async () => {
    const user = userEvent.setup();
    const mockFlattenedData = [
      { ldap: "user2", chatSpace: "General Chat", counts: 20 },
      { ldap: "user1", chatSpace: "General Chat", counts: 10 },
    ];
    flattenMicrosoftChatData.mockReturnValue(mockFlattenedData);
    flattenGoogleChatData.mockReturnValue([]);

    render(<ChatReportTable {...mockProps} />);

    await waitFor(() => {
      const dataElement = screen.getByTestId("table-data");
      expect(dataElement).toHaveTextContent('["user2","user1"]');
    });

    await user.click(screen.getByTestId("sort-button-ldap"));
    await waitFor(() => {
      const dataElement = screen.getByTestId("table-data");
      expect(dataElement).toHaveTextContent('["user1","user2"]');
      expect(screen.getByTestId("sort-config")).toHaveTextContent("ldap-asc");
    });

    await user.click(screen.getByTestId("sort-button-ldap"));
    await waitFor(() => {
      const dataElement = screen.getByTestId("table-data");
      expect(dataElement).toHaveTextContent('["user2","user1"]');
      expect(screen.getByTestId("sort-config")).toHaveTextContent("ldap-desc");
    });
  });
});
