import { Link } from "react-router-dom";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

const START_HERE_ID = "start-here";

/**
 * The guide's landing page: a Start here card pointing at the first flow to
 * read, then one card per visible chapter listing its flows.
 *
 * @param {Object} props
 * @param {Array<Object>} props.chapters - Chapters the viewer may see.
 * @returns {JSX.Element}
 */
const GuideHome = ({ chapters }) => {
  const startHere = chapters.find((chapter) => chapter.id === START_HERE_ID);
  const first = startHere?.flows[0];

  return (
    <div className="flex max-w-4xl flex-col gap-7">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight">Work guide</h1>
        <p className="text-muted-foreground">
          How to do your work in Purrf, step by step. You only see the parts
          that match your permissions.
        </p>
      </div>

      {first && (
        <Link
          to={ROUTE_PATHS.WORK_GUIDE_FLOW(first.id)}
          className="flex flex-col justify-between gap-4 rounded-xl border border-primary/30 bg-primary/5 p-6 text-foreground no-underline hover:bg-primary/10 sm:flex-row sm:items-center"
        >
          <div className="flex flex-col gap-1.5">
            <span className="text-xs font-semibold tracking-wide text-primary uppercase">
              {startHere.title}
            </span>
            <span className="text-xl font-semibold">{first.title}</span>
            <span className="text-sm text-muted-foreground">
              {startHere.description}
            </span>
          </div>
          <span className="text-sm font-semibold whitespace-nowrap text-primary">
            Read this first →
          </span>
        </Link>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {chapters.map((chapter) => (
          <section
            key={chapter.id}
            className="flex flex-col gap-2.5 rounded-xl border p-5"
          >
            <h2 className="text-lg font-semibold">{chapter.title}</h2>
            <p className="text-sm text-muted-foreground">
              {chapter.description}
            </p>
            <ul className="flex flex-col gap-1.5 text-sm">
              {chapter.flows.map((flow) => (
                <li key={flow.id}>
                  <Link
                    to={ROUTE_PATHS.WORK_GUIDE_FLOW(flow.id)}
                    className="text-primary hover:underline"
                  >
                    {flow.title}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
};

export default GuideHome;
