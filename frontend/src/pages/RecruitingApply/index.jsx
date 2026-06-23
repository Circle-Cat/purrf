import React, { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { toast } from "sonner";

import { getJob, submitApplication } from "@/api/recruitingApi";
import { getMyProfile, updateMyProfile } from "@/api/profileApi";
import JsonSchemaForm, {
  validate,
} from "@/components/recruiting/JsonSchemaForm";
import ExperienceEditModal from "@/pages/Profile/modals/ExperienceEditModal";
import { Button } from "@/components/ui/button";
import {
  parseDateParts,
  sortExperienceOrEducationList,
} from "@/pages/Profile/utils";

/**
 * Map a raw workHistory array from the profile API into the shape expected
 * by ExperienceEditModal.
 *
 * @param {Array<object>} workHistory - Raw work-history entries from the API.
 * @returns {Array<object>} Mapped and sorted experience list.
 */
function mapWorkHistory(workHistory) {
  return (workHistory ?? [])
    .map((exp) => {
      const startParts = parseDateParts(exp.startDate);
      const endParts = parseDateParts(exp.endDate);
      return {
        id: exp.id,
        title: exp.title,
        company: exp.companyOrOrganization,
        startMonth: startParts.month,
        startYear: startParts.year,
        endMonth: endParts.month,
        endYear: endParts.year,
        isCurrentlyWorking: exp.isCurrentJob,
      };
    })
    .sort(sortExperienceOrEducationList);
}

/**
 * RecruitingApply
 *
 * Candidate-facing page for applying to a job posting.
 *
 * - Loads the job via `getJob(jobId)` on mount and shows the title + description.
 * - Lets the candidate review / edit their work-history experience using the
 *   shared `ExperienceEditModal`, persisting changes via `updateMyProfile`.
 * - Renders a `JsonSchemaForm` bound to `job.formSchema` for role-specific
 *   questions, keeping answers in local state.
 * - On submit: validates required fields via `validate(schema, answers)`; if
 *   any are missing shows inline errors and blocks submission. On success calls
 *   `submitApplication(jobId, answers)` and shows a sonner success toast.
 * - Round-name banner is deferred (no backend endpoint yet).
 * - No permission gate — any authenticated user may apply.
 *
 * Route: /recruiting/apply/:jobId
 *
 * @returns {JSX.Element}
 */
const RecruitingApply = () => {
  const { jobId } = useParams();

  /** @type {[object|null, Function]} */
  const [job, setJob] = useState(null);

  /** @type {[boolean, Function]} */
  const [isLoadingJob, setIsLoadingJob] = useState(true);

  /** Candidate's current work-history, shaped for ExperienceEditModal. */
  const [experienceList, setExperienceList] = useState([]);

  /** Controls whether ExperienceEditModal is open. */
  const [isExpModalOpen, setIsExpModalOpen] = useState(false);

  /** Role-question answers keyed by formSchema property name. */
  const [answers, setAnswers] = useState({});

  /** Validation errors from the last submit attempt, keyed by field name. */
  const [fieldErrors, setFieldErrors] = useState({});

  /** Whether a submission is in-flight. */
  const [isSubmitting, setIsSubmitting] = useState(false);

  /**
   * Fetch the job posting on mount.
   */
  useEffect(() => {
    let cancelled = false;
    setIsLoadingJob(true);
    getJob(jobId)
      .then(({ data }) => {
        if (!cancelled) setJob(data);
      })
      .finally(() => {
        if (!cancelled) setIsLoadingJob(false);
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  /**
   * Fetch the candidate's profile (work history) on mount so we can
   * pre-populate the experience editor.
   */
  useEffect(() => {
    getMyProfile().then(({ data: { profile } }) => {
      if (!profile) return;
      setExperienceList(mapWorkHistory(profile.workHistory));
    });
  }, []);

  /**
   * Save updated experience via the profile API and refresh local state.
   * Called by ExperienceEditModal's `onSave` prop; the modal handles closing
   * itself after this resolves.
   *
   * @param {object} payload - Payload shaped by ExperienceEditModal's onSave.
   */
  const handleSaveExperience = async (payload) => {
    const {
      data: { profile },
    } = await updateMyProfile(payload);
    if (profile) {
      setExperienceList(mapWorkHistory(profile.workHistory));
    }
  };

  /**
   * Validate and submit the application.
   */
  const handleSubmit = async () => {
    if (!job) return;

    const errors = validate(job.formSchema, answers);
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setFieldErrors({});
    setIsSubmitting(true);
    try {
      await submitApplication(jobId, answers);
      toast.success("Application submitted successfully!");
    } catch (err) {
      toast.error("Failed to submit application. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoadingJob) {
    return (
      <div className="flex items-center justify-center p-12">
        <p className="text-muted-foreground">Loading…</p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="flex items-center justify-center p-12">
        <p className="text-muted-foreground">Job posting not found.</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-8">
      {/* ── Job header ──────────────────────────────────────────────────── */}
      <div className="space-y-2">
        <h1 className="text-2xl font-bold">{job.title}</h1>
        {job.description && (
          <p className="text-muted-foreground whitespace-pre-wrap">
            {job.description}
          </p>
        )}
      </div>

      {/* ── Experience section ───────────────────────────────────────────── */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">Your Experience</h2>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsExpModalOpen(true)}
          >
            Edit experience
          </Button>
        </div>

        {experienceList.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No work history on file. Click &quot;Edit experience&quot; to add
            entries.
          </p>
        ) : (
          <ul className="space-y-2">
            {experienceList.map((exp) => (
              <li
                key={exp.id}
                className="rounded-lg border p-3 text-sm space-y-0.5"
              >
                <p className="font-medium">{exp.title}</p>
                <p className="text-muted-foreground">{exp.company}</p>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* ── Role questions ────────────────────────────────────────────────── */}
      {job.formSchema && (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold">Role questions</h2>
          <JsonSchemaForm
            schema={job.formSchema}
            value={answers}
            onChange={setAnswers}
          />
          {/* Show per-field validation errors */}
          {Object.keys(fieldErrors).length > 0 && (
            <ul className="space-y-1">
              {Object.entries(fieldErrors).map(([key, msg]) => (
                <li key={key} className="text-sm text-destructive">
                  {job.formSchema.properties?.[key]?.title ?? key}: {msg}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* ── Submit ────────────────────────────────────────────────────────── */}
      <Button
        onClick={handleSubmit}
        disabled={isSubmitting}
        className="w-full"
      >
        {isSubmitting ? "Submitting…" : "Submit application"}
      </Button>

      {/* ── Experience modal ──────────────────────────────────────────────── */}
      <ExperienceEditModal
        isOpen={isExpModalOpen}
        onClose={() => setIsExpModalOpen(false)}
        initialData={experienceList}
        onSave={handleSaveExperience}
      />
    </div>
  );
};

export default RecruitingApply;
