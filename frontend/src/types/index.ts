export type InstrumentFamily =
  | "piano"
  | "guitar"
  | "bass"
  | "drums"
  | "vocals"
  | "strings"
  | "brass"
  | "reed"
  | "organ"
  | "synth"
  | "other";

export type SyllableType = "single" | "begin" | "middle" | "end";

export interface NoteEvent {
  id: string;
  track_id: string;
  pitch: number;
  start_time: number;
  duration: number;
  velocity: number;
  confidence: number;
  source_stem?: string;
  is_edited?: boolean;
}

export interface LyricEvent {
  id: string;
  text: string;
  start_time: number;
  duration: number;
  note_id?: string;
  syllable_type: SyllableType;
  confidence: number;
  is_edited?: boolean;
}

export interface ChordEvent {
  id: string;
  symbol: string;
  root: string;
  quality: string;
  start_time: number;
  duration: number;
  confidence: number;
  is_edited?: boolean;
}

export interface TempoEvent {
  start_time: number;
  bpm: number;
  confidence: number;
}

export interface TimeSignatureEvent {
  start_time: number;
  numerator: number;
  denominator: number;
}

export interface KeySignatureEvent {
  start_time: number;
  key: string;
  mode: string;
}

export interface Track {
  id: string;
  name: string;
  family: InstrumentFamily;
  midi_program: number;
  is_percussion: boolean;
  color: string;
  volume: number;
  pan: number;
  muted: boolean;
  solo: boolean;
  notes: NoteEvent[];
}

export interface ProjectMetadata {
  project_id: string;
  title: string;
  artist?: string;
  original_filename: string;
  audio_format: string;
  duration_seconds: number;
  sample_rate: number;
  channels: number;
  created_at: string;
  model_version_demucs?: string;
  model_version_muscriptor?: string;
  stt_provider?: string;
}

export interface Arrangement {
  metadata: ProjectMetadata;
  tempo_map: TempoEvent[];
  time_signatures: TimeSignatureEvent[];
  key_signatures: KeySignatureEvent[];
  chords: ChordEvent[];
  lyrics: LyricEvent[];
  tracks: Record<string, Track>;
  stem_references: Record<string, string>;
}

export type JobStage =
  | "queued"
  | "upload_complete"
  | "audio_preprocessing"
  | "demucs_separation"
  | "muscriptor_transcription"
  | "external_lyrics_recognition"
  | "lyric_to_note_alignment"
  | "chord_and_music_analysis"
  | "arrangement_generation"
  | "export_preparation"
  | "completed"
  | "failed";

export type JobStatus = "pending" | "processing" | "success" | "failed" | "cancelled";

export interface JobProgressEvent {
  project_id: string;
  stage: JobStage;
  status: JobStatus;
  progress_percent: number;
  current_step: number;
  total_steps: number;
  stage_name: string;
  message: string;
  timestamp: string;
  details?: Record<string, any>;
}

export interface ProjectSummary {
  id: string;
  title: string;
  artist?: string;
  original_filename: string;
  created_at: string;
  status: JobStatus;
  stage: JobStage;
  progress_percent: number;
  duration_seconds?: number;
  total_notes?: number;
  tracks_count?: number;
}

