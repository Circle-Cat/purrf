import { useState } from "react";
import {
  Link,
  useLocation,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { formatInTz } from "@/utils/dateTime";
import { MEETING_TIMEZONE } from "@/pages/MentorshipManagement/utils/attendanceIssues";
import {
  RUN_STATUS,
  checkedLabels,
  personWithId,
  scoreLabel,
  surveyLabel,
} from "@/pages/MentorshipManagement/utils/matchingLabels";
import {
  useMatchingResults,
  useMatchingRun,
  useMatchingUnmatched,
} from "@/pages/MentorshipManagement/hooks/useMatchingRun";
import { useParticipantSearchRounds } from "@/pages/MentorshipManagement/hooks/useParticipantSearchRounds";

const LIMIT = 20;

const TAB = Object.freeze({
  MATCHED: "matched",
  UNMATCHED: "unmatched",
});

const STATUS_BADGE = {
  [RUN_STATUS.NEVER_RUN]: { label: "Not run", variant: "secondary" },
  [RUN_STATUS.RUNNING]: { label: "Running", variant: "secondary" },
  [RUN_STATUS.FAILED]: { label: "Failed", variant: "destructive" },
  [RUN_STATUS.UNUSABLE]: { label: "Unusable", variant: "destructive" },
  [RUN_STATUS.SUCCEEDED]: { label: "Succeeded", variant: "secondary" },
};

const MATCH_TYPE_LABEL = {
  hungarian: "Scored",
  mutual_yes: "Both asked",
};

const CANDIDATES_NOTE =
  "A candidate can score higher than the chosen mentor: the matcher finds the best set of pairs overall, not the best mentor for each mentee alone.";

/** @param {{overview: Object}} props */
const StatusBadge = ({ overview }) => {
  const published =
    overview.status === RUN_STATUS.SUCCEEDED && overview.published;
  const { label, variant } = published
    ? { label: "Published", variant: "default" }
    : (STATUS_BADGE[overview.status] ?? {
        label: overview.status,
        variant: "secondary",
      });
  return <Badge variant={variant}>{label}</Badge>;
};

/** "Run 12 · started by Ann Lee at 2026-10-05 14:30 · 3 mentors, 5 mentees" */
const runLine = (overview) => {
  const by =
    overview.triggeredByName ||
    (overview.triggeredByUserId != null
      ? `ID ${overview.triggeredByUserId}`
      : "unknown");
  const at = formatInTz(
    overview.startedAt,
    MEETING_TIMEZONE,
    "yyyy-MM-dd HH:mm",
  );
  return `Run ${overview.runId} · started by ${by} at ${at} · ${overview.mentorCount} mentors, ${overview.menteeCount} mentees`;
};

/** A titled block of a profile card; nothing at all when it has no lines. */
const Section = ({ title, lines }) => {
  const shown = lines.filter(Boolean);
  if (shown.length === 0) return null;
  return (
    <div>
      <div className="text-xs font-semibold uppercase text-muted-foreground">
        {title}
      </div>
      {shown.map((line, i) => (
        <div key={i}>{line}</div>
      ))}
    </div>
  );
};

const span = (start, end) =>
  start || end ? `${start ?? "?"}–${end ?? ""}` : "";

const workLine = (w) => {
  const role = [w.title, w.company].filter(Boolean).join(" at ");
  const when = span(w.startDate, w.isCurrentJob ? "present" : w.endDate);
  return [role, when].filter(Boolean).join(", ");
};

const educationLine = (e) =>
  [e.degree, e.fieldOfStudy, e.school, span(e.startDate, e.endDate)]
    .filter(Boolean)
    .join(", ");

const labelled = (label, value) => (value ? `${label}: ${value}` : null);

const surveyLines = (p, isMentor) => {
  const roleLines = isMentor
    ? [
        labelled(
          "Career transition",
          surveyLabel(
            "careerTransition",
            p.careerTransition,
            p.careerTransitionOther,
          ),
        ),
        labelled(
          "Development region",
          surveyLabel(
            "developmentRegion",
            p.developmentRegion,
            p.developmentRegionOther,
          ),
        ),
        labelled(
          "Mentoring elsewhere",
          surveyLabel("externalMentoringExp", p.externalMentoringExp),
        ),
        p.maxPartners != null ? `Slots this run: ${p.maxPartners}` : null,
      ]
    : [
        labelled(
          "Transition",
          surveyLabel(
            "transitionType",
            p.transitionType,
            p.transitionTypeOther,
          ),
        ),
        labelled("Urgency", surveyLabel("urgency", p.urgency)),
        labelled(
          "Job market",
          surveyLabel(
            "jobMarketRegion",
            p.jobMarketRegion,
            p.jobMarketRegionOther,
          ),
        ),
        labelled("Stage", surveyLabel("menteeStage", p.menteeStage)),
        labelled(
          "Industry",
          checkedLabels("specificIndustry", p.specificIndustry).join(", "),
        ),
      ];
  return [
    ...roleLines,
    labelled("Skills", checkedLabels("skills", p.skills).join(", ")),
  ];
};

const peopleList = (people) => (people ?? []).map(personWithId).join(", ");

/**
 * What one side of a match put on file, read-only.
 *
 * @param {{role: "mentee"|"mentor", profile: Object|null}} props
 */
const ProfileCard = ({ role, profile }) => {
  const isMentor = role === "mentor";
  const title = isMentor ? "Mentor" : "Mentee";
  return (
    <section
      aria-label={`${title} profile`}
      className="space-y-3 rounded-md border border-border p-3 text-sm"
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-semibold">{title}</span>
        {profile?.timezone ? (
          <span className="text-xs text-muted-foreground">
            {profile.timezone}
          </span>
        ) : null}
      </div>
      {profile ? (
        <>
          <Section
            title="Mentorship history"
            lines={[
              `Rounds taken part: ${profile.mentorshipRoundsParticipated ?? 0} (with meetings: ${profile.mentorshipRoundsCompleted ?? 0})`,
            ]}
          />
          <Section title="Goal" lines={[profile.goal]} />
          <Section
            title="Experience"
            lines={(profile.workHistory ?? []).map(workLine)}
          />
          <Section
            title="Education"
            lines={(profile.education ?? []).map(educationLine)}
          />
          <Section title="Survey" lines={surveyLines(profile, isMentor)} />
          <Section
            title="Preferences"
            lines={[
              labelled("Wants", peopleList(profile.expectedPartners)),
              labelled("Does not want", peopleList(profile.unexpectedPartners)),
            ]}
          />
        </>
      ) : (
        <p className="text-muted-foreground">No profile on file.</p>
      )}
    </section>
  );
};

/** What the matcher noted about a mentee. */
const NotesBlock = ({ text }) => (
  <div>
    <div className="font-semibold">Matcher&apos;s notes</div>
    <p className="whitespace-pre-wrap">{text || "No notes."}</p>
  </div>
);

/** The mentors the matcher weighed for a mentee besides the one chosen. */
const CandidatesBlock = ({ candidates }) => (
  <div>
    <div className="font-semibold">Other candidates</div>
    {candidates?.length ? (
      <>
        <ul className="list-disc pl-5">
          {candidates.map((c) => (
            <li key={c.userId}>
              {personWithId(c)} · {scoreLabel(c.score)}
            </li>
          ))}
        </ul>
        <p className="mt-1 text-xs text-muted-foreground">{CANDIDATES_NOTE}</p>
      </>
    ) : (
      <p>No other candidates.</p>
    )}
  </div>
);

const DETAIL = "space-y-4 border-t border-border bg-muted/40 p-3 text-sm";

/** The detail under an opened pair row. */
const MatchDetail = ({ item }) => (
  <div className={DETAIL}>
    <div className="grid gap-3 md:grid-cols-2">
      <ProfileCard role="mentee" profile={item.menteeProfile} />
      {item.mentor ? (
        <ProfileCard role="mentor" profile={item.mentorProfile} />
      ) : null}
    </div>
    <div>
      <div className="font-semibold">Reason shown to the pair</div>
      <p className="whitespace-pre-wrap">
        {item.recommendationReason || "No reason."}
      </p>
    </div>
    <NotesBlock text={item.diagnosticReason} />
    <CandidatesBlock candidates={item.candidates} />
  </div>
);

/** A name followed by its ID, the name left out when it did not resolve. */
const NameWithId = ({ person }) => (
  <>
    {person.name ? <span className="font-medium">{person.name} </span> : null}
    <span className="text-xs text-muted-foreground">ID {person.userId}</span>
  </>
);

/**
 * A row that opens the detail under it; several can be open at once.
 *
 * @param {{summary: JSX.Element, detail: JSX.Element, open: boolean,
 *          onToggle: () => void, columns: string}} props
 */
const ExpandableRow = ({ summary, detail, open, onToggle, columns }) => (
  <li className="border-b border-border last:border-b-0">
    <button
      type="button"
      aria-expanded={open}
      onClick={onToggle}
      className={`grid w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-muted ${columns}`}
    >
      {summary}
    </button>
    {open ? detail : null}
  </li>
);

/** One mentee's pair: who they got, how, the score and the reason. */
const MatchRow = ({ item, open, onToggle }) => {
  const { mentee, mentor } = item;
  return (
    <ExpandableRow
      open={open}
      onToggle={onToggle}
      columns="grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_3rem_minmax(0,2fr)]"
      detail={<MatchDetail item={item} />}
      summary={
        <>
          <span className="min-w-0">
            <NameWithId person={mentee} />
          </span>
          <span className="min-w-0">
            {mentor ? (
              <>
                → <NameWithId person={mentor} />
              </>
            ) : (
              <span className="text-muted-foreground">No mentor</span>
            )}
          </span>
          <Badge variant={mentor ? "secondary" : "outline"}>
            {mentor
              ? (MATCH_TYPE_LABEL[item.matchType] ?? item.matchType)
              : "No match"}
          </Badge>
          <span className="tabular-nums">{scoreLabel(item.score)}</span>
          <span className="truncate text-muted-foreground">
            {item.recommendationReason}
          </span>
        </>
      }
    />
  );
};

/** One person the run left without a partner, mentee or mentor. */
const UnmatchedRow = ({ item, open, onToggle }) => {
  const isMentor = item.role === "mentor";
  return (
    <ExpandableRow
      open={open}
      onToggle={onToggle}
      columns="grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]"
      detail={
        <div className={DETAIL}>
          <div className="grid gap-3 md:grid-cols-2">
            <ProfileCard role={item.role} profile={item.profile} />
          </div>
          {isMentor ? null : (
            <>
              <NotesBlock text={item.diagnosticReason} />
              <CandidatesBlock candidates={item.candidates} />
            </>
          )}
        </div>
      }
      summary={
        <>
          <span className="min-w-0">
            <NameWithId person={item.person} />
          </span>
          <Badge variant="secondary">{isMentor ? "Mentor" : "Mentee"}</Badge>
          <span className="text-muted-foreground">
            {isMentor ? "No mentee" : "No mentor"}
          </span>
        </>
      }
    />
  );
};

/** The open rows of a list, by key. */
const useOpenRows = () => {
  const [openKeys, setOpenKeys] = useState(() => new Set());
  const toggle = (key) =>
    setOpenKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  return [openKeys, toggle];
};

/**
 * A page of rows with its Prev/Next pager.
 *
 * @param {{load: {page: Object|null, isLoading: boolean, error: boolean},
 *          offset: number, onOffset: (offset: number) => void,
 *          renderRow: (item: Object) => JSX.Element}} props
 */
const PagedList = ({ load, offset, onOffset, renderRow }) => {
  const { page, isLoading, error } = load;
  const total = page?.total ?? 0;
  const items = page?.items ?? [];

  let list;
  if (isLoading && !page) {
    list = <div className="py-8 text-center text-gray-500">Loading...</div>;
  } else if (error) {
    list = (
      <div className="py-8 text-center text-gray-500">
        Could not load the matching results.
      </div>
    );
  } else if (items.length === 0) {
    list = <div className="py-8 text-center text-gray-500">Nobody here.</div>;
  } else {
    list = (
      <ul className="rounded-lg border border-border">
        {items.map(renderRow)}
      </ul>
    );
  }

  return (
    <>
      {list}
      <div className="mt-4 flex items-center justify-between gap-2 text-sm text-muted-foreground">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onOffset(Math.max(0, offset - LIMIT))}
          disabled={offset === 0}
        >
          Prev
        </Button>
        <span>
          {total === 0 ? 0 : offset + 1}–{Math.min(offset + LIMIT, total)} of{" "}
          {total}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onOffset(offset + LIMIT)}
          disabled={offset + LIMIT >= total}
        >
          Next
        </Button>
      </div>
    </>
  );
};

