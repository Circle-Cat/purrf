import { beforeAll, describe, expect, it, vi } from "vitest";
import worker from "./index.js";

let keyPair;
let jwks;

beforeAll(async () => {
  keyPair = await crypto.subtle.generateKey(
    {
      name: "RSASSA-PKCS1-v1_5",
      modulusLength: 2048,
      publicExponent: new Uint8Array([1, 0, 1]),
      hash: "SHA-256",
    },
    true,
    ["sign", "verify"],
  );
  const jwk = await crypto.subtle.exportKey("jwk", keyPair.publicKey);
  jwks = { keys: [{ ...jwk, kid: "test-key", alg: "RS256", use: "sig" }] };
});

/** Signs a Google-shaped OIDC token with the test key. */
async function makeToken(overrides = {}) {
  const header = { alg: "RS256", kid: "test-key", typ: "JWT" };
  const claims = {
    iss: "https://accounts.google.com",
    aud: "purrf",
    sub: "111476081826269898524",
    exp: Math.floor(Date.now() / 1000) + 600,
    ...overrides,
  };
  const encode = (value) =>
    btoa(JSON.stringify(value))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  const signingInput = `${encode(header)}.${encode(claims)}`;
  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    keyPair.privateKey,
    new TextEncoder().encode(signingInput),
  );
  const encodedSignature = btoa(
    String.fromCharCode(...new Uint8Array(signature)),
  )
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
  return `${signingInput}.${encodedSignature}`;
}

function environment() {
  return {
    ORIGIN_URL: "https://api.purrf.io/api/notifications/deliver",
    ALLOWED_SUBS: "111476081826269898524",
    EXPECTED_AUDIENCE: "purrf",
    CF_ACCESS_CLIENT_ID: "client-id",
    CF_ACCESS_CLIENT_SECRET: "client-secret",
    JWKS_URL: "https://jwks.test/certs",
  };
}

function request(token) {
  return new Request("https://hook.purrf.io/notify", {
    method: "POST",
    headers: token ? { authorization: `Bearer ${token}` } : {},
    body: JSON.stringify({ message: { data: "e30=" } }),
  });
}

function stubFetch(originResponse) {
  return vi.fn(async (input) => {
    const url = typeof input === "string" ? input : input.url;
    if (url === "https://jwks.test/certs") {
      return new Response(JSON.stringify(jwks), {
        headers: { "content-type": "application/json" },
      });
    }
    return originResponse;
  });
}

describe("pubsub gateway", () => {
  it("forwards a valid token with the Access service token attached", async () => {
    const fetchMock = stubFetch(new Response("ok", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await worker.fetch(
      request(await makeToken()),
      environment(),
    );

    expect(response.status).toBe(200);
    const forwarded = fetchMock.mock.calls.find(([input]) =>
      (typeof input === "string" ? input : input.url).includes("api.purrf.io"),
    );
    expect(forwarded[1].headers["CF-Access-Client-Id"]).toBe("client-id");
    expect(forwarded[1].headers["CF-Access-Client-Secret"]).toBe(
      "client-secret",
    );
    expect(forwarded[1].headers.authorization).toBeUndefined();
  });

  it("passes the origin status straight back so Pub/Sub sees the truth", async () => {
    vi.stubGlobal("fetch", stubFetch(new Response("", { status: 503 })));
    const response = await worker.fetch(
      request(await makeToken()),
      environment(),
    );
    expect(response.status).toBe(503);
  });

  it.each([
    ["a missing token", undefined],
    ["the wrong audience", { aud: "somebody-else" }],
    ["an unlisted subject", { sub: "999" }],
    ["an expired token", { exp: Math.floor(Date.now() / 1000) - 60 }],
    ["a foreign issuer", { iss: "https://evil.example" }],
  ])("rejects %s without touching the origin", async (_label, overrides) => {
    const fetchMock = stubFetch(new Response("ok", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const token =
      overrides === undefined ? undefined : await makeToken(overrides);
    const response = await worker.fetch(request(token), environment());

    expect(response.status).toBe(403);
    const reachedOrigin = fetchMock.mock.calls.some(([input]) =>
      (typeof input === "string" ? input : input.url).includes("api.purrf.io"),
    );
    expect(reachedOrigin).toBe(false);
  });

  it("rejects every caller when ALLOWED_SUBS is missing, without touching the origin", async () => {
    const fetchMock = stubFetch(new Response("ok", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const env = { ...environment(), ALLOWED_SUBS: undefined };

    const response = await worker.fetch(request(await makeToken()), env);

    expect(response.status).toBe(403);
    const reachedOrigin = fetchMock.mock.calls.some(([input]) =>
      (typeof input === "string" ? input : input.url).includes("api.purrf.io"),
    );
    expect(reachedOrigin).toBe(false);
  });

  it("fetches the JWKS once and reuses it for a second verification", async () => {
    const fetchMock = stubFetch(new Response("ok", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const token = await makeToken();

    const first = await worker.fetch(request(token), environment());
    const second = await worker.fetch(request(token), environment());

    expect(first.status).toBe(200);
    expect(second.status).toBe(200);
    const jwksCalls = fetchMock.mock.calls.filter(
      ([input]) =>
        (typeof input === "string" ? input : input.url) ===
        "https://jwks.test/certs",
    );
    expect(jwksCalls.length).toBe(1);
  });

  it("rejects a token whose signature does not match the JWKS", async () => {
    const token = await makeToken();
    const tampered = `${token.slice(0, -4)}AAAA`;
    const fetchMock = stubFetch(new Response("ok", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await worker.fetch(request(tampered), environment());
    expect(response.status).toBe(403);
  });
});
