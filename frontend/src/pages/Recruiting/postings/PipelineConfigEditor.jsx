import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import PeoplePicker from "@/pages/Recruiting/components/PeoplePicker";

const STAGES = ["recruiter_screening", "behavioral", "tech", "board_review"];
const ASSIGNABLE = new Set(["recruiter_screening", "behavioral"]);

/** A selected owner rendered as a chip, with a button to remove it. */
const OwnerChip = ({ name, onRemove }) => (
  <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-sm text-slate-700">
    {name}
    <button
      type="button"
      onClick={onRemove}
      aria-label={`Remove recruiter ${name}`}
      className="text-slate-400 hover:text-slate-600"
    >
      ×
    </button>
  </span>
);

/**
 * Editor for a posting's interview pipeline: owners + ordered selected stages
 * (each with sessions, and a default assignee on screening/behavioral).
 *
 * @param {{value: {ownerIds?: number[], ownerId?: number, stages: object[]},
 *          onChange: (next: object) => void,
 *          interviewPool: object[], jobOwners: object[]}} props
 */
const PipelineConfigEditor = ({
  value = { stages: [] },
  onChange,
  interviewPool = [],
  jobOwners = [],
}) => {
  const stages = value.stages ?? [];
  const stageOf = (name) => stages.find((s) => s.stage === name);

  // Legacy postings stored a single `ownerId`; new ones store `ownerIds`.
  const ownerIds =
    value.ownerIds ?? (value.ownerId != null ? [value.ownerId] : []);
  const ownerName = (id) =>
    jobOwners.find((u) => u.userId === id)?.name ?? `#${id}`;
  const availableOwners = jobOwners.filter((u) => !ownerIds.includes(u.userId));

  /** Emit a new owner list, dropping the deprecated `ownerId` key. */
  const emitOwnerIds = (next) =>
    onChange({ ...value, ownerId: undefined, ownerIds: next });
  const removeOwner = (id) =>
    emitOwnerIds(ownerIds.filter((existing) => existing !== id));
  const addOwner = (id) => {
    if (id != null) emitOwnerIds([...ownerIds, id]);
  };

  /**
   * Narrow a stage to the keys the API accepts. Postings saved by older
   * versions of this editor carry retired keys, and the request DTO forbids
   * unknown fields — so they are dropped here rather than echoed back on save.
   */
  const toStagePayload = ({ stage, rounds, defaultAssigneeId }) =>
    defaultAssigneeId == null
      ? { stage, rounds }
      : { stage, rounds, defaultAssigneeId };

  /** Re-emit stages in canonical order after a mutation map. */
  const emitStages = (next) =>
    onChange({
      ...value,
      stages: STAGES.filter((n) => next[n]).map((n) => toStagePayload(next[n])),
    });
  const asMap = () => Object.fromEntries(stages.map((s) => [s.stage, s]));

  const toggleStage = (name, on) => {
    const map = asMap();
    if (on) map[name] = { stage: name, rounds: 1 };
    else delete map[name];
    emitStages(map);
  };
  const patchStage = (name, fields) => {
    const map = asMap();
    if (!map[name]) return;
    map[name] = { ...map[name], ...fields };
    emitStages(map);
  };

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-slate-700">Interview pipeline</p>
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <Label className="shrink-0">Recruiter</Label>
          <PeoplePicker
            label="Add recruiter"
            pool={availableOwners}
            value={undefined}
            onChange={addOwner}
          />
        </div>
        {ownerIds.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            {ownerIds.map((id) => (
              <OwnerChip
                key={id}
                name={ownerName(id)}
                onRemove={() => removeOwner(id)}
              />
            ))}
          </div>
        )}
      </div>
      {STAGES.map((name) => {
        const s = stageOf(name);
        return (
          <div
            key={name}
            className="space-y-2 rounded-md border border-slate-200 p-3"
          >
            <Label className="flex items-center gap-2">
              <Checkbox
                checked={!!s}
                onCheckedChange={(on) => toggleStage(name, !!on)}
                aria-label={name
                  .replace(/_/g, " ")
                  .replace(/\b\w/g, (c) => c.toUpperCase())}
              />
              {name}
            </Label>
            {s && (
              <div className="space-y-2 pl-6">
                <Label className="flex flex-wrap items-center gap-2 text-sm font-normal">
                  This stage has
                  <Input
                    type="number"
                    min={1}
                    aria-label={`${name} sessions`}
                    className="w-20"
                    value={s.rounds}
                    onChange={(e) =>
                      patchStage(name, {
                        rounds: Math.max(1, Number(e.target.value) || 1),
                      })
                    }
                  />
                  {(s.rounds ?? 1) === 1 ? "session" : "sessions"} in total
                </Label>
                {ASSIGNABLE.has(name) && (
                  <Label className="flex flex-wrap items-center gap-2 text-sm font-normal">
                    Applicants entering this stage are assigned to
                    {/* Bounded so the picker's own `w-full` trigger does not
                        claim a whole flex line and split the sentence. */}
                    <span className="inline-block w-64">
                      <PeoplePicker
                        label={`${name} assignee`}
                        pool={interviewPool}
                        value={s.defaultAssigneeId}
                        onChange={(id) =>
                          patchStage(name, { defaultAssigneeId: id })
                        }
                        noneLabel="no one"
                      />
                    </span>
                    for evaluation by default
                  </Label>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default PipelineConfigEditor;
