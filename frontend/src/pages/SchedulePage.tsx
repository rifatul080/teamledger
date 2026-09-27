import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMe } from "../app/auth";
import {
  ScheduleSlot,
  useSaveWeeklyPlan,
  useTeamCalendar,
  useTeamOverload,
  useTeams,
  useWeeklyPlan,
} from "../app/data";
import { EmptyState } from "../components/ui/EmptyState";
import { pushToast } from "../components/ui/Toast";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function toMinutes(hhmm: string): number {
  const parts = hhmm.split(":").map((n) => Number(n));
  const h = parts[0];
  const m = parts[1];
  if (h === undefined || m === undefined || Number.isNaN(h) || Number.isNaN(m)) return 0;
  return h * 60 + m;
}

function toHHMM(minutes: number): string {
  const h = Math.floor(minutes / 60) % 24;
  const m = minutes % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function mondayOf(date: Date): Date {
  const d = new Date(date);
  const day = (d.getDay() + 6) % 7; // 0 = Monday
  d.setDate(d.getDate() - day);
  return d;
}

function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export default function SchedulePage() {
  const me = useMe();
  const teams = useTeams();
  const nav = useNavigate();
  const firstTeam = teams.data?.[0];
  const [teamId, setTeamId] = useState<string | undefined>(undefined);
  const activeTeam = teamId ?? firstTeam?.id;

  const [weekStart, setWeekStart] = useState(() => mondayOf(new Date()));
  const [slots, setSlots] = useState<ScheduleSlot[] | null>(null);
  const [cap, setCap] = useState<string | null>(null);

  const plan = useWeeklyPlan(activeTeam, me.data?.id);
  const savePlan = useSaveWeeklyPlan(activeTeam ?? "");
  const start = iso(weekStart);
  const end = iso(new Date(weekStart.getTime() + 6 * 86400000));
  const calendar = useTeamCalendar(activeTeam, start, end, me.data?.id);
  const overload = useTeamOverload(activeTeam, start);

  const effectiveSlots = useMemo(
    () => slots ?? plan.data?.slots ?? [],
    [slots, plan.data?.slots],
  );
  const effectiveCap = cap ?? String(plan.data?.weekly_cap_hours ?? 20);

  const byDay = useMemo(() => {
    const map = new Map<number, ScheduleSlot[]>();
    for (const s of effectiveSlots) {
      const list = map.get(s.weekday) ?? [];
      list.push(s);
      map.set(s.weekday, list);
    }
    for (const list of map.values()) list.sort((a, b) => a.start_minute - b.start_minute);
    return map;
  }, [effectiveSlots]);

  const scheduledHours = useMemo(
    () =>
      effectiveSlots.reduce(
        (sum, s) => sum + Math.max(0, s.end_minute - s.start_minute) / 60,
        0,
      ),
    [effectiveSlots],
  );

  const events = useMemo(() => calendar.data?.items ?? [], [calendar.data?.items]);
  const byDate = useMemo(() => {
    const map = new Map<string, typeof events>();
    for (const e of events) {
      const key = (e.due_date ?? e.start_date ?? "").slice(0, 10);
      const list = map.get(key) ?? [];
      list.push(e);
      map.set(key, list);
    }
    return map;
  }, [events]);

  if ((teams.data?.length ?? 0) === 0) {
    return (
      <EmptyState
        title="No team yet"
        body="Create a team to plan your week with your teammates."
        action={
          <button className="btn-primary" onClick={() => nav("/onboarding")}>
            Create a team
          </button>
        }
      />
    );
  }

  function addSlot(weekday: number) {
    setSlots([...effectiveSlots, { weekday, start_minute: 9 * 60, end_minute: 12 * 60 }]);
  }

  function updateSlot(i: number, patch: Partial<ScheduleSlot>) {
    setSlots(effectiveSlots.map((s, idx) => (idx === i ? { ...s, ...patch } : s)));
  }

  function removeSlot(i: number) {
    setSlots(effectiveSlots.filter((_, idx) => idx !== i));
  }

  async function save() {
    if (!activeTeam || !me.data) return;
    try {
      await savePlan.mutateAsync({
        user_id: me.data.id,
        weekly_cap_hours: Number(effectiveCap) || 0,
        slots: effectiveSlots,
      });
      setSlots(null);
      setCap(null);
      pushToast({ kind: "ok", title: "Week saved" });
    } catch (e) {

      pushToast({
        kind: "error",
        title: "Could not save your week",
        body: e instanceof Error ? e.message : "Please try again.",
      });

    }
  }

  const weekOverload = (overload.data?.items ?? []).find(
    (i) => i.user_id === me.data?.id && i.assigned_hours > i.cap_hours,
  );


  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-h1">My week</h1>
          <p className="text-meta">Your availability and the deadlines assigned to you.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {(teams.data?.length ?? 0) > 1 && (
            <select
              className="input"
              value={activeTeam ?? ""}
              onChange={(e) => setTeamId(e.target.value)}
            >
              {(teams.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          )}
          <button
            className="btn-secondary"
            onClick={() => setWeekStart(new Date(weekStart.getTime() - 7 * 86400000))}
            aria-label="Previous week"
          >
            ←
          </button>
          <span className="text-meta">
            {weekStart.toLocaleDateString(undefined, { month: "short", day: "numeric" })} –{" "}
            {new Date(weekStart.getTime() + 6 * 86400000).toLocaleDateString(undefined, {
              month: "short",
              day: "numeric",
            })}
          </span>
          <button
            className="btn-secondary"
            onClick={() => setWeekStart(new Date(weekStart.getTime() + 7 * 86400000))}
            aria-label="Next week"
          >
            →
          </button>
        </div>
      </header>

      {weekOverload && (
        <div className="card border-accent text-sm">
          Booked for {weekOverload.assigned_hours}h against a {weekOverload.cap_hours}h cap
          this week.
        </div>
      )}

      <section className="card">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <h2 className="text-h2">Availability</h2>
          <div className="flex items-center gap-2">
            <label className="text-sm text-meta flex items-center gap-1">
              Weekly cap (h)
              <input
                type="number"
                min="0"
                step="1"
                className="input w-20"
                value={effectiveCap}
                onChange={(e) => setCap(e.target.value)}
              />
            </label>
            <button className="btn-primary" onClick={() => void save()}>
              {savePlan.isPending ? "Saving…" : "Save week"}
            </button>
          </div>
        </div>


        <ul className="flex flex-col gap-2">
          {WEEKDAYS.map((label, weekday) => (
            <li key={label} className="flex flex-wrap items-center gap-2">
              <span className="w-10 text-sm text-faint">{label}</span>
              {(byDay.get(weekday) ?? []).map((s) => {
                const i = effectiveSlots.indexOf(s);
                return (
                  <span key={`${weekday}-${i}`} className="flex items-center gap-1">
                    <input
                      type="time"
                      className="input w-28"
                      value={toHHMM(s.start_minute)}
                      onChange={(e) =>
                        updateSlot(i, { start_minute: toMinutes(e.target.value) })
                      }
                    />
                    <span className="text-faint">–</span>
                    <input
                      type="time"
                      className="input w-28"
                      value={toHHMM(s.end_minute)}
                      onChange={(e) => updateSlot(i, { end_minute: toMinutes(e.target.value) })}
                    />
                    <button
                      className="btn-ghost btn-sm"
                      onClick={() => removeSlot(i)}
                      aria-label={`Remove ${label} block`}
                    >
                      ×
                    </button>
                  </span>
                );
              })}
              <button
                className="btn-ghost btn-sm"
                onClick={() => addSlot(weekday)}
                aria-label={`Add ${label} block`}
              >
                + block
              </button>
            </li>
          ))}
        </ul>
        <p className="text-faint text-xs mt-2">
          {scheduledHours.toFixed(1)}h scheduled against a {effectiveCap}h cap.
        </p>
      </section>

      <section className="card">
        <h2 className="text-h2 mb-3">Your deadlines this week</h2>
        {events.length === 0 ? (
          <div className="text-meta">Nothing due this week.</div>
        ) : (
          <ul className="flex flex-col gap-2">
            {WEEKDAYS.map((label, weekday) => {
              const day = new Date(weekStart.getTime() + weekday * 86400000);
              const items = byDate.get(iso(day)) ?? [];
              if (!items.length) return null;
              return (
                <li key={label} className="flex flex-col gap-1">
                  <span className="text-sm text-faint">
                    {day.toLocaleDateString(undefined, {
                      weekday: "long",
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                  <ul className="flex flex-col gap-1">
                    {items.map((e) => (
                      <li key={`${e.kind}-${e.id}`} className="flex items-center gap-2 text-sm">
                        <span className="text-faint uppercase font-mono text-[10px]">
                          {e.kind}
                        </span>
                        <span>{e.title}</span>
                        {e.status && (
                          <span className="text-faint">· {e.status.replace("_", " ")}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}