import { useState } from "react";
import FormRenderer from "@/pages/Recruiting/postings/FormRenderer";
import RecruitingProfileForm from "@/pages/Recruiting/components/RecruitingProfileForm";

/**
 * Read-only, applicant-facing rendering of one version of a posting: title,
 * kind, description, the profile form, and the interactive submission form.
 * Profile value and answers can be lifted to a parent (e.g. a future
 * submission form) via `profileValue`/`onProfileChange` and
 * `answers`/`onAnswerChange`; when those callbacks are omitted, the component
 * owns throwaway internal state so `showWhen` conditionals work while
 * previewing and answers are never submitted. Remount with a `key` to reset
 * internally-owned answers.
 *
 * @param {{title?: string, kind?: string, description?: string,
 *          questions?: object[], profileConfig?: object,
 *          profileValue?: {personal: object, education: object[], experience: object[]},
 *          onProfileChange?: (value: object) => void,
 *          answers?: Record<string, unknown>,
 *          onAnswerChange?: (id: string, value: unknown) => void,
 *          contactEmail?: string,
 *          onResumeStored?: (resume: {sha256: string, objectKey: string}) => void}} props
 */
const PostingApplicantView = ({
  title,
  kind,
  description,
  questions = [],
  profileConfig,
  profileValue,
  onProfileChange,
  answers: controlledAnswers,
  onAnswerChange,
  contactEmail,
  onResumeStored,
}) => {
  const [internalAnswers, setInternalAnswers] = useState({});
  const answers = controlledAnswers ?? internalAnswers;
  /** Merge one answer into the controlling parent's state or internal state. */
  const handleAnswerChange = (id, value) => {
    if (onAnswerChange) onAnswerChange(id, value);
    else setInternalAnswers((a) => ({ ...a, [id]: value }));
  };

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        {title && (
          <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        )}
        {kind && <p className="text-sm text-slate-500 capitalize">{kind}</p>}
      </div>
      {description && (
        <p className="text-sm whitespace-pre-line text-slate-700">
          {description}
        </p>
      )}
      <RecruitingProfileForm
        profileConfig={profileConfig}
        value={profileValue}
        onChange={onProfileChange}
        contactEmail={contactEmail}
        onResumeStored={onResumeStored}
      />
      <FormRenderer
        questions={questions}
        answers={answers}
        onAnswerChange={handleAnswerChange}
      />
    </div>
  );
};

export default PostingApplicantView;
