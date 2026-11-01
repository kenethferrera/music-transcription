import React, { useEffect, useState } from "react";
import {
  CheckCircle2,
  CircleDashed,
  AlertCircle,
  ArrowRight,
  Disc3,
  Mic2,
  Music,
  Sliders,
  FileCheck,
  FileText,
  Activity,
  Layers,
} from "lucide-react";
import { subscribeToProjectEvents, getProject } from "../api/client";
import { JobProgressEvent, JobStage, JobStatus, ProjectSummary } from "../types";

interface ProcessingViewProps {
  projectId: string;
  onProcessingComplete: () => void;
}

interface StageInfo {
  key: JobStage;
  name: string;
  description: string;
  icon: any;
}

const STAGES: StageInfo[] = [
  { key: "upload_complete", name: "1. Upload Verification", description: "Verify uploaded audio in Cloudflare R2", icon: FileCheck },
  { key: "audio_preprocessing", name: "2. Audio Preprocessing", description: "Probe format, duration, and sample rate", icon: Activity },
  { key: "demucs_separation", name: "3. Demucs Separation", description: "Isolate vocals, drums, bass, and other audio", icon: Disc3 },
  { key: "muscriptor_transcription", name: "4. MuScriptor Large", description: "Transcribe notes using MuScriptor Large", icon: Music },
  { key: "external_lyrics_recognition", name: "5. Lyrics Recognition", description: "External STT on vocal stem", icon: Mic2 },
  { key: "lyric_to_note_alignment", name: "6. Lyric-to-Note Alignment", description: "Align syllables to vocal melody notes", icon: Sliders },
  { key: "chord_and_music_analysis", name: "7. Musical Analysis", description: "Non-AI chords, tempo, key, and meter", icon: Layers },
  { key: "arrangement_generation", name: "8. Arrangement Assembly", description: "Reconcile notes and canonical tracks", icon: FileText },
  { key: "export_preparation", name: "9. Export Preparation", description: "Generate MIDI, KAR, and PDF scores", icon: CheckCircle2 },
];

export const ProcessingView: React.FC<ProcessingViewProps> = ({
  projectId,
  onProcessingComplete,
}) => {
  const [project, setProject] = useState<ProjectSummary | null>(null);
  const [latestEvent, setLatestEvent] = useState<JobProgressEvent | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Initial fetch
    getProject(projectId).then(setProject).catch(console.error);

    // Subscribe to SSE events
    const unsubscribe = subscribeToProjectEvents(
      projectId,
      (event) => {
        setLatestEvent(event);
        if (event.status === "failed") {
          setError(event.message || "An error occurred during processing.");
        }
        if (event.status === "success") {
          getProject(projectId).then(setProject).catch(console.error);
        }
      },
      (err) => {
        console.error("SSE Error:", err);
      }
    );

    return () => unsubscribe();
  }, [projectId]);

  const currentStep = latestEvent?.current_step || (project?.status === "success" ? 9 : 1);
  const progressPercent = latestEvent?.progress_percent || project?.progress_percent || 0;
  const isDone = latestEvent?.status === "success" || project?.status === "success";
  const isFailed = latestEvent?.status === "failed" || project?.status === "failed";

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      {/* Top Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <span className="text-xs uppercase tracking-wider text-blue-400 font-semibold">
              Pipeline Stage {currentStep} of 9
            </span>
            <h2 className="text-2xl font-bold text-white mt-1">
              {project ? project.title : "Processing Song..."}
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              {latestEvent?.message || "Running automated Demucs + MuScriptor Large pipeline..."}
            </p>
          </div>

          {isDone && (
            <button
              onClick={onProcessingComplete}
              className="px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium flex items-center space-x-2 shadow-lg shadow-emerald-600/25 transition shrink-0"
            >
              <span>Open in Editor</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Progress Bar */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs text-slate-400 font-medium">
            <span>Overall Progress</span>
            <span>{Math.round(progressPercent)}%</span>
          </div>
          <div className="w-full h-3 bg-slate-950 rounded-full overflow-hidden p-0.5 border border-slate-800">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                isDone
                  ? "bg-emerald-500"
                  : isFailed
                  ? "bg-rose-500"
                  : "bg-gradient-to-r from-blue-500 to-indigo-500 animate-pulse"
              }`}
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {error && (
          <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-2xl text-rose-400 text-sm flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Processing Failed</p>
              <p className="text-xs opacity-90 mt-0.5">{error}</p>
            </div>
          </div>
        )}
      </div>

      {/* 9 Stages List */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-400 px-1">Pipeline Stages</h3>
        <div className="space-y-2">
          {STAGES.map((st, index) => {
            const stepNum = index + 1;
            const isPassed = stepNum < currentStep || isDone;
            const isCurrent = stepNum === currentStep && !isDone && !isFailed;
            const isFailedStage = isFailed && stepNum === currentStep;

            const Icon = st.icon;

            return (
              <div
                key={st.key}
                className={`flex items-center justify-between p-4 rounded-2xl border transition ${
                  isCurrent
                    ? "bg-slate-900 border-blue-500/50 shadow-md shadow-blue-500/5"
                    : isPassed
                    ? "bg-slate-900/40 border-slate-800/80 text-slate-300"
                    : "bg-slate-950/40 border-slate-900 text-slate-500"
                }`}
              >
                <div className="flex items-center space-x-3.5">
                  <div
                    className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
                      isPassed
                        ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                        : isCurrent
                        ? "bg-blue-500/10 text-blue-400 border border-blue-500/20 animate-pulse"
                        : isFailedStage
                        ? "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                        : "bg-slate-800/40 text-slate-600 border border-slate-800"
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                  </div>
                  <div>
                    <h4
                      className={`text-sm font-semibold ${
                        isCurrent ? "text-white" : isPassed ? "text-slate-200" : "text-slate-500"
                      }`}
                    >
                      {st.name}
                    </h4>
                    <p className="text-xs text-slate-400">{st.description}</p>
                  </div>
                </div>

                <div className="shrink-0">
                  {isPassed ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  ) : isCurrent ? (
                    <CircleDashed className="w-5 h-5 text-blue-400 animate-spin" />
                  ) : isFailedStage ? (
                    <AlertCircle className="w-5 h-5 text-rose-400" />
                  ) : (
                    <span className="text-xs text-slate-600 font-mono">Pending</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

