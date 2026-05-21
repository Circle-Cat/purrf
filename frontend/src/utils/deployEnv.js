export const ENV_LABELS = {
  staging: "STAGING ENVIRONMENT",
  test: "TEST ENVIRONMENT",
};

export const isBannerEnv = (env) =>
  Object.prototype.hasOwnProperty.call(ENV_LABELS, env);
