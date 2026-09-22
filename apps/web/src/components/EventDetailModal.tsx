"use client";

import React from "react";
import { PollutionEvent } from "../types/api";
import FusionScoreMeter from "./FusionScoreMeter";
import EvidenceGrid from "./EvidenceGrid";

interface EventDetailModalProps {
  event: PollutionEvent | null;
  onClose: () => void;
}

export default function EventDetailModal({ event, onClose }: EventDetailModalProps) {
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
                Cell: {event.cell.cell_id}
              </span>
              {event.needs_human_review && (
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950 text-amber-300 border border-amber-800/60">
                  Human Review Required
                </span>
              )}
            </div>
            <h2 className="text-xl font-extrabold text-white tracking-tight flex items-center gap-2">
              <span>{event.probable_source || "Corroborated Pollution Event"}</span>
              <span className="text-sm font-normal text-slate-400">
                ({event.cell.center_lat.toFixed(4)}, {event.cell.center_lon.toFixed(4)})
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
              score={event.fusion_score}
              status={event.status}
              severity={event.severity}
              size="lg"
            />
          </div>

          <div className="md:col-span-2 space-y-3 flex flex-col justify-center">
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div>
                <span className="text-slate-400 block mb-0.5">Detection Window</span>
                <span className="font-mono text-slate-200">
                  {new Date(event.timestamp_start).toLocaleTimeString()} — {new Date(event.timestamp_latest).toLocaleTimeString()}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Confidence</span>
                <span className="font-mono font-bold text-emerald-400">
                  {(event.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">Spatial Extent</span>
                <span className="text-slate-200">
                  Radius: {event.cell.radius_km} km
                </span>
              </div>
              <div>
                <span className="text-slate-400 block mb-0.5">State Machine</span>
                <span className="font-mono font-semibold text-cyan-400">
                  {event.status}
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
                {event.explanation || "Corroborated across multiple operational observation sources."}
              </p>
            </div>
          </div>
        </div>

        {/* Evidence Breakdown Matrix */}
        <div className="space-y-2">
          <EvidenceGrid
            evidence={event.evidence_breakdown}
            participatingStations={event.participating_station_ids}
            participatingReports={event.participating_report_ids}
          />
        </div>

        {/* Scientific & Legal Advisory Footer */}
        <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 text-[11px] text-slate-400 flex items-start gap-2">
          <svg className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <span className="font-semibold text-slate-300">Phase 3B Boundary Adherence:</span> Scores are calculated exclusively by the backend fusion service using verified ground anomalies and multimodal visual features. In accordance with platform governance, this automated signal does not impute legal liability or specify individual proprietary entities.
          </div>
        </div>
      </div>
    </div>
  );
}
