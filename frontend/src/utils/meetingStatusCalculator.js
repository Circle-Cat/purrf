import { MeetingStatus } from "@/constants/MeetingStatus";

/**
 * Classifies a meeting into one of the `MeetingStatus` values based on its
 * completion state and scheduled start time.
 *
 * Meetings that are not completed remain `SCHEDULED` until their scheduled
 * start time passes, after which they become `PAST_INCOMPLETE`.
 */
export function getMeetingStatus(isCompleted, startDatetime) {
  if (isCompleted) return MeetingStatus.COMPLETED;
  if (new Date(startDatetime) <= new Date())
    return MeetingStatus.PAST_INCOMPLETE;
  return MeetingStatus.SCHEDULED;
}
