import { useState } from "react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";
import DataSearch from "@/pages/DataSearch.jsx";
import Tab from "@/components/common/Tab.jsx";

/**
 * Mock MemberSelector:
 * - Renders a simple dialog when open=true
 * - Calls onSelectedChange to push ids live
 * - Calls props.onClose() on OK/Cancel to emulate real component
 */
vi.mock("@/components/common/MemberSelector", () => {
  return {
    __esModule: true,
    default: function MockMemberSelector(props) {
      const {
        open,
        onClose,
        selectedIds = [],
        onSelectedChange,
        onConfirm,
        onCancel,
      } = props;

      if (!open) return null;

      return (
        <div role="dialog" aria-modal="true">
          <div>
            <input placeholder="Search by LDAP or full name" />
          </div>
          <div data-testid="ms-selected">Selected: {selectedIds.length}</div>

          <button
            type="button"
            onClick={() =>
              onSelectedChange?.([...selectedIds, "alice"] /* , members */)
            }
          >
            Add One
          </button>

          <button
            type="button"
            onClick={() => {
              onConfirm?.(selectedIds /* , members */);
              onClose?.();
            }}
          >
            OK
          </button>

          <button
            type="button"
            onClick={() => {
              onCancel?.();
              onClose?.();
            }}
          >
            Cancel
          </button>
        </div>
      );
    },
  };
});

