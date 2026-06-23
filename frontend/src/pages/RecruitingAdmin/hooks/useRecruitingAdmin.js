import { useCallback, useEffect, useState } from "react";
import {
  getJobs,
  createJob,
  updateJob,
  publishJob,
  closeJob,
} from "@/api/recruitingApi";

/**
 * Hook for the Recruiting Admin page.
 *
 * Fetches published job postings on mount and maintains a merged local list
 * that also tracks draft postings created in the current session (since the
 * backend `getJobs` endpoint returns published postings only). Manages the
 * create/edit modal state and exposes handlers for publish and close actions.
 *
 * @param {boolean} [canRead=true] - Whether the current user holds
 *   `RECRUITING_JOB_READ`; skips the API call and returns empty state when false.
 * @returns {{
 *   postings: Object[],
 *   isLoading: boolean,
 *   jobModalState: { open: boolean, job: Object|null },
 *   openCreate: () => void,
 *   openEdit: (job: Object) => void,
 *   closeModal: () => void,
 *   saveJob: (payload: Object) => Promise<void>,
 *   handlePublish: (jobId: number|string) => Promise<void>,
 *   handleClose: (jobId: number|string) => Promise<void>,
 * }}
 */
export const useRecruitingAdmin = (canRead = true) => {
  const [postings, setPostings] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  /**
   * Modal state.
   * - `open: false` → modal closed
   * - `job: null`   → create mode
   * - `job: Object` → edit mode
   *
   * @type {{ open: boolean, job: Object|null }}
   */
  const [jobModalState, setJobModalState] = useState({
    open: false,
    job: null,
  });

  /**
   * Merges a set of freshly-fetched published postings with any locally-held
   * draft postings created in the current session. Draft postings that have
   * since been published (returned by `getJobs`) are replaced by the server
   * version so their status badge stays accurate.
   *
   * @param {Object[]} fetched - Published postings returned by `getJobs`.
   */
  const mergePublished = useCallback((fetched) => {
    setPostings((prev) => {
      const fetchedById = new Map(fetched.map((j) => [j.id, j]));
      // Keep locally-created drafts that are not yet in the fetched set.
      const localDrafts = prev.filter(
        (j) => j.status === "draft" && !fetchedById.has(j.id),
      );
      return [...fetched, ...localDrafts];
    });
  }, []);

  const refreshJobs = useCallback(async () => {
    if (!canRead) {
      setPostings([]);
      setIsLoading(false);
      return;
    }
    setIsLoading(true);
    try {
      const { data } = await getJobs();
      mergePublished(data ?? []);
    } catch (err) {
      console.error("Failed to fetch job postings", err);
    } finally {
      setIsLoading(false);
    }
  }, [canRead, mergePublished]);

  useEffect(() => {
    refreshJobs();
  }, [refreshJobs]);

  /** Opens the modal in create mode. */
  const openCreate = () => setJobModalState({ open: true, job: null });

  /**
   * Opens the modal in edit mode for an existing posting.
   *
   * @param {Object} job - The posting to edit.
   */
  const openEdit = (job) => setJobModalState({ open: true, job });

  /** Closes the modal without saving. */
  const closeModal = () => setJobModalState({ open: false, job: null });

  /**
   * Creates or updates a posting, adds drafts to the local list immediately,
   * and closes the modal.
   *
   * @param {Object} payload - Fields from the modal form.
   * @param {string} payload.title
   * @param {string} payload.description
   * @param {string} payload.kind
   * @param {string} payload.mentorshipRole
   * @param {Object} payload.formSchema
   * @returns {Promise<void>}
   */
  const saveJob = async (payload) => {
    const { job } = jobModalState;
    if (job?.id) {
      const { data: updated } = await updateJob(job.id, payload);
      setPostings((prev) =>
        prev.map((p) => (p.id === updated.id ? updated : p)),
      );
    } else {
      const { data: created } = await createJob(payload);
      // Keep the new draft in the local list; refreshJobs would not return it.
      setPostings((prev) => {
        const exists = prev.some((p) => p.id === created.id);
        return exists ? prev : [...prev, created];
      });
    }
    closeModal();
  };

  /**
   * Publishes the posting with the given id and refreshes the list.
   *
   * @param {number|string} jobId
   * @returns {Promise<void>}
   */
  const handlePublish = async (jobId) => {
    await publishJob(jobId);
    await refreshJobs();
  };

  /**
   * Closes the posting with the given id and refreshes the list.
   *
   * @param {number|string} jobId
   * @returns {Promise<void>}
   */
  const handleClose = async (jobId) => {
    await closeJob(jobId);
    await refreshJobs();
  };

  return {
    postings,
    isLoading,
    jobModalState,
    openCreate,
    openEdit,
    closeModal,
    saveJob,
    handlePublish,
    handleClose,
  };
};
