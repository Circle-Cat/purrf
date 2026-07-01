import { useState } from "react";
import { Button } from "@/components/ui/button";
import PostingApplicantView from "@/pages/Recruiting/components/PostingApplicantView";
import PipelineSummary from "@/pages/Recruiting/components/PipelineSummary";

/**
 * Shared reviewer/preview body for a posting: the applicant-facing view plus a
 * readable pipeline summary. For a revision (an edit to a published posting) it
 * shows a Pending|Live toggle (Pending default) over the form/profile/pipeline.
 *
 * @param {{job: object, isRevision?: boolean}} props
 */
const PostingReviewView = ({ job, isRevision = false }) => {
  const [version, setVersion] = useState("pending");
  const showPending = isRevision && version === "pending";

  const questions = showPending
    ? (job.pendingFormSchema?.questions ?? [])
    : (job.formSchema?.questions ?? []);
  const profileConfig = showPending
    ? (job.pendingProfileConfig ?? job.profileConfig)
    : job.profileConfig;
  const pipelineConfig = showPending
    ? (job.pendingPipelineConfig ?? job.pipelineConfig)
    : job.pipelineConfig;

  return (
    <div className="space-y-4">
      {isRevision && (
        <div className="flex gap-2">
          <Button
            size="sm"
            variant={version === "pending" ? "default" : "outline"}
            onClick={() => setVersion("pending")}
          >
            Pending
          </Button>
          <Button
            size="sm"
            variant={version === "live" ? "default" : "outline"}
            onClick={() => setVersion("live")}
          >
            Live
          </Button>
        </div>
      )}
      <PostingApplicantView
        key={version}
        title={job.title}
        kind={job.kind}
        description={job.description}
        questions={questions}
        profileConfig={profileConfig}
      />
      <PipelineSummary pipelineConfig={pipelineConfig} />
    </div>
  );
};

export default PostingReviewView;
