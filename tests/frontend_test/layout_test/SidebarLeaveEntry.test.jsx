import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import Sidebar from "@/components/layout/Sidebar";
import { useAuth } from "@/context/auth";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { PERMISSIONS } from "@/constants/Permissions";

vi.mock("@/context/auth", () => ({ useAuth: vi.fn() }));
vi.mock("@/hooks/useFeatureFlags", () => ({ useFeatureFlags: vi.fn() }));

const renderSidebar = () =>
  render(
    <MemoryRouter>
      <Sidebar />
    </MemoryRouter>,
  );

describe("Sidebar leave administration entry", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ permissions: [PERMISSIONS.LEAVE_ADMIN] });
    useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.LEAVE_MANAGEMENT]: true });
  });

  it("is shown to somebody who administers leave", () => {
    renderSidebar();

    expect(screen.getByText("Leave Administration")).toBeInTheDocument();
  });

  it("is hidden while the feature is switched off", () => {
    // Both are needed: the permission to use it, and the flag that says the
    // feature exists at all.
    useFeatureFlags.mockReturnValue({});

    renderSidebar();

    expect(screen.queryByText("Leave Administration")).not.toBeInTheDocument();
  });

  it("is hidden from somebody without the permission", () => {
    useAuth.mockReturnValue({ permissions: [] });

    renderSidebar();

    expect(screen.queryByText("Leave Administration")).not.toBeInTheDocument();
  });

  it("keeps the employee-facing leave screens out of the sidebar", () => {
    // Whether leave applies to somebody is not a permission, and this sidebar
    // is driven entirely by permissions -- so those entries live on the
    // dashboard instead.
    renderSidebar();

    expect(screen.queryByText("Time off")).not.toBeInTheDocument();
    expect(screen.queryByText("Leave Approvals")).not.toBeInTheDocument();
    expect(screen.queryByText("Leave Balances")).not.toBeInTheDocument();
  });
});
