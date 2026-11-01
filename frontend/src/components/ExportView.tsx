import React, { useEffect, useState } from "react";
import { Download, FileText, Music2, Mic2, FileCode, ExternalLink, CheckCircle } from "lucide-react";
import { getExportUrl, getProject } from "../api/client";
import { ProjectSummary } from "../types";

interface ExportViewProps {
  projectId: string;
}

interface ExportItem {
  key: "midi" | "kar" | "musicxml" | "lead-musicxml" | "pdf" | "lead-pdf";
  title: string;
  description: string;
  formatName: string;
  badge: string;
  icon: any;
}

const EXPORTS: ExportItem[] = [
  {
    key: "midi",
    title: "Multitrack MIDI (.mid)",
    description: "Standard Type 1 MIDI with isolated tracks for Vocals, Piano, Guitar, Bass, and Drums.",
    formatName: ".mid",
    badge: "MIDI Type 1",
    icon: Music2,
  },
  {
    key: "kar",
    title: "Karaoke MIDI (.kar)",
    description: "Standard Karaoke MIDI with syllable-synchronized lyric meta-events on vocal melody channel.",
    formatName: ".kar",
    badge: "Karaoke MIDI",
    icon: Mic2,
  },
  {
    key: "pdf",
    title: "Full-Score Sheet Music PDF",
    description: "Engraved multi-stave sheet music score with clefs, tempo, key, bar lines, and parts.",
    formatName: ".pdf",
    badge: "PDF Score",
    icon: FileText,
  },
  {
    key: "lead-pdf",
    title: "Lead-Sheet PDF",
    description: "Vocal melody with lyrics aligned below notes and chord symbols engraved above.",
    formatName: ".pdf",
    badge: "Lead Sheet",
    icon: FileText,
  },
  {
    key: "musicxml",
    title: "Full-Score MusicXML",
    description: "Universal notation interchange format for MuseScore, Sibelius, Dorico, and Finale.",
    formatName: ".musicxml",
    badge: "MusicXML 4.0",
    icon: FileCode,
  },
  {
    key: "lead-musicxml",
    title: "Lead-Sheet MusicXML",
    description: "Universal MusicXML representation of lead melody, lyrics, and chords.",
    formatName: ".musicxml",
    badge: "MusicXML 4.0",
    icon: FileCode,
  },
];

export const ExportView: React.FC<ExportViewProps> = ({ projectId }) => {
  const [project, setProject] = useState<ProjectSummary | null>(null);
  const [downloadUrls, setDownloadUrls] = useState<Record<string, string>>({});
  const [loadingKeys, setLoadingKeys] = useState<Record<string, boolean>>({});

  useEffect(() => {
    getProject(projectId).then(setProject).catch(console.error);

    // Fetch initial export URLs
    EXPORTS.forEach(async (exp) => {
      try {
        const { download_url } = await getExportUrl(projectId, exp.key);
        setDownloadUrls((prev) => ({ ...prev, [exp.key]: download_url }));
      } catch (err) {
        // May not be generated yet if still processing
      }
    });
  }, [projectId]);

  const handleDownload = async (key: ExportItem["key"]) => {
    try {
      setLoadingKeys((prev) => ({ ...prev, [key]: true }));
      let url = downloadUrls[key];
      if (!url) {
        const res = await getExportUrl(projectId, key);
        url = res.download_url;
        setDownloadUrls((prev) => ({ ...prev, [key]: url }));
      }
      window.open(url, "_blank");
    } catch (err: any) {
      alert(`Download failed: ${err.message}`);
    } finally {
      setLoadingKeys((prev) => ({ ...prev, [key]: false }));
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 space-y-2">
        <span className="text-xs font-semibold uppercase tracking-wider text-blue-400">
          Generated Outputs & Downloads
        </span>
        <h2 className="text-2xl font-bold text-white">
          {project ? project.title : "Song Exports"}
        </h2>
        <p className="text-xs text-slate-400 max-w-xl">
          All files are generated from the canonical arrangement representation and stored in Cloudflare R2.
        </p>
      </div>

      {/* Export Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {EXPORTS.map((exp) => {
          const Icon = exp.icon;
          const isLoading = loadingKeys[exp.key];
          const hasUrl = Boolean(downloadUrls[exp.key]);

          return (
            <div
              key={exp.key}
              className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 flex flex-col justify-between space-y-4 hover:border-slate-700 transition"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center">
                    <Icon className="w-5 h-5" />
                  </div>
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                    {exp.badge}
                  </span>
                </div>

                <div className="space-y-1">
                  <h4 className="text-base font-semibold text-white">{exp.title}</h4>
                  <p className="text-xs text-slate-400 leading-relaxed">{exp.description}</p>
                </div>
              </div>

              <div className="pt-2">
                <button
                  onClick={() => handleDownload(exp.key)}
                  disabled={isLoading}
                  className="w-full py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center justify-center space-x-2 shadow-md shadow-blue-600/20 transition disabled:opacity-50"
                >
                  <Download className="w-4 h-4" />
                  <span>{isLoading ? "Retrieving URL..." : `Download ${exp.formatName}`}</span>
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

