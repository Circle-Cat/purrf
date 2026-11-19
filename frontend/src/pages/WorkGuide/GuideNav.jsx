import { useState } from "react";
import { Link } from "react-router-dom";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { searchFlows } from "@/pages/WorkGuide/guideModel";

const FlowLink = ({ flow, current, onNavigate }) => (
  <Link
    to={ROUTE_PATHS.WORK_GUIDE_FLOW(flow.id)}
    onClick={onNavigate}
    aria-current={current ? "page" : undefined}
    className={`rounded-md px-2 py-1.5 text-sm no-underline ${
      current
        ? "bg-primary/10 font-semibold text-primary"
        : "text-foreground hover:bg-muted"
    }`}
  >
    {flow.title}
  </Link>
);

/**
 * The guide's own navigation: a search box over the visible flows, then the
 * chapters with their flows, the current flow highlighted.
 *
 * @param {Object} props
 * @param {Array<Object>} props.chapters - Chapters the viewer may see.
 * @param {string} [props.currentFlowId] - The flow being read, if any.
 * @param {() => void} [props.onNavigate] - Called when a flow link is
 *   followed, so a sheet holding the nav can close.
 * @returns {JSX.Element}
 */
const GuideNav = ({ chapters, currentFlowId, onNavigate }) => {
  const [query, setQuery] = useState("");
  const searching = query.trim() !== "";
  const matches = searching ? searchFlows(chapters, query) : [];

  return (
    <nav aria-label="Work guide contents" className="flex flex-col gap-5">
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="work-guide-search"
          className="text-xs font-semibold text-muted-foreground"
        >
          Search the guide
        </label>
        <div className="relative">
          <Search
            className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            id="work-guide-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g. reply, reject, approve"
            className="bg-background pl-8"
          />
        </div>
      </div>

      {searching ? (
        matches.length === 0 ? (
          <p className="px-2 text-sm text-muted-foreground">No matches</p>
        ) : (
          <div className="flex flex-col gap-1">
            {matches.map((flow) => (
              <FlowLink
                key={flow.id}
                flow={flow}
                current={flow.id === currentFlowId}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        )
      ) : (
        chapters.map((chapter) => (
          <div key={chapter.id} className="flex flex-col gap-1">
            <div className="px-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
              {chapter.title}
            </div>
            {chapter.flows.map((flow) => (
              <FlowLink
                key={flow.id}
                flow={flow}
                current={flow.id === currentFlowId}
                onNavigate={onNavigate}
              />
            ))}
          </div>
        ))
      )}
    </nav>
  );
};

export default GuideNav;
