import { CitizenReport, PollutionEvent } from "../types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export async function checkApiHealth(): Promise<{ status: string; timestamp: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/health`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    return { status: "unreachable", timestamp: new Date().toISOString() };
  }
}

export async function submitCitizenReport(payload: {
  latitude: number;
  longitude: number;
  description?: string;
  image?: File;
  sample_image?: string;
}): Promise<CitizenReport> {
  const formData = new FormData();
  formData.append("latitude", payload.latitude.toString());
  formData.append("longitude", payload.longitude.toString());
  if (payload.description) {
    formData.append("description", payload.description);
  }
  if (payload.sample_image) {
    formData.append("sample_image", payload.sample_image);
  }
  if (payload.image) {
    formData.append("image", payload.image);
  }

  const res = await fetch(`${API_BASE}/api/v1/reports`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Report submission failed: ${errorText}`);
  }

  return await res.json();
}

export async function analyzeCitizenReport(reportId: string): Promise<CitizenReport> {
  const res = await fetch(`${API_BASE}/api/v1/reports/${encodeURIComponent(reportId)}/analyze`, {
    method: "POST",
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Multimodal analysis failed: ${errorText}`);
  }

  return await res.json();
}

export async function detectPollutionEvents(payload: {
  report_id?: string;
  station_id?: string;
  force_corroboration?: boolean;
}): Promise<{ message: string; events_detected: number; events: PollutionEvent[] }> {
  const res = await fetch(`${API_BASE}/api/v1/events/detect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorText = await res.text();
    throw new Error(`Event detection failed: ${errorText}`);
  }

  return await res.json();
}

export async function fetchEvents(status?: string, activeOnly: boolean = false): Promise<PollutionEvent[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (activeOnly) params.set("active_only", "true");

  const query = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(`${API_BASE}/api/v1/events${query}`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch events: HTTP ${res.status}`);
  }

  return await res.json();
}

export async function fetchEventById(eventId: string): Promise<PollutionEvent> {
  const res = await fetch(`${API_BASE}/api/v1/events/${encodeURIComponent(eventId)}`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch event ${eventId}: HTTP ${res.status}`);
  }

  return await res.json();
}
