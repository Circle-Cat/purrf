import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  getMicrosoftChatTopics,
  getGoogleChatSpaces,
  getGoogleCalendars,
  getJiraProjects,
  getGerritProjects,
} from "@/api/dataSearchApi";
import { ChatProvider, DataSourceNames } from "@/constants/Groups";
import { DataSourceSelector } from "@/components/common/DataSourceSelector";

vi.mock("@/api/dataSearchApi", () => ({
  getMicrosoftChatTopics: vi.fn(),
  getGoogleChatSpaces: vi.fn(),
  getGoogleCalendars: vi.fn(),
  getJiraProjects: vi.fn(),
  getGerritProjects: vi.fn(),
}));

describe("DataSourceSelector", () => {
  const onConfirmMock = vi.fn();
  const onCancelMock = vi.fn();

  // Helper function to render the component with default props
  const renderDataSourceSelector = (props = {}) => {
    return render(
      <DataSourceSelector
        isOpen={true}
        onConfirm={onConfirmMock}
        onCancel={onCancelMock}
        {...props}
      />,
    );
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Mock successful API responses
    getMicrosoftChatTopics.mockResolvedValue({
      data: {
        "ms-chat-1": "Microsoft Chat 1",
        "ms-chat-2": "Microsoft Chat 2",
      },
    });
    getGoogleChatSpaces.mockResolvedValue({
      data: {
        "gc-space-1": "Google Space A",
        "gc-space-2": "Google Space B",
      },
    });
    getJiraProjects.mockResolvedValue({
      data: {
        JIRA1: "Jira Project Alpha",
        JIRA2: "Jira Project Beta",
      },
    });
    getGerritProjects.mockResolvedValue({
      data: ["gerrit/project/foo", "gerrit/project/bar"],
    });
    getGoogleCalendars.mockResolvedValue({
      data: [
        { id: "cal-1", name: "My Personal Calendar" },
        { id: "cal-2", name: "Team Events" },
      ],
    });
  });

  it("should not render the selector content when isOpen is false", () => {
    renderDataSourceSelector({ isOpen: false });
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
    expect(screen.queryByText(DataSourceNames.CHAT)).not.toBeInTheDocument();
  });

  it("should display loading state initially", () => {
    getMicrosoftChatTopics.mockReturnValue(new Promise(() => {}));
    getGoogleChatSpaces.mockReturnValue(new Promise(() => {}));
    getJiraProjects.mockReturnValue(new Promise(() => {}));
    getGerritProjects.mockReturnValue(new Promise(() => {}));
    getGoogleCalendars.mockReturnValue(new Promise(() => {}));

    renderDataSourceSelector();
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("should render data sources and items after successful data fetch and activate the first source", async () => {
    renderDataSourceSelector();

    await waitFor(() => {
      expect(screen.getByText(DataSourceNames.CHAT)).toBeInTheDocument();
      expect(screen.getByText(DataSourceNames.JIRA)).toBeInTheDocument();
      expect(screen.getByText(DataSourceNames.GERRIT)).toBeInTheDocument();
      expect(screen.getByText(DataSourceNames.CALENDAR)).toBeInTheDocument();

      expect(screen.getByText("Microsoft Chat 1")).toBeInTheDocument();
      expect(screen.getByText("Google Space A")).toBeInTheDocument();
    });

    expect(screen.queryByText("Jira Project Alpha")).not.toBeInTheDocument();
    const chatSidebarButton = screen
      .getByText(DataSourceNames.CHAT)
      .closest('[role="button"]');
    expect(chatSidebarButton).toHaveClass("active");
  });

  it("should switch active source when a sidebar item is clicked", async () => {
    renderDataSourceSelector();

    await waitFor(() => {
      expect(screen.getByText(DataSourceNames.CHAT)).toBeInTheDocument();
      expect(screen.getByText("Microsoft Chat 1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(DataSourceNames.JIRA));

    await waitFor(() => {
      expect(screen.getByText("Jira Project Alpha")).toBeInTheDocument();
      expect(screen.getByText("Jira Project Beta")).toBeInTheDocument();
    });

    expect(screen.queryByText("Microsoft Chat 1")).not.toBeInTheDocument(); // Chat items should no longer be visible
    const jiraSidebarButton = screen
      .getByText(DataSourceNames.JIRA)
      .closest('[role="button"]');
    expect(jiraSidebarButton).toHaveClass("active");
  });

  it("should allow selecting and deselecting individual items", async () => {
    renderDataSourceSelector();
    await waitFor(() => screen.getByText("Microsoft Chat 1"));

    const item1 = screen.getByLabelText("Microsoft Chat 1");
    const item2 = screen.getByLabelText("Google Space A");

    fireEvent.click(item1);
    expect(item1).toBeChecked();

    fireEvent.click(item2);
    expect(item2).toBeChecked();

    fireEvent.click(item1); // Deselect item1
    expect(item1).not.toBeChecked();

    fireEvent.click(screen.getByRole("button", { name: "OK" }));

    await waitFor(() => {
      expect(onConfirmMock).toHaveBeenCalledWith({
        Chat: [
          {
            id: "gc-space-1",
            name: "Google Space A",
            provider: ChatProvider.Google,
          },
        ],
      });
    });
  });

  it('should toggle "Select All" for the active source', async () => {
    renderDataSourceSelector();
    await waitFor(() => screen.getByText("Microsoft Chat 1"));

    const chatSelectAll = screen.getByLabelText(
      `Select all ${DataSourceNames.CHAT}`,
    );
    fireEvent.click(chatSelectAll); // Select all

    expect(screen.getByLabelText("Microsoft Chat 1")).toBeChecked();
    expect(screen.getByLabelText("Microsoft Chat 2")).toBeChecked();
    expect(screen.getByLabelText("Google Space A")).toBeChecked();
    expect(screen.getByLabelText("Google Space B")).toBeChecked();
    expect(chatSelectAll).toBeChecked();

    fireEvent.click(chatSelectAll); // Deselect all
    expect(screen.getByLabelText("Microsoft Chat 1")).not.toBeChecked();
    expect(screen.getByLabelText("Google Space A")).not.toBeChecked();
    expect(chatSelectAll).not.toBeChecked();
  });

  it('should update source "Select All" checkbox when individual items are toggled', async () => {
    renderDataSourceSelector();
    await waitFor(() => screen.getByText("Microsoft Chat 1"));

    const chatSelectAll = screen.getByLabelText(
      `Select all ${DataSourceNames.CHAT}`,
    );
    expect(chatSelectAll).not.toBeChecked();

    fireEvent.click(screen.getByLabelText("Microsoft Chat 1"));
    fireEvent.click(screen.getByLabelText("Microsoft Chat 2"));
    fireEvent.click(screen.getByLabelText("Google Space A"));
    fireEvent.click(screen.getByLabelText("Google Space B"));

    await waitFor(() => {
      expect(chatSelectAll).toBeChecked(); // All items selected, so source select all should be checked
    });

    fireEvent.click(screen.getByLabelText("Microsoft Chat 1")); // Deselect one item
    await waitFor(() => {
      expect(chatSelectAll).not.toBeChecked(); // Source select all should now be unchecked
    });
  });

  it('should toggle global "Select All" across all data sources', async () => {
    renderDataSourceSelector();
    await waitFor(() => screen.getByText("Microsoft Chat 1"));

    const globalSelectAll = screen.getByLabelText(
      "Select all items across all sources",
    );
    expect(globalSelectAll).not.toBeChecked();

    fireEvent.click(globalSelectAll); // Select all globally

    await waitFor(() => {
      // Verify chat items are selected
      expect(screen.getByLabelText("Microsoft Chat 1")).toBeChecked();
      expect(screen.getByLabelText("Google Space A")).toBeChecked();
      expect(globalSelectAll).toBeChecked();
    });

    // Switch to other sources and verify items are selected
    fireEvent.click(screen.getByText(DataSourceNames.JIRA));
    expect(screen.getByLabelText("Jira Project Alpha")).toBeChecked();
    expect(screen.getByLabelText("Jira Project Beta")).toBeChecked();

    fireEvent.click(screen.getByText(DataSourceNames.GERRIT));
    expect(screen.getByLabelText("gerrit/project/foo")).toBeChecked();
    expect(screen.getByLabelText("gerrit/project/bar")).toBeChecked();

    fireEvent.click(screen.getByText(DataSourceNames.CALENDAR));
    expect(screen.getByLabelText("My Personal Calendar")).toBeChecked();
    expect(screen.getByLabelText("Team Events")).toBeChecked();

    fireEvent.click(globalSelectAll); // Deselect all globally

    await waitFor(() => {
      expect(globalSelectAll).not.toBeChecked();
    });

    fireEvent.click(screen.getByText(DataSourceNames.CHAT));
    expect(screen.getByLabelText("Microsoft Chat 1")).not.toBeChecked();
    expect(screen.getByLabelText("Google Space A")).not.toBeChecked();

    fireEvent.click(screen.getByText(DataSourceNames.JIRA));
    expect(screen.getByLabelText("Jira Project Alpha")).not.toBeChecked();
  });

  it("should call onConfirm with the correct payload when OK is clicked", async () => {
    renderDataSourceSelector();
    await waitFor(() => screen.getByText("Microsoft Chat 1"));

    fireEvent.click(screen.getByLabelText("Microsoft Chat 1"));
    fireEvent.click(screen.getByLabelText("Google Space B"));

    fireEvent.click(screen.getByText(DataSourceNames.JIRA));
    fireEvent.click(screen.getByLabelText("Jira Project Alpha"));

    fireEvent.click(screen.getByText(DataSourceNames.GERRIT));
    fireEvent.click(screen.getByLabelText("gerrit/project/bar"));

    fireEvent.click(screen.getByText(DataSourceNames.CALENDAR));
    fireEvent.click(screen.getByLabelText("My Personal Calendar"));

    fireEvent.click(screen.getByRole("button", { name: "OK" }));

    await waitFor(() => {
      expect(onConfirmMock).toHaveBeenCalledTimes(1);
      expect(onConfirmMock).toHaveBeenCalledWith({
        Chat: [
          {
            id: "ms-chat-1",
            name: "Microsoft Chat 1",
            provider: ChatProvider.Microsoft,
          },
          {
            id: "gc-space-2",
            name: "Google Space B",
            provider: ChatProvider.Google,
          },
        ],
        Jira: ["JIRA1"],
        Gerrit: {
          projectList: ["gerrit/project/bar"],
          includeAllProjects: false,
        },
        Calendar: ["cal-1"],
      });
    });
  });

  it("should call onCancel when Cancel is clicked", async () => {
    renderDataSourceSelector();
    await waitFor(() => screen.getByText("Microsoft Chat 1"));

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onCancelMock).toHaveBeenCalledTimes(1);
  });

  it("should handle empty data sources gracefully", async () => {
    getMicrosoftChatTopics.mockResolvedValue({ data: {} });
    getGoogleChatSpaces.mockResolvedValue({ data: {} });
    getJiraProjects.mockResolvedValue({ data: {} });
    getGerritProjects.mockResolvedValue({ data: [] });
    getGoogleCalendars.mockResolvedValue({ data: [] });

    renderDataSourceSelector();

    await waitFor(() => {
      // Data sources should still be listed in the sidebar
      expect(screen.getByText(DataSourceNames.CHAT)).toBeInTheDocument();
      expect(screen.getByText(DataSourceNames.JIRA)).toBeInTheDocument();
    });

    // No chat items should be visible
    expect(screen.queryByText("Microsoft Chat 1")).not.toBeInTheDocument();

    const globalSelectAll = screen.getByLabelText(
      "Select all items across all sources",
    );

    // Global "Select All" should not be checked if there are no selectable items
    expect(globalSelectAll).not.toBeChecked();

    fireEvent.click(globalSelectAll); // Try to select all

    await waitFor(() => {
      expect(globalSelectAll).not.toBeChecked(); // Should still be unchecked as there are no items
    });

    fireEvent.click(screen.getByRole("button", { name: "OK" }));

    await waitFor(() => {
      expect(onConfirmMock).toHaveBeenCalledWith({
        Chat: [],
        Jira: [],
        Gerrit: { projectList: [], includeAllProjects: false },
        Calendar: [],
      });
    });
  });

  it("should clear all temporary selections when Cancel is clicked and reset the state for next open", async () => {
    // Initial render and perform selections
    const { rerender } = renderDataSourceSelector();
    await waitFor(() => screen.getByText("Microsoft Chat 1"));

    fireEvent.click(screen.getByLabelText("Microsoft Chat 1"));
    fireEvent.click(screen.getByLabelText("Google Space A"));

    fireEvent.click(screen.getByText(DataSourceNames.JIRA));
    await waitFor(() => screen.getByText("Jira Project Alpha"));
    fireEvent.click(screen.getByLabelText("Jira Project Alpha"));

    // Verify items were selected
    expect(screen.getByLabelText("Jira Project Alpha")).toBeChecked();

    // Click Cancel
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    // Verify onCancel was called (modal closed)
    expect(onCancelMock).toHaveBeenCalledTimes(1);

    rerender(
      <DataSourceSelector
        isOpen={false}
        onConfirm={onConfirmMock}
        onCancel={onCancelMock}
      />,
    );
    expect(screen.queryByText("Microsoft Chat 1")).not.toBeInTheDocument();

    // Re-open the modal
    rerender(
      <DataSourceSelector
        isOpen={true}
        onConfirm={onConfirmMock}
        onCancel={onCancelMock}
      />,
    );
    await waitFor(() => screen.getByText("Microsoft Chat 1"));

    // Verify all items are unselected (state has been reset)

    expect(screen.getByLabelText("Microsoft Chat 1")).not.toBeChecked();
    expect(screen.getByLabelText("Google Space A")).not.toBeChecked();

    fireEvent.click(screen.getByText(DataSourceNames.JIRA));
    await waitFor(() => screen.getByText("Jira Project Alpha"));
    expect(screen.getByLabelText("Jira Project Alpha")).not.toBeChecked();
  });
});
