import { execFileSync } from "node:child_process";
import { databaseUrl, libpqUrl } from "./seed.js";

const psql = (sql) =>
  execFileSync(
    "psql",
    [
      libpqUrl(databaseUrl()),
      "-X",
      "-q",
      "-At",
      "-v",
      "ON_ERROR_STOP=1",
      "-c",
      sql,
    ],
    { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
  );

const sqlText = (value) => `'${String(value).replace(/'/g, "''")}'`;

/**
 * Throw unless the database holds `email` for `userId`, as the API reported
 * them: otherwise the URL points at another database than the API's, and a
 * grant there would land on whoever has that id.
 */
export function checkSameDatabase(userId, email) {
  if (!Number.isInteger(userId)) throw new Error(`bad user id ${userId}`);
  if (typeof email !== "string" || !email.trim())
    throw new Error(`bad email ${email}`);
  const held = psql(
    `SELECT email FROM user_emails WHERE user_id = ${userId}
       AND lower(email) = lower(${sqlText(email.trim())})`,
  ).trim();
  if (!held) {
    throw new Error(
      `the database at the configured URL has no address ${email} for user ${userId}, which the API reported; it is not the database the API uses, so nothing was written there`,
    );
  }
}

/**
 * Grant permissions to a test account straight in the database, as the
 * permission console would (`granted_source = 'admin'`, no granter), skipping
 * any it already holds. Only for the suite's own accounts on test, and only
 * once the database is shown to be the API's (`checkSameDatabase`).
 */
export function grantInDatabase(userId, email, permissionNames) {
  if (!Number.isInteger(userId)) throw new Error(`bad user id ${userId}`);
  const names = permissionNames.map((n) => {
    if (!/^[a-z_.*]+$/.test(n)) throw new Error(`bad permission name ${n}`);
    return `'${n}'`;
  });
  checkSameDatabase(userId, email);
  psql(`
    INSERT INTO user_permissions (user_id, permission_name, granted_source)
    SELECT ${userId}, p, 'admin'
    FROM unnest(ARRAY[${names.join(",")}]::text[]) AS p
    WHERE NOT EXISTS (
      SELECT 1 FROM user_permissions u
      WHERE u.user_id = ${userId} AND u.permission_name = p
        AND u.revoked_timestamp IS NULL
    )`);
}
