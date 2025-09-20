import request from "@/utils/request";

export async function getJiraIssueBrief({
  startDate,
  endDate,
  projectIds,
  statusList,
  ldaps,
}) {
  const body = {
    startDate,
    endDate,
    projectIds,
    statusList,
    ldaps,
  };

  return await request.post(`/jira/brief`, body);
}

export async function getJiraIssueDetails({ issueIds }) {
  const body = { issueIds };
  return await request.post(`/jira/detail/batch`, body);
}

export async function getGoogleCalendarEvents({
  startDate,
  endDate,
  calendarIds,
  ldaps,
}) {
  const body = {
    startDate,
    endDate,
    calendarIds,
    ldaps,
  };
  return await request.post(`/calendar/events`, body);
}
