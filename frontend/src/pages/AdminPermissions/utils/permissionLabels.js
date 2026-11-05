/**
 * Render the super-admin marker row ("*") as a human label; pass through every
 * real permission name unchanged.
 *
 * @param {string} name
 * @returns {string}
 */
export const displayPermission = (name) =>
  name === "*" ? "Super-admin" : name;
