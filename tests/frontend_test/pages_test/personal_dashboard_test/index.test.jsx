import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import PersonalDashboard from "@/pages/PersonalDashboard";
import { useMentorshipData } from "@/pages/PersonalDashboard/hooks/useMentorshipData";
import { useAuth } from "@/context/auth";
import { useWorkActivityData } from "@/pages/PersonalDashboard/hooks/useWorkActivityData";
import { USER_ROLES } from "@/constants/UserRoles";

vi.mock("@/pages/PersonalDashboard/components/MentorshipInfoBanner", () => ({
  default: vi.fn(({ registration, isRegistrationOpen }) => (
    <div data-testid="mock-banner">
      Banner - {isRegistrationOpen ? "Open" : "Closed"} - {registration?.status}
    </div>
  )),
}));

vi.mock("@/pages/PersonalDashboard/hooks/useMentorshipData", () => ({
  useMentorshipData: vi.fn(),
}));

vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/pages/PersonalDashboard/hooks/useWorkActivityData", () => ({
  useWorkActivityData: vi.fn(),
}));

vi.mock("@/pages/PersonalDashboard/components/WorkActivityDataCard", () => ({
  WorkActivityDataCard: (props) => (
    <div data-testid="work-activity-card">
      <button disabled={props.isLoading}>Mock Work Card</button>
    </div>
  ),
}));

describe("PersonalDashboard", () => {
  const mockHookData = {
    registration: { id: "reg-1", status: "PENDING" },
    isRegistrationOpen: true,
    isFeedbackEnabled: false,
    saveRegistration: vi.fn(),
    pastPartners: [],
    isPartnersLoading: false,
    loadPastPartners: vi.fn(),
    isLoading: false,
  };

  const defaultWorkActivityMock = {
    summary: {},
    isPersonalSummaryLoading: false,
    fetchPersonalSummary: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    useMentorshipData.mockReturnValue(mockHookData);
    useWorkActivityData.mockReturnValue(defaultWorkActivityMock);
    useAuth.mockReturnValue({ roles: [] });
  });

  it("renders the welcome header", () => {
    render(<PersonalDashboard />);

    expect(screen.getByText("Welcome")).toBeInTheDocument();
  });

  it("renders the clapping hands emoji", () => {
    render(<PersonalDashboard />);

    const emoji = screen.getByRole("img", {
      name: /clapping hands/i,
    });

    expect(emoji).toBeInTheDocument();
  });

  it("renders the welcome header layout container", () => {
    render(<PersonalDashboard />);

    const header = screen.getByText("Welcome").closest("div");
    expect(header).toBeTruthy();
  });

  it("passes hook data to MentorshipInfoBanner", () => {
    useMentorshipData.mockReturnValue({
      ...mockHookData,
      isRegistrationOpen: true,
      registration: { status: "SUCCESS" },
    });

    render(<PersonalDashboard />);

    // Verify that the mocked child component received the correct props
    // and rendered the expected content
    const banner = screen.getByTestId("mock-banner");
    expect(banner.innerHTML).toContain("Open");
    expect(banner.innerHTML).toContain("SUCCESS");
  });

  it("passes the correct state to the banner when registration is closed", () => {
    useMentorshipData.mockReturnValue({
      ...mockHookData,
      isRegistrationOpen: false,
      registration: null,
    });

    render(<PersonalDashboard />);

    const banner = screen.getByTestId("mock-banner");
    expect(banner.innerHTML).toContain("Closed");
  });

  it("keeps the layout structure intact even when data is loading", () => {
    useMentorshipData.mockReturnValue({
      ...mockHookData,
      isLoading: true, // simulate loading state
    });

    render(<PersonalDashboard />);

    // The welcome header should still be rendered
    expect(screen.getByText("Welcome")).toBeDefined();
    // The banner should still be rendered
    expect(screen.getByTestId("mock-banner")).toBeDefined();
  });

  it("shows work activity card for internal users", () => {
    useAuth.mockReturnValue({
      roles: [USER_ROLES.CC_INTERNAL],
    });

    useWorkActivityData.mockReturnValue({
      summary: {},
      isPersonalSummaryLoading: false,
      fetchPersonalSummary: vi.fn(),
    });

    render(<PersonalDashboard />);

    expect(screen.getByTestId("work-activity-card")).toBeInTheDocument();
  });

  it("does not show work activity card for non internal users", () => {
    useAuth.mockReturnValue({
      roles: [],
    });

    useWorkActivityData.mockReturnValue({
      summary: {},
      isPersonalSummaryLoading: false,
      fetchPersonalSummary: vi.fn(),
    });

    render(<PersonalDashboard />);

    expect(screen.queryByTestId("work-activity-card")).toBeNull();
  });

  it("disables work activity card search button while loading for internal users", () => {
    useAuth.mockReturnValue({
      roles: [USER_ROLES.CC_INTERNAL],
    });

    useWorkActivityData.mockReturnValue({
      summary: {},
      isPersonalSummaryLoading: true,
      fetchPersonalSummary: vi.fn(),
    });

    render(<PersonalDashboard />);

    const button = screen.getByRole("button");

    expect(button).toBeDisabled();
  });
});