vi.mock("@/components/common/DateRangePicker", () => {
  return {
    __esModule: true,
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
            value={startDate}
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

vi.mock("@/components/common/DataSourceSelector", () => {
  return {
    __esModule: true,
    DataSourceSelector: vi.fn(({ isOpen, onConfirm, onCancel }) => {
      if (!isOpen) return null;
      return (
        <div
          role="dialog"
          aria-modal="true"
          data-testid="mock-data-source-selector"
        >
          <h2>Select Data Source</h2>
          <button onClick={() => onConfirm("mockDataSourceSelection")}>
            Confirm Selection
          </button>
          <button onClick={onCancel}>Cancel</button>
        </div>
      );
    }),
  };
});

vi.mock("@/components/common/Tab.jsx", () => {
  return {
    __esModule: true,
    default: vi.fn(({ committedSearchParams }) => (
      <div data-testid="mock-tab-component">
        <h3>Tab Content</h3>
        <pre data-testid="tab-params">
          {JSON.stringify(committedSearchParams, null, 2)}
        </pre>
      </div>
    )),
  };
});

describe("DataSearch page", () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("updates date range via DateRangePicker mock", async () => {
    render(<DataSearch />);
    const startDateInput = screen.getByTestId("start-date-input");
    const endDateInput = screen.getByTestId("end-date-input");

    const newStartDate = "2024-10-01";
    const newEndDate = "2025-09-19";

    await user.clear(startDateInput);
    await user.type(startDateInput, newStartDate);
    expect(startDateInput).toHaveValue(newStartDate);

    await user.clear(endDateInput);
    await user.type(endDateInput, newEndDate);
    expect(endDateInput).toHaveValue(newEndDate);
  });

  it("opens modal when clicking the LDAP chip", async () => {
    render(<DataSearch />);

    await user.click(screen.getByRole("button", { name: /ldap/i }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByPlaceholderText(/search by ldap or full name/i),
    ).toBeInTheDocument();
    expect(within(dialog).getByTestId("ms-selected")).toHaveTextContent(
      "Selected: 0",
    );
  });

  it("updates chip count live via onSelectedChange (controlled)", async () => {
    render(<DataSearch />);

    await user.click(screen.getByRole("button", { name: /ldap/i }));
    const dialog = await screen.findByRole("dialog");

    await user.click(within(dialog).getByRole("button", { name: /add one/i }));

    expect(
      screen.getByRole("button", { name: /ldap \(1\)/i }),
    ).toBeInTheDocument();
    expect(within(dialog).getByTestId("ms-selected")).toHaveTextContent(
      "Selected: 1",
    );
  });

  it("onConfirm closes the modal and keeps the confirmed selection", async () => {
    render(<DataSearch />);

    await user.click(screen.getByRole("button", { name: /ldap/i }));
    let dialog = await screen.findByRole("dialog");

    await user.click(within(dialog).getByRole("button", { name: /add one/i }));
    expect(
      screen.getByRole("button", { name: /ldap \(1\)/i }),
    ).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: /^ok$/i }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /ldap \(1\)/i }),
    ).toBeInTheDocument();
  });

  it("reopening the modal shows the previous selection (controlled)", async () => {
    render(<DataSearch />);

    await user.click(screen.getByRole("button", { name: /ldap/i }));
    let dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /add one/i }));
    await user.click(within(dialog).getByRole("button", { name: /^ok$/i }));

    await user.click(screen.getByRole("button", { name: /ldap \(1\)/i }));
    dialog = await screen.findByRole("dialog");

    expect(within(dialog).getByTestId("ms-selected")).toHaveTextContent(
      "Selected: 1",
    );
  });

  it("cancel closes the modal; chip stays on current controlled value", async () => {
    render(<DataSearch />);

    await user.click(screen.getByRole("button", { name: /ldap/i }));
    let dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /add one/i }));

    await user.click(within(dialog).getByRole("button", { name: /cancel/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: /ldap \(1\)/i }),
    ).toBeInTheDocument();
  });

  it("opens modal when clicking the Data Source chip", async () => {
    render(<DataSearch />);
    await user.click(screen.getByRole("button", { name: /data source/i }));
    expect(
      await screen.findByTestId("mock-data-source-selector"),
    ).toBeInTheDocument();
    expect(screen.getByText("Select Data Source")).toBeInTheDocument();
  });

  it("onConfirmSelection closes the modal and effectively keeps the confirmed selection", async () => {
    render(<DataSearch />);
    await user.click(screen.getByRole("button", { name: /data source/i }));
    const dataSourceDialog = await screen.findByTestId(
      "mock-data-source-selector",
    );
    await user.click(
      within(dataSourceDialog).getByRole("button", {
        name: /confirm selection/i,
      }),
    );
    expect(
      screen.queryByTestId("mock-data-source-selector"),
    ).not.toBeInTheDocument();
  });

  it("onCancelSelection closes the modal and resets selectedData to null", async () => {
    render(<DataSearch />);
    // First, select a data source
    await user.click(screen.getByRole("button", { name: /data source/i }));
    let dataSourceDialog = await screen.findByTestId(
      "mock-data-source-selector",
    );
    await user.click(
      within(dataSourceDialog).getByRole("button", {
        name: /confirm selection/i,
      }),
    );
    expect(
      screen.queryByTestId("mock-data-source-selector"),
    ).not.toBeInTheDocument();

    // Reopen and cancel
    await user.click(screen.getByRole("button", { name: /data source/i }));
    dataSourceDialog = await screen.findByTestId("mock-data-source-selector");
    await user.click(
      within(dataSourceDialog).getByRole("button", { name: /cancel/i }),
    );
    expect(
      screen.queryByTestId("mock-data-source-selector"),
    ).not.toBeInTheDocument();
    // The effect of selectedData being null will be verified by a failed search attempt.
  });

  it("Search button shows Tab component with committed params when all fields are present", async () => {
    render(<DataSearch />);
    // 1. Select LDAP
    await user.click(screen.getByRole("button", { name: /ldap/i }));
    const ldapDialog = await screen.findByRole("dialog");
    await user.click(
      within(ldapDialog).getByRole("button", { name: /add one/i }),
    );
    await user.click(within(ldapDialog).getByRole("button", { name: /^ok$/i }));
    expect(
      screen.getByRole("button", { name: /ldap \(1\)/i }),
    ).toBeInTheDocument();

    // 2. Select Date Range
    const startDateInput = screen.getByTestId("start-date-input");
    const endDateInput = screen.getByTestId("end-date-input");
    await user.clear(startDateInput);
    await user.type(startDateInput, "2024-01-01");
    await user.clear(endDateInput);
    await user.type(endDateInput, "2024-01-31");

    // 3. Select Data Source
    await user.click(screen.getByRole("button", { name: /data source/i }));
    const dataSourceDialog = await screen.findByTestId(
      "mock-data-source-selector",
    );
    await user.click(
      within(dataSourceDialog).getByRole("button", {
        name: /confirm selection/i,
      }),
    );

    // 4. Click Search
    await user.click(screen.getByRole("button", { name: /search/i }));

    // Verify Tab is shown and received correct params
    const tabComponent = await screen.findByTestId("mock-tab-component");
    expect(tabComponent).toBeInTheDocument();
    expect(vi.mocked(Tab)).toHaveBeenCalledWith(
      expect.objectContaining({
        committedSearchParams: {
          ldaps: ["alice"],
          startDate: "2024-01-01",
          endDate: "2024-01-31",
          selectedDataSources: "mockDataSourceSelection",
        },
      }),
      undefined,
    );
  });

  it("Changing a filter after search resets the Tab component (hides it)", async () => {
    render(<DataSearch />);

    // 1. Complete a successful search
    // Select LDAP
    await user.click(screen.getByRole("button", { name: /ldap/i }));
    const ldapDialog = await screen.findByRole("dialog");
    await user.click(
      within(ldapDialog).getByRole("button", { name: /add one/i }),
    );
    await user.click(within(ldapDialog).getByRole("button", { name: /^ok$/i }));

    // Select Date Range
    const startDateInput = screen.getByTestId("start-date-input");
    const endDateInput = screen.getByTestId("end-date-input");
    await user.clear(startDateInput);
    await user.type(startDateInput, "2024-01-01");
    await user.clear(endDateInput);
    await user.type(endDateInput, "2024-01-31");

    // Select Data Source
    await user.click(screen.getByRole("button", { name: /data source/i }));
    const dataSourceDialog = await screen.findByTestId(
      "mock-data-source-selector",
    );
    await user.click(
      within(dataSourceDialog).getByRole("button", {
        name: /confirm selection/i,
      }),
    );

    // Click Search
    await user.click(screen.getByRole("button", { name: /search/i }));

    // Verify Tab is initially shown
    expect(await screen.findByTestId("mock-tab-component")).toBeInTheDocument();

    // 2. Change one of the filter criteria (e.g., add another LDAP)
    await user.click(screen.getByRole("button", { name: /ldap \(1\)/i })); // Reopen LDAP selector
    const updatedLdapDialog = await screen.findByRole("dialog");
    await user.click(
      within(updatedLdapDialog).getByRole("button", { name: /add one/i }),
    ); // Add another LDAP
    await user.click(
      within(updatedLdapDialog).getByRole("button", { name: /^ok$/i }),
    ); // Confirm

    // Verify Tab component is no longer in the document
    await waitFor(() => {
      expect(
        screen.queryByTestId("mock-tab-component"),
      ).not.toBeInTheDocument();
    });

    // Test for changing date (resetting state for a new search)
    await user.click(screen.getByRole("button", { name: /search/i })); // Re-trigger search to show tab
    expect(await screen.findByTestId("mock-tab-component")).toBeInTheDocument();
    await user.clear(startDateInput);
    await user.type(startDateInput, "2024-02-01"); // Change start date
    await waitFor(() => {
      expect(
        screen.queryByTestId("mock-tab-component"),
      ).not.toBeInTheDocument();
    });

    // Test for changing data source (resetting state for a new search)
    await user.click(screen.getByRole("button", { name: /search/i })); // Re-trigger search to show tab
    expect(await screen.findByTestId("mock-tab-component")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /data source/i })); // Open data source selector
    const newDataSourceDialog = await screen.findByTestId(
      "mock-data-source-selector",
    );
    await user.click(
      within(newDataSourceDialog).getByRole("button", { name: /cancel/i }),
    ); // Cancel selection, resetting selectedData to null

    await waitFor(() => {
      expect(
        screen.queryByTestId("mock-tab-component"),
      ).not.toBeInTheDocument();
    });
  });
});
