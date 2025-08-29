import request from "@/utils/request";

/**
 * Sends a POST request to get a summary report.
 * @param {object} params - The parameters for the summary report.
 * @param {string} params.startDate - The start date for the report.
 * @param {string} params.endDate - The end date for the report.
 * @param {boolean} params.includeTerminated - Whether to include terminated members.
 * @param {string[]} params.groups - A list of groups to filter by.
 */
export async function getSummary({
  startDate,
  endDate,
  includeTerminated,
  groups,
}) {
  const body = {
    startDate,
    endDate,
    includeTerminated,
    groups,
  };

  return await request.post(`/summary`, body);
}

export async function getLdapsAndDisplayNames({ status, groups }) {
  const params = new URLSearchParams();
  if (groups && groups.length > 0) {
    groups.forEach((group) => {
      params.append("groups[]", group);
    });
  }

  const url = `/microsoft/${status}/ldaps?${params.toString()}`;
  return await request.get(url);
}
