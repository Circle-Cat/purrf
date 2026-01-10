import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import MultipleSelector from "@/components/common/MultipleSelector";

// Mock ResizeObserver (required by Radix UI components)
globalThis.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// Mock PointerEvent for environments where it is not available
if (!globalThis.PointerEvent) {
  class PointerEvent extends MouseEvent {
    constructor(type, props) {
      super(type, props);
      this.pointerId = props.pointerId || 0;
      this.pointerType = props.pointerType || "mouse";
    }
  }
  globalThis.PointerEvent = PointerEvent;
}

// 2. Mock scrollIntoView (required by cmdk / Command library)
window.HTMLElement.prototype.scrollIntoView = vi.fn();

describe("MultipleSelector component", () => {
  const mockOptions = [
    { id: 1, name: "Alice", category: "Recent" },
    { id: 2, name: "Bob", category: "Recent" },
    { id: 3, name: "Charlie", category: "Earlier" },
  ];

  const defaultProps = {
    options: mockOptions,
    value: [],
    onChange: vi.fn(),
    placeholder: "Select partners...",
  };

  let user;

  beforeEach(() => {
    vi.clearAllMocks();
    // Initialize userEvent for each test
    user = userEvent.setup();
  });

  // Helper: get the main trigger button
  // (exclude badge remove buttons and clear-all button)
  const getMainTrigger = () => screen.getByLabelText("select-trigger");

  // --- 1. Basic rendering ---
  it("should display placeholder text when no value is selected", () => {
    render(<MultipleSelector {...defaultProps} />);
    expect(screen.getByText("Select partners...")).toBeInTheDocument();
  });

  it("should render selected item badges and corresponding remove buttons", () => {
    const selected = [mockOptions[0]]; // Alice selected
    render(<MultipleSelector {...defaultProps} value={selected} />);

    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByLabelText("Remove Alice")).toBeInTheDocument();
  });

  // --- 2. Interaction behavior ---
  it("should call onChange when clicking an option to add it", async () => {
    const onChange = vi.fn();
    render(<MultipleSelector {...defaultProps} onChange={onChange} />);

    await user.click(getMainTrigger());
    await user.click(screen.getByText("Bob"));

    expect(onChange).toHaveBeenCalledWith([
      { id: 2, name: "Bob", category: "Recent" },
    ]);
  });

  it("should remove an item when clicking the badge remove button", async () => {
    const onChange = vi.fn();
    const selected = [mockOptions[0]];

    render(
      <MultipleSelector
        {...defaultProps}
        value={selected}
        onChange={onChange}
      />,
    );

    const removeBtn = screen.getByLabelText("Remove Alice");
    await user.click(removeBtn);

    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("should clear all selections when clicking the clear-all button", async () => {
    const onChange = vi.fn();
    const selected = [{ id: 1, name: "Alice" }];

    render(
      <MultipleSelector
        {...defaultProps}
        value={selected}
        onChange={onChange}
      />,
    );

    const clearAllBtn = screen.getByLabelText("Clear all selections");
    await user.click(clearAllBtn);

    expect(onChange).toHaveBeenCalledWith([]);
  });

  // --- 3. maxSelected constraint ---
  it("should prevent selection beyond maxSelected and trigger onMaxSelected", async () => {
    const onMaxSelected = vi.fn();
    const onChange = vi.fn();
    const selected = [mockOptions[0]];

    render(
      <MultipleSelector
        {...defaultProps}
        value={selected}
        maxSelected={1}
        onChange={onChange}
        onMaxSelected={onMaxSelected}
      />,
    );

    await user.click(getMainTrigger());
    const optionBob = await screen.findByText("Bob");
    await user.click(optionBob);

    expect(onMaxSelected).toHaveBeenCalledWith(1);
    expect(onChange).not.toHaveBeenCalled();
  });

  // --- 4. Grouping behavior ---
  it("should render grouped options and support select-group action", async () => {
    const onChange = vi.fn();

    render(
      <MultipleSelector
        {...defaultProps}
        groupBy="category"
        onChange={onChange}
      />,
    );

    await user.click(getMainTrigger());

    expect(screen.getByText("Recent")).toBeInTheDocument();

    const recentGroup = screen.getByText("Recent").closest("div");
    const selectGroupBtn = within(recentGroup).getByText("Select Group");
    await user.click(selectGroupBtn);

    expect(onChange).toHaveBeenCalledWith([
      { id: 1, name: "Alice", category: "Recent" },
      { id: 2, name: "Bob", category: "Recent" },
    ]);
  });

  // --- 5. Select all / deselect all ---
  it("should select all options and then deselect all", async () => {
    const onChange = vi.fn();

    const { rerender } = render(
      <MultipleSelector
        {...defaultProps}
        showSelectAll={true}
        onChange={onChange}
      />,
    );

    // Step 1: select all
    await user.click(getMainTrigger());
    const selectAllBtn = await screen.findByText("Select All");
    await user.click(selectAllBtn);

    expect(onChange).toHaveBeenCalledWith(mockOptions);

    // Step 2: rerender with all options selected
    rerender(
      <MultipleSelector
        {...defaultProps}
        showSelectAll={true}
        value={mockOptions}
        onChange={onChange}
      />,
    );

    // Step 3: deselect all
    const trigger = getMainTrigger();
    if (trigger.getAttribute("data-state") === "closed") {
      await user.click(trigger);
    }

    const deselectBtn = await screen.findByText("Deselect All");
    await user.click(deselectBtn);

    expect(onChange).toHaveBeenLastCalledWith([]);
  });

  // --- 6. Search behavior ---
  it("should filter options based on search input", async () => {
    render(<MultipleSelector {...defaultProps} />);

    await user.click(getMainTrigger());
    const input = await screen.findByPlaceholderText("Search...");

    await user.type(input, "Ali");

    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.queryByText("Bob")).not.toBeInTheDocument();
  });

  // --- 7. Disabled state ---
  it("should not respond to interactions when disabled", async () => {
    render(<MultipleSelector {...defaultProps} disabled={true} />);

    const trigger = getMainTrigger();
    expect(trigger).toBeDisabled();

    await user.click(trigger);
    expect(screen.queryByPlaceholderText("Search...")).not.toBeInTheDocument();
  });
});
