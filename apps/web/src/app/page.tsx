"use client";

import React, { useState, useEffect } from "react";
import Header from "../components/Header";
import AnalysisCard from "../components/AnalysisCard";
import FusionScoreMeter from "../components/FusionScoreMeter";
import EventDetailModal from "../components/EventDetailModal";
import {
  submitCitizenReport,
  analyzeCitizenReport,
  detectPollutionEvents,
  fetchEvents,
} from "../lib/api";
import { CitizenReport, PollutionEvent, EventStatus } from "../types/api";

const NCR_LOCATIONS = [
  { name: "Anand Vihar, Delhi", lat: 28.6469, lon: 77.3160, station: "DL001" },
  { name: "Sector 62, Noida", lat: 28.6258, lon: 77.3648, station: "UP001" },
  { name: "Punjabi Bagh, Delhi", lat: 28.6710, lon: 77.1280, station: "DL002" },
  { name: "Manesar, Gurugram", lat: 28.3515, lon: 76.9428, station: "HR001" },
];

const SAMPLE_IMAGES = [
  {
    id: "industrial_smoke",
    title: "Industrial Smoke Plume",
    subtitle: "Dense particulate emissions",
    category: "Industrial",
  },
  {
    id: "crop_burning",
    title: "Crop Residue Burning",
    subtitle: "Open agricultural fire & haze",
    category: "Agricultural",
  },
  {
    id: "clear_sky",
    title: "Clear Sky Baseline",
    subtitle: "No visible particulate plumes",
    category: "Baseline",
  },
];

