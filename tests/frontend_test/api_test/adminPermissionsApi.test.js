import { describe, it, expect, vi, beforeEach } from "vitest";
import request from "@/utils/request";
import {
  getPermissionCatalog,
  getUsers,
  getUserPermissions,
  getPermissionHolders,
  getAuditLog,
  grantPermissions,
  revokePermissions,
  setSuperAdmin,
  revokeSuperAdmin,
} from "@/api/adminPermissionsApi";

vi.mock("@/utils/request", () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

describe("adminPermissionsApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("getPermissionCatalog GETs the catalog endpoint", async () => {
    request.get.mockResolvedValue({ data: { permissions: ["a"] } });
    const res = await getPermissionCatalog();
    expect(request.get).toHaveBeenCalledWith("/admin/permissions");
    expect(res).toEqual({ data: { permissions: ["a"] } });
  });

  it("getUsers passes search/limit/offset and maps camelCase to snake_case params", async () => {
    request.get.mockResolvedValue({ data: { users: [], total: 0 } });
    await getUsers({
      search: "jo",
      limit: 20,
      offset: 40,
      sortBy: "last_name",
      order: "desc",
      isSuperAdmin: true,
      userType: "internal",
    });
    expect(request.get).toHaveBeenCalledWith("/admin/users", {
      params: {
        search: "jo",
        limit: 20,
        offset: 40,
        sort_by: "last_name",
        order: "desc",
        is_super_admin: true,
        user_type: "internal",
      },
    });
  });

  it("getUserPermissions builds the path from userId", async () => {
    request.get.mockResolvedValue({ data: {} });
    await getUserPermissions(7);
    expect(request.get).toHaveBeenCalledWith("/admin/users/7/permissions");
  });

  it("getPermissionHolders encodes the name and passes filter params as snake_case", async () => {
    request.get.mockResolvedValue({ data: { grants: [] } });
    await getPermissionHolders("mentorship.admin.read", {
      includeRevoked: true,
      grantedSource: "manual",
    });
    expect(request.get).toHaveBeenCalledWith(
      "/admin/permissions/mentorship.admin.read/users",
      { params: { include_revoked: true, granted_source: "manual" } },
    );
  });

  it("getAuditLog passes all filter params mapped to snake_case", async () => {
    request.get.mockResolvedValue({ data: { entries: [], total: 0 } });
    await getAuditLog({
      userId: 3,
      permissionName: "permission.manage",
      action: "granted",
      limit: 50,
      offset: 0,
    });
    expect(request.get).toHaveBeenCalledWith(
      "/admin/audit/permission-changes",
      {
        params: {
          user_id: 3,
          permission_name: "permission.manage",
          action: "granted",
          limit: 50,
          offset: 0,
        },
      },
    );
  });

  it("grantPermissions POSTs permissionNames", async () => {
    request.post.mockResolvedValue({ data: {} });
    await grantPermissions(7, ["a", "b"]);
    expect(request.post).toHaveBeenCalledWith(
      "/admin/users/7/permissions/grant",
      { permissionNames: ["a", "b"] },
    );
  });

  it("revokePermissions POSTs permissionNames", async () => {
    request.post.mockResolvedValue({ data: {} });
    await revokePermissions(7, ["a"]);
    expect(request.post).toHaveBeenCalledWith(
      "/admin/users/7/permissions/revoke",
      { permissionNames: ["a"] },
    );
  });

  it("setSuperAdmin POSTs to the super-admin endpoint", async () => {
    request.post.mockResolvedValue({ data: {} });
    await setSuperAdmin(7);
    expect(request.post).toHaveBeenCalledWith("/admin/users/7/super-admin");
  });

  it("revokeSuperAdmin DELETEs the super-admin endpoint", async () => {
    request.delete.mockResolvedValue({ data: {} });
    await revokeSuperAdmin(7);
    expect(request.delete).toHaveBeenCalledWith("/admin/users/7/super-admin");
  });
});
