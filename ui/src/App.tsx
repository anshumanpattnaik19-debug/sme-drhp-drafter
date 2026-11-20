import { Navigate, Route, Routes, useParams } from "react-router-dom";
import { ConnectionBanner, TopBar } from "./components/TopBar";
import { ProjectShell } from "./components/ProjectShell";
import { SettingsDialog } from "./components/SettingsDialog";
import { ProjectProvider } from "./lib/state";
import ProjectsPage from "./pages/Projects";
import OverviewPage from "./pages/Overview";
import DocumentsPage from "./pages/Documents";
import OfferPage from "./pages/Offer";
import FactsPage from "./pages/Facts";
import DraftPage from "./pages/Draft";
import ReviewPage from "./pages/Review";
import ExportPage from "./pages/Export";
import AssistantPage from "./pages/Assistant";

function ProjectRoutes() {
  const { pid = "" } = useParams();
  return (
    <ProjectProvider pid={pid}>
      <ProjectShell>
        <Routes>
          <Route index element={<Navigate to="overview" replace />} />
          <Route path="overview" element={<OverviewPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="offer" element={<OfferPage />} />
          <Route path="facts" element={<FactsPage />} />
          <Route path="draft" element={<DraftPage />} />
          <Route path="draft/:key" element={<DraftPage />} />
          <Route path="review" element={<ReviewPage />} />
          <Route path="export" element={<ExportPage />} />
          <Route path="assistant" element={<AssistantPage />} />
          <Route path="*" element={<Navigate to="overview" replace />} />
        </Routes>
      </ProjectShell>
    </ProjectProvider>
  );
}

export default function App() {
  return (
    <div className="flex h-full flex-col">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-surface px-3 py-2 text-sm font-medium shadow-pop focus:not-sr-only focus:fixed focus:left-3 focus:top-3"
      >
        Skip to content
      </a>
      <TopBar />
      <ConnectionBanner />
      <div className="min-h-0 flex-1">
        <Routes>
          <Route path="/" element={<Navigate to="/projects" replace />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/p/:pid/*" element={<ProjectRoutes />} />
          <Route path="*" element={<Navigate to="/projects" replace />} />
        </Routes>
      </div>
      <SettingsDialog />
    </div>
  );
}
