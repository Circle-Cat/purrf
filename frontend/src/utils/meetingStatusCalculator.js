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

/**
 * How long after a meeting's scheduled end it can still be joined.
 *
 * Completion alone cannot bound this: `is_completed` is only ever set true by
 * the attendance sweep finding enough interaction, so a meeting nobody
 * attended stays uncompleted forever and would otherwise keep offering a way
 * in months later. An hour covers running late and overrunning without
 * leaving stale entry points behind.
 */
export const JOIN_GRACE_MS = 60 * 60 * 1000;

/**
 * Whether a meeting is close enough in time to still be worth joining.
 *
 * A missing or unparseable `endDatetime` yields NaN, and every comparison
 * against NaN is false -- which lands on hiding the entry point, the safe
 * direction for a timestamp we cannot read.
 *
 * @param {string} endDatetime - Scheduled end, in UTC ISO format.
 * @param {number} [now] - Epoch milliseconds to judge against; defaults to now.
 * @returns {boolean}
 */
export function isWithinJoinWindow(endDatetime, now = Date.now()) {
  return now < new Date(endDatetime).getTime() + JOIN_GRACE_MS;
}
