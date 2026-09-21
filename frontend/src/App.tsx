import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import TeamsPage from "./pages/TeamsPage";
import TeamDetailPage from "./pages/TeamDetailPage";
import ProjectDetailPage from "./pages/ProjectDetailPage";
import GoalDetailPage from "./pages/GoalDetailPage";
import ScoringPage from "./pages/ScoringPage";
import ChatPage from "./pages/ChatPage";
import NotificationsPage, { useUnreadCount } from "./pages/NotificationsPage";
import ProfilePage from "./pages/ProfilePage";
import { useMe } from "./app/auth";

export default function App() {
  // Trigger /me once so the layout can decide.
  useMe();

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedLayout />}>
        <Route path="/" element={<Navigate to="/teams" replace />} />
        <Route path="/teams" element={<TeamsPage />} />
        <Route path="/teams/:teamId" element={<TeamDetailPage />} />
        <Route path="/teams/:teamId/chat" element={<ChatPage />} />
        <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        <Route path="/projects/:projectId/score" element={<ScoringPage />} />
        <Route path="/projects/:projectId/goals/:goalId" element={<GoalDetailPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function ProtectedLayout() {
  const me = useMe();
  if (me.isLoading) {
    return (
      <main className="min-h-screen flex items-center justify-center text-slate-600">
        Loading…
      </main>
    );
  }
  if (!me.data) {
    return <Navigate to="/login" replace />;
  }
  return <Layout />;
}

// Sidebar shows an unread badge.
export function UnreadBadge() {
  const unread = useUnreadCount();
  const n = unread.data?.unread ?? 0;
  if (n === 0) return null;
  return (
    <span className="ml-1 inline-flex items-center justify-center text-xs bg-red-600 text-white rounded-full px-1.5 min-w-[1.25rem]">
      {n}
    </span>
  );
}
