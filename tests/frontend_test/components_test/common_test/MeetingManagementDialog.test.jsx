import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import MeetingManagementDialog from "@/components/common/MeetingManagementDialog";
import { useMeetingManagement } from "@/pages/PersonalDashboard/hooks/useMeetingManagement";

vi.mock("@/pages/PersonalDashboard/hooks/useMeetingManagement", () => ({
  useMeetingManagement: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock TimezoneSelector to simplify option interaction in JSDOM
vi.mock("@/components/common/TimezoneSelector", () => ({
  default: ({ value, onChange }) => (
    <select
      data-testid="timezone-selector"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="America/New_York">America/New_York</option>
      <option value="Asia/Shanghai">Asia/Shanghai</option>
    </select>
  ),
}));

// Mock static datasets
const mockPartners = new Map([
  [
    1,
    {
      id: 1,
      name: "John Doe",
      preferredName: "Johnny",
      email: "john@test.com",
    },
  ],
  [
    2,
    { id: 2, name: "Alice Smith", preferredName: "", email: "alice@test.com" },
  ],
]);

const mockBookMeeting = vi.fn();

describe("MeetingManagementDialog Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default hook state setup
    useMeetingManagement.mockReturnValue({
      partners: mockPartners,
      bookMeeting: mockBookMeeting,
      isLoading: false,
    });
  });

  it("should disable the button and show correct tooltip when roundId is invalid", () => {
    const { rerender } = render(<MeetingManagementDialog roundId={null} />);

    const triggerButton = screen.getByRole("button", {
      name: /manage meetings/i,
    });
    expect(triggerButton).toBeDisabled();

    const wrapperDiv = triggerButton.closest("div");
    expect(wrapperDiv).toHaveAttribute("title", "No active mentorship round");

    // Re-render with valid roundId to verify enablement
    rerender(<MeetingManagementDialog roundId={2} />);
    expect(
      screen.getByRole("button", { name: /manage meetings/i }),
    ).not.toBeDisabled();
  });

  it("should open the dialog and switch tabs correctly when interactions occur", async () => {
    render(<MeetingManagementDialog roundId={2} />);

    const triggerButton = screen.getByRole("button", {
      name: /manage meetings/i,
    });
    await userEvent.click(triggerButton);

    // Verify dialog header text and default scheduling fields are active
    expect(screen.getByText("Meeting Management")).toBeInTheDocument();

    const partnerSelect = document.querySelector('select[name="partnerId"]');
    expect(partnerSelect).toBeInTheDocument();

    // Switch to the 'Upcoming' tab
    const upcomingTab = screen.getByRole("tab", { name: /upcoming/i });
    await userEvent.click(upcomingTab);

    // Verify the empty state placeholder text is visible
    expect(screen.getByText("No upcoming meetings found")).toBeInTheDocument();
  });

  it("should handle submission validation if required fields are missing", async () => {
    render(<MeetingManagementDialog roundId={2} />);

    // Open Dialog
    await userEvent.click(
      screen.getByRole("button", { name: /manage meetings/i }),
    );

    const scheduleTab = screen.getByRole("tab", { name: /schedule meeting/i });
    await userEvent.click(scheduleTab);

    const form = screen.getByRole("dialog").querySelector("form");
    if (!form) throw new Error("Form still not found in DOM");
    fireEvent.submit(form);

    expect(mockBookMeeting).not.toHaveBeenCalled();
  });

  it("should reset form data with a 200ms delay after the dialog is closed", async () => {
    render(<MeetingManagementDialog roundId={2} />);

    await userEvent.click(
      screen.getByRole("button", { name: /manage meetings/i }),
    );

    let partnerSelect = screen.getByRole("combobox", {
      name: /select partner/i,
    });
    await userEvent.selectOptions(partnerSelect, "1");

    fireEvent.keyDown(document.activeElement || document.body, {
      key: "Escape",
      code: "Escape",
    });
    await new Promise((resolve) => setTimeout(resolve, 250));

    await userEvent.click(
      screen.getByRole("button", { name: /manage meetings/i }),
    );

    const refreshedPartnerSelect = screen.getByRole("combobox", {
      name: /select partner/i,
    });
    expect(refreshedPartnerSelect.value).toBe("");
  });
});
