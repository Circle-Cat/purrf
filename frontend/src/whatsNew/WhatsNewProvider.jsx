import {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/auth";
import { FlagsContext } from "@/context/flags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";
import { listGuideProgress, recordGuideProgress } from "@/api/guidesApi";
import { WHATS_NEW_ENTRIES } from "@/whatsNew/entries";
import { WhatsNewContext } from "@/whatsNew/WhatsNewContext";
import WhatsNewPanel from "@/whatsNew/WhatsNewPanel";
import { highlightAnchor } from "@/whatsNew/highlightAnchor";
import { WHATS_NEW_INTRO_KEY, whatsNewEntryKey } from "@/whatsNew/progressKeys";

/**
 * Holds the viewer's What's new read state and renders the panel.
 *
 * Read state is one progress row per entry: no row means unread (counted by
 * the avatar dot), `dismissed` means seen in the panel, and `completed` means
 * the viewer followed its "Show me" link (until then the panel marks it New).
 *
 * Active only when the `whats-new` flag is on, auth has loaded, the email is
 * verified and there is no auth error; otherwise nothing is fetched or shown.
 * If the progress fetch fails the feature stays silent. Must sit inside the
 * router, AuthProvider and FlagsProvider.
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children
 * @param {ReadonlyArray<Object>} [props.entries] - Entries to offer; defaults
 *   to WHATS_NEW_ENTRIES.
 * @returns {JSX.Element}
 */
export const WhatsNewProvider = ({ children, entries = WHATS_NEW_ENTRIES }) => {
  const { loading, hasVerifiedEmail, accessDenied, authError, permissions } =
    useAuth();
  const { flags, ready: flagsReady } = useContext(FlagsContext);
  const flagOn = flagsReady && Boolean(flags[FEATURE_FLAGS.WHATS_NEW]);
  const active =
    flagOn && !loading && hasVerifiedEmail && !accessDenied && !authError;
  const navigate = useNavigate();

  // null until the fetch succeeds; a failed fetch leaves it null for good.
  const [rows, setRows] = useState(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [introHidden, setIntroHidden] = useState(false);
  const writes = useRef(new Map());
  const cancelHighlight = useRef(null);

  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    listGuideProgress()
      .then((list) => {
        if (cancelled) return;
        setRows(new Map((list ?? []).map((row) => [row.guideKey, row.status])));
      })
      .catch((error) => {
        console.error("Failed to load What's new progress", error);
      });
    return () => {
      cancelled = true;
    };
  }, [active]);

  useEffect(() => () => cancelHighlight.current?.(), []);

  const visible = useMemo(() => {
    const viewer = { permissions: permissions ?? [], flags };
    return entries.filter(
      (entry) =>
        (!entry.flag || Boolean(flags[entry.flag])) &&
        (!entry.audience || entry.audience(viewer)),
    );
  }, [entries, permissions, flags]);

  // Writes to one key go out in order, so a quick "Show me" right after
  // opening the panel cannot be overwritten by the earlier dismissal.
  const record = useCallback((key, status) => {
    setRows((prev) => new Map(prev).set(key, status));
    const previous = writes.current.get(key) ?? Promise.resolve();
    const next = previous
      .then(() => recordGuideProgress(key, status))
      .catch((error) => {
        console.error(`Failed to record What's new progress "${key}"`, error);
      });
    writes.current.set(key, next);
  }, []);

  const ready = active && rows !== null;

  const openPanel = useCallback(() => {
    if (!ready) return;
    for (const entry of visible) {
      const key = whatsNewEntryKey(entry.id);
      if (!rows.has(key)) record(key, "dismissed");
    }
    setPanelOpen(true);
  }, [ready, visible, rows, record]);

  const showMe = useCallback(
    (entry) => {
      setPanelOpen(false);
      record(whatsNewEntryKey(entry.id), "completed");
      navigate(entry.showMe.route);
      cancelHighlight.current?.();
      cancelHighlight.current = highlightAnchor(entry.showMe.anchor);
    },
    [navigate, record],
  );

  const acknowledgeIntro = useCallback(() => {
    record(WHATS_NEW_INTRO_KEY, "completed");
  }, [record]);

  const hideIntro = useCallback(() => setIntroHidden(true), []);

  const unreadCount = ready
    ? visible.filter((entry) => !rows.has(whatsNewEntryKey(entry.id))).length
    : 0;
  const showIntro = ready && !introHidden && !rows.has(WHATS_NEW_INTRO_KEY);

  const value = useMemo(
    () => ({
      enabled: ready,
      unreadCount,
      showIntro,
      openPanel,
      acknowledgeIntro,
      hideIntro,
    }),
    [ready, unreadCount, showIntro, openPanel, acknowledgeIntro, hideIntro],
  );

  const panelEntries = ready
    ? visible.map((entry) => ({
        ...entry,
        isNew: rows.get(whatsNewEntryKey(entry.id)) !== "completed",
      }))
    : [];

  return (
    <WhatsNewContext.Provider value={value}>
      {children}
      {ready && (
        <WhatsNewPanel
          open={panelOpen}
          onOpenChange={setPanelOpen}
          entries={panelEntries}
          onShowMe={showMe}
        />
      )}
    </WhatsNewContext.Provider>
  );
};
