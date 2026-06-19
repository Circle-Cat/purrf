import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
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
  it("renders audit rows from the feed", async () => {
    render(<AuditTab catalog={catalog} />);
    // findByText waits for the async fetch to resolve and the rows to render
    // (the table shows "Loading…" until then) — avoids a flaky race where the
    // assertion runs while loading is still true.
    expect(await screen.findByText("permission.manage")).toBeInTheDocument();
    expect(screen.getAllByText("granted").length).toBeGreaterThan(0);
  });

  it("renders the '*' permission row as 'Super-admin', not a literal '*'", async () => {
    render(<AuditTab catalog={catalog} />);
    expect(await screen.findByText("Super-admin")).toBeInTheDocument();
    expect(screen.queryByText("*")).toBeNull();
  });
});
