import { execFileSync } from "node:child_process";
import { databaseUrl, libpqUrl } from "./seed.js";

/**
 * Grant permissions to a test account straight in the database, as the
 * permission console would (`granted_source = 'admin'`, no granter), skipping
 * any it already holds. Only for the suite's own accounts on test.
 */
export function grantInDatabase(userId, permissionNames) {
  if (!Number.isInteger(userId)) throw new Error(`bad user id ${userId}`);
  const names = permissionNames.map((n) => {
    if (!/^[a-z_.*]+$/.test(n)) throw new Error(`bad permission name ${n}`);
    return `'${n}'`;
  });
  const sql = `
    INSERT INTO user_permissions (user_id, permission_name, granted_source)
    SELECT ${userId}, p, 'admin'
    FROM unnest(ARRAY[${names.join(",")}]::text[]) AS p
    WHERE NOT EXISTS (
      SELECT 1 FROM user_permissions u
      WHERE u.user_id = ${userId} AND u.permission_name = p
        AND u.revoked_timestamp IS NULL
    )`;
  execFileSync(
    "psql",
    [libpqUrl(databaseUrl()), "-X", "-q", "-v", "ON_ERROR_STOP=1", "-c", sql],
    { stdio: ["ignore", "pipe", "pipe"] },
  );
}
