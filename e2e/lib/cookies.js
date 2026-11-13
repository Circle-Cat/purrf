import { ENV } from "./env.js";

/** The Access cookie on both hosts; they share one Access application. */
export function browserCookies(token) {
  return [ENV.web, ENV.api].map((origin) => ({
    name: "CF_Authorization",
    value: token,
    domain: new URL(origin).hostname,
    path: "/",
    secure: true,
  }));
}
