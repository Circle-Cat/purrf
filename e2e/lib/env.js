// The only deployments this suite may touch. Production is deliberately absent.
const ENVIRONMENTS = {
  test: {
    web: "https://test.purrf.io",
    api: "https://test-api.purrf.io",
    banner: "TEST ENVIRONMENT",
    writesAllowed: true,
  },
  staging: {
    web: "https://staging.purrf.io",
    api: "https://staging-api.purrf.io",
    banner: "STAGING ENVIRONMENT",
    writesAllowed: false,
  },
};

const name = process.env.E2E_ENV ?? "test";
if (!Object.hasOwn(ENVIRONMENTS, name)) {
  throw new Error(
    `E2E_ENV must be one of ${Object.keys(ENVIRONMENTS).join(", ")}, got "${name}"`,
  );
}

export const ENV = { name, ...ENVIRONMENTS[name] };
