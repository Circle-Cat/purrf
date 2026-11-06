import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import worker, {
  chooseVariant,
  escapeHtml,
  purrfRatio,
  readBucket,
  workableUrl,
} from "./index.js";

const JOBS = [
  {
    id: 7,
    title: "Mentee",
    kind: "activity",
    description: "Line one\nLine two",
  },
  { id: 12, title: "Mentor <Lead>", kind: "activity", description: null },
];

const BOARD = "https://apply.workable.com/circlecat-canada/";
const MENTEE_ON_WORKABLE = "https://apply.workable.com/circlecat-canada/j/ABC/";

const ENV = {
  API_ORIGIN: "https://api.example.test",
  APP_ORIGIN: "https://app.example.test",
  CF_ACCESS_CLIENT_ID: "id-123",
  CF_ACCESS_CLIENT_SECRET: "secret-456",
  PURRF_RATIO: "0.3",
  WORKABLE_BOARD_URL: BOARD,
  WORKABLE_JOBS: JSON.stringify({ 7: MENTEE_ON_WORKABLE }),
};

const PURRF_VISITOR = { cookie: "apply_bucket=10" };
const WORKABLE_VISITOR = { cookie: "apply_bucket=80" };

function stubBackend(
  status = 200,
  body = { success: true, data: JOBS },
  headers = {},
) {
  const fetchMock = vi.fn(
    async () => new Response(JSON.stringify(body), { status, headers }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function get(path, headers = {}, env = ENV) {
  return worker.fetch(
    new Request(`https://apply.example.test${path}`, { headers }),
    env,
  );
}

function destination(response) {
  const location = new URL(response.headers.get("location"));
  return {
    url: location.origin + location.pathname,
    variant: location.searchParams.get("utm_content"),
  };
}

let log;
beforeEach(() => {
  log = vi.spyOn(console, "log").mockImplementation(() => {});
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("escapeHtml", () => {
  it("escapes markup and both quote kinds", () => {
    expect(escapeHtml(`<a href="x">'&'</a>`)).toBe(
      "&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;",
    );
  });
});

describe("purrfRatio", () => {
  it("reads the configured share", () => {
    expect(purrfRatio({ PURRF_RATIO: "0.25" })).toBe(0.25);
  });

  it("treats a missing or unparseable value as 0", () => {
    expect(purrfRatio({})).toBe(0);
    expect(purrfRatio({ PURRF_RATIO: "ten percent" })).toBe(0);
  });

  it("clamps to [0, 1]", () => {
    expect(purrfRatio({ PURRF_RATIO: "4" })).toBe(1);
    expect(purrfRatio({ PURRF_RATIO: "-1" })).toBe(0);
  });

  it("reads a posting's own share from PURRF_RATIOS", () => {
    const env = { PURRF_RATIO: "1", PURRF_RATIOS: '{"1":0.5,"3":0}' };
    expect(purrfRatio(env, 1)).toBe(0.5);
    expect(purrfRatio(env, 3)).toBe(0);
  });

  it("falls back to PURRF_RATIO for the list and for unlisted postings", () => {
    const env = { PURRF_RATIO: "1", PURRF_RATIOS: '{"1":0.5}' };
    expect(purrfRatio(env)).toBe(1);
    expect(purrfRatio(env, 9)).toBe(1);
  });

  it("ignores an unreadable PURRF_RATIOS or entry", () => {
    expect(purrfRatio({ PURRF_RATIO: "0.4", PURRF_RATIOS: "{" }, 1)).toBe(0.4);
    expect(
      purrfRatio({ PURRF_RATIO: "0.4", PURRF_RATIOS: '{"1":"half"}' }, 1),
    ).toBe(0.4);
  });
});

describe("readBucket", () => {
  const withCookie = (cookie) =>
    new Request("https://apply.example.test/", { headers: { cookie } });

  it("reads the bucket among other cookies", () => {
    expect(readBucket(withCookie("a=1; apply_bucket=42; b=2"))).toBe(42);
  });

  it("is null without the cookie or with an out-of-range value", () => {
    expect(readBucket(withCookie("other=5"))).toBeNull();
    expect(readBucket(withCookie("apply_bucket=100"))).toBeNull();
    expect(readBucket(withCookie("my_apply_bucket=3"))).toBeNull();
  });
});

describe("workableUrl", () => {
  it("uses the posting's own page when it is mapped", () => {
    expect(workableUrl(ENV, 7)).toBe(MENTEE_ON_WORKABLE);
  });

  it("falls back to the board for an unmapped posting and for the list", () => {
    expect(workableUrl(ENV, 12)).toBe(BOARD);
    expect(workableUrl(ENV, null)).toBe(BOARD);
  });

  it("accepts the mapping as an object too", () => {
    expect(workableUrl({ WORKABLE_JOBS: { 7: "https://w/7" } }, 7)).toBe(
      "https://w/7",
    );
  });

  it("ignores a mapping that is not valid JSON", () => {
    expect(workableUrl({ ...ENV, WORKABLE_JOBS: "{7:" }, 7)).toBe(BOARD);
  });

  it("is undefined when nothing is configured", () => {
    expect(workableUrl({}, 7)).toBeUndefined();
    expect(workableUrl({ WORKABLE_BOARD_URL: "" }, null)).toBeUndefined();
  });
});

describe("chooseVariant", () => {
  const workable = "https://apply.workable.com/x/";

  it("sends buckets below the ratio to Purrf and the rest to Workable", () => {
    expect(chooseVariant(29, 0.3, workable)).toBe("purrf");
    expect(chooseVariant(30, 0.3, workable)).toBe("workable");
  });

  it("sends everyone to Workable at ratio 0 and to Purrf at 1", () => {
    expect(chooseVariant(0, 0, workable)).toBe("workable");
    expect(chooseVariant(99, 1, workable)).toBe("purrf");
  });

  it("sends everyone to Purrf when there is no Workable page", () => {
    expect(chooseVariant(99, 0, undefined)).toBe("purrf");
  });
});

describe("Purrf visitors", () => {
  it("reads the list with the service token and never follows redirects", async () => {
    const fetchMock = stubBackend();
    await get("/jobs", PURRF_VISITOR);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://api.example.test/api/recruiting/anonymous/jobs");
    expect(init.headers["CF-Access-Client-Id"]).toBe("id-123");
    expect(init.headers["CF-Access-Client-Secret"]).toBe("secret-456");
    expect(init.redirect).toBe("manual");
  });

  it("see every posting with escaped titles", async () => {
    stubBackend();
    const response = await get("/jobs", PURRF_VISITOR);
    const html = await response.text();

    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("text/html");
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(html).toContain('href="/jobs/7"');
    expect(html).toContain('href="/jobs/12"');
    expect(html).toContain("Mentor &lt;Lead&gt;");
    expect(html).not.toContain("<Lead>");
  });

  it("see one posting with its description and an Apply link", async () => {
    stubBackend();
    const html = await (await get("/jobs/7", PURRF_VISITOR)).text();

    expect(html).toContain("<title>Mentee</title>");
    expect(html).toContain("Line one\nLine two");
    expect(html).toContain('href="/jobs/7/apply"');
    expect(html).not.toContain("/jobs/12");
  });

  it("are sent to the Purrf apply page on Apply", async () => {
    stubBackend();
    const response = await get("/jobs/7/apply", PURRF_VISITOR);

    expect(response.status).toBe(302);
    expect(destination(response)).toEqual({
      url: "https://app.example.test/recruiting/jobs/7/apply",
      variant: "purrf",
    });
    expect(response.headers.get("set-cookie")).toBeNull();
  });

  it("get 404 for a posting that is not open", async () => {
    stubBackend();
    expect((await get("/jobs/99", PURRF_VISITOR)).status).toBe(404);
    expect((await get("/jobs/99/apply", PURRF_VISITOR)).status).toBe(404);
  });

  it("are sent to Workable when the job list cannot be read", async () => {
    stubBackend(302, {}, { location: "https://login.example.test" });
    const response = await get("/jobs/7", PURRF_VISITOR);

    expect(destination(response)).toEqual({
      url: MENTEE_ON_WORKABLE,
      variant: "workable",
    });
    expect(JSON.parse(log.mock.calls[0][0])).toMatchObject({
      fallback: true,
    });
  });

  it("get 502 when the list cannot be read and there is no Workable page", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("network down");
      }),
    );
    const env = { ...ENV, WORKABLE_BOARD_URL: "", WORKABLE_JOBS: "{}" };
    const response = await get("/jobs", PURRF_VISITOR, env);

    expect(response.status).toBe(502);
  });

  it("reuse the cached list instead of asking the backend again", async () => {
    const fetchMock = stubBackend();
    await get("/jobs", PURRF_VISITOR);
    await get("/jobs/7", PURRF_VISITOR);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("Workable visitors", () => {
  it("are sent from the list to the Workable board without reading the backend", async () => {
    const fetchMock = stubBackend();
    const response = await get("/jobs", WORKABLE_VISITOR);

    expect(response.status).toBe(302);
    expect(destination(response)).toEqual({ url: BOARD, variant: "workable" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("are sent from a mapped posting to its Workable page", async () => {
    stubBackend();
    for (const path of ["/jobs/7", "/jobs/7/apply"]) {
      const response = await get(path, WORKABLE_VISITOR);
      expect(destination(response).url).toBe(MENTEE_ON_WORKABLE);
    }
  });

  it("are sent from an unmapped posting to the Workable board", async () => {
    stubBackend();
    const response = await get("/jobs/12", WORKABLE_VISITOR);
    expect(destination(response).url).toBe(BOARD);
  });

  it("see Purrf when no Workable page is configured", async () => {
    stubBackend();
    const env = {
      ...ENV,
      WORKABLE_BOARD_URL: undefined,
      WORKABLE_JOBS: undefined,
    };
    const response = await get("/jobs", WORKABLE_VISITOR, env);
    expect(response.status).toBe(200);
  });

  it("are split per posting when PURRF_RATIOS names it", async () => {
    stubBackend();
    const env = { ...ENV, PURRF_RATIO: "1", PURRF_RATIOS: '{"7":0}' };
    const posting = await get("/jobs/7", PURRF_VISITOR, env);
    expect(destination(posting).url).toBe(MENTEE_ON_WORKABLE);
    const list = await get("/jobs", PURRF_VISITOR, env);
    expect(list.status).toBe(200);
  });

  it("all go back to Workable at ratio 0, including former Purrf visitors", async () => {
    stubBackend();
    const env = { ...ENV, PURRF_RATIO: "0" };
    const response = await get("/jobs/7", PURRF_VISITOR, env);
    expect(destination(response).url).toBe(MENTEE_ON_WORKABLE);
  });
});

describe("new visitors", () => {
  it("get a bucket pinned in a cookie and are routed by it", async () => {
    stubBackend();
    vi.spyOn(Math, "random").mockReturnValue(0.55);
    const response = await get("/jobs");
    const cookie = response.headers.get("set-cookie");

    expect(cookie).toContain("apply_bucket=55");
    expect(cookie).toContain("HttpOnly");
    expect(cookie).toContain("Secure");
    expect(destination(response).url).toBe(BOARD);
  });

  it("get the cookie on a rendered page too", async () => {
    stubBackend();
    vi.spyOn(Math, "random").mockReturnValue(0.05);
    const response = await get("/jobs");

    expect(response.status).toBe(200);
    expect(response.headers.get("set-cookie")).toContain("apply_bucket=5");
  });
});

describe("routing", () => {
  it("logs each visit with where it was sent", async () => {
    stubBackend();
    await get("/jobs/7/apply", PURRF_VISITOR);

    expect(JSON.parse(log.mock.calls[0][0])).toEqual({
      event: "apply",
      jobId: 7,
      bucket: 10,
      variant: "purrf",
    });
  });

  it("redirects the root to the list", async () => {
    const response = await get("/");
    expect(response.status).toBe(302);
    expect(response.headers.get("location")).toBe("/jobs");
  });

  it("answers 404 for an unknown path without calling the backend", async () => {
    const fetchMock = stubBackend();
    expect((await get("/admin", PURRF_VISITOR)).status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects methods other than GET and HEAD", async () => {
    const response = await worker.fetch(
      new Request("https://apply.example.test/jobs", { method: "POST" }),
      ENV,
    );
    expect(response.status).toBe(405);
  });
});
