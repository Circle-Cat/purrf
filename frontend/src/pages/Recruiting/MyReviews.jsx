import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { listMyReviews, getJob, decideReview } from "@/api/recruitingApi";
import ReviewQueue from "@/pages/Recruiting/components/ReviewQueue";
import ReviewDetail from "@/pages/Recruiting/components/ReviewDetail";
import HowItWorksDialog from "@/pages/Recruiting/components/HowItWorksDialog";
import { REVIEWS_GUIDE } from "@/pages/Recruiting/components/guideContent";

/** Reviewer's queue page: list pending reviews and decide on one. */
const MyReviews = () => {
  const [reviews, setReviews] = useState([]);
  const [active, setActive] = useState(null); // {review, job}

  const refresh = useCallback(async () => {
    const { data } = await listMyReviews();
    setReviews(data ?? []);
  }, []);

  useEffect(() => {
    refresh().catch((e) => toast.error(e.message));
  }, [refresh]);

  const open = async (review) => {
    try {
      const { data } = await getJob(review.jobId);
      setActive({ review, job: data });
    } catch (e) {
      toast.error(e.message);
    }
  };

  const decide = async (body, ok) => {
    try {
      await decideReview(active.review.reviewId, body);
      setActive(null);
      await refresh();
      toast.success(ok);
    } catch (e) {
      toast.error(e.message);
    }
  };

  if (active) {
    return (
      <ReviewDetail
        review={active.review}
        job={active.job}
        onApprove={() => decide({ decision: "approve" }, "Review approved.")}
        onReject={(comment) =>
          decide({ decision: "reject", comment }, "Review rejected.")
        }
        onBack={() => setActive(null)}
      />
    );
  }

  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">My reviews</h1>
        <HowItWorksDialog {...REVIEWS_GUIDE} />
      </div>
      <ReviewQueue reviews={reviews} onOpen={open} />
    </div>
  );
};

export default MyReviews;
