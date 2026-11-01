import React, { useState } from "react";
import { Upload, X, Music, AlertCircle } from "lucide-react";
import { createProject, uploadAudioFile, startProcessing } from "../api/client";

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onProjectCreated: (projectId: string) => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onProjectCreated,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [artist, setArtist] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      setFile(selected);
      if (!title) {
        const baseName = selected.name.replace(/\.[^/.]+$/, "");
        setTitle(baseName);
      }
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const dropped = e.dataTransfer.files[0];
      setFile(dropped);
      if (!title) {
        const baseName = dropped.name.replace(/\.[^/.]+$/, "");
        setTitle(baseName);
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !title.trim()) return;

    setIsUploading(true);
    setUploadProgress(5);
    setError(null);

    try {
      // 1. Create project & request upload URL
      const { project_id, upload_url } = await createProject(
        title.trim(),
        artist.trim() || "Unknown Artist",
        file.name,
        file.type || "audio/wav"
      );

      setUploadProgress(15);

      // 2. Upload file to presigned URL
      await uploadAudioFile(upload_url, file, (pct) => {
        setUploadProgress(15 + Math.round((pct * 0.7)));
      });

      setUploadProgress(90);

      // 3. Trigger processing pipeline
      await startProcessing(project_id);

      setUploadProgress(100);
      onProjectCreated(project_id);
      onClose();
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Failed to upload song and start transcription");
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl">
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Music className="w-5 h-5 text-blue-500" />
            <h2 className="text-lg font-semibold text-white">Transcribe New Song</h2>
          </div>
          <button
            onClick={onClose}
            disabled={isUploading}
            className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-sm flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* File Dropzone */}
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition ${
              file
                ? "border-emerald-500/50 bg-emerald-500/5"
                : "border-slate-700 hover:border-blue-500/50 hover:bg-blue-500/5"
            }`}
            onClick={() => document.getElementById("file-input")?.click()}
          >
            <input
              id="file-input"
              type="file"
              accept="audio/*,.mp3,.wav,.flac,.ogg,.m4a"
              className="hidden"
              onChange={handleFileChange}
              disabled={isUploading}
            />
            <Upload className={`w-8 h-8 mx-auto mb-2 ${file ? "text-emerald-400" : "text-slate-400"}`} />
            {file ? (
              <div>
                <p className="text-sm font-medium text-emerald-400 truncate">{file.name}</p>
                <p className="text-xs text-slate-400">{(file.size / (1024 * 1024)).toFixed(2)} MB</p>
              </div>
            ) : (
              <div>
                <p className="text-sm font-medium text-slate-200">
                  Drop your song here or <span className="text-blue-400 underline">browse</span>
                </p>
                <p className="text-xs text-slate-400 mt-1">Supports MP3, WAV, FLAC, OGG, and M4A</p>
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Song Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Bohemian Rhapsody"
              required
              disabled={isUploading}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Artist / Band</label>
            <input
              type="text"
              value={artist}
              onChange={(e) => setArtist(e.target.value)}
              placeholder="e.g. Queen"
              disabled={isUploading}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          {isUploading && (
            <div className="space-y-1.5 pt-2">
              <div className="flex justify-between text-xs text-slate-400">
                <span>Uploading song...</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            </div>
          )}

          <div className="pt-2 flex justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isUploading}
              className="px-4 py-2 rounded-lg text-sm text-slate-400 hover:text-white hover:bg-slate-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!file || !title.trim() || isUploading}
              className="px-5 py-2 rounded-lg text-sm font-medium bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white shadow-lg shadow-blue-600/20"
            >
              {isUploading ? "Processing..." : "Start Transcription"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

