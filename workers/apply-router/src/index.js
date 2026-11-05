/**
 * Public entry for candidates coming from the official site.
 *
 * Each visitor is sent to Purrf or to Workable on arrival. Purrf visitors see
 * the open postings rendered here; Workable visitors are redirected to the
 * matching Workable page. The split is by a sticky per-visitor bucket against
 * PURRF_RATIO, so raising the ratio only moves visitors from Workable to
 * Purrf, and setting it to 0 sends everyone back.
 */

const JOBS_PATH = "/api/recruiting/anonymous/jobs";
const JOBS_CACHE_SECONDS = 60;
const BUCKET_COOKIE = "apply_bucket";
const BUCKET_MAX_AGE_SECONDS = 60 * 60 * 24 * 90;

/** Escapes text for HTML element content and quoted attributes. */
export function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/**
 * Reads the Purrf share from the environment.
 *
 * @param {object} env Worker environment bindings.
 * @returns {number} A ratio in [0, 1]; anything unparseable is 0, which
 *   sends everyone to Workable.
 */
export function purrfRatio(env) {
  const ratio = Number(env.PURRF_RATIO);
  if (!Number.isFinite(ratio)) return 0;
  return Math.min(1, Math.max(0, ratio));
}

/**
 * Returns the visitor's bucket from the cookie, or null if it has none.
 *
 * @param {Request} request Incoming request.
 * @returns {number|null} An integer in [0, 100), or null.
 */
export function readBucket(request) {
  const cookie = request.headers.get("cookie") ?? "";
  const match = cookie.match(new RegExp(`(?:^|;\\s*)${BUCKET_COOKIE}=(\\d+)`));
  if (!match) return null;
  const bucket = Number(match[1]);
  return bucket < 100 ? bucket : null;
}

/**
 * Returns the Workable page for a request: the posting's own page when
 * WORKABLE_JOBS maps it, otherwise the job board.
 *
 * @param {object} env Worker environment bindings.
 * @param {number|null} jobId The posting asked for, or null for the list.
 * @returns {string|undefined} A URL, or undefined if none is configured.
 */
export function workableUrl(env, jobId) {
  if (jobId !== null) {
    let jobs = env.WORKABLE_JOBS ?? {};
    if (typeof jobs === "string") {
      try {
        jobs = JSON.parse(jobs);
      } catch {
        console.error("apply-router: WORKABLE_JOBS is not valid JSON");
        jobs = {};
      }
    }
    if (jobs[String(jobId)]) return jobs[String(jobId)];
  }
  return env.WORKABLE_BOARD_URL || undefined;
}

/**
 * Picks where a visitor goes.
 *
 * @param {number} bucket The visitor's bucket in [0, 100).
 * @param {number} ratio The Purrf share in [0, 1].
 * @param {string|undefined} workable The Workable page for this request.
 * @returns {"purrf"|"workable"} The destination; Purrf when there is no
 *   Workable page to send to.
 */
export function chooseVariant(bucket, ratio, workable) {
  if (!workable) return "purrf";
  return bucket < ratio * 100 ? "purrf" : "workable";
}

/**
 * Fetches the open postings from the backend, reusing a recent copy.
 *
 * @param {object} env Worker environment bindings.
 * @returns {Promise<object[]|null>} The postings, or null if the backend
 *   could not be read.
 */
export async function loadJobs(env) {
  const url = `${env.API_ORIGIN}${JOBS_PATH}`;
  const cache = caches.default;
  const cached = await cache.match(url);
  if (cached) return (await cached.json()).data;

  let origin;
  try {
    origin = await fetch(url, {
      headers: {
        "CF-Access-Client-Id": env.CF_ACCESS_CLIENT_ID,
        "CF-Access-Client-Secret": env.CF_ACCESS_CLIENT_SECRET,
      },
      // A redirect here is Access sending the token to a login page because
      // the path is missing from its application; never follow it.
      redirect: "manual",
    });
  } catch (error) {
    console.error(`apply-router: ${JOBS_PATH} failed: ${error}`);
    return null;
  }
  if (origin.status !== 200) {
    console.error(
      `apply-router: ${JOBS_PATH} answered ${origin.status} ${origin.headers.get("location") ?? ""}`,
    );
    return null;
  }

  const body = await origin.text();
  await cache.put(
    url,
    new Response(body, {
      headers: {
        "content-type": "application/json",
        "cache-control": `max-age=${JOBS_CACHE_SECONDS}`,
      },
    }),
  );
  return JSON.parse(body).data;
}

const STYLE = `
  body { margin: 0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; color: #0f172a; background: #fff; }
  main { max-width: 720px; margin: 0 auto; padding: 32px 16px; }
  h1 { font-size: 24px; margin: 0 0 24px; }
  a { color: inherit; }
  .job { display: block; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 12px; text-decoration: none; }
  .job:hover { background: #f8fafc; }
  .job h2 { font-size: 16px; margin: 0 0 8px; }
  .summary { color: #334155; font-size: 14px; margin: 0; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
  .description { white-space: pre-wrap; line-height: 1.6; color: #334155; }
  .apply { display: inline-block; margin-top: 24px; padding: 10px 20px; border-radius: 6px; background: #0f172a; color: #fff; text-decoration: none; }
  .back { display: inline-block; margin-bottom: 16px; font-size: 14px; color: #64748b; }
  .muted { color: #64748b; }
`;

