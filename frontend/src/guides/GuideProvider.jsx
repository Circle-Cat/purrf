import { useContext, useEffect, useMemo, useRef, useState } from "react";
import {
  generatePath,
  matchPath,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { useAuth } from "@/context/auth";
import { FlagsContext } from "@/context/flags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { listGuideProgress, recordGuideProgress } from "@/api/guidesApi";
import { listMyApplications } from "@/api/recruitingApi";
import { GUIDES } from "@/guides/definitions";
import { GuideContext } from "@/guides/GuideContext";
import GuideTourRenderer from "@/guides/GuideTourRenderer";
import TaskChooser from "@/guides/TaskChooser";
import { visibleIndices, waitForAnchors } from "@/guides/anchors";
import {
  RESET_KEY,
  autoStartCandidates,
  indexProgress,
  isResettableKey,
  isSeen,
  pageKey,
  qualifyingTasks,
} from "@/guides/progress";
import {
  blockAutoStartOn,
  forgetAutoStarts,
  isAutoStartBlocked,
  markAutoStarted,
  noteVisitedPath,
} from "@/guides/session";
import { resolveSteps } from "@/guides/steps";

// How long a `before` action that changed the layout gets to settle before
// the step is highlighted. Matches the sidebar's `duration-200` width
// transition.
const LAYOUT_SETTLE_MS = 200;

// How long a segment waits for its anchors to render before it is skipped.
export const ANCHOR_TIMEOUT_MS = 5000;

// What each way of ending a guide writes. A manually started guide only ever
// records completion: closing a replay says nothing new about the guide. A
// guide that never showed a step writes nothing at all.
const END_STATUS = {
  done: { auto: "completed", manual: "completed" },
  dismiss: { auto: "dismissed", manual: null },
  close: { auto: "snoozed", manual: null },
  route: { auto: "snoozed", manual: null },
};

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const DOM_CHANGES = {
  childList: true,
  subtree: true,
  attributes: true,
  attributeFilter: ["data-tour"],
};

/**
 * The guide engine, outside React: one run at a time (a guide, a task or a
 * page intro being walked), the task chooser, and the progress rows. It reads
 * the current location, viewer and props from `latest` and draws through the
 * two setters, so it is created once per provider.
 */
const createEngine = ({ latest, setTour, setChooser }) => {
  let run = null;
  let chooser = null;
  let progress = new Map();

  const here = () => latest.current.location.pathname;
  const viewer = () => latest.current.viewer;
  const busy = () => run !== null || chooser !== null;

  const write = (key, status) => {
    const previous = progress.get(key);
    if (!(status === "snoozed" && isSeen(previous))) {
      progress.set(key, { ...previous, guideKey: key, status });
    }
    recordGuideProgress(key, status)
      .then((row) => {
        if (row?.guideKey === key) progress.set(key, row);
      })
      .catch((error) => {
        console.error(`Failed to record guide "${key}"`, error);
      });
  };

  // Where a segment runs, or null when its route needs params it cannot get.
  const resolvePath = (segment) => {
    if (!segment.route) return here();
    try {
      if (segment.params) {
        const params = segment.params(viewer());
        return params ? generatePath(segment.route, params) : null;
      }
      if (matchPath(segment.route, here())) return here();
      return generatePath(segment.route, {});
    } catch {
      return null;
    }
  };

  // Whether a segment after the current one could still show a step: one on
  // another page might, one on this page only if its anchors are here.
  const laterSegmentMayRun = (r) => {
    for (let s = r.segIndex + 1; s < r.segments.length; s += 1) {
      const path = resolvePath(r.segments[s]);
      if (path === null) continue;
      if (path !== here()) return true;
      if (visibleIndices(r.segments[s].steps).length > 0) return true;
    }
    return false;
  };

  // The last visible step of the segment before this one, when that segment
  // ran on the page the viewer is still on.
  const previousSegmentStep = (r) => {
    const previous = r.history[r.history.length - 1];
    if (!previous || previous.path !== here()) return null;
    const visible = visibleIndices(r.segments[previous.segIndex].steps);
    if (visible.length === 0) return null;
    return { segIndex: previous.segIndex, index: visible[visible.length - 1] };
  };

  // Draws the current step, deciding Back and Done from the anchors on the
  // page now. Called again whenever the page changes while a step shows.
  const display = (r) => {
    if (run !== r || r.busy || r.index < 0) return;
    const { steps } = r.segments[r.segIndex];
    const visible = visibleIndices(steps);
    const showBack =
      visible.some((i) => i < r.index) || previousSegmentStep(r) !== null;
    const isLastStep =
      !visible.some((i) => i > r.index) && !laterSegmentMayRun(r);
    setTour((previous) =>
      previous?.run === r &&
      previous.steps === steps &&
      previous.index === r.index &&
      previous.showBack === showBack &&
      previous.isLastStep === isLastStep
        ? previous
        : { run: r, steps, index: r.index, showBack, isLastStep },
    );
  };

  const finish = (r, reason) => {
    if (run !== r) return;
    run = null;
    setTour(null);
    const status = r.shown
      ? END_STATUS[reason]?.[r.manual ? "manual" : "auto"]
      : null;
    if (status) write(r.writeKey, status);
    if (reason === "done" && r.onDone) {
      r.onDone();
      return;
    }
    if (reason === "skip" && r.onSkip) {
      r.onSkip();
      return;
    }
    if (r.shown) blockAutoStartOn(here());
  };

  const showStep = async (r, segIndex, index) => {
    r.busy = true;
    const step = r.segments[segIndex].steps[index];
    const action = step.before && latest.current.actions[step.before];
    if (action && action()) {
      await delay(LAYOUT_SETTLE_MS);
    }
    if (run !== r) return false;
    r.busy = false;
    r.segIndex = segIndex;
    r.index = index;
    if (!r.shown) {
      r.shown = true;
      r.onShown?.();
    }
    display(r);
    return true;
  };

  // Starts the first segment from `from` that can run: navigates to its page
  // if needed and waits for its anchors. Resolves to whether a step showed.
  const enterSegment = async (r, from) => {
    r.busy = true;
    for (let s = from; s < r.segments.length; s += 1) {
      const segment = r.segments[s];
      const path = resolvePath(segment);
      if (path === null) continue;
      const samePage = path === here();
      if (!samePage) {
        setTour(null);
        // Claimed before navigating, so the route change is not read as the
        // viewer leaving.
        r.path = path;
        latest.current.navigate(path);
      }
      // A page the run already showed a step on has rendered: what is not
      // there now is not coming, so there is nothing to wait for.
      const visible =
        r.shown && samePage
          ? visibleIndices(segment.steps)
          : await waitForAnchors(
              segment.steps,
              r.shown ? 1 : r.minSteps,
              latest.current.anchorTimeoutMs,
            );
      if (run !== r) return false;
      if (visible?.length) return showStep(r, s, visible[0]);
    }
    finish(r, r.shown ? "done" : "skip");
    return false;
  };

  const begin = (r) => {
    if (busy()) return Promise.resolve(false);
    run = r;
    return enterSegment(r, 0);
  };

  // A run of a whole guide or task, or of one task segment as a page intro.
  const buildRun = (guide, { manual, segment, onShown, onDone, onSkip }) => {
    const source = segment
      ? [{ ...segment, route: undefined, params: undefined }]
      : (guide.segments ?? [
          { key: guide.key, route: guide.route, steps: guide.steps },
        ]);
    const single = segment || guide.type !== "task";
    return {
      manual,
      writeKey: segment ? pageKey(segment) : guide.key,
      // Auto-started basics tours and page intros need two steps to be worth
      // interrupting for; a new-feature guide may be a single step.
      minSteps: !manual && single && guide.kind !== "new-feature" ? 2 : 1,
      segments: source.map((s) => ({
        ...s,
        steps: resolveSteps(s.steps, viewer()),
      })),
      segIndex: 0,
      index: -1,
      path: here(),
      shown: false,
      busy: false,
      history: [],
      onShown,
      onDone,
      onSkip,
    };
  };

  const resetPageIntros = () => {
    for (const key of [...progress.keys()]) {
      if (isResettableKey(key)) progress.delete(key);
    }
    forgetAutoStarts(isResettableKey);
    write(RESET_KEY, "completed");
  };

  const startTask = (task, manual, fromChooser) => {
    const after = fromChooser
      ? () => offerTasks(manual)
      : () => blockAutoStartOn(here());
    begin(buildRun(task, { manual, onDone: after, onSkip: after }));
  };

  // What follows the basics tour: the one task the viewer qualifies for, or
  // a choice between several.
  const offerTasks = (manual) => {
    const tasks = qualifyingTasks(latest.current.guides, viewer());
    if (tasks.length === 0) {
      blockAutoStartOn(here());
      return;
    }
    if (tasks.length === 1) {
      startTask(tasks[0], manual, false);
      return;
    }
    chooser = { manual };
    setChooser(
      tasks.map((task) => ({
        key: task.key,
        title: task.title,
        completed: progress.get(task.key)?.status === "completed",
      })),
    );
  };

  const closeChooser = (block) => {
    if (!chooser) return null;
    const closed = chooser;
    chooser = null;
    setChooser(null);
    if (block) blockAutoStartOn(here());
    return closed;
  };

  return {
    setProgress: (rows) => {
      progress = indexProgress(rows);
    },

    autoStart: async () => {
      const { location } = latest.current;
      if (busy() || isAutoStartBlocked(location.pathname)) return;
      const candidates = autoStartCandidates(
        latest.current.guides,
        progress,
        viewer(),
        location,
      );
      for (const { guide, segment } of candidates) {
        if (busy() || here() !== location.pathname) return;
        const key = segment ? pageKey(segment) : guide.key;
        const r = buildRun(guide, {
          manual: false,
          segment,
          onShown: () => markAutoStarted(key),
          onDone:
            !segment && guide.basics ? () => offerTasks(false) : undefined,
        });
        if (await begin(r)) return;
      }
    },

    start: (key) => {
      const guide = latest.current.guides.find((g) => g.key === key);
      if (!guide) return;
      // An auto guide still waiting for its page gives way to the request.
      if (run && !run.shown && !run.manual) {
        run = null;
        setTour(null);
      }
      if (busy()) return;
      if (guide.type === "task") {
        startTask(guide, true, false);
        return;
      }
      begin(
        buildRun(guide, {
          manual: true,
          onShown: guide.basics ? resetPageIntros : undefined,
          onDone: guide.basics ? () => offerTasks(true) : undefined,
        }),
      );
    },

    chooseTask: (key) => {
      const closed = closeChooser(false);
      const task = latest.current.guides.find((g) => g.key === key);
      if (closed && task) startTask(task, closed.manual, true);
    },

    closeChooser: () => closeChooser(true),

    move: (direction) => {
      const r = run;
      if (!r || r.busy || r.index < 0) return;
      const visible = visibleIndices(r.segments[r.segIndex].steps);
      const target =
        direction === 1
          ? visible.find((i) => i > r.index)
          : visible.filter((i) => i < r.index).pop();
      if (target !== undefined) {
        showStep(r, r.segIndex, target);
        return;
      }
      if (direction === 1) {
        r.history.push({ segIndex: r.segIndex, path: r.path });
        enterSegment(r, r.segIndex + 1);
        return;
      }
      const back = previousSegmentStep(r);
      if (back) {
        r.history.pop();
        showStep(r, back.segIndex, back.index);
      }
    },

    end: (reason) => {
      if (run) finish(run, reason);
    },

    refresh: () => {
      if (run) display(run);
    },

    routeChanged: (pathname) => {
      noteVisitedPath(pathname);
      if (run && run.path !== pathname) finish(run, "route");
      closeChooser(true);
    },

    deactivate: () => {
      if (run) finish(run, "inactive");
      closeChooser(false);
    },
  };
};

/**
 * Runs onboarding guides: single-page tours, tasks (guides walked across
 * several pages in segments) and page intros (one task segment shown on its
 * own when the viewer opens its page). Records how each ended and lets
 * `useGuides().start` replay one on demand.
 *
 * Rules: one guide on screen at a time; after one ends, nothing starts on its
 * own until the viewer changes page; each guide and page intro starts on its
 * own at most once per session; an auto-started basics tour or page intro
 * needs two visible steps. When the basics tour (`basics: true`) is completed,
 * the tasks the viewer qualifies for follow: one starts at once, several are
 * offered in a chooser. Replaying the basics tour makes page intros and tasks
 * count as unseen again (see RESET_KEY).
 *
 * Only active once auth has loaded, the email is verified and there is no
 * auth error, so nothing runs on the verify wall or the error screens. Must
 * sit inside the router, AuthProvider and FlagsProvider.
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - The layout the guides point at.
 * @param {Record<string, () => boolean>} [props.actions] - Layout actions a
 *   step can ask for with `before`. Each returns true when it changed the
 *   layout, in which case the step waits LAYOUT_SETTLE_MS before showing.
 * @param {Array<Object>} [props.guides] - Guide definitions; defaults to
 *   GUIDES.
 * @param {number} [props.anchorTimeoutMs] - How long a segment waits for its
 *   anchors; defaults to ANCHOR_TIMEOUT_MS.
 * @returns {JSX.Element}
 */
export const GuideProvider = ({
  children,
  actions = {},
  guides = GUIDES,
  anchorTimeoutMs = ANCHOR_TIMEOUT_MS,
}) => {
  const { loading, hasVerifiedEmail, accessDenied, authError, permissions } =
    useAuth();
  // The whole engine sits behind one LaunchDarkly flag. Until LaunchDarkly
  // answers the flag reads as off, so nothing starts early; with no client
  // (local builds) it never answers and guides stay off.
  const { flags, ready: flagsReady } = useContext(FlagsContext);
  const enabled = flagsReady && Boolean(flags[FEATURE_FLAGS.ONBOARDING_GUIDES]);
  const location = useLocation();
  const navigate = useNavigate();
  const active =
    enabled && !loading && hasVerifiedEmail && !accessDenied && !authError;

  const [tour, setTour] = useState(null);
  const [chooser, setChooser] = useState(null);
  const [progressReady, setProgressReady] = useState(false);
  // Null until loaded, so audiences are not judged on a guess.
  const [mentorshipRoles, setMentorshipRoles] = useState(null);

  const latest = useRef({});
  latest.current = {
    actions,
    guides,
    anchorTimeoutMs,
    location,
    navigate,
    viewer: {
      permissions,
      flags,
      mentorshipRoles: mentorshipRoles ?? [],
    },
  };

  const [engine] = useState(() =>
    createEngine({ latest, setTour, setChooser }),
  );

  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    listGuideProgress()
      .then((rows) => {
        if (cancelled) return;
        engine.setProgress(rows ?? []);
        setProgressReady(true);
      })
      .catch((error) => {
        console.error("Failed to load guide progress", error);
      });
    // The same source the dashboard reads; a failure means no roles.
    listMyApplications()
      .then((response) => response?.data?.mentorshipRoles ?? [])
      .catch(() => [])
      .then((roles) => {
        if (!cancelled) setMentorshipRoles(roles);
      });
    return () => {
      cancelled = true;
    };
  }, [active, engine]);

  // Declared before the auto-start effect so a page change first ends what
  // the viewer left, then looks for what the new page offers.
  useEffect(() => {
    engine.routeChanged(location.pathname);
  }, [location.pathname, engine]);

  useEffect(() => {
    if (!active || !progressReady || mentorshipRoles === null) return;
    engine.autoStart();
  }, [active, progressReady, mentorshipRoles, location.pathname, engine]);

  useEffect(() => {
    if (!active) engine.deactivate();
  }, [active, engine]);

  useEffect(() => {
    if (!tour) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") engine.end("close");
    };
    // Anchors that render after a step opens can add a later step or a Back.
    const observer = new MutationObserver(() => engine.refresh());
    observer.observe(document.body, DOM_CHANGES);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      observer.disconnect();
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [tour, engine]);

  const value = useMemo(
    () => ({ active, start: (key) => active && engine.start(key) }),
    [active, engine],
  );

  return (
    <GuideContext.Provider value={value}>
      {children}
      {active && tour && (
        <GuideTourRenderer
          steps={tour.steps}
          stepIndex={tour.index}
          showBack={tour.showBack}
          isLastStep={tour.isLastStep}
          showDismiss={!tour.run.manual}
          onBack={() => engine.move(-1)}
          onNext={() => engine.move(1)}
          onDone={() => engine.end("done")}
          onClose={() => engine.end("close")}
          onDismiss={() => engine.end("dismiss")}
        />
      )}
      {active && chooser && (
        <TaskChooser
          tasks={chooser}
          onChoose={engine.chooseTask}
          onClose={engine.closeChooser}
        />
      )}
    </GuideContext.Provider>
  );
};
