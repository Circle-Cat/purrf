import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

/** Grantable-permission catalog (the backend code enum). */
export const getPermissionCatalog = () =>
  request.get(API_ENDPOINTS.ADMIN_PERMISSIONS);

/**
 * Paginated user list with optional search, sort, and filter params.
 * @param {{search?: string, userId?: number|string, limit?: number,
 *          offset?: number, sortBy?: string, order?: string,
 *          isSuperAdmin?: boolean, userType?: string}} params
 */
export const getUsers = ({
  search,
  userId,
  limit,
  offset,
  sortBy,
  order,
  isSuperAdmin,
  userType,
} = {}) =>
  request.get(API_ENDPOINTS.ADMIN_USERS, {
    params: {
      search,
      user_id: userId,
      limit,
      offset,
      sort_by: sortBy,
      order,
      is_super_admin: isSuperAdmin,
      user_type: userType,
    },
  });

/** A user's active permissions plus full grant/revoke history. */
export const getUserPermissions = (userId) =>
  request.get(API_ENDPOINTS.ADMIN_USER_PERMISSIONS(userId));

/**
 * Reverse lookup: who holds a given permission.
 * @param {string} name
 * @param {{includeRevoked?: boolean, grantedSource?: string}} [filters]
 */
export const getPermissionHolders = (
  name,
  { includeRevoked, grantedSource } = {},
) =>
  request.get(API_ENDPOINTS.ADMIN_PERMISSION_USERS(name), {
    params: { include_revoked: includeRevoked, granted_source: grantedSource },
  });

/**
 * Global permission-change audit feed.
 * @param {{userId?: number, permissionName?: string, action?: string,
 *          limit?: number, offset?: number}} params
 */
export const getAuditLog = ({
  userId,
  permissionName,
  action,
  limit,
  offset,
} = {}) =>
  request.get(API_ENDPOINTS.ADMIN_AUDIT_PERMISSION_CHANGES, {
    params: {
      user_id: userId,
      permission_name: permissionName,
      action,
      limit,
      offset,
    },
  });

/** Grant a batch of permissions to a user. */
export const grantPermissions = (userId, permissionNames) =>
  request.post(API_ENDPOINTS.ADMIN_USER_GRANT(userId), { permissionNames });

/** Revoke a batch of a user's permissions. */
export const revokePermissions = (userId, permissionNames) =>
  request.post(API_ENDPOINTS.ADMIN_USER_REVOKE(userId), { permissionNames });

/** Promote a user to super-admin (caller must be super-admin). */
export const setSuperAdmin = (userId) =>
  request.post(API_ENDPOINTS.ADMIN_USER_SUPER_ADMIN(userId));

/** Demote a super-admin (SUPER_ADMIN_REVOKE gated; cannot self-revoke). */
export const revokeSuperAdmin = (userId) =>
  request.delete(API_ENDPOINTS.ADMIN_USER_SUPER_ADMIN(userId));
