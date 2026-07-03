import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { listInterviewPool, listJobOwners } from "@/api/recruitingApi";
import PostingApplicantView from "@/pages/Recruiting/components/PostingApplicantView";
import PipelineSummary from "@/pages/Recruiting/components/PipelineSummary";

/**
 * Shared reviewer/preview body for a posting: the applicant-facing view plus a
 * readable pipeline summary. For a revision (an edit to a published posting) it
 * shows a Pending|Live toggle (Pending default) over the form/profile/pipeline.
 * Fetches the interview + owner pools once so PipelineSummary can show names.
 *
 * @param {{job: object, isRevision?: boolean}} props
 */
const PostingReviewView = ({ job, isRevision = false }) => {
  const [version, setVersion] = useState("pending");
  const [interviewPool, setInterviewPool] = useState([]);
  const [jobOwners, setJobOwners] = useState([]);
  const showPending = isRevision && version === "pending";

  useEffect(() => {
    Promise.all([listInterviewPool(), listJobOwners()])
      .then(([pool, owners]) => {
        setInterviewPool(pool.data ?? []);
        setJobOwners(owners.data ?? []);
      })
      .catch((e) => toast.error(e.message));
  }, []);

  const questions = showPending
    ? (job.pendingPayload?.formSchema?.questions ??
      job.formSchema?.questions ??
      [])
    : (job.formSchema?.questions ?? []);
  const profileConfig = showPending
    ? (job.pendingPayload?.profileConfig ?? job.profileConfig)
    : job.profileConfig;
  const pipelineConfig = showPending
    ? (job.pendingPayload?.pipelineConfig ?? job.pipelineConfig)
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
      <PipelineSummary
        pipelineConfig={pipelineConfig}
        interviewPool={interviewPool}
        jobOwners={jobOwners}
      />
    </div>
  );
};

export default PostingReviewView;
