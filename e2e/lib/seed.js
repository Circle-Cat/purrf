import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { readLocal } from "./local.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SEED_DIR = path.join(ROOT, "seed");
export const SEED_STATE_FILE = path.join(ROOT, ".state", "seed.json");

/** First user id the seed hands out; everything at or above it is seeded. */
export const SEED_USER_ID_FLOOR = 990001;

/** How many people seed.sql creates, e2e-member not counted. */
const SEEDED_PEOPLE = 22;

/**
 * psql wants a libpq URL; the backend's DATABASE_URL is SQLAlchemy-shaped
 * (`postgresql+asyncpg://…?ssl=require`). Accept either.
 */
export function libpqUrl(url) {
  return url
    .replace("+asyncpg", "")
    .replace(/([?&])ssl=require/, "$1sslmode=require");
}

const URL_FILE = path.join(ROOT, ".tokens", "database-url.txt");

/**
 * The test database's URL, from E2E_DATABASE_URL, `e2e.local.json` or
 * `.tokens/database-url.txt`.
 */
export function databaseUrl() {
  if (process.env.E2E_DATABASE_URL) return process.env.E2E_DATABASE_URL;
  const local = readLocal().databaseUrl?.trim();
  if (local) return local;
  if (fs.existsSync(URL_FILE))
    return fs.readFileSync(URL_FILE, "utf8").trim() || null;
  return null;
}

function psql(args) {
  const url = databaseUrl();
  if (!url) throw new Error("No database URL; see README.md");
  return execFileSync(
    "psql",
    [libpqUrl(url), "-X", "-q", "-v", "ON_ERROR_STOP=1", ...args],
    { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
  );
}

const vars = (values) =>
  Object.entries(values).flatMap(([k, v]) => ["-v", `${k}=${v}`]);

/** Remove whatever an earlier run left behind. Safe when nothing is there. */
export function cleanup({ roundId, memberId }) {
  psql([
    ...vars({ round_id: roundId, member_id: memberId }),
    "-f",
    path.join(SEED_DIR, "cleanup.sql"),
  ]);
}

/**
 * Seed the round and return who was created: user id by last name (the
 * seed names people "E2E" + a role label), plus e2e-member's id.
 */
export function seed({ roundId, prevRoundId, memberId }) {
  psql([
    ...vars({
      round_id: roundId,
      prev_round_id: prevRoundId,
      member_id: memberId,
    }),
    "-f",
    path.join(SEED_DIR, "seed.sql"),
  ]);
  const rows = psql([
    "-At",
    "-F",
    "\t",
    "-c",
    `SELECT user_id, last_name FROM users WHERE user_id >= ${SEED_USER_ID_FLOOR} ORDER BY user_id`,
  ]);
  const byName = Object.fromEntries(
    rows
      .trim()
      .split("\n")
      .filter(Boolean)
      .map((line) => {
        const [id, name] = line.split("\t");
        return [name, Number(id)];
      }),
  );
  // seed.sql refuses with exit code 0 when rows are already there, so check
  // that the people actually came into being.
  if (Object.keys(byName).length !== SEEDED_PEOPLE) {
    throw new Error(
      `seed created ${Object.keys(byName).length} people, expected ${SEEDED_PEOPLE}; run cleanup.sql and look at the psql output`,
    );
  }
  return {
    roundId,
    prevRoundId,
    memberId,
    byName,
    people: [...Object.values(byName), memberId],
  };
}

export function writeSeedState(state) {
  fs.mkdirSync(path.dirname(SEED_STATE_FILE), { recursive: true });
  fs.writeFileSync(SEED_STATE_FILE, JSON.stringify(state, null, 2));
}

/** What global setup seeded this run, or null when it did not seed. */
export function readSeedState() {
  if (!fs.existsSync(SEED_STATE_FILE)) return null;
  return JSON.parse(fs.readFileSync(SEED_STATE_FILE, "utf8"));
}