/** Wraps page content in the shared document shell. */
function page(title, content, status = 200) {
  const html = `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${escapeHtml(title)}</title>
<meta property="og:title" content="${escapeHtml(title)}">
<style>${STYLE}</style>
</head>
<body><main>${content}</main></body>
</html>`;
  return new Response(html, {
    status,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      "content-security-policy":
        "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
      "x-content-type-options": "nosniff",
    },
  });
}

function listPage(jobs) {
  const items = jobs.length
    ? jobs
        .map(
          (job) => `<a class="job" href="/jobs/${job.id}">
<h2>${escapeHtml(job.title)}</h2>
${job.description ? `<p class="summary">${escapeHtml(job.description)}</p>` : ""}
</a>`,
        )
        .join("\n")
    : `<p class="muted">No open positions right now.</p>`;
  return page("Open positions", `<h1>Open positions</h1>\n${items}`);
}

function detailPage(job) {
  return page(
    job.title,
    `<a class="back" href="/jobs">All open positions</a>
<h1>${escapeHtml(job.title)}</h1>
${job.description ? `<div class="description">${escapeHtml(job.description)}</div>` : ""}
<a class="apply" href="/jobs/${job.id}/apply">Apply</a>`,
  );
}

function notFoundPage() {
  return page(
    "Position not found",
    `<h1>Position not found</h1>
<p class="muted">This position may have closed. <a href="/jobs">See all open positions</a>.</p>`,
    404,
  );
}

function unavailablePage() {
  return page(
    "Temporarily unavailable",
    `<h1>Temporarily unavailable</h1>
<p class="muted">We could not load open positions. Please try again in a few minutes.</p>`,
    502,
  );
}

/** A no-store 302 to the given location. */
function redirect(location) {
  return new Response(null, {
    status: 302,
    headers: { location, "cache-control": "no-store" },
  });
}

/** Appends the utm parameters that tag where a visitor was sent. */
function tagged(url, variant) {
  const target = new URL(url);
  target.searchParams.set("utm_source", "apply_router");
  target.searchParams.set("utm_content", variant);
  return target.toString();
}

/**
 * Builds the response for a job page, the list or an Apply click.
 *
 * Workable visitors are redirected without reading the backend, so they are
 * unaffected by a Purrf outage; Purrf visitors fall back to Workable when the
 * job list cannot be read and a Workable page exists.
 *
 * @param {object} env Worker environment bindings.
 * @param {number} bucket The visitor's bucket.
 * @param {"list"|"detail"|"apply"} kind Which page was asked for.
 * @param {number|null} jobId The posting asked for, or null for the list.
 * @returns {Promise<Response>} A page or a redirect.
 */
async function route(env, bucket, kind, jobId) {
  const workable = workableUrl(env, jobId);
  const variant = chooseVariant(bucket, purrfRatio(env), workable);
  const log = (fields) =>
    console.log(JSON.stringify({ event: kind, jobId, bucket, ...fields }));

  if (variant === "workable") {
    log({ variant });
    return redirect(tagged(workable, variant));
  }

  const jobs = await loadJobs(env);
  if (jobs === null) {
    if (workable) {
      log({ variant: "workable", fallback: true });
      return redirect(tagged(workable, "workable"));
    }
    return unavailablePage();
  }

  if (kind === "list") {
    log({ variant });
    return listPage(jobs);
  }
  const job = jobs.find((j) => j.id === jobId);
  if (!job) return notFoundPage();
  log({ variant });
  if (kind === "detail") return detailPage(job);
  return redirect(
    tagged(`${env.APP_ORIGIN}/recruiting/jobs/${jobId}/apply`, variant),
  );
}

export default {
  /**
   * Serves the public job pages, sending each visitor to Purrf or Workable.
   *
   * @param {Request} request Incoming request.
   * @param {object} env Worker environment bindings.
   * @returns {Promise<Response>} A page, a redirect, or an error page.
   */
  async fetch(request, env) {
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response(null, {
        status: 405,
        headers: { allow: "GET, HEAD" },
      });
    }

    const { pathname } = new URL(request.url);
    if (pathname === "/") return redirect("/jobs");

    const apply = pathname.match(/^\/jobs\/(\d+)\/apply$/);
    const detail = pathname.match(/^\/jobs\/(\d+)$/);
    let kind;
    if (pathname === "/jobs") kind = "list";
    else if (detail) kind = "detail";
    else if (apply) kind = "apply";
    else return notFoundPage();
    const jobId = kind === "list" ? null : Number((apply ?? detail)[1]);

    const known = readBucket(request);
    const bucket = known ?? Math.floor(Math.random() * 100);
    const response = await route(env, bucket, kind, jobId);
    if (known === null) {
      response.headers.append(
        "set-cookie",
        `${BUCKET_COOKIE}=${bucket}; Path=/; Max-Age=${BUCKET_MAX_AGE_SECONDS}; Secure; HttpOnly; SameSite=Lax`,
      );
    }
    return response;
  },
};
