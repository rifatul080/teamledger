import { Route, Routes } from "react-router-dom";
import { Toaster } from "./components/ui/Toast";
import ProtectedLayout from "./shell/ProtectedLayout";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import DashboardPage from "./pages/DashboardPage";
import TeamsPage from "./pages/TeamsPage";
import TeamDetailPage from "./pages/TeamDetailPage";
import ProjectDetailPage from "./pages/ProjectDetailPage";
import ProjectNewPage from "./pages/ProjectNewPage";
import GoalDetailPage from "./pages/GoalDetailPage";
import ChatPage from "./pages/ChatPage";
import ScoringPage from "./pages/ScoringPage";
import NotificationsPage from "./pages/NotificationsPage";
import ProfilePage from "./pages/ProfilePage";
import OnboardingPage from "./pages/OnboardingPage";
import VerifyEmailPage from "./pages/VerifyEmailPage";
import AcceptInvitePage from "./pages/AcceptInvitePage";
import NotFoundPage from "./pages/NotFoundPage";
import CommandPaletteHost from "./shell/CommandPaletteHost";

export default function App() {
  return (
    <>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/accept-invite" element={<AcceptInvitePage />} />

        <Route element={<ProtectedLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/teams" element={<TeamsPage />} />
          <Route path="/teams/:teamId" element={<TeamDetailPage />} />
          <Route path="/teams/:teamId/projects/new" element={<ProjectNewPage />} />
          <Route path="/teams/:teamId/chat" element={<ChatPage />} />
          <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
          <Route
            path="/projects/:projectId/goals/:goalId"
            element={<GoalDetailPage />}
          />
          <Route path="/projects/:projectId/scoring" element={<ScoringPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/me" element={<ProfilePage />} />
          <Route path="/u/:userId" element={<ProfilePage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
      <CommandPaletteHost />
      <Toaster />
    </>
  );
}