/** The Matched tab: one row per pair, in the backend's order. */
const MatchedList = ({ roundId, offset, onOffset }) => {
  const load = useMatchingResults(roundId, {
    limit: LIMIT,
    offset,
    matched: true,
  });
  const [openKeys, toggle] = useOpenRows();
  return (
    <PagedList
      load={load}
      offset={offset}
      onOffset={onOffset}
      renderRow={(item) => (
        <MatchRow
          key={item.mentee.userId}
          item={item}
          open={openKeys.has(item.mentee.userId)}
          onToggle={() => toggle(item.mentee.userId)}
        />
      )}
    />
  );
};

/** The Unmatched tab: one row per person, mentees first, as the API sends. */
const UnmatchedList = ({ roundId, offset, onOffset }) => {
  const load = useMatchingUnmatched(roundId, { limit: LIMIT, offset });
  const [openKeys, toggle] = useOpenRows();
  return (
    <PagedList
      load={load}
      offset={offset}
      onOffset={onOffset}
      renderRow={(item) => {
        const key = `${item.role}-${item.person.userId}`;
        return (
          <UnmatchedRow
            key={key}
            item={item}
            open={openKeys.has(key)}
            onToggle={() => toggle(key)}
          />
        );
      }}
    />
  );
};

/**
 * The results of a succeeded run: the summary and the Matched / Unmatched
 * tabs, each a paged list. Tab and page are in the URL; no tab is Matched.
 */
