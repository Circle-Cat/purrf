import { useState } from "react";
import FormRenderer from "@/pages/Recruiting/postings/FormRenderer";
import ProfileRequirements from "@/pages/Recruiting/components/ProfileRequirements";

/**
 * Read-only, applicant-facing rendering of one version of a posting: title,
 * kind, description, profile requirements, and the interactive submission form.
 * Owns throwaway answer state so `showWhen` conditionals work while previewing;
 * answers are never submitted. Remount with a `key` to reset answers.
 *
 * @param {{title?: string, kind?: string, description?: string,
 *          questions?: object[], profileConfig?: object}} props
 */
const PostingApplicantView = ({
  title,
  kind,
  description,
  questions = [],
  profileConfig,
}) => {
  const [answers, setAnswers] = useState({});

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
      <ProfileRequirements profileConfig={profileConfig} />
      <FormRenderer
        questions={questions}
        answers={answers}
        onAnswerChange={(id, value) =>
          setAnswers((a) => ({ ...a, [id]: value }))
        }
      />
    </div>
  );
};

export default PostingApplicantView;
