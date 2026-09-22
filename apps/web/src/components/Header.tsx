"use client";

import React, { useEffect, useState } from "react";
import { checkApiHealth } from "../lib/api";

interface HeaderProps {
  activeTab: "citizen" | "events" | "authority";
  setActiveTab: (tab: "citizen" | "events" | "authority") => void;
  eventCount: number;
  incidentCount: number;
}

export default function Header({
  activeTab,
  setActiveTab,
  eventCount,
  incidentCount,
}: HeaderProps) {
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      const res = await checkApiHealth();
      if (mounted) {
        setApiOnline(res.status === "ok" || res.status === "healthy");
      }
    };
    check();
    const interval = setInterval(check, 10000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <header className="sticky top-0 z-50 backdrop-blur-md bg-slate-950/80 border-b border-slate-800/80 px-6 py-4 shadow-lg shadow-black/20">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Brand & Platform Identity */}
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-emerald-500 via-teal-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-emerald-500/20 ring-1 ring-emerald-400/30">
            <svg
              className="w-6 h-6 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 00-9.78 2.096A4.001 4.001 0 003 15z"
              />
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg tracking-tight text-white">
                AIR-RESILIENCE
              </span>
              <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-500/30">
                Phase 3C
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Authority Operations &bull; Multimodal Evidence &bull; Forecast Context
            </p>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center bg-slate-900/90 p-1.5 rounded-xl border border-slate-800">
          <button
            onClick={() => setActiveTab("citizen")}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTab === "citizen"
                ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-md shadow-emerald-600/30"
                : "text-slate-400 hover:text-white hover:bg-slate-800/50"
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Citizen Vision
          </button>

          <button
            onClick={() => setActiveTab("events")}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTab === "events"
                ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-md shadow-emerald-600/30"
                : "text-slate-400 hover:text-white hover:bg-slate-800/50"
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            Events Feed
            {eventCount > 0 && (
              <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                {eventCount}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab("authority")}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              activeTab === "authority"
                ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-md shadow-emerald-600/30"
                : "text-slate-400 hover:text-white hover:bg-slate-800/50"
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            Authority Command Center
            {incidentCount > 0 && (
              <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                {incidentCount}
              </span>
            )}
          </button>
        </div>

        {/* System Backend Health Status */}
        <div className="flex items-center gap-2 bg-slate-900/60 px-3 py-1.5 rounded-lg border border-slate-800 text-xs">
          <div
            className={`h-2 w-2 rounded-full animate-pulse ${
              apiOnline === true
                ? "bg-emerald-400 ring-4 ring-emerald-500/20"
                : apiOnline === false
                ? "bg-rose-500 ring-4 ring-rose-500/20"
                : "bg-amber-400"
            }`}
          />
          <span className="text-slate-300">
            Backend:{" "}
            {apiOnline === true ? (
              <span className="text-emerald-400 font-medium">FastAPI Online</span>
            ) : apiOnline === false ? (
              <span className="text-rose-400 font-medium">Offline</span>
            ) : (
              <span className="text-slate-400">Connecting...</span>
            )}
          </span>
        </div>
      </div>
    </header>
  );
}
