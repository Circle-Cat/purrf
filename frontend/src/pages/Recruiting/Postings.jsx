import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/context/auth/AuthContext";
import {
  listJobs, createJob, updateJob, closeJob, reopenJob,
  listApprovers, submitForReview,
} from "@/api/recruitingApi";
import PostingsList from "@/pages/Recruiting/components/PostingsList";
import PostingForm from "@/pages/Recruiting/components/PostingForm";
import SubmitReviewDialog from "@/pages/Recruiting/components/SubmitReviewDialog";

/** Postings management page: lifecycle + review submission. */
const Postings = () => {
  const { user } = useAuth();
  const [jobs, setJobs] = useState([]);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [submitOpen, setSubmitOpen] = useState(false);
  const [submitJobId, setSubmitJobId] = useState(null);
  const [approvers, setApprovers] = useState([]);

  const refresh = useCallback(async () => {
    const { data } = await listJobs();
    setJobs(data ?? []);
  }, []);

  useEffect(() => {
    refresh().catch((e) => toast.error(e.message));
  }, [refresh]);

  const run = async (fn, ok) => {
    try {
      await fn();
      await refresh();
      toast.success(ok);
    } catch (e) {
      toast.error(e.message);
    }
  };

  const openCreate = () => { setEditing(null); setFormOpen(true); };
  const openEdit = (job) => { setEditing(job); setFormOpen(true); };

  const handleFormSubmit = (body) => {
    setFormOpen(false);
    run(
      () => (editing ? updateJob(editing.id, body) : createJob(body)),
      editing ? "Posting updated." : "Posting created.",
    );
  };

  const openSubmit = async (jobId) => {
    try {
      const { data } = await listApprovers();
      setApprovers(data ?? []);
      setSubmitJobId(jobId);
      setSubmitOpen(true);
    } catch (e) {
      toast.error(e.message);
    }
  };

  const handleSubmitReview = (body) => {
    setSubmitOpen(false);
    run(() => submitForReview(submitJobId, body), "Submitted for review.");
  };

  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Postings</h1>
        <Button onClick={openCreate}>New posting</Button>
      </div>
      <PostingsList
        jobs={jobs}
        onEdit={openEdit}
        onSubmit={openSubmit}
        onClose={(id) => run(() => closeJob(id), "Posting closed.")}
        onReopen={(id) => run(() => reopenJob(id), "Posting reopened.")}
      />
      <PostingForm
        open={formOpen}
        job={editing}
        onSubmit={handleFormSubmit}
        onOpenChange={setFormOpen}
      />
      <SubmitReviewDialog
        open={submitOpen}
        approvers={approvers}
        currentUserId={user?.userId}
        onSubmit={handleSubmitReview}
        onOpenChange={setSubmitOpen}
      />
    </div>
  );
};

export default Postings;
