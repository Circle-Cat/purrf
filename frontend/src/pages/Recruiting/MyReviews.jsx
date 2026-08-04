import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { listMyReviews } from "@/api/recruitingApi";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import ReviewQueue from "@/pages/Recruiting/components/ReviewQueue";
import HowItWorksDialog from "@/pages/Recruiting/components/HowItWorksDialog";
import { REVIEWS_GUIDE } from "@/pages/Recruiting/components/guideContent";

/** Reviewer's queue page: list pending reviews, opening one goes to the unified job detail page. */
const MyReviews = () => {
  const navigate = useNavigate();
  const [reviews, setReviews] = useState([]);

  const refresh = useCallback(async () => {
    const { data } = await listMyReviews();
    setReviews(data ?? []);
  }, []);

  useEffect(() => {
    refresh().catch((e) => toast.error(e.message));
  }, [refresh]);

  const open = (review) => {
    navigate(ROUTE_PATHS.RECRUITING_POSTING_DETAIL(review.jobId));
  };

  return (
    <div className="space-y-4 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">
          My Posting Reviews
        </h1>
        <HowItWorksDialog {...REVIEWS_GUIDE} />
      </div>
      <ReviewQueue reviews={reviews} onOpen={open} />
    </div>
  );
};

export default MyReviews;
