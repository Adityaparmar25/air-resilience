"use client";

import React from "react";
import { EvidenceBreakdown, EvidenceSignal } from "../types/api";

interface EvidenceGridProps {
  evidence: EvidenceBreakdown;
  participatingStations?: string[];
  participatingReports?: string[];
}

export default function EvidenceGrid({
  evidence,
  participatingStations = [],
  participatingReports = [],
}: EvidenceGridProps) {
  const getSignal = (key: string, defaultWeight: number): EvidenceSignal => {
    if (evidence?.signals && evidence.signals[key]) {
      return evidence.signals[key];
    }
    const legacy = (evidence as unknown as Record<string, unknown>)?.[key] as EvidenceSignal | undefined;
    if (legacy) return legacy;
    return {
      source: key,
      timestamp: new Date().toISOString(),
      location: { lat: 0, lng: 0 },
      signal_type: "unspecified",
      score: null,
      weight: defaultWeight,
      availability: false,
      metadata: {},
    };
  };

  const signalList = [
    {
      key: "ground_sensor",
      label: "Ground Sensor",
      signal: getSignal("ground_sensor", 0.30),
      icon: (
        <svg className="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
        </svg>
      ),
    },
    {
      key: "satellite",
      label: "Sentinel-5P Satellite",
      signal: getSignal("satellite", 0.20),
      icon: (
        <svg className="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    {
      key: "citizen_report",
      label: "Citizen Report",
      signal: getSignal("citizen_report", 0.15),
      icon: (
        <svg className="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
        </svg>
      ),
    },
    {
      key: "weather",
      label: "IMD Weather",
      signal: getSignal("weather", 0.15),
      icon: (
        <svg className="w-4 h-4 text-teal-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10l-2 1m0 0l-2-1m2 1v2.5M20 7l-2 1m2-1l-2-1m2 1v2.5M14 4l-2-1-2 1M4 7l2-1M4 7l2 1M4 7v2.5M12 21a9 9 0 110-18 9 9 0 010 18z" />
        </svg>
      ),
    },
    {
      key: "fire",
      label: "NASA FIRMS Fire",
      signal: getSignal("fire", 0.20),
      icon: (
        <svg className="w-4 h-4 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
        </svg>
      ),
    },
  ];

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
          <span>Multimodal Evidence Matrix</span>
          <span className="text-[10px] text-emerald-400 font-mono bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/40">
            D-006 / D-007
          </span>
        </h4>
        <span className="text-[11px] text-slate-500 italic">
          Missing data excluded from denominator, never penalized as 0.0
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {signalList.map(({ key, label, signal, icon }) => {
          const isAvailable = signal.availability && signal.score !== null;
          const weightPercent = Math.round(signal.weight * 100);

          return (
            <div
              key={key}
              className={`p-3 rounded-xl border transition-all ${
                isAvailable
                  ? "bg-slate-900/90 border-slate-700/80 shadow-md shadow-black/30"
                  : "bg-slate-950/50 border-slate-800/50 opacity-60"
              }`}
            >
              {/* Card Header */}
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1.5">
                  <div className="p-1 rounded-lg bg-slate-800/80">{icon}</div>
                  <span className="text-xs font-bold text-slate-200 truncate" title={label}>
                    {label}
                  </span>
                </div>
                <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded">
                  {weightPercent}%
                </span>
              </div>

              {/* Status & Score */}
              <div className="mt-2 space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">Status:</span>
                  {isAvailable ? (
                    <span className="text-emerald-400 font-semibold text-[11px] flex items-center gap-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                      Available
                    </span>
                  ) : (
                    <span className="text-slate-500 font-medium text-[11px]">Unavailable</span>
                  )}
                </div>

                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">Signal Score:</span>
                  <span className="font-mono font-bold text-slate-200">
                    {isAvailable && signal.score !== null ? signal.score.toFixed(2) : "—"}
                  </span>
                </div>

                {isAvailable && signal.score !== null && (
                  <div className="flex items-center justify-between text-xs pt-1 border-t border-slate-800">
                    <span className="text-slate-400">Contribution:</span>
                    <span className="font-mono font-semibold text-emerald-400">
                      +{(signal.weight * signal.score).toFixed(3)}
                    </span>
                  </div>
                )}
              </div>

              {/* Metadata Notes */}
              {signal.metadata && (
                <div className="mt-2 text-[10px] text-slate-400 line-clamp-2 leading-relaxed bg-slate-950/60 p-1.5 rounded border border-slate-800/40">
                  {signal.metadata.claim_statement ? String(signal.metadata.claim_statement) : signal.metadata.notice ? String(signal.metadata.notice) : signal.metadata.reason ? String(signal.metadata.reason) : signal.signal_type}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Corroboration Context footer */}
      {(participatingStations.length > 0 || participatingReports.length > 0) && (
        <div className="flex flex-wrap items-center gap-3 pt-2 text-xs text-slate-400 border-t border-slate-800/60">
          {participatingStations.length > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-slate-300">Ground Sensors:</span>
              <span className="font-mono text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-900/40">
                {participatingStations.join(", ")}
              </span>
            </div>
          )}
          {participatingReports.length > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-slate-300">Citizen Reports:</span>
              <span className="font-mono text-indigo-400 bg-indigo-950/40 px-2 py-0.5 rounded border border-indigo-900/40">
                {participatingReports.join(", ")}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
