import {
  AuditRecord,
  CitizenReport,
  CityNode,
  FederatedInferenceRequest,
  FederatedInferenceResponse,
  FederatedRound,
  HistoricalSmogData,
  Incident,
  IncidentNote,
  ModelParams,
  PollutionEvent,
  SystemHealthResponse,
} from "../types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export async function checkApiHealth(): Promise<{ status: string; timestamp: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/health`, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch {
    return { status: "unreachable", timestamp: new Date().toISOString() };
  }
}

export async function fetchSystemHealth(): Promise<SystemHealthResponse> {
  const res = await fetch(`${API_BASE}/api/v1/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch system health: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchHistoricalSmogData(): Promise<HistoricalSmogData> {
  const res = await fetch(`${API_BASE}/api/v1/historical/delhi-smog-2023`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to fetch historical smog data: HTTP ${res.status}`);
  }
  return await res.json();
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

export async function fetchEvents(
  status?: string,
  activeOnly: boolean = false,
  limit: number = 50,
  offset: number = 0
): Promise<PollutionEvent[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (activeOnly) params.set("active_only", "true");
  if (limit) params.set("limit", limit.toString());
  if (offset) params.set("offset", offset.toString());

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

// =============================================================================
// AUTHORITY INCIDENT APIS (PHASE 3C)
// =============================================================================

export async function createIncident(payload: {
  event_id: string;
  priority?: string;
  actor?: string;
  initial_notes?: string;
}): Promise<Incident> {
  const res = await fetch(`${API_BASE}/api/v1/incidents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event_id: payload.event_id,
      priority: payload.priority || null,
      actor: payload.actor || "authority_dispatcher",
      initial_notes: payload.initial_notes || null,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Create incident failed: ${err}`);
  }
  return await res.json();
}

export async function fetchIncidents(
  status?: string,
  priority?: string,
  limit: number = 50,
  offset: number = 0
): Promise<Incident[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (priority) params.set("priority", priority);
  if (limit) params.set("limit", limit.toString());
  if (offset) params.set("offset", offset.toString());

  const query = params.toString() ? `?${params.toString()}` : "";
  const res = await fetch(`${API_BASE}/api/v1/incidents${query}`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch incidents: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchIncidentById(incidentId: string): Promise<Incident> {
  const res = await fetch(`${API_BASE}/api/v1/incidents/${encodeURIComponent(incidentId)}`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch incident ${incidentId}: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function assignIncident(
  incidentId: string,
  payload: {
    assigned_to: string;
    assigned_team?: string;
    actor?: string;
    notes?: string;
  }
): Promise<Incident> {
  const res = await fetch(`${API_BASE}/api/v1/incidents/${encodeURIComponent(incidentId)}/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      assigned_to: payload.assigned_to,
      assigned_team: payload.assigned_team || "Delhi Enforcement Squad",
      actor: payload.actor || "dispatcher_1",
      notes: payload.notes || null,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Assign failed: ${err}`);
  }
  return await res.json();
}

export async function acknowledgeIncident(
  incidentId: string,
  payload: { actor: string; notes?: string }
): Promise<Incident> {
  const res = await fetch(`${API_BASE}/api/v1/incidents/${encodeURIComponent(incidentId)}/acknowledge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload.actor,
      notes: payload.notes || null,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Acknowledge failed: ${err}`);
  }
  return await res.json();
}

export async function investigateIncident(
  incidentId: string,
  payload: { actor: string; notes?: string }
): Promise<Incident> {
  const res = await fetch(`${API_BASE}/api/v1/incidents/${encodeURIComponent(incidentId)}/investigate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload.actor,
      notes: payload.notes || null,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Investigate transition failed: ${err}`);
  }
  return await res.json();
}

export async function resolveIncident(
  incidentId: string,
  payload: { actor: string; resolution_summary: string; notes?: string }
): Promise<Incident> {
  const res = await fetch(`${API_BASE}/api/v1/incidents/${encodeURIComponent(incidentId)}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload.actor,
      resolution_summary: payload.resolution_summary,
      notes: payload.notes || null,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Resolve failed: ${err}`);
  }
  return await res.json();
}

export async function dismissIncident(
  incidentId: string,
  payload: { actor: string; dismissal_reason: string; notes?: string }
): Promise<Incident> {
  const res = await fetch(`${API_BASE}/api/v1/incidents/${encodeURIComponent(incidentId)}/dismiss`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload.actor,
      dismissal_reason: payload.dismissal_reason,
      notes: payload.notes || null,
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Dismiss failed: ${err}`);
  }
  return await res.json();
}

export async function addIncidentNote(
  incidentId: string,
  payload: { actor: string; content: string }
): Promise<IncidentNote> {
  const res = await fetch(`${API_BASE}/api/v1/incidents/${encodeURIComponent(incidentId)}/notes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Add note failed: ${err}`);
  }
  return await res.json();
}

export async function fetchIncidentAudit(incidentId: string): Promise<AuditRecord[]> {
  const res = await fetch(`${API_BASE}/api/v1/incidents/${encodeURIComponent(incidentId)}/audit`, {
    cache: "no-store",
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch audit records: HTTP ${res.status}`);
  }
  return await res.json();
}

// =============================================================================
// FEDERATION NETWORK API
// =============================================================================

export async function fetchFederationNodes(): Promise<CityNode[]> {
  const res = await fetch(`${API_BASE}/api/v1/federation/nodes`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch federation nodes: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchFederationRounds(): Promise<FederatedRound[]> {
  const res = await fetch(`${API_BASE}/api/v1/federation/rounds`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch federation rounds: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function fetchFederationRound(roundId: string): Promise<FederatedRound> {
  const res = await fetch(`${API_BASE}/api/v1/federation/rounds/${encodeURIComponent(roundId)}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch round ${roundId}: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function createFederationRound(payload?: {
  participating_nodes?: string[];
  base_model_version?: string;
}): Promise<FederatedRound> {
  const res = await fetch(`${API_BASE}/api/v1/federation/rounds`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Create round failed: ${err}`);
  }
  return await res.json();
}

export async function trainFederationRound(
  roundId: string,
  payload?: { epochs?: number; learning_rate?: number }
): Promise<FederatedRound> {
  const res = await fetch(`${API_BASE}/api/v1/federation/rounds/${encodeURIComponent(roundId)}/train`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Local training failed: ${err}`);
  }
  return await res.json();
}

export async function aggregateFederationRound(
  roundId: string,
  payload?: { min_required_nodes?: number }
): Promise<FederatedRound> {
  const res = await fetch(`${API_BASE}/api/v1/federation/rounds/${encodeURIComponent(roundId)}/aggregate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Aggregation failed: ${err}`);
  }
  return await res.json();
}

export async function fetchCurrentFederationModel(): Promise<ModelParams> {
  const res = await fetch(`${API_BASE}/api/v1/federation/models/current`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch model: HTTP ${res.status}`);
  }
  return await res.json();
}

export async function runFederationInference(
  payload: FederatedInferenceRequest
): Promise<FederatedInferenceResponse> {
  const res = await fetch(`${API_BASE}/api/v1/federation/infer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Inference failed: ${err}`);
  }
  return await res.json();
}
