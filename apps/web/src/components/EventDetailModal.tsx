"use client";

import React from "react";
import { PollutionEvent } from "../types/api";
import FusionScoreMeter from "./FusionScoreMeter";
import EvidenceGrid from "./EvidenceGrid";

interface EventDetailModalProps {
  event: PollutionEvent | null;
  onClose: () => void;
  onEscalateToIncident?: (eventId: string) => void;
}

export default function EventDetailModal({
  event,
  onClose,
  onEscalateToIncident,
}: EventDetailModalProps) {
  if (!event) return null;

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
              <span className="font-mono text-xs text-slate-400">ID: {event.event_id}</span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300">
                Cell: {event.location?.cell_id || "N/A"}
              </span>
              {event.human_verification_required && (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950 text-amber-300 border border-amber-800/60">
                  Human Review Required
                </span>
              )}
            </div>
            <h2 className="text-xl font-extrabold text-white tracking-tight flex items-center gap-2">
              <span>{event.probable_source || "Corroborated Pollution Event"}</span>
              <span className="text-sm font-normal text-slate-400">
                ({event.location?.lat?.toFixed(4) ?? 0}, {event.location?.lng?.toFixed(4) ?? 0})
              </span>
            </h2>
          </div>

          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-all"
            aria-label="Close"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Top Summary: Score Meter + Event Meta */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-slate-950/60 p-4 rounded-xl border border-slate-800">
          <div className="flex items-center justify-center border-b md:border-b-0 md:border-r border-slate-800 pb-4 md:pb-0 md:pr-4">
            <FusionScoreMeter
              score={event.evidence?.fusion_score ?? 0}
              status={event.status}
              severity={event.severity}
              size="lg"
            />
          </div>

          <div className="md:col-span-2 space-y-3 flex flex-col justify-center">
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <span className="text-slate-400 block mb-0.5">Detection Timestamp</span>
                <span className="font-mono text-slate-200">
                  {event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "Recent"}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Fusion Confidence</span>
                <span className="font-mono font-bold text-emerald-400">
                  {((event.evidence?.fusion_score ?? 0) * 100).toFixed(0)}%
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Evidence Status</span>
                <span className="font-mono text-cyan-400">
                  {event.evidence_status || "CORROBORATED"}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Operational Lifecycle</span>
                <span className="font-mono font-semibold text-emerald-400">
                  {event.operational_status || event.status}
                </span>
              </div>
            </div>

            {/* Explanation card */}
            <div className="bg-slate-900/90 p-3 rounded-lg border border-slate-800">
              <h4 className="text-xs font-bold text-slate-200 mb-1 flex items-center gap-1.5">
                <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Why Was This Event Created?
              </h4>
              <p className="text-xs text-slate-300 leading-relaxed font-sans">
                {event.evidence?.explanation_text || "Corroborated across multiple operational observation sources."}
              </p>
            </div>
          </div>
        </div>

        {/* Forecast Preview Card */}
        {event.forecast && (
          <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                <span>Forecast Context</span>
                <span className="text-[10px] text-teal-400 font-mono bg-teal-950/60 px-1.5 py-0.5 rounded border border-teal-800/40">
                  {event.forecast.provider_name || "Baseline"}
                </span>
              </h4>
              <span className="text-[10px] text-slate-500">
                Hourly PM2.5 Projection (D-008: non-fabricated bounds)
              </span>
            </div>
            {event.forecast.available ? (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-xs">
                <div className="bg-slate-900 p-2 rounded-lg border border-slate-800">
                  <span className="text-[11px] text-slate-400 block">Current PM2.5</span>
                  <span className="font-mono font-bold text-slate-200">
                    {event.forecast.current_pm25?.toFixed(1) || "—"} ug/m³
                  </span>
                </div>
                <div className="bg-slate-900 p-2 rounded-lg border border-slate-800">
                  <span className="text-[11px] text-slate-400 block">+6h Forecast</span>
                  <span className="font-mono font-bold text-teal-300">
                    {event.forecast.forecast_6h?.toFixed(1) || "—"} ug/m³
                  </span>
                </div>
                <div className="bg-slate-900 p-2 rounded-lg border border-slate-800">
                  <span className="text-[11px] text-slate-400 block">+12h Forecast</span>
                  <span className="font-mono font-bold text-teal-300">
                    {event.forecast.forecast_12h?.toFixed(1) || "—"} ug/m³
                  </span>
                </div>
                <div className="bg-slate-900 p-2 rounded-lg border border-slate-800">
                  <span className="text-[11px] text-slate-400 block">+24h Forecast</span>
                  <span className="font-mono font-bold text-amber-300">
                    {event.forecast.forecast_24h?.toFixed(1) || "—"} ug/m³
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-xs text-slate-500 italic">
                Forecast unavailable: {event.forecast.reason || "No monitoring series available."}
              </div>
            )}
          </div>
        )}

        {/* Evidence Breakdown Matrix */}
        <div className="space-y-2">
          <EvidenceGrid
            evidence={event.evidence}
            participatingStations={event.station_ids}
            participatingReports={event.report_ids}
          />
        </div>

        {/* Escalate to Incident Action */}
        {onEscalateToIncident && (
          <div className="flex justify-end pt-2">
            <button
              type="button"
              onClick={() => onEscalateToIncident(event.event_id)}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-rose-700 via-rose-600 to-amber-600 hover:from-rose-600 hover:to-amber-500 text-white text-xs font-bold shadow-lg shadow-rose-900/30 transition-all cursor-pointer"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              Escalate to Authority Incident (Phase 3C)
            </button>
          </div>
        )}

        {/* Scientific & Legal Advisory Footer */}
        <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-[11px] text-slate-400 flex items-start gap-2">
          <svg className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <span className="font-semibold text-slate-300">Phase 3C Governance:</span> Operational alerting requires minimum evidence diversity (D-017). FIRMS thermal anomalies represent detected heat signatures only. Atmospheric columns are never presented as surface PM2.5.
          </div>
        </div>
      </div>
    </div>
  );
}
