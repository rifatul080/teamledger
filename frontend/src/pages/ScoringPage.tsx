import { useParams } from "react-router-dom";
import { useCreditCategories, useProject } from "../app/data";
import { EmptyState } from "../components/ui/EmptyState";

export default function ScoringPage() {
  const { projectId } = useParams();
  const project = useProject(projectId);
  const cats = useCreditCategories();

  if (!projectId) return null;
  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-h1">Contribution scoring</h1>
        <p className="text-meta">
          Adjust the weights for each CRediT category. The author order on the
          right recomputes live — nothing is saved until you confirm.
        </p>
      </header>
      <div className="grid lg:grid-cols-2 gap-4">
        <section className="card">
          <h2 className="text-h2 mb-3">Categories</h2>
          {cats.isLoading ? (
            <div className="text-meta">Loading…</div>
          ) : (
            <ul className="flex flex-col divide-y divide-line">
              {(cats.data ?? []).map((c) => (
                <li key={c.code} className="py-2 flex items-center justify-between">
                  <span>{c.label}</span>
                  <span className="text-faint font-mono">{c.code}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section className="card">
          <h2 className="text-h2 mb-3">Finalization</h2>
          {project.data?.finalized_at ? (
            <div>
              <div className="badge badge-done">Finalized</div>
              <p className="text-meta mt-2">
                Locked at {new Date(project.data.finalized_at).toLocaleString()}.
              </p>
            </div>
          ) : (
            <EmptyState
              title="Not yet finalized"
              body="Once finalized, scores and author order are revisioned and locked from silent edits."
              action={
                <button className="btn-primary" disabled>
                  Finalize (coming soon)
                </button>
              }
            />
          )}
        </section>
      </div>
    </div>
  );
}
