import { Link, useNavigate } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import GuideBlocks from "@/pages/WorkGuide/GuideBlocks";
import { headingsOf, neighbours } from "@/pages/WorkGuide/guideModel";
import { highlightAnchor } from "@/whatsNew/highlightAnchor";
import { renderBody } from "@/whatsNew/renderBody";

const NeighbourCard = ({ flow, label, align }) => (
  <Link
    to={ROUTE_PATHS.WORK_GUIDE_FLOW(flow.id)}
    className={`flex flex-col gap-1 rounded-xl border p-4 no-underline hover:bg-muted ${
      align === "right" ? "text-right" : ""
    }`}
  >
    <span className="text-xs text-muted-foreground">{label}</span>
    <span className="font-semibold text-primary">
      {align === "right" ? `${flow.title} →` : `← ${flow.title}`}
    </span>
  </Link>
);

/**
 * One flow of the guide: breadcrumb, title, who it is for, intro, its blocks,
 * links to the flows before and after it, and an "On this page" list.
 *
 * "Open in Purrf →" on a step goes to the step's page and outlines the
 * element it names.
 *
 * @param {Object} props
 * @param {Object} props.chapter - The flow's chapter.
 * @param {Object} props.flow - The flow to show.
 * @param {Array<Object>} props.chapters - Chapters the viewer may see, for
 *   the previous and next flows.
 * @returns {JSX.Element}
 */
const GuideArticle = ({ chapter, flow, chapters }) => {
  const navigate = useNavigate();
  const headings = headingsOf(flow);
  const { previous, next } = neighbours(chapters, flow.id);

  const openStep = (step) => {
    navigate(step.route);
    if (step.anchor) highlightAnchor(step.anchor);
  };

  return (
    <div className="flex items-start gap-12">
      <article className="flex max-w-3xl min-w-0 flex-1 flex-col gap-6">
        <nav
          aria-label="Breadcrumb"
          className="flex flex-wrap gap-1.5 text-sm text-muted-foreground"
        >
          <Link to={ROUTE_PATHS.WORK_GUIDE} className="hover:underline">
            Work guide
          </Link>
          <span aria-hidden="true">/</span>
          <span>{chapter.title}</span>
          <span aria-hidden="true">/</span>
          <span className="text-foreground">{flow.title}</span>
        </nav>

        <header className="flex flex-col gap-2.5">
          <h1 className="text-3xl font-bold tracking-tight">{flow.title}</h1>
          {flow.whoFor && (
            <Badge variant="outline" className="font-normal">
              For: {flow.whoFor}
            </Badge>
          )}
          {flow.intro && (
            <p className="leading-relaxed text-muted-foreground">
              {renderBody(flow.intro)}
            </p>
          )}
        </header>

        <GuideBlocks
          blocks={flow.blocks}
          headingIds={headings.map((h) => h.id)}
          onOpen={openStep}
        />

        {(previous || next) && (
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {previous ? (
              <NeighbourCard flow={previous} label="Previous" align="left" />
            ) : (
              <span />
            )}
            {next && <NeighbourCard flow={next} label="Next" align="right" />}
          </div>
        )}
      </article>

      {headings.length > 0 && (
        <nav
          aria-label="On this page"
          className="sticky top-28 hidden w-48 shrink-0 flex-col gap-2.5 pt-12 text-sm xl:flex"
        >
          <div className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            On this page
          </div>
          {headings.map((heading) => (
            <a
              key={heading.id}
              href={`#${heading.id}`}
              className="border-l-2 pl-2.5 text-muted-foreground hover:border-primary hover:text-foreground"
            >
              {heading.text}
            </a>
          ))}
        </nav>
      )}
    </div>
  );
};

export default GuideArticle;
