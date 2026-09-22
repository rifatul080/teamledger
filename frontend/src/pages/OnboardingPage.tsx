import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMe } from "../app/auth";
import {
  PRESETS,
  useCreateTeam,
  useCreditCategories,
  useTeams,
  WorkType,
  WORK_TYPES,
} from "../app/data";
import { pushToast } from "../components/ui/Toast";

const SUGGESTED_NAMES = [
  "Lab Notebook",
  "Cell 1 Research",
  "Group 12b",
  "Project Lighthouse",
  "Team Aurora",
];

export default function OnboardingPage() {
  const me = useMe();
  const teams = useTeams();
  const cat = useCreditCategories();
  const createTeam = useCreateTeam();
  const nav = useNavigate();

  // Existing team count = 0 means first team (full wizard). Otherwise condensed.
  const isFirstTeam = (teams.data?.length ?? 0) === 0;

  const [step, setStep] = useState<1 | 2 | 3 | 4 | 5>(1);
  const [name, setName] = useState("");
  const [workType, setWorkType] = useState<WorkType>("conference_paper");
  const [preset, setPreset] = useState<WorkType>("conference_paper");
  // Categories: store code -> selected boolean, weight.
  const [cats, setCats] = useState<Record<string, { selected: boolean; weight: number }>>({});

  // Init preset selection.
  useEffect(() => {
    if (!cat.data) return;
    if (isFirstTeam) {
      const init: Record<string, { selected: boolean; weight: number }> = {};
      for (const c of cat.data) {
        const w = PRESETS[workType].categories.find((p) => p.code === c.code)?.weight ?? 1.0;
        const sel = PRESETS[workType].categories.some((p) => p.code === c.code);
        init[c.code] = { selected: sel, weight: w };
      }
      setCats(init);
      setPreset(workType);
    }
  }, [workType, cat.data, isFirstTeam]);

  const selectedCats = useMemo(
    () => Object.entries(cats).filter(([, v]) => v.selected).map(([k]) => k),
    [cats],
  );

  if (!me.data) return null;
  // Pure invitees (never created a team) skip straight to dashboard — they
  // see the wizard only if they click "Create a new team".
  // The wizard itself is always the same UX; the route is just "/onboarding".

  async function submit() {
    try {
      const t = await createTeam.mutateAsync({
        name,
        work_type: workType,
        category_preset: preset,
        categories: isFirstTeam ? selectedCats : undefined,
      });
      pushToast({ kind: "ok", title: `Team "${t.name}" created` });
      nav(`/teams/${t.id}`);
    } catch (e) {
      pushToast({
        kind: "error",
        title: "Couldn't create team",
        body: (e as { message?: string }).message,
      });
    }
  }

  if (!isFirstTeam) {
    // Condensed one-step form.
    return (
      <div className="max-w-xl mx-auto">
        <h1 className="text-h1 mb-1">Create another team</h1>
        <p className="text-meta mb-6">Just the essentials — you can edit categories later.</p>
        <div className="card flex flex-col gap-4">
          <div>
            <label className="label">Team name</label>
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. ML Safety Reading Group"
            />
            <div className="flex flex-wrap gap-2 mt-2">
              {SUGGESTED_NAMES.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="btn-secondary btn-sm"
                  onClick={() => setName(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="label">What kind of work?</label>
            <select
              className="input"
              value={workType}
              onChange={(e) => setWorkType(e.target.value as WorkType)}
            >
              {WORK_TYPES.map((w) => (
                <option key={w.value} value={w.value}>
                  {w.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex justify-end gap-2">
            <button
              className="btn-secondary"
              onClick={() => nav("/dashboard")}
            >
              Cancel
            </button>
            <button
              className="btn-primary"
              disabled={!name || createTeam.isPending}
              onClick={submit}
            >
              {createTeam.isPending ? "Creating…" : "Create team"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Full wizard (first team).
  return (
    <div className="max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-h1">Set up your first team</h1>
        <p className="text-meta">
          Step {step} of 5. This picks sensible defaults; everything stays editable
          later.
        </p>
      </div>
      <Progress step={step} max={5} />

      {step === 1 && (
        <Card title="What's this team working toward?" sub="You can change this later in team settings.">
          <div className="grid sm:grid-cols-2 gap-2">
            {WORK_TYPES.map((w) => (
              <button
                key={w.value}
                type="button"
                className={`btn justify-start ${workType === w.value ? "border border-line bg-paper-sun" : "btn-secondary"}`}
                onClick={() => setWorkType(w.value)}
              >
                {w.label}
              </button>
            ))}
          </div>
          <Nav step={step} setStep={setStep} canNext={Boolean(workType)} />
        </Card>
      )}

      {step === 2 && (
        <Card title="Pick a starting preset" sub="Each preset pre-selects a subset of CRediT categories and reasonable weights.">
          <div className="flex flex-col gap-2">
            {WORK_TYPES.map((w) => (
              <button
                key={w.value}
                type="button"
                className={`btn justify-start ${preset === w.value ? "border border-line bg-paper-sun" : "btn-secondary"}`}
                onClick={() => {
                  setPreset(w.value);
                  setWorkType(w.value);
                }}
              >
                <div className="flex flex-col text-left">
                  <span className="font-medium">{PRESETS[w.value].label}</span>
                  <span className="text-faint">
                    {PRESETS[w.value].categories.length} categories pre-selected
                  </span>
                </div>
              </button>
            ))}
          </div>
          <Nav step={step} setStep={setStep} canNext={Boolean(preset)} />
        </Card>
      )}

      {step === 3 && (
        <Card title="Adjust the categories" sub="Everything stays editable later. Nothing is locked out.">
          {cat.isLoading ? (
            <div className="text-meta">Loading categories…</div>
          ) : (
            <ul className="grid sm:grid-cols-2 gap-2">
              {(cat.data ?? []).map((c) => {
                const v = cats[c.code] ?? { selected: false, weight: 1 };
                return (
                  <li
                    key={c.code}
                    className={`flex items-center gap-3 rounded-md border border-line p-3 ${v.selected ? "bg-paper-sun" : "bg-paper"}`}
                  >
                    <input
                      type="checkbox"
                      checked={v.selected}
                      className="w-4 h-4"
                      onChange={(e) =>
                        setCats((cur) => ({
                          ...cur,
                          [c.code]: { ...v, selected: e.target.checked },
                        }))
                      }
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-ink truncate">{c.label}</div>
                      <div className="text-faint font-mono">{c.code}</div>
                    </div>
                    {v.selected && (
                      <div className="flex items-center gap-1">
                        <label className="text-faint">×</label>
                        <input
                          type="number"
                          step="0.1"
                          min="0"
                          max="5"
                          className="input-sm w-16 text-right"
                          value={v.weight}
                          onChange={(e) =>
                            setCats((cur) => ({
                              ...cur,
                              [c.code]: {
                                ...v,
                                weight: parseFloat(e.target.value) || 0,
                              },
                            }))
                          }
                        />
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
          <Nav step={step} setStep={setStep} canNext={selectedCats.length > 0} />
        </Card>
      )}

      {step === 4 && (
        <Card title="Name your team" sub="Suggestions are tap-to-fill.">
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Team name"
          />
          <div className="flex flex-wrap gap-2 mt-3">
            {SUGGESTED_NAMES.map((s) => (
              <button
                key={s}
                type="button"
                className="btn-secondary btn-sm"
                onClick={() => setName(s)}
              >
                {s}
              </button>
            ))}
          </div>
          <Nav step={step} setStep={setStep} canNext={name.trim().length > 0} />
        </Card>
      )}

      {step === 5 && (
        <Card title="All set" sub="Review and create the team.">
          <dl className="text-sm">
            <dt className="text-faint">Team name</dt>
            <dd className="mb-2">{name}</dd>
            <dt className="text-faint">Work type</dt>
            <dd className="mb-2">{WORK_TYPES.find((w) => w.value === workType)?.label}</dd>
            <dt className="text-faint">Preset</dt>
            <dd className="mb-2">{PRESETS[preset].label}</dd>
            <dt className="text-faint">Categories ({selectedCats.length})</dt>
            <dd>
              {selectedCats.length === 0
                ? "(none)"
                : selectedCats
                    .map((c) => {
                      const label = cat.data?.find((x) => x.code === c)?.label ?? c;
                      const w = cats[c]?.weight ?? 1;
                      return `${label} ×${w.toFixed(1)}`;
                    })
                    .join(", ")}
            </dd>
          </dl>
          <div className="flex justify-between items-center mt-6">
            <button
              type="button"
              className="btn-ghost"
              onClick={() => setStep(4)}
            >
              Back
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={submit}
              disabled={createTeam.isPending}
            >
              {createTeam.isPending ? "Creating…" : "Create team"}
            </button>
          </div>
        </Card>
      )}
    </div>
  );
}

function Nav({
  step,
  setStep,
  canNext,
}: {
  step: number;
  setStep: (n: 1 | 2 | 3 | 4 | 5) => void;
  canNext: boolean;
}) {
  return (
    <div className="flex justify-between items-center mt-6">
      <button
        type="button"
        className="btn-ghost"
        onClick={() => setStep(Math.max(1, step - 1) as 1 | 2 | 3 | 4 | 5)}
        disabled={step === 1}
      >
        Back
      </button>
      <button
        type="button"
        className="btn-primary"
        disabled={!canNext}
        onClick={() => setStep(Math.min(5, step + 1) as 1 | 2 | 3 | 4 | 5)}
      >
        Next
      </button>
    </div>
  );
}

function Progress({ step, max }: { step: number; max: number }) {
  return (
    <div className="flex items-center gap-1 mb-4">
      {Array.from({ length: max }).map((_, i) => (
        <span
          key={i}
          className={`h-1 flex-1 rounded-full ${i + 1 <= step ? "bg-accent" : "bg-paper-sun"}`}
        />
      ))}
    </div>
  );
}

function Card({
  title,
  sub,
  children,
}: {
  title: string;
  sub?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="card">
      <h2 className="text-h1 mb-1">{title}</h2>
      {sub && <p className="text-meta mb-4">{sub}</p>}
      {children}
    </section>
  );
}
