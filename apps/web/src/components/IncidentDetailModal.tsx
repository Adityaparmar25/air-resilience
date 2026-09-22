"use client";

import React, { useState, useEffect } from "react";
import { AuditRecord, Incident, IncidentStatus } from "../types/api";
import {
  acknowledgeIncident,
  addIncidentNote,
  assignIncident,
  dismissIncident,
  fetchIncidentAudit,
  investigateIncident,
  resolveIncident,
} from "../lib/api";

interface IncidentDetailModalProps {
  incident: Incident | null;
  onClose: () => void;
  onRefresh: () => void;
}

export default function IncidentDetailModal({
  incident,
  onClose,
  onRefresh,
}: IncidentDetailModalProps) {
  const [auditLogs, setAuditLogs] = useState<AuditRecord[]>([]);
  const [isLoadingAudit, setIsLoadingAudit] = useState(false);

  // Action form state
  const [actionType, setActionType] = useState<
    "assign" | "resolve" | "dismiss" | "note" | null
  >(null);
  const [assignedTo, setAssignedTo] = useState("");
  const [assignedTeam, setAssignedTeam] = useState("Delhi Enforcement Squad");
  const [actionNotes, setActionNotes] = useState("");
  const [resolutionSummary, setResolutionSummary] = useState("");
  const [dismissalReason, setDismissalReason] = useState("");
  const [actorName, setActorName] = useState("Command_Officer_1");
  const [isSubmittingAction, setIsSubmittingAction] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadAudit = async (incId: string) => {
    setIsLoadingAudit(true);
    try {
      const records = await fetchIncidentAudit(incId);
      setAuditLogs(records);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoadingAudit(false);
    }
  };

  useEffect(() => {
    if (incident) {
      loadAudit(incident.incident_id);
    }
  }, [incident]);

  if (!incident) return null;

  const handleAssign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignedTo.trim()) return;
    setIsSubmittingAction(true);
    setActionError(null);
    try {
      await assignIncident(incident.incident_id, {
        assigned_to: assignedTo.trim(),
        assigned_team: assignedTeam.trim() || undefined,
        actor: actorName.trim(),
        notes: actionNotes.trim() || undefined,
      });
      setActionType(null);
      setActionNotes("");
      onRefresh();
      await loadAudit(incident.incident_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSubmittingAction(false);
    }
  };

  const handleAcknowledge = async () => {
    setIsSubmittingAction(true);
    setActionError(null);
    try {
      await acknowledgeIncident(incident.incident_id, {
        actor: actorName.trim(),
        notes: "Field unit acknowledged dispatch instructions.",
      });
      onRefresh();
      await loadAudit(incident.incident_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSubmittingAction(false);
    }
  };

  const handleInvestigate = async () => {
    setIsSubmittingAction(true);
    setActionError(null);
    try {
      await investigateIncident(incident.incident_id, {
        actor: actorName.trim(),
        notes: "Responders arrived on site; active inspection in progress.",
      });
      onRefresh();
      await loadAudit(incident.incident_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSubmittingAction(false);
    }
  };

  const handleResolve = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resolutionSummary.trim()) return;
    setIsSubmittingAction(true);
    setActionError(null);
    try {
      await resolveIncident(incident.incident_id, {
        actor: actorName.trim(),
        resolution_summary: resolutionSummary.trim(),
        notes: actionNotes.trim() || undefined,
      });
      setActionType(null);
      setResolutionSummary("");
      setActionNotes("");
      onRefresh();
      await loadAudit(incident.incident_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSubmittingAction(false);
    }
  };

  const handleDismiss = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dismissalReason.trim()) return;
    setIsSubmittingAction(true);
    setActionError(null);
    try {
      await dismissIncident(incident.incident_id, {
        actor: actorName.trim(),
        dismissal_reason: dismissalReason.trim(),
        notes: actionNotes.trim() || undefined,
      });
      setActionType(null);
      setDismissalReason("");
      setActionNotes("");
      onRefresh();
      await loadAudit(incident.incident_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSubmittingAction(false);
    }
  };

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!actionNotes.trim()) return;
    setIsSubmittingAction(true);
    setActionError(null);
    try {
      await addIncidentNote(incident.incident_id, {
        actor: actorName.trim(),
        content: actionNotes.trim(),
      });
      setActionType(null);
      setActionNotes("");
      onRefresh();
      await loadAudit(incident.incident_id);
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsSubmittingAction(false);
    }
  };

  const getPriorityBadge = (p: string) => {
    switch (p) {
      case "CRITICAL":
        return "bg-rose-950 text-rose-300 border-rose-800";
      case "HIGH":
        return "bg-amber-950 text-amber-300 border-amber-800";
      case "MEDIUM":
        return "bg-sky-950 text-sky-300 border-sky-800";
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  const getStatusBadge = (s: IncidentStatus) => {
    switch (s) {
      case "ALERTED":
        return "bg-rose-950 text-rose-300 border-rose-800";
      case "ASSIGNED":
        return "bg-amber-950 text-amber-300 border-amber-800";
      case "ACKNOWLEDGED":
        return "bg-indigo-950 text-indigo-300 border-indigo-800";
      case "INVESTIGATING":
        return "bg-teal-950 text-teal-300 border-teal-800";
      case "RESOLVED":
        return "bg-emerald-950 text-emerald-300 border-emerald-800";
      case "DISMISSED":
        return "bg-slate-800 text-slate-400 border-slate-700";
      default:
        return "bg-sky-950 text-sky-300 border-sky-800";
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        className="bg-slate-900 border border-slate-700/80 rounded-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto shadow-2xl shadow-emerald-950/40 p-6 space-y-6"
        role="dialog"
        aria-modal="true"
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4 border-b border-slate-800 pb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono text-xs text-slate-400">
                {incident.incident_id}
              </span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getPriorityBadge(
                  incident.priority
                )}`}
              >
                {incident.priority} PRIORITY
              </span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getStatusBadge(
                  incident.status
                )}`}
              >
                {incident.status}
              </span>
            </div>
            <h2 className="text-xl font-extrabold text-white tracking-tight flex items-center gap-2">
              <span>{incident.probable_source || "Corroborated Incident"}</span>
              <span className="text-sm font-normal text-slate-400">
                ({incident.location.lat.toFixed(4)},{" "}
                {incident.location.lng.toFixed(4)})
              </span>
            </h2>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-all cursor-pointer"
            aria-label="Close"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Action Error */}
        {actionError && (
          <div className="bg-rose-950/80 border border-rose-800 text-rose-200 px-3 py-2 rounded-xl text-xs flex justify-between items-center">
            <span>{actionError}</span>
            <button
              onClick={() => setActionError(null)}
              className="text-rose-400 font-bold ml-2"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Incident Metadata Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-slate-950/60 p-4 rounded-xl border border-slate-800 text-xs">
          <div>
            <span className="text-slate-400 block mb-0.5">Assigned Responder</span>
            <span className="font-semibold text-slate-200">
              {incident.assigned_to || "Unassigned"}
            </span>
            <span className="text-[11px] text-slate-400 block">
              {incident.assigned_team || "No Unit"}
            </span>
          </div>

          <div>
            <span className="text-slate-400 block mb-0.5">Originating Event</span>
            <span className="font-mono text-emerald-400">
              {incident.event_id}
            </span>
            <span className="text-[11px] text-slate-400 block">
              Evidence Status: {incident.evidence_status}
            </span>
          </div>

          <div>
            <span className="text-slate-400 block mb-0.5">Created Timestamp</span>
            <span className="text-slate-200">
              {new Date(incident.created_at).toLocaleString()}
            </span>
          </div>
        </div>

        {/* Evidence Coverage & Minimum Diversity (D-017) */}
        <div className="bg-slate-950/50 p-4 rounded-xl border border-slate-800 space-y-2.5">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <span>Evidence Coverage & Diversity</span>
              <span className="text-[10px] text-emerald-400 font-mono bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/40">
                D-017
              </span>
            </h4>
            <span className="text-xs font-mono font-bold text-slate-300">
              Coverage: {incident.evidence_coverage?.available_count || 0}/5 (
              {((incident.evidence_coverage?.coverage_ratio || 0) * 100).toFixed(0)}%)
            </span>
          </div>

          <div className="flex flex-wrap gap-2 text-xs">
            <span
              className={`px-2.5 py-1 rounded-lg border flex items-center gap-1.5 ${
                incident.evidence_coverage?.ground_sensor
                  ? "bg-emerald-950/60 text-emerald-300 border-emerald-700/60"
                  : "bg-slate-900 text-slate-500 border-slate-800"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  incident.evidence_coverage?.ground_sensor
                    ? "bg-emerald-400"
                    : "bg-slate-600"
                }`}
              />
              Ground Sensor
            </span>

            <span
              className={`px-2.5 py-1 rounded-lg border flex items-center gap-1.5 ${
                incident.evidence_coverage?.citizen_report
                  ? "bg-emerald-950/60 text-emerald-300 border-emerald-700/60"
                  : "bg-slate-900 text-slate-500 border-slate-800"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  incident.evidence_coverage?.citizen_report
                    ? "bg-emerald-400"
                    : "bg-slate-600"
                }`}
              />
              Citizen Report
            </span>

            <span
              className={`px-2.5 py-1 rounded-lg border flex items-center gap-1.5 ${
                incident.evidence_coverage?.weather
                  ? "bg-emerald-950/60 text-emerald-300 border-emerald-700/60"
                  : "bg-slate-900 text-slate-500 border-slate-800"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  incident.evidence_coverage?.weather
                    ? "bg-emerald-400"
                    : "bg-slate-600"
                }`}
              />
              IMD Weather
            </span>

            <span
              className={`px-2.5 py-1 rounded-lg border flex items-center gap-1.5 ${
                incident.evidence_coverage?.satellite
                  ? "bg-emerald-950/60 text-emerald-300 border-emerald-700/60"
                  : "bg-slate-900 text-slate-500 border-slate-800"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  incident.evidence_coverage?.satellite
                    ? "bg-emerald-400"
                    : "bg-slate-600"
                }`}
              />
              Sentinel-5P Satellite
            </span>

            <span
              className={`px-2.5 py-1 rounded-lg border flex items-center gap-1.5 ${
                incident.evidence_coverage?.fire
                  ? "bg-emerald-950/60 text-emerald-300 border-emerald-700/60"
                  : "bg-slate-900 text-slate-500 border-slate-800"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  incident.evidence_coverage?.fire
                    ? "bg-emerald-400"
                    : "bg-slate-600"
                }`}
              />
              NASA FIRMS
            </span>
          </div>

          <div className="text-[11px] text-slate-400 italic pt-1">
            {incident.evidence_coverage?.diversity_eligible_for_alert
              ? "Eligible for operational alerting (>= 2 independent corroborating classes available)."
              : "Below minimum evidence diversity threshold; requires human review before automated dispatch."}
          </div>
        </div>

        {/* Forecast Context Card */}
        {incident.forecast && (
          <div className="bg-slate-950/50 p-4 rounded-xl border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <span>PM2.5 Horizon Forecast</span>
                <span className="text-[10px] text-teal-400 font-mono bg-teal-950/60 px-1.5 py-0.5 rounded border border-teal-800/40">
                  {incident.forecast.provider_name || "Baseline"}
                </span>
              </h4>
              <span className="text-[10px] text-slate-500">
                Empirical 95% Confidence Bounds
              </span>
            </div>

            {incident.forecast.available ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-xs">
                <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                  <span className="text-[11px] text-slate-400 block">Current PM2.5</span>
                  <span className="font-mono font-bold text-slate-200">
                    {incident.forecast.current_pm25?.toFixed(1) || "—"} ug/m³
                  </span>
                </div>
                <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                  <span className="text-[11px] text-slate-400 block">+6h Forecast</span>
                  <span className="font-mono font-bold text-teal-300">
                    {incident.forecast.forecast_6h?.toFixed(1) || "—"} ug/m³
                  </span>
                </div>
                <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                  <span className="text-[11px] text-slate-400 block">+12h Forecast</span>
                  <span className="font-mono font-bold text-teal-300">
                    {incident.forecast.forecast_12h?.toFixed(1) || "—"} ug/m³
                  </span>
                </div>
                <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                  <span className="text-[11px] text-slate-400 block">+24h Forecast</span>
                  <span className="font-mono font-bold text-amber-300">
                    {incident.forecast.forecast_24h?.toFixed(1) || "—"} ug/m³
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-xs text-slate-500 italic p-2 bg-slate-900 rounded-lg">
                Forecast unavailable: {incident.forecast.reason || "No monitoring series available."}
              </div>
            )}
          </div>
        )}

        {/* Gemini Explanation & Assessment */}
        {incident.explanation && (
          <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800 space-y-1.5">
            <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
              <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              Multimodal Evidence Synthesis
            </h4>
            <p className="text-xs text-slate-300 leading-relaxed font-sans">
              {incident.explanation}
            </p>
          </div>
        )}

        {/* Resolution or Dismissal Info (if terminal) */}
        {incident.status === "RESOLVED" && incident.resolution_summary && (
          <div className="p-3 bg-emerald-950/30 rounded-xl border border-emerald-800/40 text-xs text-emerald-200">
            <strong className="block text-emerald-400 mb-0.5">Incident Resolved:</strong>
            {incident.resolution_summary}
          </div>
        )}
        {incident.status === "DISMISSED" && incident.dismissal_reason && (
          <div className="p-3 bg-slate-800/40 rounded-xl border border-slate-700 text-xs text-slate-300">
            <strong className="block text-slate-400 mb-0.5">Incident Dismissed:</strong>
            {incident.dismissal_reason}
          </div>
        )}

        {/* Operational Actions Panel */}
        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Operational Actions & Dispatch
            </h4>
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <span>Actor ID:</span>
              <input
                type="text"
                value={actorName}
                onChange={(e) => setActorName(e.target.value)}
                className="bg-slate-900 border border-slate-700 px-2 py-0.5 rounded text-xs text-white font-mono w-32 focus:outline-none"
              />
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-2">
            {(incident.status === "DETECTED" || incident.status === "ALERTED") && (
              <button
                type="button"
                onClick={() => setActionType("assign")}
                className="px-3 py-1.5 rounded-lg bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold transition-all cursor-pointer"
              >
                Assign Response Unit
              </button>
            )}

            {incident.status === "ASSIGNED" && (
              <button
                type="button"
                onClick={handleAcknowledge}
                disabled={isSubmittingAction}
                className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-all cursor-pointer disabled:opacity-50"
              >
                {isSubmittingAction ? "Processing..." : "Acknowledge Incident"}
              </button>
            )}

            {incident.status === "ACKNOWLEDGED" && (
              <button
                type="button"
                onClick={handleInvestigate}
                disabled={isSubmittingAction}
                className="px-3 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-xs font-bold transition-all cursor-pointer disabled:opacity-50"
              >
                {isSubmittingAction ? "Processing..." : "Start Investigation"}
              </button>
            )}

            {incident.status === "INVESTIGATING" && (
              <button
                type="button"
                onClick={() => setActionType("resolve")}
                className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all cursor-pointer"
              >
                Resolve Incident
              </button>
            )}

            {incident.status !== "RESOLVED" && incident.status !== "DISMISSED" && (
              <button
                type="button"
                onClick={() => setActionType("dismiss")}
                className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-all cursor-pointer border border-slate-700"
              >
                Dismiss
              </button>
            )}

            <button
              type="button"
              onClick={() => setActionType("note")}
              className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-all cursor-pointer border border-slate-700 ml-auto"
            >
              + Add Field Note
            </button>
          </div>

          {/* Action Sub-Forms */}
          {actionType === "assign" && (
            <form
              onSubmit={handleAssign}
              className="p-3 bg-slate-900 rounded-lg border border-slate-800 space-y-2 animate-in fade-in duration-150"
            >
              <span className="text-xs font-bold text-slate-200 block">
                Assign Responder & Response Unit
              </span>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  placeholder="Responder Name (e.g. Officer Sharma)"
                  value={assignedTo}
                  onChange={(e) => setAssignedTo(e.target.value)}
                  className="bg-slate-950 border border-slate-800 p-2 rounded text-xs text-white focus:outline-none"
                  required
                />
                <input
                  type="text"
                  placeholder="Team (e.g. East Delhi Patrol)"
                  value={assignedTeam}
                  onChange={(e) => setAssignedTeam(e.target.value)}
                  className="bg-slate-950 border border-slate-800 p-2 rounded text-xs text-white focus:outline-none"
                />
              </div>
              <textarea
                placeholder="Dispatch instructions / notes..."
                value={actionNotes}
                onChange={(e) => setActionNotes(e.target.value)}
                rows={2}
                className="w-full bg-slate-950 border border-slate-800 p-2 rounded text-xs text-white focus:outline-none"
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setActionType(null)}
                  className="px-3 py-1 text-xs text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingAction}
                  className="px-3 py-1 bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold rounded"
                >
                  Confirm Assignment
                </button>
              </div>
            </form>
          )}

          {actionType === "resolve" && (
            <form
              onSubmit={handleResolve}
              className="p-3 bg-slate-900 rounded-lg border border-slate-800 space-y-2 animate-in fade-in duration-150"
            >
              <span className="text-xs font-bold text-emerald-300 block">
                Resolve Incident with Mitigation Summary
              </span>
              <textarea
                placeholder="Detailed mitigation actions taken (e.g. Furnace shut down; water-fog cannons deployed)..."
                value={resolutionSummary}
                onChange={(e) => setResolutionSummary(e.target.value)}
                rows={2}
                className="w-full bg-slate-950 border border-slate-800 p-2 rounded text-xs text-white focus:outline-none"
                required
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setActionType(null)}
                  className="px-3 py-1 text-xs text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingAction}
                  className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded"
                >
                  Confirm Resolution
                </button>
              </div>
            </form>
          )}

          {actionType === "dismiss" && (
            <form
              onSubmit={handleDismiss}
              className="p-3 bg-slate-900 rounded-lg border border-slate-800 space-y-2 animate-in fade-in duration-150"
            >
              <span className="text-xs font-bold text-rose-300 block">
                Dismiss Incident
              </span>
              <textarea
                placeholder="Dismissal justification (e.g. Confirmed permitted steam exhaust; no unpermitted particulate plume)..."
                value={dismissalReason}
                onChange={(e) => setDismissalReason(e.target.value)}
                rows={2}
                className="w-full bg-slate-950 border border-slate-800 p-2 rounded text-xs text-white focus:outline-none"
                required
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setActionType(null)}
                  className="px-3 py-1 text-xs text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingAction}
                  className="px-3 py-1 bg-rose-700 hover:bg-rose-600 text-white text-xs font-bold rounded"
                >
                  Confirm Dismissal
                </button>
              </div>
            </form>
          )}

          {actionType === "note" && (
            <form
              onSubmit={handleAddNote}
              className="p-3 bg-slate-900 rounded-lg border border-slate-800 space-y-2 animate-in fade-in duration-150"
            >
              <span className="text-xs font-bold text-slate-200 block">
                Add Operational Field Note
              </span>
              <textarea
                placeholder="Enter field observation or tactical update..."
                value={actionNotes}
                onChange={(e) => setActionNotes(e.target.value)}
                rows={2}
                className="w-full bg-slate-950 border border-slate-800 p-2 rounded text-xs text-white focus:outline-none"
                required
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setActionType(null)}
                  className="px-3 py-1 text-xs text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingAction}
                  className="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded"
                >
                  Save Note
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Immutable Audit Trail Timeline */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
              <span>Immutable Audit Trail</span>
              <span className="text-[10px] text-indigo-400 font-mono bg-indigo-950/60 px-1.5 py-0.5 rounded border border-indigo-800/40">
                Tamper-Resistant
              </span>
            </h4>
            <span className="text-[10px] text-slate-500">
              {auditLogs.length} logged record(s)
            </span>
          </div>

          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
            {isLoadingAudit ? (
              <div className="text-xs text-slate-500">Loading audit history...</div>
            ) : auditLogs.length > 0 ? (
              auditLogs.map((log) => (
                <div
                  key={log.audit_id}
                  className="bg-slate-950/70 p-2 rounded-lg border border-slate-800/80 text-xs flex items-center justify-between"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] text-slate-400">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                    <span className="font-bold text-slate-200">
                      [{log.action}]
                    </span>
                    <span className="text-slate-400">
                      {log.previous_status || "INIT"} &rarr; {log.new_status}
                    </span>
                  </div>
                  <span className="font-mono text-[11px] text-emerald-400">
                    {log.actor}
                  </span>
                </div>
              ))
            ) : (
              <div className="text-xs text-slate-500 italic">No audit records recorded yet.</div>
            )}
          </div>
        </div>

        {/* Compliance Footer */}
        <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-[11px] text-slate-400">
          <span className="font-semibold text-slate-300">Authority Governance:</span> All transitions are validated server-side. Audit history cannot be altered or deleted.
        </div>
      </div>
    </div>
  );
}
