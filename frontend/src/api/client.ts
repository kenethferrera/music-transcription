import { Arrangement, JobProgressEvent, ProjectSummary } from "../types";

const API_BASE = "/api";

export async function createProject(
  title: string,
  artist: string,
  filename: string,
  contentType: string = "audio/wav"
): Promise<{ project_id: string; title: string; upload_url: string; upload_key: string }> {
  const res = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, artist, filename, content_type: contentType }),
  });
  if (!res.ok) throw new Error(`Failed to create project: ${res.statusText}`);
  return res.json();
}

export async function uploadAudioFile(
  uploadUrl: string,
  file: File,
  onProgress?: (pct: number) => void
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", uploadUrl);
    xhr.setRequestHeader("Content-Type", file.type || "audio/wav");

    if (xhr.upload && onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
          const pct = Math.round((e.loaded / e.total) * 100);
          onProgress(pct);
        }
      };
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(new Error(`Upload failed with status ${xhr.status}`));
      }
    };
    xhr.onerror = () => reject(new Error("Network error during file upload"));
    xhr.send(file);
  });
}

export async function startProcessing(projectId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/process`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to start processing: ${res.statusText}`);
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const res = await fetch(`${API_BASE}/projects`);
  if (!res.ok) throw new Error(`Failed to fetch projects: ${res.statusText}`);
  return res.json();
}

export async function getProject(projectId: string): Promise<ProjectSummary> {
  const res = await fetch(`${API_BASE}/projects/${projectId}`);
  if (!res.ok) throw new Error(`Failed to fetch project: ${res.statusText}`);
  return res.json();
}

export async function deleteProject(projectId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${projectId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete project: ${res.statusText}`);
}

export async function getArrangement(projectId: string): Promise<Arrangement> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/arrangement`);
  if (!res.ok) throw new Error(`Failed to fetch arrangement: ${res.statusText}`);
  return res.json();
}

export async function updateArrangement(projectId: string, arrangement: Arrangement): Promise<Arrangement> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/arrangement`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(arrangement),
  });
  if (!res.ok) throw new Error(`Failed to update arrangement: ${res.statusText}`);
  return res.json();
}

export async function getStemUrls(projectId: string): Promise<Record<string, string>> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/stems`);
  if (!res.ok) throw new Error(`Failed to fetch stems: ${res.statusText}`);
  const data = await res.json();
  return data.stems;
}

export async function getExportUrl(
  projectId: string,
  format: "midi" | "kar" | "musicxml" | "lead-musicxml" | "pdf" | "lead-pdf" | "lyrics-txt" | "lyrics-lrc" | "lyrics-elrc"
): Promise<{ download_url: string; filename: string }> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/export/${format}`);
  if (!res.ok) throw new Error(`Failed to fetch export URL: ${res.statusText}`);
  return res.json();
}

export function subscribeToProjectEvents(
  projectId: string,
  onMessage: (event: JobProgressEvent) => void,
  onError?: (err: any) => void
): () => void {
  const eventSource = new EventSource(`${API_BASE}/projects/${projectId}/events`);

  eventSource.onmessage = (e) => {
    try {
      const data: JobProgressEvent = JSON.parse(e.data);
      onMessage(data);
    } catch (err) {
      // Ignore non-json heartbeats
    }
  };

  eventSource.onerror = (e) => {
    if (onError) onError(e);
  };

  return () => {
    eventSource.close();
  };
}

