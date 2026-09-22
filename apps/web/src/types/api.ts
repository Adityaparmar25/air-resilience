export type EventStatus = "POSSIBLE" | "CORROBORATED" | "HIGH_CONFIDENCE" | "FALSE_POSITIVE";
export type EventSeverity = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface CitizenImageAnalysis {
  visible_smoke: boolean;
  visible_flames: boolean;
  event_type: "smoke_plume" | "fire" | "dust" | "haze" | "clear" | "other";
  smoke_intensity?: "none" | "light" | "moderate" | "dense" | null;
  visual_evidence: string[];
  uncertain_fields: string[];
  needs_human_verification: boolean;
  confidence: number;
}

export interface CitizenReport {
  id: string;
  timestamp: string;
  latitude: number;
  longitude: number;
  description?: string | null;
  image_url?: string | null;
  image_metadata?: Record<string, unknown> | null;
  analysis?: CitizenImageAnalysis | null;
}

export interface EvidenceSignal {
  name: string;
  weight: number;
  score: number | null;
  available: boolean;
  weighted_contribution?: number;
  notes?: string;
}

export interface EvidenceBreakdown {
  ground_anomaly: EvidenceSignal;
  satellite: EvidenceSignal;
  citizen_reports: EvidenceSignal;
  weather_context: EvidenceSignal;
  fire_radiative_power: EvidenceSignal;
}

export interface LocationCell {
  cell_id: string;
  center_lat: number;
  center_lon: number;
  radius_km: number;
}

export interface PollutionEvent {
  event_id: string;
  cell: LocationCell;
  timestamp_start: string;
  timestamp_latest: string;
  status: EventStatus;
  severity: EventSeverity;
  fusion_score: number;
  confidence: number;
  probable_source?: string | null;
  explanation?: string | null;
  evidence_breakdown: EvidenceBreakdown;
  participating_station_ids: string[];
  participating_report_ids: string[];
  active: boolean;
  needs_human_review: boolean;
}
