import React, { useEffect, useState } from "react";
import { Plus, Music2, Clock, Trash2, ArrowRight, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";
import { deleteProject, listProjects } from "../api/client";
import { ProjectSummary } from "../types";

interface DashboardProps {
  onSelectProject: (projectId: string, tab: "processing" | "editor" | "exports") => void;
  onNewProjectClick: () => void;
}

export const Dashboard: React.FC<DashboardProps> = ({
  onSelectProject,
  onNewProjectClick,
}) => {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      const data = await listProjects();
      setProjects(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load projects");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this project and all its stems and exports?")) return;
    try {
      await deleteProject(id);
      setProjects((prev) => prev.filter((p) => p.id !== id));
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-8">
      {/* Hero Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-r from-blue-900/40 via-indigo-900/20 to-slate-900 border border-slate-800 p-8 sm:p-10">
        <div className="relative z-10 max-w-2xl space-y-4">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-semibold">
            <span>Demucs + MuScriptor Large</span>
          </div>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight">
            Transcribe Any Song into Score, Chords & Multitrack MIDI
          </h2>
          <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
            Upload your audio track to separate stems via Demucs, transcribe notes with MuScriptor Large, align lyrics with external STT, and export synchronized MIDI, Karaoke KAR, and sheet music PDFs.
          </p>
          <div className="pt-2 flex items-center space-x-4">
            <button
              onClick={onNewProjectClick}
              className="px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-medium shadow-lg shadow-blue-500/25 flex items-center space-x-2 transition"
            >
              <Plus className="w-5 h-5" />
              <span>Transcribe Song</span>
            </button>
            <button
              onClick={fetchProjects}
              className="p-3 rounded-xl border border-slate-700 hover:bg-slate-800 text-slate-300 transition"
              title="Refresh projects"
            >
              <RefreshCw className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Projects List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-xl font-bold text-white">Your Projects</h3>
          <span className="text-xs text-slate-400">{projects.length} songs transcribed</span>
        </div>

        {loading ? (
          <div className="p-12 text-center text-slate-400">Loading projects...</div>
        ) : error ? (
          <div className="p-6 bg-rose-500/10 border border-rose-500/20 rounded-2xl text-rose-400 text-sm flex items-center justify-between">
            <span>{error}</span>
            <button onClick={fetchProjects} className="underline text-xs">Retry</button>
          </div>
        ) : projects.length === 0 ? (
          <div className="border border-slate-800 rounded-2xl p-12 text-center space-y-3 bg-slate-900/40">
            <Music2 className="w-12 h-12 text-slate-600 mx-auto" />
            <h4 className="text-base font-semibold text-slate-300">No projects yet</h4>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Upload your first MP3 or WAV audio track to start separating stems and generating sheet music.
            </p>
            <button
              onClick={onNewProjectClick}
              className="mt-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium"
            >
              Upload Song
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((p) => {
              const isDone = p.status === "success";
              const isFailed = p.status === "failed";
              const isProcessing = p.status === "processing";

              return (
                <div
                  key={p.id}
                  onClick={() => onSelectProject(p.id, isDone ? "editor" : "processing")}
                  className="bg-slate-900/60 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 transition cursor-pointer group flex flex-col justify-between space-y-4 shadow-sm"
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between">
                      <div className="space-y-1">
                        <h4 className="text-base font-semibold text-white group-hover:text-blue-400 transition truncate max-w-[200px]">
                          {p.title}
                        </h4>
                        <p className="text-xs text-slate-400">{p.artist || "Unknown Artist"}</p>
                      </div>

                      {/* Status Badge */}
                      <span
                        className={`text-xs px-2.5 py-0.5 rounded-full font-medium flex items-center space-x-1 ${
                          isDone
                            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                            : isFailed
                            ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                            : "bg-blue-500/10 text-blue-400 border border-blue-500/20 animate-pulse"
                        }`}
                      >
                        {isDone ? (
                          <>
                            <CheckCircle2 className="w-3 h-3" />
                            <span>Ready</span>
                          </>
                        ) : isFailed ? (
                          <>
                            <AlertCircle className="w-3 h-3" />
                            <span>Failed</span>
                          </>
                        ) : (
                          <span>{p.progress_percent}%</span>
                        )}
                      </span>
                    </div>

                    <div className="text-xs text-slate-500 flex items-center space-x-3 pt-1">
                      <span className="flex items-center space-x-1">
                        <Clock className="w-3 h-3" />
                        <span>{new Date(p.created_at).toLocaleDateString()}</span>
                      </span>
                      {p.total_notes !== undefined && p.total_notes !== null && (
                        <span>• {p.total_notes} notes</span>
                      )}
                    </div>
                  </div>

                  <div className="pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs">
                    <div className="flex items-center space-x-2">
                      {isDone && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectProject(p.id, "exports");
                          }}
                          className="text-blue-400 hover:text-blue-300 font-medium"
                        >
                          Downloads
                        </button>
                      )}
                    </div>

                    <div className="flex items-center space-x-2">
                      <button
                        onClick={(e) => handleDelete(e, p.id)}
                        className="text-slate-500 hover:text-rose-400 p-1 rounded"
                        title="Delete project"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                      <ArrowRight className="w-4 h-4 text-slate-500 group-hover:text-blue-400 group-hover:translate-x-0.5 transition" />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

