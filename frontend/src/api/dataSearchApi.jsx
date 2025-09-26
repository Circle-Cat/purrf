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

export async function getGoogleChatMessagesCount({
  startDate,
  endDate,
  spaceIds,
  ldaps,
}) {
  const body = {
    startDate,
    endDate,
    spaceIds,
    ldaps,
  };
  return await request.post(`/google/chat/count`, body);
}

export async function getMicrosoftChatMessagesCount({
  ldaps,
  startDate,
  endDate,
}) {
  const body = {
    ldaps,
    startDate,
    endDate,
  };
  return await request.post(`/microsoft/chat/count`, body);
}

export async function getGerritStats({ ldaps, startDate, endDate, project }) {
  const body = {
    ldaps,
    startDate,
    endDate,
    project,
  };
  return await request.post("/gerrit/stats", body);
}
