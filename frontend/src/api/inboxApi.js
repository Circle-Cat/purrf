import request from "@/utils/request";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

/** List Inbox threads. params: filter, search and paging fields. */
export const listInboxThreads = (params) =>
  request.get(API_ENDPOINTS.INBOX_THREADS, { params });

/** Fetch the sidebar badge count. */
export const getInboxCount = () => request.get(API_ENDPOINTS.INBOX_COUNT);

/** Fetch one thread with its messages. */
export const getInboxThread = (id) =>
  request.get(API_ENDPOINTS.INBOX_THREAD(id));

/** Send a reply on a thread. */
export const replyToInboxThread = (id, body) =>
  request.post(API_ENDPOINTS.INBOX_THREAD_REPLY(id), body);

/** Archive a thread. */
export const archiveInboxThread = (id) =>
  request.post(API_ENDPOINTS.INBOX_THREAD_ARCHIVE(id));

/** Restore an archived thread. */
export const unarchiveInboxThread = (id) =>
  request.post(API_ENDPOINTS.INBOX_THREAD_UNARCHIVE(id));

/** Assign a thread; on success it leaves the Inbox and `data` is null. */
export const assignInboxThread = (id, body) =>
  request.put(API_ENDPOINTS.INBOX_THREAD_ASSIGNMENT(id), body);

/** Move a thread to another service. */
export const moveInboxThread = (id, service) =>
  request.post(API_ENDPOINTS.INBOX_THREAD_MOVE(id), { service });

/** Fetch the assign options for a thread, optionally for one person. */
export const getInboxAssignOptions = (id, userId) =>
  request.get(API_ENDPOINTS.INBOX_THREAD_ASSIGN_OPTIONS(id), {
    params: { userId },
  });

/** Search people to assign or look up. */
export const searchInboxPeople = (q) =>
  request.get(API_ENDPOINTS.INBOX_PEOPLE, { params: { q } });

/** Build the absolute URL of an attachment, for a plain download link. */
export const inboxAttachmentUrl = (id, messageId, index) =>
  `${request.defaults.baseURL}${API_ENDPOINTS.INBOX_ATTACHMENT(id, messageId, index)}`;
