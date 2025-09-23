/**
 * Handles multiple promises and separates successes from failures.
 * @param {Promise[]} promises - Array of promises to execute
 * @param {string[]} [providerNames=[]] - An optional array of names corresponding to each promise,
 *                                        used for more descriptive error reporting.
 * @param {string} [logContext=""] - An optional string prefix to add to console error and warning
 *                                   messages, providing context about where the promises are being
 *                                   handled (e.g., "Chat count API:").
 * @returns {Promise<any[]>}
 */
async function handleMultiplePromises(
  promises,
  providerNames = [],
  logContext = "",
) {
  const results = await Promise.allSettled(promises);

  const success = [];
  const failed = [];

  results.forEach((result, index) => {
    if (result.status === "fulfilled") {
      success.push(result.value);
    } else {
      const providerName = providerNames[index] || `Provider #${index}`;
      failed.push(providerName);
      console.error(
        `${logContext} Failed to fetch data for ${providerName}:`,
        result.reason,
      );
    }
  });

  if (failed.length > 0) {
    console.warn(`${logContext} Failed providers: ${failed.join(", ")}`);
  }

  return success.flat();
}

export default handleMultiplePromises;
