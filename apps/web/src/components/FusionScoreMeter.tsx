"use client";

import React from "react";
import { EventStatus, EventSeverity } from "../types/api";

interface FusionScoreMeterProps {
  score: number;
  status: EventStatus;
  severity: EventSeverity;
  size?: "sm" | "md" | "lg";
}

export default function FusionScoreMeter({
  score,
  status,
  severity,
  size = "md",
}: FusionScoreMeterProps) {
  // Score is between 0.0 and 1.0
  const clampedScore = Math.max(0, Math.min(1, score));
  const percentage = Math.round(clampedScore * 100);

  // SVG dimensions
  const dimensions = size === "sm" ? 90 : size === "lg" ? 160 : 120;
  const strokeWidth = size === "sm" ? 8 : size === "lg" ? 14 : 10;
  const radius = (dimensions - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - clampedScore * circumference;

  const getStatusColor = () => {
    switch (status) {
      case "HIGH_CONFIDENCE":
        return {
          stroke: "stroke-rose-500",
          text: "text-rose-400",
          bg: "bg-rose-950/40 border-rose-500/30",
          label: "High Confidence",
        };
      case "CORROBORATED":
        return {
          stroke: "stroke-amber-500",
          text: "text-amber-400",
          bg: "bg-amber-950/40 border-amber-500/30",
          label: "Corroborated",
        };
      case "POSSIBLE":
        return {
          stroke: "stroke-sky-500",
          text: "text-sky-400",
          bg: "bg-sky-950/40 border-sky-500/30",
          label: "Possible Event",
        };
      default:
        return {
          stroke: "stroke-slate-500",
          text: "text-slate-400",
          bg: "bg-slate-900 border-slate-700",
          label: "False Positive / Low",
        };
    }
  };

  const statusConfig = getStatusColor();

  return (
    <div className="flex flex-col items-center justify-center p-3">
      <div className="relative flex items-center justify-center" style={{ width: dimensions, height: dimensions }}>
        <svg
          className="transform -rotate-90"
          width={dimensions}
          height={dimensions}
        >
          {/* Background circle */}
          <circle
            cx={dimensions / 2}
            cy={dimensions / 2}
            r={radius}
            stroke="currentColor"
            strokeWidth={strokeWidth}
            className="text-slate-800"
            fill="transparent"
          />
          {/* Progress circle */}
          <circle
            cx={dimensions / 2}
            cy={dimensions / 2}
            r={radius}
            stroke="currentColor"
            strokeWidth={strokeWidth}
            className={`${statusConfig.stroke} transition-all duration-1000 ease-out`}
            fill="transparent"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
          />
        </svg>

        {/* Center label */}
        <div className="absolute flex flex-col items-center justify-center text-center">
          <span className={`font-extrabold tracking-tight ${statusConfig.text} ${
            size === "sm" ? "text-lg" : size === "lg" ? "text-3xl" : "text-2xl"
          }`}>
            {score.toFixed(2)}
          </span>
          <span className="text-[10px] text-slate-400 uppercase tracking-widest font-semibold">
            Score
          </span>
        </div>
      </div>

      <div className="mt-2 flex items-center gap-1.5">
        <span className={`px-2 py-0.5 rounded-md text-[11px] font-semibold border ${statusConfig.bg} ${statusConfig.text}`}>
          {statusConfig.label}
        </span>
        <span className="px-1.5 py-0.5 rounded-md text-[10px] font-mono font-medium bg-slate-800 text-slate-300">
          Sev: {severity}
        </span>
      </div>
    </div>
  );
}