const Results = ({ roundId, overview }) => {
  const [searchParams, setSearchParams] = useSearchParams();
  const tab =
    searchParams.get("tab") === TAB.UNMATCHED ? TAB.UNMATCHED : TAB.MATCHED;
  const rawOffset = searchParams.get("offset") ?? "";
  const offset = /^\d+$/.test(rawOffset) ? Number(rawOffset) : 0;

  const go = (nextTab, nextOffset) => {
    const next = new URLSearchParams();
    if (nextTab !== TAB.MATCHED) next.set("tab", nextTab);
    if (nextOffset > 0) next.set("offset", String(nextOffset));
    setSearchParams(next);
  };
  const onOffset = (nextOffset) => go(tab, nextOffset);

  const matched = overview.matchedCount ?? 0;
  const unmatched =
    (overview.unmatchedCount ?? 0) + (overview.unmatchedMentors ?? []).length;

  return (
    <div className="space-y-4">
      <Tabs value={tab} onValueChange={(v) => go(v, 0)}>
        <TabsList>
          <TabsTrigger value={TAB.MATCHED}>Matched ({matched})</TabsTrigger>
          <TabsTrigger value={TAB.UNMATCHED}>
            Unmatched ({unmatched})
          </TabsTrigger>
        </TabsList>
      </Tabs>
      {tab === TAB.MATCHED ? (
        <MatchedList roundId={roundId} offset={offset} onOffset={onOffset} />
      ) : (
        <UnmatchedList roundId={roundId} offset={offset} onOffset={onOffset} />
      )}
    </div>
  );
};

