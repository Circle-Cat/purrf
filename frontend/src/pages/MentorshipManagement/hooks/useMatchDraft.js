import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  releaseMatchingEditLock,
  releaseMatchingEditLockOnLeave,
  saveMatchingDraft,
  takeMatchingEditLock,
} from "@/api/mentorshipApi";
import { savedRow } from "@/pages/MentorshipManagement/utils/matchDraft";

/** A change renews the lock at most this often. */
export const RENEW_EVERY_MS = 60 * 1000;

/** How long before the lock ends the page asks whether you are still there. */
export const WARN_BEFORE_MS = 2 * 60 * 1000;

const HTTP_CONFLICT = 409;

const messageOf = (err, fallback) => err?.response?.data?.message || fallback;

/**
 * Editing a round's matching result as a draft, one admin at a time.
 *
 * `start` takes the edit lock and enters edit mode. While editing, changes
 * live here keyed by menteeId until `save` sends them (the server releases
 * the lock) or `discard` drops them (and releases it). Each change renews the
 * lock, at most once a minute; `nearEnd` turns on two minutes before it ends
 * and `keepEditing` renews it then. When it ends, edit mode is left, the
 * changes are dropped and `lapsed` says so. Leaving the page while editing
 * releases the lock on a best-effort request.
 *
 * @param {number|string} roundId - The mentorship round's id.
 * @param {() => Promise<void>} reloadOverview - Fetches the run's overview
 *   again, after the lock or the draft changed.
 * @returns {{
 *   editing: boolean,
 *   busy: boolean,
 *   lock: {userId: number|string, name: string|null, expiresAt: string}|null,
 *   nearEnd: boolean,
 *   lapsed: boolean,
 *   changes: Object<string, {mentorId: string|null,
 *     recommendationReason: string, baseMentorId: string|null}>,
 *   reloadKey: number,
 *   start: () => Promise<void>,
 *   keepEditing: () => Promise<void>,
 *   setRow: (item: Object, next: {mentorId: string|null,
 *     recommendationReason: string}) => void,
 *   save: () => Promise<void>,
 *   discard: () => void,
 * }} `baseMentorId` is the saved mentor the change moves the mentee from;
 *   `reloadKey` changes after a save so the lists fetch their page again.
 */
export const useMatchDraft = (roundId, reloadOverview) => {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [lock, setLock] = useState(null);
  const [nearEnd, setNearEnd] = useState(false);
  const [lapsed, setLapsed] = useState(false);
  const [changes, setChanges] = useState({});
  const [reloadKey, setReloadKey] = useState(0);
  const renewedAtRef = useRef(0);
  const renewingRef = useRef(Promise.resolve());
  const editingRef = useRef(false);

  useEffect(() => {
    editingRef.current = editing;
  }, [editing]);

  const leave = useCallback(() => {
    setEditing(false);
    setLock(null);
    setNearEnd(false);
    setChanges({});
  }, []);

  const lapse = useCallback(() => {
    leave();
    setLapsed(true);
  }, [leave]);

  const takeLock = useCallback(async () => {
    renewedAtRef.current = Date.now();
    const { data } = await takeMatchingEditLock(roundId);
    setLock(data);
  }, [roundId]);

  const start = async () => {
    setBusy(true);
    setLapsed(false);
    try {
      await takeLock();
      setEditing(true);
    } catch (err) {
      toast.error(messageOf(err, "Could not start editing."));
      if (err?.response?.status === HTTP_CONFLICT) reloadOverview();
    } finally {
      setBusy(false);
    }
  };

  const renew = () => {
    const renewing = takeLock().catch((err) => {
      toast.error(messageOf(err, "Could not renew your editing lock."));
      if (err?.response?.status === HTTP_CONFLICT && editingRef.current) {
        lapse();
        reloadOverview();
      }
    });
    renewingRef.current = renewing;
    return renewing;
  };

  const setRow = (item, next) => {
    const saved = savedRow(item);
    setChanges((prev) => {
      const rest = { ...prev };
      delete rest[saved.menteeId];
      if (
        next.mentorId === saved.mentorId &&
        next.recommendationReason === saved.recommendationReason
      ) {
        return rest;
      }
      return {
        ...rest,
        [saved.menteeId]: {
          mentorId: next.mentorId,
          recommendationReason: next.recommendationReason,
          baseMentorId: saved.mentorId,
        },
      };
    });
    if (Date.now() - renewedAtRef.current >= RENEW_EVERY_MS) renew();
  };

  const save = async () => {
    const payload = Object.entries(changes).map(([menteeId, change]) => ({
      menteeId,
      mentorId: change.mentorId,
      recommendationReason: change.recommendationReason,
    }));
    if (payload.length === 0) return;
    setBusy(true);
    // A renewal landing after the save would take the lock back.
    await renewingRef.current;
    try {
      await saveMatchingDraft(roundId, payload);
      leave();
      setReloadKey((k) => k + 1);
      reloadOverview();
    } catch (err) {
      toast.error(messageOf(err, "Could not save the draft."));
    } finally {
      setBusy(false);
    }
  };

  const discard = () => {
    leave();
    renewingRef.current
      .then(() => releaseMatchingEditLock(roundId))
      .catch((err) => {
        console.error("Failed to release the matching edit lock", err);
      })
      .finally(reloadOverview);
  };

  const expiresAt = editing && lock ? Date.parse(lock.expiresAt) : null;
  useEffect(() => {
    if (expiresAt == null) return undefined;
    const check = () => {
      const left = expiresAt - Date.now();
      if (left <= 0) lapse();
      else setNearEnd(left <= WARN_BEFORE_MS);
    };
    check();
    const timers = [
      setTimeout(check, Math.max(0, expiresAt - WARN_BEFORE_MS - Date.now())),
      setTimeout(check, Math.max(0, expiresAt - Date.now() + 1)),
    ];
    return () => timers.forEach(clearTimeout);
  }, [expiresAt, lapse]);

  useEffect(() => {
    const release = () => {
      if (editingRef.current) releaseMatchingEditLockOnLeave(roundId);
    };
    window.addEventListener("pagehide", release);
    return () => {
      window.removeEventListener("pagehide", release);
      release();
    };
  }, [roundId]);

  return {
    editing,
    busy,
    lock,
    nearEnd,
    lapsed,
    changes,
    reloadKey,
    start,
    keepEditing: renew,
    setRow,
    save,
    discard,
  };
};
