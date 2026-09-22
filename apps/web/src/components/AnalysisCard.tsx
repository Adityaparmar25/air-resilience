"use client";

import React from "react";
import { CitizenImageAnalysis } from "../types/api";

interface AnalysisCardProps {
  analysis: CitizenImageAnalysis;
  onCorroborate?: () => void;
  isCorroborating?: boolean;
}

export default function AnalysisCard({
  analysis,
  onCorroborate,
  isCorroborating = false,
}: AnalysisCardProps) {
  const confidencePercent = Math.round(analysis.confidence * 100);

  return (
    <div className="bg-slate-900/90 rounded-2xl border border-slate-800 p-5 shadow-xl shadow-black/40 space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-lg bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              Gemini Vision Multimodal Analysis
              <span className="text-[10px] bg-indigo-950 text-indigo-400 font-mono px-2 py-0.5 rounded border border-indigo-800/40">
                Structured Schema
              </span>
            </h3>
            <p className="text-xs text-slate-400">
              Visual feature classification under strict non-hallucination guardrails
            </p>
          </div>
        </div>

        {/* Confidence Meter */}
        <div className="flex items-center gap-2 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
          <span className="text-xs text-slate-400">Confidence:</span>
          <span className="text-sm font-mono font-bold text-emerald-400">
            {confidencePercent}%
          </span>
        </div>
      </div>

      {/* Primary Classification Badges */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
        <div className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800">
          <span className="text-[11px] text-slate-400 block mb-1">Event Classification</span>
          <span className="text-xs font-bold text-slate-200 capitalize flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-indigo-400"></span>
            {analysis.event_type.replace("_", " ")}
          </span>
        </div>

        <div className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800">
          <span className="text-[11px] text-slate-400 block mb-1">Visible Smoke</span>
          <div className="flex items-center gap-1.5">
            {analysis.visible_smoke ? (
              <span className="text-xs font-bold text-rose-400 flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-rose-500"></span>
                Detected ({analysis.smoke_intensity || "present"})
              </span>
            ) : (
              <span className="text-xs font-medium text-slate-400">Not Detected</span>
            )}
          </div>
        </div>

        <div className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800">
          <span className="text-[11px] text-slate-400 block mb-1">Visible Flames</span>
          <div className="flex items-center gap-1.5">
            {analysis.visible_flames ? (
              <span className="text-xs font-bold text-amber-400 flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse"></span>
                Active Flames
              </span>
            ) : (
              <span className="text-xs font-medium text-slate-400">None Visible</span>
            )}
          </div>
        </div>

        <div className="p-2.5 rounded-xl bg-slate-950/70 border border-slate-800">
          <span className="text-[11px] text-slate-400 block mb-1">Review Protocol</span>
          <div className="flex items-center gap-1.5">
            {analysis.needs_human_verification ? (
              <span className="text-xs font-semibold text-amber-300 bg-amber-950/60 px-1.5 py-0.5 rounded border border-amber-800/40">
                Advisory Review
              </span>
            ) : (
              <span className="text-xs font-medium text-emerald-400">Direct Corroboration</span>
            )}
          </div>
        </div>
      </div>

      {/* Visual Evidence Items */}
      <div className="space-y-1.5">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
          Structured Visual Evidence
        </h4>
        <div className="space-y-1">
          {analysis.visual_evidence.map((evidence, idx) => (
            <div
              key={idx}
              className="flex items-start gap-2 text-xs text-slate-300 bg-slate-950/50 p-2 rounded-lg border border-slate-800/60"
            >
              <svg className="w-3.5 h-3.5 text-emerald-400 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              <span>{evidence}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Uncertainties (if any) */}
      {analysis.uncertain_fields && analysis.uncertain_fields.length > 0 && (
        <div className="space-y-1.5">
          <h4 className="text-xs font-bold uppercase tracking-wider text-amber-400/90 flex items-center gap-1">
            <svg className="w-3.5 h-3.5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            Explicit Visual Uncertainties
          </h4>
          <div className="space-y-1">
            {analysis.uncertain_fields.map((item, idx) => (
              <div
                key={idx}
                className="text-xs text-amber-200/80 bg-amber-950/30 p-2 rounded-lg border border-amber-900/30"
              >
                &bull; {item}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Guardrail Policy Attestation */}
      <div className="p-2.5 rounded-xl bg-emerald-950/20 border border-emerald-800/30 text-[11px] text-emerald-300/80 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-emerald-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>
            <strong>Guardrails Enforced:</strong> No synthetic PM2.5 generated; non-accusatory; visual evidence only.
          </span>
        </div>
      </div>

      {/* Action to trigger evidence fusion / corroboration */}
      {onCorroborate && (
        <button
          onClick={onCorroborate}
          disabled={isCorroborating}
          className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-gradient-to-r from-emerald-600 via-teal-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white text-xs font-bold shadow-lg shadow-emerald-600/30 transition-all disabled:opacity-50 cursor-pointer"
        >
          {isCorroborating ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Corroborating with Ground Sensors & Fusion Engine...
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Corroborate & Trigger Evidence Fusion Engine
            </>
          )}
        </button>
      )}
    </div>
  );
}
