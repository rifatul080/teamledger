import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <main className="min-h-screen grid place-items-center px-4 bg-paper-muted">
      <div className="card max-w-sm text-center">
        <h1 className="text-h1 mb-1">Not found</h1>
        <p className="text-meta mb-4">That page doesn't exist (or you don't have access).</p>
        <Link to="/" className="btn-primary">
          Back to start
        </Link>
      </div>
    </main>
  );
}