/**
 * MatchingResultsPage
 *
 * A round's latest matching run, read-only: who started it and over whom,
 * where it stands, and once it has succeeded every mentee's result with the
 * reasons and both sides' profiles. Opened from the Participants card. With
 * the matching-run flag off it says so and asks the API nothing.
 *
 * Route: /mentorship-management/matching/:roundId
 *
 * @returns {JSX.Element}
 */
const MatchingResultsPage = () => {
  const { roundId } = useParams();
  const location = useLocation();
  const returnSearch = location.state?.returnSearch;
  const rounds = useParticipantSearchRounds();
  const roundName =
    (rounds ?? []).find((r) => String(r.id) === String(roundId))?.name ?? "";
  const flags = useFeatureFlags();
  // The backend refuses every matching endpoint while the flag is off.
  const matchingOn = Boolean(flags[FEATURE_FLAGS.MATCHING_RUN]);
  const { overview, isLoading, error } = useMatchingRun(
    matchingOn ? roundId : null,
  );

  let body;
  if (!matchingOn) {
    body = <p className="text-sm">Matching runs are not available.</p>;
  } else if (isLoading) {
    body = (
      <div className="py-10 text-center text-gray-500">
        Loading matching run...
      </div>
    );
  } else if (error || !overview) {
    body = (
      <div className="py-10 text-center text-gray-500">
        Could not load this round&apos;s matching run.
      </div>
    );
  } else if (overview.status === RUN_STATUS.NEVER_RUN) {
    body = (
      <p className="text-sm">
        No matching run for {roundName || "this round"} yet.
      </p>
    );
  } else if (overview.status === RUN_STATUS.RUNNING) {
    body = (
      <p className="text-sm">
        Running. No other run can start in this round until it finishes; you
        will get an email when it does.
      </p>
    );
  } else if (overview.status === RUN_STATUS.SUCCEEDED) {
    body = <Results roundId={roundId} overview={overview} />;
  } else {
    body = (
      <p className="whitespace-pre-wrap text-sm text-red-700">
        {overview.error}
      </p>
    );
  }

  const hasRun = overview && overview.status !== RUN_STATUS.NEVER_RUN;

  return (
    <Card className="border-gray-200">
      <CardHeader className="space-y-2">
        <Link
          to={{
            pathname: ROUTE_PATHS.MENTORSHIP_MANAGEMENT,
            search: typeof returnSearch === "string" ? returnSearch : "",
          }}
          className="flex w-fit items-center gap-1 text-sm text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" />
          Participants
        </Link>
        <div className="flex flex-wrap items-center gap-3">
          <CardTitle>Matching{roundName ? ` — ${roundName}` : ""}</CardTitle>
          {overview ? <StatusBadge overview={overview} /> : null}
        </div>
        {hasRun ? (
          <p className="text-sm text-gray-500">{runLine(overview)}</p>
        ) : null}
      </CardHeader>
      <CardContent>{body}</CardContent>
    </Card>
  );
};

export default MatchingResultsPage;
