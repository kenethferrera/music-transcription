import React from "react";
import { Music, Sliders, FileDown, Layers, PlusCircle } from "lucide-react";

interface NavbarProps {
  activeTab: "dashboard" | "processing" | "editor" | "exports";
  setActiveTab: (tab: "dashboard" | "processing" | "editor" | "exports") => void;
  hasActiveProject: boolean;
  projectTitle?: string;
  onNewProjectClick: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  hasActiveProject,
  projectTitle,
  onNewProjectClick,
}) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab("dashboard")}>
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/20">
            <Music className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-bold bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
              MuScriptor Studio
            </h1>
            <p className="text-xs text-slate-400">Demucs + MuScriptor Large + STT</p>
          </div>
        </div>

        {hasActiveProject && projectTitle && (
          <div className="hidden md:flex items-center space-x-2 px-3 py-1 bg-slate-800/60 rounded-full border border-slate-700/50">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-medium text-slate-300 max-w-xs truncate">{projectTitle}</span>
          </div>
        )}

        <nav className="flex items-center space-x-1 sm:space-x-2">
          <button
            onClick={() => setActiveTab("dashboard")}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition flex items-center space-x-1.5 ${
              activeTab === "dashboard"
                ? "bg-blue-600 text-white shadow-md shadow-blue-600/20"
                : "text-slate-400 hover:text-white hover:bg-slate-800"
            }`}
          >
            <Layers className="w-4 h-4" />
            <span className="hidden sm:inline">Dashboard</span>
          </button>

          {hasActiveProject && (
            <>
              <button
                onClick={() => setActiveTab("processing")}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition flex items-center space-x-1.5 ${
                  activeTab === "processing"
                    ? "bg-blue-600 text-white shadow-md shadow-blue-600/20"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                }`}
              >
                <span className="w-2 h-2 rounded-full bg-blue-400" />
                <span className="hidden sm:inline">Pipeline</span>
              </button>

              <button
                onClick={() => setActiveTab("editor")}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition flex items-center space-x-1.5 ${
                  activeTab === "editor"
                    ? "bg-blue-600 text-white shadow-md shadow-blue-600/20"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                }`}
              >
                <Sliders className="w-4 h-4" />
                <span className="hidden sm:inline">Editor</span>
              </button>

              <button
                onClick={() => setActiveTab("exports")}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition flex items-center space-x-1.5 ${
                  activeTab === "exports"
                    ? "bg-blue-600 text-white shadow-md shadow-blue-600/20"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                }`}
              >
                <FileDown className="w-4 h-4" />
                <span className="hidden sm:inline">Exports</span>
              </button>
            </>
          )}

          <button
            onClick={onNewProjectClick}
            className="ml-2 px-3 py-1.5 rounded-lg text-sm font-medium bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white shadow-md shadow-blue-500/25 flex items-center space-x-1.5 transition"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Upload Song</span>
          </button>
        </nav>
      </div>
    </header>
  );
};