export default function Home() {
  const [activeTab, setActiveTab] = useState<"citizen" | "events">("citizen");

  // Form State
  const [selectedLocation, setSelectedLocation] = useState(NCR_LOCATIONS[0]);
  const [description, setDescription] = useState(
    "Heavy dark smoke visible above commercial/industrial zone with noticeable odor."
  );
  const [selectedSample, setSelectedSample] = useState<string>("industrial_smoke");
  const [customFile, setCustomFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  // Workflow State
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isCorroborating, setIsCorroborating] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [currentReport, setCurrentReport] = useState<CitizenReport | null>(null);

  // Events State
  const [events, setEvents] = useState<PollutionEvent[]>([]);
  const [eventsFilter, setEventsFilter] = useState<string>("ALL");
  const [selectedEvent, setSelectedEvent] = useState<PollutionEvent | null>(null);
  const [isDetectingEvents, setIsDetectingEvents] = useState(false);

  // Load events
  const loadEvents = async () => {
    try {
      const data = await fetchEvents();
      setEvents(data);
    } catch (err) {
      console.error("Failed to load events:", err);
    }
  };

  useEffect(() => {
    loadEvents();
    const interval = setInterval(loadEvents, 8000);
    return () => clearInterval(interval);
  }, []);

  const handleCustomFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setCustomFile(file);
      setSelectedSample("");
      setPreviewUrl(URL.createObjectURL(file));
    }
  };

  const handleSelectSample = (sampleId: string) => {
    setSelectedSample(sampleId);
    setCustomFile(null);
    setPreviewUrl(null);
  };

  // Submit and Analyze
  const handleSubmitAndAnalyze = async () => {
    setIsSubmitting(true);
    setIsAnalyzing(false);
    setErrorMessage(null);

    try {
      // 1. Submit report
      const report = await submitCitizenReport({
        latitude: selectedLocation.lat,
        longitude: selectedLocation.lon,
        description,
        sample_image: selectedSample || undefined,
        image: customFile || undefined,
      });

      setCurrentReport(report);
      setIsSubmitting(false);

      // 2. Trigger Gemini multimodal analysis
      setIsAnalyzing(true);
      const analyzed = await analyzeCitizenReport(report.id);
      setCurrentReport(analyzed);
      setIsAnalyzing(false);
    } catch (err: unknown) {
      setIsSubmitting(false);
      setIsAnalyzing(false);
      setErrorMessage(err instanceof Error ? err.message : String(err));
    }
  };

  // Corroborate report with ground stations to generate event
  const handleCorroborate = async () => {
    if (!currentReport) return;
    setIsCorroborating(true);
    setErrorMessage(null);

    try {
      const res = await detectPollutionEvents({
        report_id: currentReport.id,
        station_id: selectedLocation.station,
        force_corroboration: true,
      });

      setIsCorroborating(false);
      await loadEvents();

      if (res.events && res.events.length > 0) {
        setSelectedEvent(res.events[0]);
        setActiveTab("events");
      }
    } catch (err: unknown) {
      setIsCorroborating(false);
      setErrorMessage(err instanceof Error ? err.message : String(err));
    }
  };

  const handleRunEventDetection = async () => {
    setIsDetectingEvents(true);
    try {
      await detectPollutionEvents({ force_corroboration: true });
      await loadEvents();
    } catch (err: unknown) {
      console.error(err);
    } finally {
      setIsDetectingEvents(false);
    }
  };

  const filteredEvents = events.filter((ev) => {
    if (eventsFilter === "ALL") return true;
    return ev.status === eventsFilter;
  });

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-emerald-500 selection:text-black">
      {/* Navigation Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        eventCount={events.length}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 space-y-6">
        {/* Error Notification */}
        {errorMessage && (
          <div className="bg-rose-950/70 border border-rose-800 text-rose-200 px-4 py-3 rounded-xl flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-rose-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{errorMessage}</span>
            </div>
            <button
              onClick={() => setErrorMessage(null)}
              className="text-rose-400 hover:text-white"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 1: CITIZEN OBSERVATION STUDIO */}
        {/* ========================================================================= */}
        {activeTab === "citizen" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Column: Input Panel */}
            <div className="lg:col-span-6 space-y-5">
              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 shadow-xl shadow-black/30 space-y-5">
                <div>
                  <h2 className="text-base font-extrabold text-white tracking-tight flex items-center gap-2">
                    <span>Submit Ground Observation</span>
                    <span className="text-[10px] bg-emerald-950 text-emerald-400 font-mono px-2 py-0.5 rounded border border-emerald-800/40">
                      Phase 3B Ingestion
                    </span>
                  </h2>
                  <p className="text-xs text-slate-400 mt-1">
                    Upload visual evidence or select a calibrated test scenario to initiate multimodal AI verification.
                  </p>
                </div>

                {/* Delhi-NCR Location Selector */}
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Observation Location (Delhi-NCR Hotspots)
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    {NCR_LOCATIONS.map((loc) => {
                      const isSelected = selectedLocation.name === loc.name;
                      return (
                        <button
                          key={loc.name}
                          type="button"
                          onClick={() => setSelectedLocation(loc)}
                          className={`p-2.5 rounded-xl text-left border transition-all text-xs cursor-pointer ${
                            isSelected
                              ? "bg-emerald-950/60 border-emerald-500/60 text-emerald-300 shadow-md shadow-emerald-950/30 ring-1 ring-emerald-500/30"
                              : "bg-slate-950/50 border-slate-800 text-slate-300 hover:border-slate-700"
                          }`}
                        >
                          <div className="font-semibold text-slate-100">{loc.name}</div>
                          <div className="text-[10px] font-mono text-slate-400 mt-0.5">
                            Sensor: {loc.station} &bull; {loc.lat.toFixed(3)}, {loc.lon.toFixed(3)}
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Visual Evidence Selection */}
                <div className="space-y-2">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Visual Evidence Source
                  </label>

                  {/* Sample Scenarios */}
                  <div className="grid grid-cols-3 gap-2">
                    {SAMPLE_IMAGES.map((sample) => {
                      const isSelected = selectedSample === sample.id;
                      return (
                        <button
                          key={sample.id}
                          type="button"
                          onClick={() => handleSelectSample(sample.id)}
                          className={`p-2 rounded-xl text-left border transition-all cursor-pointer ${
                            isSelected
                              ? "bg-indigo-950/60 border-indigo-500 text-indigo-300 ring-1 ring-indigo-500/40"
                              : "bg-slate-950/50 border-slate-800 text-slate-400 hover:border-slate-700"
                          }`}
                        >
                          <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-400 block">
                            {sample.category}
                          </span>
                          <span className="text-xs font-semibold text-slate-200 block truncate">
                            {sample.title}
                          </span>
                        </button>
                      );
                    })}
                  </div>

                  {/* Custom File Upload */}
                  <div className="mt-2">
                    <label className="block text-[11px] text-slate-400 mb-1">
                      Or Upload Custom Visual Observation:
                    </label>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleCustomFileChange}
                      className="block w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-emerald-400 hover:file:bg-slate-700 cursor-pointer bg-slate-950/60 p-2 rounded-xl border border-slate-800"
                    />
                  </div>

                  {/* Image Preview if custom */}
                  {previewUrl && (
                    <div className="mt-2 rounded-xl overflow-hidden border border-slate-800 h-36 bg-black flex items-center justify-center">
                      <img
                        src={previewUrl}
                        alt="Preview"
                        className="h-full w-full object-cover"
                      />
                    </div>
                  )}
                </div>

                {/* Description */}
                <div className="space-y-1.5">
                  <label className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Field Description & Notes
                  </label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={2}
                    className="w-full bg-slate-950/80 border border-slate-800 rounded-xl p-3 text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                    placeholder="Enter visual observations..."
                  />
                </div>

                {/* Submit and Analyze Trigger */}
                <button
                  type="button"
                  onClick={handleSubmitAndAnalyze}
                  disabled={isSubmitting || isAnalyzing}
                  className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-gradient-to-r from-emerald-600 via-teal-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white text-xs font-bold shadow-lg shadow-emerald-600/30 transition-all disabled:opacity-50 cursor-pointer"
                >
                  {isSubmitting ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Registering Observation...
                    </>
                  ) : isAnalyzing ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Gemini Multimodal Inspection in Progress...
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                      </svg>
                      Analyze with Gemini Multimodal Vision
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Right Column: Multimodal Analysis Result */}
            <div className="lg:col-span-6 space-y-5">
              {currentReport && currentReport.analysis ? (
                <div className="space-y-4 animate-in fade-in slide-in-from-right-4 duration-300">
                  <AnalysisCard
                    analysis={currentReport.analysis}
                    onCorroborate={handleCorroborate}
                    isCorroborating={isCorroborating}
                  />

                  {/* Report Metadata Badge */}
                  <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
                    <div>
                      Report ID: <span className="font-mono text-slate-300">{currentReport.id}</span>
                    </div>
                    <div>
                      Target Station: <span className="font-mono text-emerald-400">{selectedLocation.station}</span>
                    </div>
                  </div>
                </div>
              ) : isAnalyzing ? (
                <div className="h-full min-h-[380px] bg-slate-900/40 border border-slate-800 rounded-2xl flex flex-col items-center justify-center p-8 text-center space-y-4">
                  <div className="w-12 h-12 border-4 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin" />
                  <div>
                    <h4 className="text-sm font-bold text-slate-200">Executing Structured Gemini Vision</h4>
                    <p className="text-xs text-slate-400 mt-1 max-w-sm">
                      Detecting particulate smoke plumes, flame presence, and visual intensities without hallucinated PM2.5 measurements...
                    </p>
                  </div>
                </div>
              ) : (
                <div className="h-full min-h-[380px] bg-slate-900/30 border border-dashed border-slate-800 rounded-2xl flex flex-col items-center justify-center p-8 text-center space-y-3">
                  <div className="h-12 w-12 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-500">
                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <h4 className="text-sm font-semibold text-slate-400">
                    Awaiting Ground Observation
                  </h4>
                  <p className="text-xs text-slate-500 max-w-xs leading-relaxed">
                    Select a test scenario or upload field imagery on the left, then trigger analysis to view Gemini&apos;s structured visual evidence.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 2: ACTIVE POLLUTION EVENTS & FUSION FEED */}
        {/* ========================================================================= */}
        {activeTab === "events" && (
          <div className="space-y-6">
            {/* Top Bar: Controls & Filters */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-slate-900/80 p-4 rounded-2xl border border-slate-800">
              <div>
                <h2 className="text-base font-extrabold text-white tracking-tight flex items-center gap-2">
                  <span>Pollution Events Feed</span>
                  <span className="text-[10px] bg-cyan-950 text-cyan-400 font-mono px-2 py-0.5 rounded border border-cyan-800/40">
                    Corroborated Engine
                  </span>
                </h2>
                <p className="text-xs text-slate-400">
                  Multimodal events classified via D-006 evidence weights and D-007 missing data handling.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {/* Status Filters */}
                {(["ALL", "HIGH_CONFIDENCE", "CORROBORATED", "POSSIBLE"] as const).map((filter) => (
                  <button
                    key={filter}
                    onClick={() => setEventsFilter(filter)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                      eventsFilter === filter
                        ? "bg-slate-700 text-white border border-slate-600"
                        : "bg-slate-950 text-slate-400 hover:text-white border border-slate-800"
                    }`}
                  >
                    {filter.replace("_", " ")}
                  </button>
                ))}

                {/* Force Detect Trigger */}
                <button
                  onClick={handleRunEventDetection}
                  disabled={isDetectingEvents}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-950 border border-emerald-700/60 text-emerald-300 text-xs font-semibold hover:bg-emerald-900 transition-all cursor-pointer"
                >
                  <svg className={`w-3.5 h-3.5 ${isDetectingEvents ? "animate-spin" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Run Spatial Fusion
                </button>
              </div>
            </div>

            {/* Events Grid */}
            {filteredEvents.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredEvents.map((ev) => (
                  <div
                    key={ev.event_id}
                    onClick={() => setSelectedEvent(ev)}
                    className="group bg-slate-900/90 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 shadow-lg shadow-black/20 hover:shadow-emerald-950/20 transition-all cursor-pointer flex flex-col justify-between"
                  >
                    <div>
                      {/* Top Badges */}
                      <div className="flex items-center justify-between gap-2 mb-3">
                        <span className="font-mono text-[10px] text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                          {ev.cell.cell_id}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              ev.status === "HIGH_CONFIDENCE"
                                ? "bg-rose-950 text-rose-300 border border-rose-800/60"
                                : ev.status === "CORROBORATED"
                                ? "bg-amber-950 text-amber-300 border border-amber-800/60"
                                : "bg-sky-950 text-sky-300 border border-sky-800/60"
                            }`}
                          >
                            {ev.status}
                          </span>
                        </div>
                      </div>

                      {/* Source & Description */}
                      <h3 className="text-sm font-extrabold text-white group-hover:text-emerald-300 transition-colors">
                        {ev.probable_source || "Unspecified Emission"}
                      </h3>
                      <p className="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                        {ev.explanation}
                      </p>
                    </div>

                    {/* Bottom Meta & Score */}
                    <div className="mt-5 pt-3 border-t border-slate-800/80 flex items-center justify-between">
                      <div className="text-[11px] text-slate-400">
                        <div>Sensors: {ev.participating_station_ids.length}</div>
                        <div>Reports: {ev.participating_report_ids.length}</div>
                      </div>

                      <div className="flex items-center gap-2">
                        <div className="text-right">
                          <span className="text-[10px] text-slate-500 uppercase block font-semibold">
                            Fusion Score
                          </span>
                          <span className="font-mono text-sm font-bold text-emerald-400">
                            {ev.fusion_score.toFixed(2)}
                          </span>
                        </div>
                        <div className="p-1.5 rounded-lg bg-slate-800 text-slate-400 group-hover:text-white">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                          </svg>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-slate-900/30 border border-dashed border-slate-800 rounded-2xl p-12 text-center space-y-3">
                <div className="h-12 w-12 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-500 mx-auto">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                </div>
                <h4 className="text-sm font-semibold text-slate-300">
                  No Active Pollution Events Detected Yet
                </h4>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  Submit a citizen report in the Vision Studio or click &quot;Run Spatial Fusion&quot; to correlate ground sensors with operational observation grids.
                </p>
                <button
                  onClick={handleRunEventDetection}
                  className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all cursor-pointer shadow-lg shadow-emerald-600/30"
                >
                  Trigger Corroboration Engine
                </button>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Deep Event Inspection Modal */}
      <EventDetailModal
        event={selectedEvent}
        onClose={() => setSelectedEvent(null)}
      />
    </div>
  );
}
