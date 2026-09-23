export type EvidenceStatus = "FALSE_POSITIVE" | "POSSIBLE" | "CORROBORATED" | "HIGH_CONFIDENCE";
export type EventStatus = EvidenceStatus;

export type OperationalStatus =
  | "DETECTED"
  | "ALERTED"
  | "ASSIGNED"
  | "ACKNOWLEDGED"
  | "INVESTIGATING"
  | "RESOLVED"
  | "DISMISSED";

export type EventSeverity = "LOW" | "MODERATE" | "HIGH" | "CRITICAL";

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
  source: string;
  timestamp: string;
  location: { lat: number; lng: number };
  signal_type: string;
  score: number | null;
  weight: number;
  availability: boolean;
  metadata?: Record<string, unknown>;
}

export interface EvidenceBreakdown {
  signals: Record<string, EvidenceSignal>;
  fusion_score: number;
  available_weight_sum: number;
  available_sources_count: number;
  corroborating_sources_count: number;
  explanation_text: string;
}

export interface EvidenceCoverage {
  available_sources?: string[];
  missing_sources?: string[];
  coverage_level?: string;
  ground_sensor: boolean;
  citizen_report: boolean;
  satellite: boolean;
  weather: boolean;
  fire: boolean;
  available_count: number;
  total_sources: number;
  coverage_ratio: number;
  diversity_eligible_for_alert: boolean;
}

export interface ForecastContext {
  available: boolean;
  current_pm25?: number | null;
  forecast_6h?: number | null;
  forecast_12h?: number | null;
  forecast_24h?: number | null;
  interval?: { lower_95?: number | null; upper_95?: number | null } | null;
  provider_name?: string;
  model_name?: string;
  reason?: string;
  generated_at?: string;
}

export interface LocationCell {
  lat: number;
  lng: number;
  cell_id: string;
}

export interface PollutionEvent {
  event_id: string;
  timestamp: string;
  location: LocationCell;
  evidence_status: EvidenceStatus;
  operational_status: OperationalStatus;
  status: EventStatus;
  severity: EventSeverity;
  event_type: string;
  evidence: EvidenceBreakdown;
  evidence_coverage: EvidenceCoverage;
  forecast: ForecastContext;
  probable_source?: string | null;
  human_verification_required: boolean;
  report_ids: string[];
  station_ids: string[];
}

export type IncidentPriority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type IncidentStatus = OperationalStatus;

export interface IncidentNote {
  note_id: string;
  actor: string;
  timestamp: string;
  content: string;
}

export interface AuditRecord {
  audit_id: string;
  incident_id: string;
  actor: string;
  action: string;
  previous_status?: IncidentStatus | null;
  new_status?: IncidentStatus | null;
  timestamp: string;
  details?: Record<string, unknown>;
}

export interface Incident {
  incident_id: string;
  event_id: string;
  priority: IncidentPriority;
  status: IncidentStatus;
  assigned_to?: string | null;
  assigned_team?: string | null;
  created_at: string;
  acknowledged_at?: string | null;
  investigating_at?: string | null;
  resolved_at?: string | null;
  dismissed_at?: string | null;
  resolution_summary?: string | null;
  dismissal_reason?: string | null;
  notes: IncidentNote[];
  evidence_status: EvidenceStatus;
  evidence_coverage: EvidenceCoverage;
  location: LocationCell;
  probable_source?: string | null;
  forecast: ForecastContext;
  explanation?: string | null;
}

export type NodeStatus = "ACTIVE" | "OFFLINE" | "TRAINING" | "SYNCED" | "FAILED";
export type RoundStatus = "CREATED" | "TRAINING" | "AGGREGATING" | "COMPLETED" | "FAILED";

export interface CityNode {
  node_id: string;
  region: string;
  state: string;
  country: string;
  schema_version: string;
  model_version: string;
  last_sync: string;
  status: NodeStatus;
  supported_signals: string[];
  metadata?: Record<string, unknown>;
}

export interface ModelParams {
  feature_names: string[];
  weights: number[];
  bias: number;
  model_version: string;
}

export interface ModelUpdate {
  node_id: string;
  round_id: string;
  base_model_version: string;
  sample_count: number;
  update_hash: string;
  model_params: ModelParams;
  training_metrics: Record<string, number>;
  created_at: string;
}

export interface FederatedRound {
  round_id: string;
  started_at: string;
  completed_at?: string | null;
  participating_nodes: string[];
  global_model_version: string;
  aggregation_method: string;
  status: RoundStatus;
  metrics: Record<string, any>;
  node_updates: Record<string, ModelUpdate>;
}

export interface FederatedInferenceRequest {
  node_id?: string;
  use_global_model?: boolean;
  pm25: number;
  pm10?: number;
  no2?: number;
  temperature?: number;
  humidity?: number;
  wind_speed?: number;
  wind_direction?: number;
  hour?: number;
  day_of_week?: number;
}

export interface FederatedInferenceResponse {
  predicted_pm25_next_hour: number;
  predicted_risk_index: number;
  risk_level: string;
  model_version: string;
  model_source: string;
  features_used: Record<string, number>;
}
