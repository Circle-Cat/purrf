import { request } from "@playwright/test";
import { ENV } from "./env.js";

/** An API client that authenticates as whoever the token belongs to. */
export async function apiAs(token) {
  return request.newContext({
    baseURL: ENV.api,
    extraHTTPHeaders: { Cookie: `CF_Authorization=${token}` },
    maxRedirects: 0,
  });
}

/** GET a Purrf endpoint and return its `data`, throwing on anything but 200. */
export async function getData(api, url) {
  const res = await api.get(url);
  if (res.status() !== 200) {
    throw new Error(`GET ${url} -> ${res.status()}`);
  }
  return (await res.json()).data;
}
