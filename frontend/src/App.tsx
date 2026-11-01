import React, { useState } from "react";
import { Navbar } from "./components/Navbar";
import { Dashboard } from "./components/Dashboard";
import { UploadModal } from "./components/UploadModal";
import { ProcessingView } from "./components/ProcessingView";
import { ArrangementEditor } from "./components/ArrangementEditor";
import { ExportView } from "./components/ExportView";

export function App() {
  const [activeTab, setActiveTab] = useState<"dashboard" | "processing" | "editor" | "exports">("dashboard");
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);

  const handleSelectProject = (projectId: string, tab: "processing" | "editor" | "exports") => {
    setActiveProjectId(projectId);
    setActiveTab(tab);
  };

  const handleProjectCreated = (projectId: string) => {
    setActiveProjectId(projectId);
    setActiveTab("processing");
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 font-sans selection:bg-blue-500 selection:text-white">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        hasActiveProject={Boolean(activeProjectId)}
        projectTitle={activeProjectId ? `Project #${activeProjectId.slice(0, 8)}` : undefined}
        onNewProjectClick={() => setIsUploadModalOpen(true)}
      />

      <main className="flex-1 pb-16">
        {activeTab === "dashboard" && (
          <Dashboard
            onSelectProject={handleSelectProject}
            onNewProjectClick={() => setIsUploadModalOpen(true)}
          />
        )}

        {activeTab === "processing" && activeProjectId && (
          <ProcessingView
            projectId={activeProjectId}
            onProcessingComplete={() => setActiveTab("editor")}
          />
        )}

        {activeTab === "editor" && activeProjectId && (
          <ArrangementEditor
            projectId={activeProjectId}
            onNavigateToExports={() => setActiveTab("exports")}
          />
        )}

        {activeTab === "exports" && activeProjectId && (
          <ExportView projectId={activeProjectId} />
        )}
      </main>

      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onProjectCreated={handleProjectCreated}
      />
    </div>
  );
}

export default App;

