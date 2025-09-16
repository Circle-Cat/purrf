import { useState } from "react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

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

import DataSearch from "@/pages/DataSearch.jsx";

describe("DataSearch page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("updates date range via DateRangePicker mock", () => {
    render(<DataSearch />);
    const startDateInput = screen.getByTestId("start-date-input");
    const endDateInput = screen.getByTestId("end-date-input");

    const newStartDate = "2024-10-01";
    const newEndDate = "2025-09-19";

    fireEvent.change(startDateInput, { target: { value: newStartDate } });
    expect(startDateInput.value).toBe(newStartDate);

    fireEvent.change(endDateInput, { target: { value: newEndDate } });
    expect(endDateInput.value).toBe(newEndDate);
  });

  it("opens modal when clicking the LDAP chip", async () => {
    const user = userEvent.setup();
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
    const user = userEvent.setup();
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
    const user = userEvent.setup();
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
    const user = userEvent.setup();
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
    const user = userEvent.setup();
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
});
