// Author order finalize + export buttons.
import { useState } from "react";
import { useParams } from "react-router-dom";
import { openDownload } from "../app/api";
import {
  useFinalizeOrder,
  useProjectScore,
  useSnapshots,
  type OrderPosition,
} from "../app/scoring";
import { useProject } from "../app/routes";
import { Button, Card, ErrorBox } from "../components/ui";

export default function ScoringPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const score = useProjectScore(projectId);
  const finalize = useFinalizeOrder(projectId ?? "");
  const project = useProject(projectId);
  const snapshots = useSnapshots(projectId);
  const [error, setError] = useState<string | null>(null);
  const [draftOrder, setDraftOrder] = useState<OrderPosition[]>([]);

  function buildDraft() {
    if (!score.data) return;
    setDraftOrder([...score.data.suggested_order]);
  }

  function move(idx: number, dir: -1 | 1) {
    setDraftOrder((prev) => {
      const next = [...prev];
      const target = idx + dir;
      if (target < 0 || target >= next.length) return prev;
      [next[idx], next[target]] = [next[target]!, next[idx]!];
      next.forEach((p, i) => (p.position = i + 1));
      return next;
    });
  }

  async function submitFinalize() {
    setError(null);
    try {
      await finalize.mutateAsync(
        draftOrder.map((p) => ({ position: p.position, user_id: p.user_id, note: p.note ?? undefined })),
      );
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function dl(kind: "pdf" | "csv" | "statement", snapId: string) {
    try {
      await openDownload(
        `/projects/${projectId}/author-order/export.${kind === "statement" ? "statement.txt" : `export.${kind}`}`,
        { snapshot_id: snapId },
      );
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Author order</h1>
        {project.data?.finalized_at && (
          <span className="text-xs text-slate-500">
            Finalized {project.data.finalized_at}
          </span>
        )}
      </div>

      {score.isLoading ? (
        <Card>Loading…</Card>
      ) : !score.data ? (
        <Card>No score yet.</Card>
      ) : (
        <Card>
          <h2 className="text-sm font-semibold mb-2">Participants</h2>
          <ul className="text-sm">
            {score.data.participants.map((p) => (
              <li key={p.user_id} className="flex items-center justify-between border-b py-1">
                <span>{p.display_name}</span>
                <span className="font-mono text-xs">{p.total_points} pts</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {!project.data?.finalized_at && (
        <Card>
          <h2 className="text-sm font-semibold mb-2">Finalize author order</h2>
          <Button variant="secondary" onClick={buildDraft} className="mb-3">
            Use suggested order
          </Button>
          <ol className="text-sm flex flex-col gap-1">
            {draftOrder.map((p, idx) => (
              <li key={p.user_id} className="flex items-center justify-between border-b py-1">
                <span>
                  {p.position}. {p.user_id}
                </span>
                <span className="flex gap-1">
                  <Button variant="secondary" onClick={() => move(idx, -1)}>
                    ↑
                  </Button>
                  <Button variant="secondary" onClick={() => move(idx, 1)}>
                    ↓
                  </Button>
                </span>
              </li>
            ))}
          </ol>
          <div className="mt-3">
            <Button onClick={submitFinalize} disabled={draftOrder.length === 0 || finalize.isPending}>
              Finalize
            </Button>
          </div>
          <ErrorBox message={error ?? undefined} />
        </Card>
      )}

      <Card>
        <h2 className="text-sm font-semibold mb-2">Snapshots</h2>
        {snapshots.data && snapshots.data.length > 0 ? (
          <ul className="flex flex-col gap-2 text-sm">
            {snapshots.data.map((s) => (
              <li key={s.id} className="flex items-center justify-between border-b py-1">
                <div>
                  <span className="font-mono text-xs">{s.sha256.slice(0, 12)}…</span>
                  <span className="text-xs text-slate-500 ml-2">{s.finalized_at}</span>
                </div>
                <span className="flex gap-1">
                  <Button variant="secondary" onClick={() => dl("csv", s.id)}>
                    CSV
                  </Button>
                  <Button variant="secondary" onClick={() => dl("pdf", s.id)}>
                    PDF
                  </Button>
                  <Button variant="secondary" onClick={() => dl("statement", s.id)}>
                    Statement
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-slate-500">No finalized snapshots yet.</div>
        )}
        <ErrorBox message={error ?? undefined} />
      </Card>
    </div>
  );
}
