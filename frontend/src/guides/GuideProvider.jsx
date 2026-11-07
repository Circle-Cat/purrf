import {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "@/context/auth";
import { FlagsContext } from "@/context/flags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { listGuideProgress, recordGuideProgress } from "@/api/guidesApi";
import { GUIDES } from "@/guides/definitions";
import { GuideContext } from "@/guides/GuideContext";
import GuideTourRenderer from "@/guides/GuideTourRenderer";
import { hasAutoStarted, markAutoStarted } from "@/guides/session";

// How long a `before` action that changed the layout gets to settle before
// the step is highlighted. Matches the sidebar's `duration-200` width
// transition.
const LAYOUT_SETTLE_MS = 200;

const anchorExists = (anchor) =>
  document.querySelector(`[data-tour="${anchor}"]`) !== null;

// Index of the first step from `from` (walking by `direction`) whose anchor
// is on the page, or -1.
const findStep = (steps, from, direction) => {
  for (let i = from; i >= 0 && i < steps.length; i += direction) {
    if (anchorExists(steps[i].anchor)) return i;
  }
  return -1;
};

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// What each way of ending a tour writes. A manually started tour only ever
// records completion: closing a replay says nothing new about the guide.
const END_STATUS = {
  done: { auto: "completed", manual: "completed" },
  dismiss: { auto: "dismissed", manual: null },
  close: { auto: "snoozed", manual: null },
  route: { auto: "snoozed", manual: null },
  inactive: { auto: null, manual: null },
};

/**
 * Runs onboarding guides. Auto-starts at most one eligible guide per session,
 * records how each auto-started guide ended, and lets `useGuides().start`
 * replay one on demand.
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
 * @returns {JSX.Element}
 */
export const GuideProvider = ({ children, actions = {}, guides = GUIDES }) => {
  const { loading, hasVerifiedEmail, accessDenied, authError, permissions } =
    useAuth();
  // The whole engine sits behind one LaunchDarkly flag. Until LaunchDarkly
  // answers the flag reads as off, so nothing starts early; with no client
  // (local builds) it never answers and guides stay off.
  const { flags, ready: flagsReady } = useContext(FlagsContext);
  const enabled = flagsReady && Boolean(flags[FEATURE_FLAGS.ONBOARDING_GUIDES]);
  const { pathname } = useLocation();
  const active =
    enabled && !loading && hasVerifiedEmail && !accessDenied && !authError;

  // `tour` drives rendering; `tourRef` is the same thing read synchronously
  // by handlers, so two quick clicks cannot both act on a stale step.
  const [tour, setTour] = useState(null);
  const tourRef = useRef(null);
  // Bumped whenever a tour ends, so a step still waiting on its `before`
  // action knows not to show itself.
  const generationRef = useRef(0);

  const latest = useRef({});
  latest.current = { actions, guides, permissions, flags, pathname, active };

  const commit = (next) => {
    tourRef.current = next;
    setTour(next);
  };

  const showStep = useCallback(async (base, index) => {
    const generation = generationRef.current;
    const step = base.guide.steps[index];
    const action = step.before && latest.current.actions[step.before];
    if (action && action()) {
      await delay(LAYOUT_SETTLE_MS);
    }
    if (generation !== generationRef.current) return;
    const steps = base.guide.steps;
    commit({
      ...base,
      index,
      showBack: findStep(steps, index - 1, -1) !== -1,
      isLastStep: findStep(steps, index + 1, 1) === -1,
    });
  }, []);

  const begin = useCallback(
    (guide, manual) => {
      if (tourRef.current) return false;
      const first = findStep(guide.steps, 0, 1);
      if (first === -1) return false;
      const base = { guide, manual, pathname: latest.current.pathname };
      // Claim the slot now: the first step may still be waiting on its
      // `before` action.
      tourRef.current = { ...base, index: -1 };
      showStep(base, first);
      return true;
    },
    [showStep],
  );

  const end = useCallback((reason) => {
    const current = tourRef.current;
    if (!current) return;
    generationRef.current += 1;
    commit(null);
    const status = END_STATUS[reason][current.manual ? "manual" : "auto"];
    if (!status) return;
    recordGuideProgress(current.guide.key, status).catch((error) => {
      console.error(`Failed to record guide "${current.guide.key}"`, error);
    });
  }, []);

  const move = useCallback(
    (direction) => {
      const current = tourRef.current;
      if (!current || current.index === -1) return;
      const target = findStep(
        current.guide.steps,
        current.index + direction,
        direction,
      );
      if (target === -1) {
        if (direction === 1) end("done");
        return;
      }
      const { guide, manual, pathname: startedAt } = current;
      // Hold the slot while the next step prepares.
      tourRef.current = { ...current, index: -1 };
      showStep({ guide, manual, pathname: startedAt }, target);
    },
    [end, showStep],
  );

  useEffect(() => {
    if (!active || hasAutoStarted()) return undefined;
    let cancelled = false;
    listGuideProgress()
      .then((rows) => {
        if (cancelled || hasAutoStarted()) return;
        const byKey = new Map((rows ?? []).map((row) => [row.guideKey, row]));
        const {
          guides: definitions,
          permissions: perms,
          flags: flagValues,
        } = latest.current;
        const eligible = definitions
          .filter(
            (guide) =>
              guide.type === "tour" &&
              guide.trigger?.kind === "first-visit" &&
              guide.audience({ permissions: perms, flags: flagValues }) &&
              (!byKey.has(guide.key) ||
                byKey.get(guide.key).status === "snoozed"),
          )
          .sort((a, b) => b.priority - a.priority);
        for (const guide of eligible) {
          if (begin(guide, false)) {
            markAutoStarted();
            return;
          }
        }
      })
      .catch((error) => {
        console.error("Failed to load guide progress", error);
      });
    return () => {
      cancelled = true;
    };
  }, [active, begin]);

  useEffect(() => {
    const current = tourRef.current;
    if (current && current.pathname !== pathname) end("route");
  }, [pathname, end]);

  useEffect(() => {
    if (!active) end("inactive");
  }, [active, end]);

  useEffect(() => {
    if (!tour) return undefined;
    const onKeyDown = (event) => {
      if (event.key === "Escape") end("close");
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [tour, end]);

  const start = useCallback(
    (key) => {
      if (!latest.current.active) return;
      const guide = latest.current.guides.find((g) => g.key === key);
      if (guide) begin(guide, true);
    },
    [begin],
  );

  const value = useMemo(() => ({ active, start }), [active, start]);

  return (
    <GuideContext.Provider value={value}>
      {children}
      {active && tour && (
        <GuideTourRenderer
          steps={tour.guide.steps}
          stepIndex={tour.index}
          showBack={tour.showBack}
          isLastStep={tour.isLastStep}
          showDismiss={!tour.manual}
          onBack={() => move(-1)}
          onNext={() => move(1)}
          onDone={() => end("done")}
          onClose={() => end("close")}
          onDismiss={() => end("dismiss")}
        />
      )}
    </GuideContext.Provider>
  );
};
