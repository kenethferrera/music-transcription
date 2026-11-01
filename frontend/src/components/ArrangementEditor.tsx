import React, { useEffect, useRef, useState } from "react";
import {
  Play,
  Pause,
  RotateCcw,
  Volume2,
  VolumeX,
  Plus,
  Trash2,
  Save,
  ZoomIn,
  ZoomOut,
  Layers,
  Music,
  FileDown,
  Sparkles,
} from "lucide-react";
import { getArrangement, getStemUrls, updateArrangement } from "../api/client";
import { Arrangement, NoteEvent, Track, SyllableType } from "../types";

interface ArrangementEditorProps {
  projectId: string;
  onNavigateToExports: () => void;
}

const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

export const ArrangementEditor: React.FC<ArrangementEditorProps> = ({
  projectId,
  onNavigateToExports,
}) => {
  const [arrangement, setArrangement] = useState<Arrangement | null>(null);
  const [stemUrls, setStemUrls] = useState<Record<string, string>>({});
  const [activeTrackId, setActiveTrackId] = useState<string>("vocals");
  const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [zoomLevel, setZoomLevel] = useState(60); // pixels per second
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  // Audio references
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const pianoRollContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // Load arrangement & stems
    getArrangement(projectId)
      .then((data) => {
        setArrangement(data);
        if (data.tracks && Object.keys(data.tracks).length > 0) {
          if (!data.tracks[activeTrackId]) {
            setActiveTrackId(Object.keys(data.tracks)[0]);
          }
        }
      })
      .catch(console.error);

    getStemUrls(projectId)
      .then((urls) => setStemUrls(urls))
      .catch(console.error);
  }, [projectId]);

  // Audio playback ticker
  useEffect(() => {
    let animFrame: number;
    const updateTime = () => {
      if (audioRef.current && isPlaying) {
        setCurrentTime(audioRef.current.currentTime);
        animFrame = requestAnimationFrame(updateTime);
      }
    };
    if (isPlaying) {
      animFrame = requestAnimationFrame(updateTime);
    }
    return () => cancelAnimationFrame(animFrame);
  }, [isPlaying]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play().catch(console.error);
      setIsPlaying(true);
    }
  };

  const seekTo = (seconds: number) => {
    if (audioRef.current) {
      audioRef.current.currentTime = seconds;
    }
    setCurrentTime(seconds);
  };

  const handleSave = async () => {
    if (!arrangement) return;
    setIsSaving(true);
    try {
      const updated = await updateArrangement(projectId, arrangement);
      setArrangement(updated);
      setSaveMessage("Saved & exports updated!");
      setTimeout(() => setSaveMessage(null), 3000);
    } catch (err: any) {
      alert(`Failed to save: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleNotePitchChange = (noteId: string, newPitch: number) => {
    if (!arrangement) return;
    const clamped = Math.max(21, Math.min(108, newPitch));
    const newTracks = { ...arrangement.tracks };
    for (const track of Object.values(newTracks)) {
      const n = track.notes.find((x) => x.id === noteId);
      if (n) {
        n.pitch = clamped;
        n.is_edited = true;
        break;
      }
    }
    setArrangement({ ...arrangement, tracks: newTracks });
  };

  const handleNoteDelete = (noteId: string) => {
    if (!arrangement) return;
    const newTracks = { ...arrangement.tracks };
    for (const track of Object.values(newTracks)) {
      track.notes = track.notes.filter((n) => n.id !== noteId);
    }
    setArrangement({ ...arrangement, tracks: newTracks });
    setSelectedNoteId(null);
  };

  const handleAddNote = (trackId: string, startTime: number, pitch: number) => {
    if (!arrangement || !arrangement.tracks[trackId]) return;
    const newNote: NoteEvent = {
      id: "note_" + Math.random().toString(36).substring(2, 9),
      track_id: trackId,
      pitch,
      start_time: Math.round(startTime * 100) / 100,
      duration: 0.5,
      velocity: 64,
      confidence: 1.0,
      is_edited: true,
    };
    const newTracks = { ...arrangement.tracks };
    newTracks[trackId].notes = [...newTracks[trackId].notes, newNote].sort((a, b) => a.start_time - b.start_time);
    setArrangement({ ...arrangement, tracks: newTracks });
    setSelectedNoteId(newNote.id);
  };

  if (!arrangement) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center text-slate-400">
        Loading Arrangement Editor...
      </div>
    );
  }

  const duration = arrangement.metadata.duration_seconds || 60;
  const totalWidth = duration * zoomLevel;
  const currentTrack = arrangement.tracks[activeTrackId];

  // Pitch range: 36 (C2) to 84 (C6) for comfortable view
  const minPitch = 36;
  const maxPitch = 84;
  const numPitches = maxPitch - minPitch + 1;
  const pitchRowHeight = 20;

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-4">
      {/* Hidden reference audio element */}
      <audio
        ref={audioRef}
        src={stemUrls.original || stemUrls.vocals || ""}
        onEnded={() => setIsPlaying(false)}
      />

      {/* Editor Control Toolbar */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4">
        {/* Playback Controls */}
        <div className="flex items-center space-x-3">
          <button
            onClick={togglePlay}
            className="w-10 h-10 rounded-xl bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center shadow-md shadow-blue-500/25 transition"
          >
            {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
          </button>
          <button
            onClick={() => seekTo(0)}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
            title="Return to start"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
          <div className="font-mono text-sm text-slate-300 px-2 py-1 bg-slate-950 rounded border border-slate-800">
            {Math.floor(currentTime / 60)}:
            {Math.floor(currentTime % 60)
              .toString()
              .padStart(2, "0")}
            .
            {Math.floor((currentTime % 1) * 10)} / {Math.floor(duration / 60)}:
            {Math.floor(duration % 60)
              .toString()
              .padStart(2, "0")}
          </div>
        </div>

        {/* Global Musical Metadata */}
        <div className="flex items-center space-x-4 text-xs text-slate-300">
          <div className="flex items-center space-x-1.5 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
            <span className="text-slate-500">Tempo:</span>
            <span className="font-bold text-blue-400">
              {arrangement.tempo_map[0]?.bpm || 120} BPM
            </span>
          </div>
          <div className="flex items-center space-x-1.5 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
            <span className="text-slate-500">Key:</span>
            <span className="font-bold text-blue-400">
              {arrangement.key_signatures[0]?.key || "C"}{" "}
              {arrangement.key_signatures[0]?.mode || "major"}
            </span>
          </div>
          <div className="flex items-center space-x-1.5 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
            <span className="text-slate-500">Meter:</span>
            <span className="font-bold text-blue-400">
              {arrangement.time_signatures[0]?.numerator || 4}/
              {arrangement.time_signatures[0]?.denominator || 4}
            </span>
          </div>
        </div>

        {/* Zoom & Save Actions */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setZoomLevel((z) => Math.max(30, z - 15))}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
            title="Zoom Out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={() => setZoomLevel((z) => Math.min(180, z + 15))}
            className="p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
            title="Zoom In"
          >
            <ZoomIn className="w-4 h-4" />
          </button>

          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold flex items-center space-x-1.5 shadow-md shadow-blue-600/20 transition disabled:opacity-50"
          >
            <Save className="w-4 h-4" />
            <span>{isSaving ? "Saving..." : "Save Arrangement"}</span>
          </button>

          <button
            onClick={onNavigateToExports}
            className="px-3 py-2 rounded-xl border border-slate-700 hover:bg-slate-800 text-slate-300 text-xs font-medium flex items-center space-x-1.5 transition"
          >
            <FileDown className="w-4 h-4" />
            <span>Exports</span>
          </button>
        </div>
      </div>

      {saveMessage && (
        <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400 text-xs text-center">
          {saveMessage}
        </div>
      )}

      {/* Main Workspace Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Track List Sidebar */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
              Instrument Tracks
            </h3>
            <span className="text-xs text-slate-500">
              {Object.keys(arrangement.tracks).length} tracks
            </span>
          </div>

          <div className="space-y-1.5">
            {Object.entries(arrangement.tracks).map(([trackId, track]) => {
              const isSelected = trackId === activeTrackId;
              return (
                <div
                  key={trackId}
                  onClick={() => setActiveTrackId(trackId)}
                  className={`p-3 rounded-xl border transition cursor-pointer flex items-center justify-between ${
                    isSelected
                      ? "bg-slate-800 border-blue-500/50"
                      : "bg-slate-950/40 border-slate-850 hover:bg-slate-800/50"
                  }`}
                >
                  <div className="flex items-center space-x-2.5">
                    <span
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: track.color }}
                    />
                    <div>
                      <h4
                        className={`text-xs font-semibold ${
                          isSelected ? "text-white" : "text-slate-300"
                        }`}
                      >
                        {track.name}
                      </h4>
                      <p className="text-[10px] text-slate-500">{track.notes.length} notes</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Piano Roll & Synchronized Lanes */}
        <div className="lg:col-span-3 bg-slate-900 border border-slate-800 rounded-2xl p-4 space-y-3 overflow-hidden flex flex-col">
          {/* Synchronized Chords Lane */}
          <div className="space-y-1">
            <span className="text-[10px] uppercase font-bold text-slate-500">Chord Progression</span>
            <div
              className="h-8 bg-slate-950 rounded-lg border border-slate-800 relative overflow-x-auto overflow-y-hidden"
              style={{ width: "100%" }}
            >
              <div style={{ width: `${totalWidth}px`, height: "100%", position: "relative" }}>
                {arrangement.chords.map((ch) => (
                  <div
                    key={ch.id}
                    className="absolute top-1 bottom-1 bg-indigo-500/10 border border-indigo-500/30 rounded px-1.5 flex items-center text-xs font-bold text-indigo-300"
                    style={{
                      left: `${ch.start_time * zoomLevel}px`,
                      width: `${Math.max(30, ch.duration * zoomLevel - 2)}px`,
                    }}
                  >
                    {ch.symbol}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Synchronized Lyrics Lane */}
          <div className="space-y-1">
            <span className="text-[10px] uppercase font-bold text-slate-500">Lyrics / Syllables</span>
            <div
              className="h-8 bg-slate-950 rounded-lg border border-slate-800 relative overflow-x-auto overflow-y-hidden"
              style={{ width: "100%" }}
            >
              <div style={{ width: `${totalWidth}px`, height: "100%", position: "relative" }}>
                {arrangement.lyrics.map((lyr) => (
                  <div
                    key={lyr.id}
                    className="absolute top-1 bottom-1 bg-pink-500/10 border border-pink-500/20 rounded px-1.5 flex items-center text-[11px] text-pink-300 truncate"
                    style={{
                      left: `${lyr.start_time * zoomLevel}px`,
                      width: `${Math.max(25, lyr.duration * zoomLevel - 2)}px`,
                    }}
                  >
                    {lyr.text}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Piano Roll Grid */}
          <div className="flex-1 flex flex-col space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-[10px] uppercase font-bold text-slate-500">
                Piano Roll ({currentTrack ? currentTrack.name : "Track"})
              </span>
              <span className="text-[10px] text-slate-500">
                Double-click grid to add note • Click note to inspect
              </span>
            </div>

            <div
              ref={pianoRollContainerRef}
              className="relative bg-slate-950 rounded-xl border border-slate-800 h-96 overflow-auto flex"
            >
              {/* Pitch Label Sidebar */}
              <div className="sticky left-0 z-30 bg-slate-900 border-r border-slate-800 w-12 shrink-0">
                {Array.from({ length: numPitches }).map((_, i) => {
                  const pitch = maxPitch - i;
                  const noteName = NOTE_NAMES[pitch % 12];
                  const octave = Math.floor(pitch / 12) - 1;
                  const isBlackKey = noteName.includes("#");

                  return (
                    <div
                      key={pitch}
                      style={{ height: `${pitchRowHeight}px` }}
                      className={`text-[9px] font-mono px-1 flex items-center justify-between border-b border-slate-850 ${
                        isBlackKey ? "bg-slate-950 text-slate-500" : "bg-slate-900 text-slate-300"
                      }`}
                    >
                      <span>{noteName}</span>
                      <span className="opacity-60">{octave}</span>
                    </div>
                  );
                })}
              </div>

              {/* Grid Canvas */}
              <div
                className="relative"
                style={{ width: `${totalWidth}px`, height: `${numPitches * pitchRowHeight}px` }}
                onDoubleClick={(e) => {
                  const rect = e.currentTarget.getBoundingClientRect();
                  const clickX = e.clientX - rect.left;
                  const clickY = e.clientY - rect.top;
                  const startSec = clickX / zoomLevel;
                  const pitchIndex = Math.floor(clickY / pitchRowHeight);
                  const pitch = maxPitch - pitchIndex;
                  handleAddNote(activeTrackId, startSec, pitch);
                }}
              >
                {/* Horizontal Pitch Grid Lines */}
                {Array.from({ length: numPitches }).map((_, i) => (
                  <div
                    key={i}
                    style={{ top: `${i * pitchRowHeight}px`, height: `${pitchRowHeight}px` }}
                    className="absolute left-0 right-0 border-b border-slate-900/80 pointer-events-none"
                  />
                ))}

                {/* Vertical Beat Lines (1 second marks) */}
                {Array.from({ length: Math.ceil(duration) }).map((_, s) => (
                  <div
                    key={s}
                    style={{ left: `${s * zoomLevel}px` }}
                    className="absolute top-0 bottom-0 border-r border-slate-900/80 pointer-events-none"
                  />
                ))}

                {/* Playhead Marker */}
                <div
                  style={{ left: `${currentTime * zoomLevel}px` }}
                  className="absolute top-0 bottom-0 w-0.5 bg-rose-500 z-20 pointer-events-none shadow-sm shadow-rose-500"
                />

                {/* Transcribed Notes */}
                {currentTrack?.notes.map((note) => {
                  const isSelected = note.id === selectedNoteId;
                  const pitchOffset = maxPitch - note.pitch;
                  const top = pitchOffset * pitchRowHeight;
                  const left = note.start_time * zoomLevel;
                  const width = Math.max(8, note.duration * zoomLevel);

                  return (
                    <div
                      key={note.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedNoteId(note.id);
                      }}
                      style={{
                        top: `${top + 1}px`,
                        left: `${left}px`,
                        width: `${width}px`,
                        height: `${pitchRowHeight - 2}px`,
                        backgroundColor: currentTrack.color || "#3b82f6",
                      }}
                      className={`absolute rounded-sm text-[8px] font-mono font-bold text-white px-1 flex items-center justify-between cursor-pointer shadow-sm transition ${
                        isSelected ? "ring-2 ring-white z-10 brightness-125" : "hover:brightness-110"
                      }`}
                    >
                      <span className="truncate">{NOTE_NAMES[note.pitch % 12]}</span>
                      {isSelected && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleNoteDelete(note.id);
                          }}
                          className="text-white hover:text-rose-200"
                        >
                          ×
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

