import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AuditTab from "@/pages/AdminPermissions/components/AuditTab";
import * as api from "@/api/adminPermissionsApi";

vi.mock("@/api/adminPermissionsApi");

const catalog = ["permission.manage"];

beforeEach(() => {
  vi.clearAllMocks();
  api.getAuditLog.mockResolvedValue({
    data: {
      entries: [
        {
          id: 1,
          userId: 5,
          permissionName: "permission.manage",
          grantedSource: "manual",
          grantedBy: 9,
          grantedTimestamp: "2026-06-01T00:00:00Z",
          revokedTimestamp: null,
          isActive: true,
        },
        {
          id: 2,
          userId: 7,
          permissionName: "*",
          grantedSource: "manual",
          grantedBy: 9,
          grantedTimestamp: "2026-06-02T00:00:00Z",
          revokedTimestamp: null,
          isActive: true,
        },
      ],
      total: 2,
    },
  });
});

describe("AuditTab", () => {
  it("does not fetch on mount and shows the empty prompt until Search", async () => {
    render(<AuditTab catalog={catalog} />);
    await act(async () => {});
    expect(api.getAuditLog).not.toHaveBeenCalled();
    expect(
      screen.getByText("Set filters and click Search to load the audit log."),
    ).toBeInTheDocument();
  });

  it("renders audit rows from the feed after clicking Search", async () => {
    const user = userEvent.setup();
    render(<AuditTab catalog={catalog} />);
    await user.click(screen.getByRole("button", { name: "Search" }));
    // findByText waits for the async fetch to resolve and the rows to render
    // (the table shows "Loading…" until then) — avoids a flaky race where the
    // assertion runs while loading is still true.
    expect(await screen.findByText("permission.manage")).toBeInTheDocument();
    expect(screen.getAllByText("granted").length).toBeGreaterThan(0);
  });

  it("renders the '*' permission row as 'Super-admin', not a literal '*'", async () => {
    const user = userEvent.setup();
    render(<AuditTab catalog={catalog} />);
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(await screen.findByText("Super-admin")).toBeInTheDocument();
    expect(screen.queryByText("*")).toBeNull();
  });
});
