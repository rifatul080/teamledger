import { Route, Routes } from "react-router-dom";

export default function App() {
  return (
    <main className="min-h-screen">
      <Routes>
        <Route path="/" element={<HomePage />} />
      </Routes>
    </main>
  );
}

function HomePage() {
  return (
    <div className="max-w-3xl mx-auto p-6">
      <h1 className="text-2xl font-semibold">TeamLedger</h1>
      <p className="mt-2 text-slate-600">
        The app is under construction. Use the API at <code>/api/v1/docs</code>.
      </p>
    </div>
  );
}
