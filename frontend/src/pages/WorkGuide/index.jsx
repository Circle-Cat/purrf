import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { ListTree } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { useAuth } from "@/context/auth";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { useFeatureFlagsReady } from "@/hooks/useFeatureFlagsReady";
import { GUIDE_CHAPTERS } from "@/pages/WorkGuide/content";
import GuideArticle from "@/pages/WorkGuide/GuideArticle";
import GuideHome from "@/pages/WorkGuide/GuideHome";
import GuideNav from "@/pages/WorkGuide/GuideNav";
import { findFlow, visibleChapters } from "@/pages/WorkGuide/guideModel";

const NotInGuide = () => (
  <div className="flex max-w-3xl flex-col gap-3">
    <p className="text-lg font-semibold">This page isn&apos;t in the guide.</p>
    <Link to={ROUTE_PATHS.WORK_GUIDE} className="text-primary hover:underline">
      Back to the Work guide
    </Link>
  </div>
);

/**
 * The Work guide: step-by-step flows for doing work in Purrf, showing only
 * the chapters and flows the viewer's permissions cover.
 *
 * Renders nothing until the flags and auth have loaded, so a direct link is
 * not bounced early. Redirects to Access denied when the `work-guide` flag
 * is off or no chapter is visible. `/guide` shows the home page and
 * `/guide/:flowId` one flow; a flow that is unknown or hidden from the viewer
 * reads as not in the guide.
 *
 * @param {Object} props
 * @param {Array<Object>} [props.chapters] - Guide chapters; defaults to
 *   GUIDE_CHAPTERS.
 * @returns {JSX.Element|null}
 */
const WorkGuidePage = ({ chapters = GUIDE_CHAPTERS }) => {
  const { flowId } = useParams();
  const { permissions, loading } = useAuth();
  const flags = useFeatureFlags();
  const flagsReady = useFeatureFlagsReady();
  const [contentsOpen, setContentsOpen] = useState(false);
  const top = useRef(null);

  useEffect(() => {
    top.current?.scrollIntoView({ block: "start" });
  }, [flowId]);

  if (!flagsReady || loading) return null;

  const visible = visibleChapters(chapters, permissions ?? []);
  if (!flags[FEATURE_FLAGS.WORK_GUIDE] || visible.length === 0) {
    return <Navigate to={ROUTE_PATHS.ACCESS_DENIED} replace />;
  }

  const found = flowId ? findFlow(visible, flowId) : null;
  let content;
  if (!flowId) content = <GuideHome chapters={visible} />;
  else if (found) content = <GuideArticle {...found} chapters={visible} />;
  else content = <NotInGuide />;

  return (
    <div ref={top} className="flex scroll-mt-28 items-start gap-8">
      <aside className="sticky top-24 hidden max-h-[calc(100vh-7rem)] w-64 shrink-0 overflow-y-auto rounded-xl border bg-muted/40 p-4 lg:block">
        <GuideNav chapters={visible} currentFlowId={flowId} />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col gap-4">
        <div className="lg:hidden">
          <Sheet open={contentsOpen} onOpenChange={setContentsOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" size="sm">
                <ListTree aria-hidden="true" />
                Contents
              </Button>
            </SheetTrigger>
            {/* Above the fixed header (z-100), which would otherwise cover the top. */}
            <SheetContent side="left" className="z-[110] overflow-y-auto p-4">
              <SheetHeader className="p-0">
                <SheetTitle>Work guide</SheetTitle>
              </SheetHeader>
              <GuideNav
                chapters={visible}
                currentFlowId={flowId}
                onNavigate={() => setContentsOpen(false)}
              />
            </SheetContent>
          </Sheet>
        </div>
        {content}
      </div>
    </div>
  );
};

export default WorkGuidePage;
