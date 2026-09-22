"use client";

import React, { useState, useEffect } from "react";
import Header from "../components/Header";
import AnalysisCard from "../components/AnalysisCard";
import EventDetailModal from "../components/EventDetailModal";
import IncidentDetailModal from "../components/IncidentDetailModal";
import {
  createIncident,
  detectPollutionEvents,
  fetchEvents,
  fetchIncidents,
  submitCitizenReport,
  analyzeCitizenReport,
} from "../lib/api";
import {
  CitizenReport,
  Incident,
  IncidentPriority,
  IncidentStatus,
  PollutionEvent,
} from "../types/api";

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
  const [activeTab, setActiveTab] = useState<"citizen" | "events" | "authority">("citizen");

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

  // Incidents State (Phase 3C Authority Workflow)
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [selectedIncident, setSelectedIncident] = useState<Incident | null>(null);
  const [incidentStatusFilter, setIncidentStatusFilter] = useState<string>("ALL");
  const [incidentPriorityFilter, setIncidentPriorityFilter] = useState<string>("ALL");
  const [isEscalating, setIsEscalating] = useState(false);

  // Load events & incidents
  const loadData = async () => {
    try {
      const [eventsData, incidentsData] = await Promise.all([
        fetchEvents(),
        fetchIncidents(),
      ]);
      setEvents(eventsData);
      setIncidents(incidentsData);
    } catch (err) {
      console.error("Failed to load data:", err);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 6000);
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
      const report = await submitCitizenReport({
        latitude: selectedLocation.lat,
        longitude: selectedLocation.lon,
        description,
        sample_image: selectedSample || undefined,
        image: customFile || undefined,
      });

      setCurrentReport(report);
      setIsSubmitting(false);

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
      await loadData();

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
      await loadData();
    } catch (err: unknown) {
      console.error(err);
    } finally {
      setIsDetectingEvents(false);
    }
  };

  // Escalate Event to Incident
  const handleEscalateEvent = async (eventId: string) => {
    setIsEscalating(true);
    setErrorMessage(null);
    try {
      const inc = await createIncident({
        event_id: eventId,
        actor: "Authority_Commander",
        initial_notes: "Escalated from live Events Feed for response dispatch.",
      });
      await loadData();
      setSelectedEvent(null);
      setSelectedIncident(inc);
      setActiveTab("authority");
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setIsEscalating(false);
    }
  };

  const filteredEvents = events.filter((ev) => {
    if (eventsFilter === "ALL") return true;
    return ev.evidence_status === eventsFilter || ev.status === eventsFilter;
  });

  const filteredIncidents = incidents.filter((inc) => {
    if (incidentStatusFilter !== "ALL" && inc.status !== incidentStatusFilter) {
      return false;
    }
    if (
      incidentPriorityFilter !== "ALL" &&
      inc.priority !== incidentPriorityFilter
    ) {
      return false;
    }
    return true;
  });

  const activeIncidentsCount = incidents.filter(
    (i) =>
      i.status === "ALERTED" ||
      i.status === "ASSIGNED" ||
      i.status === "ACKNOWLEDGED" ||
      i.status === "INVESTIGATING"
  ).length;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-emerald-500 selection:text-black">
      {/* Navigation Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        eventCount={events.length}
        incidentCount={activeIncidentsCount}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 space-y-6">
        {/* Error Notification */}
        {errorMessage && (
          <div className="bg-rose-950/70 border border-rose-800 text-rose-200 px-4 py-3 rounded-xl flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <svg
                className="w-4 h-4 text-rose-400 shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span>{errorMessage}</span>
            </div>
            <button
              onClick={() => setErrorMessage(null)}
              className="text-rose-400 hover:text-white cursor-pointer"
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
                      Phase 3B/3C Ingestion
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

            {filteredEvents.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredEvents.map((ev) => (
                  <div
                    key={ev.event_id}
                    className="group bg-slate-900/90 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 shadow-lg shadow-black/20 hover:shadow-emerald-950/20 transition-all flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-3">
                        <span className="font-mono text-[10px] text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                          {ev.location.cell_id}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              ev.evidence_status === "HIGH_CONFIDENCE"
                                ? "bg-rose-950 text-rose-300 border border-rose-800/60"
                                : ev.evidence_status === "CORROBORATED"
                                ? "bg-amber-950 text-amber-300 border border-amber-800/60"
                                : "bg-sky-950 text-sky-300 border border-sky-800/60"
                            }`}
                          >
                            {ev.evidence_status}
                          </span>
                        </div>
                      </div>

                      <h3
                        onClick={() => setSelectedEvent(ev)}
                        className="text-sm font-extrabold text-white group-hover:text-emerald-300 transition-colors cursor-pointer"
                      >
                        {ev.probable_source || "Unspecified Emission"}
                      </h3>
                      <p className="text-xs text-slate-400 mt-1 line-clamp-2 leading-relaxed">
                        {ev.evidence?.explanation_text}
                      </p>

                      {/* Evidence coverage pill */}
                      <div className="mt-3 flex items-center gap-2 text-[11px] text-slate-400">
                        <span>Coverage:</span>
                        <span className="font-mono text-emerald-400 font-semibold bg-slate-950 px-1.5 py-0.5 rounded border border-slate-800">
                          {ev.evidence_coverage?.available_count || 0}/5 Sources
                        </span>
                        {ev.forecast?.available && (
                          <span className="font-mono text-teal-400 bg-teal-950/40 px-1.5 py-0.5 rounded border border-teal-900/40">
                            +24h: {ev.forecast.forecast_24h?.toFixed(0)} ug/m³
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="mt-5 pt-3 border-t border-slate-800/80 flex items-center justify-between gap-2">
                      <button
                        onClick={() => setSelectedEvent(ev)}
                        className="text-xs text-slate-300 hover:text-white flex items-center gap-1 font-semibold cursor-pointer"
                      >
                        Inspect Breakdown &rarr;
                      </button>

                      <button
                        onClick={() => handleEscalateEvent(ev.event_id)}
                        disabled={isEscalating}
                        className="px-2.5 py-1 rounded-lg bg-rose-950 hover:bg-rose-900 border border-rose-800/80 text-rose-300 text-[11px] font-bold transition-all cursor-pointer"
                      >
                        Escalate Incident
                      </button>
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
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB 3: AUTHORITY COMMAND CENTER (PHASE 3C) */}
        {/* ========================================================================= */}
        {activeTab === "authority" && (
          <div className="space-y-6">
            {/* Top Metrics Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-slate-900/80 p-4 rounded-xl border border-slate-800">
                <span className="text-[11px] text-slate-400 block font-semibold">Total Incidents</span>
                <span className="text-2xl font-extrabold text-white font-mono">{incidents.length}</span>
              </div>
              <div className="bg-slate-900/80 p-4 rounded-xl border border-slate-800">
                <span className="text-[11px] text-slate-400 block font-semibold">Active Responding</span>
                <span className="text-2xl font-extrabold text-rose-400 font-mono">{activeIncidentsCount}</span>
              </div>
              <div className="bg-slate-900/80 p-4 rounded-xl border border-slate-800">
                <span className="text-[11px] text-slate-400 block font-semibold">Under Investigation</span>
                <span className="text-2xl font-extrabold text-amber-400 font-mono">
                  {incidents.filter((i) => i.status === "INVESTIGATING").length}
                </span>
              </div>
              <div className="bg-slate-900/80 p-4 rounded-xl border border-slate-800">
                <span className="text-[11px] text-slate-400 block font-semibold">Resolved</span>
                <span className="text-2xl font-extrabold text-emerald-400 font-mono">
                  {incidents.filter((i) => i.status === "RESOLVED").length}
                </span>
              </div>
            </div>

            {/* Filter Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 bg-slate-900/80 p-4 rounded-2xl border border-slate-800">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-400">Status:</span>
                {(["ALL", "ALERTED", "ASSIGNED", "ACKNOWLEDGED", "INVESTIGATING", "RESOLVED", "DISMISSED"] as const).map(
                  (statusOpt) => (
                    <button
                      key={statusOpt}
                      onClick={() => setIncidentStatusFilter(statusOpt)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                        incidentStatusFilter === statusOpt
                          ? "bg-slate-700 text-white"
                          : "bg-slate-950 text-slate-400 hover:text-white"
                      }`}
                    >
                      {statusOpt}
                    </button>
                  )
                )}
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-slate-400">Priority:</span>
                {(["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).map((pri) => (
                  <button
                    key={pri}
                    onClick={() => setIncidentPriorityFilter(pri)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                      incidentPriorityFilter === pri
                        ? "bg-slate-700 text-white"
                        : "bg-slate-950 text-slate-400 hover:text-white"
                    }`}
                  >
                    {pri}
                  </button>
                ))}
              </div>
            </div>

            {/* Incidents Grid */}
            {filteredIncidents.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredIncidents.map((inc) => (
                  <div
                    key={inc.incident_id}
                    onClick={() => setSelectedIncident(inc)}
                    className="bg-slate-900/90 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 shadow-lg shadow-black/20 transition-all cursor-pointer flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className="font-mono text-xs font-bold text-slate-300">
                          {inc.incident_id}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                              inc.priority === "CRITICAL"
                                ? "bg-rose-950 text-rose-300 border-rose-800"
                                : inc.priority === "HIGH"
                                ? "bg-amber-950 text-amber-300 border-amber-800"
                                : "bg-sky-950 text-sky-300 border-sky-800"
                            }`}
                          >
                            {inc.priority}
                          </span>
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                              inc.status === "ALERTED"
                                ? "bg-rose-950 text-rose-300 border-rose-800"
                                : inc.status === "ASSIGNED"
                                ? "bg-amber-950 text-amber-300 border-amber-800"
                                : inc.status === "INVESTIGATING"
                                ? "bg-teal-950 text-teal-300 border-teal-800"
                                : inc.status === "RESOLVED"
                                ? "bg-emerald-950 text-emerald-300 border-emerald-800"
                                : "bg-slate-800 text-slate-400 border-slate-700"
                            }`}
                          >
                            {inc.status}
                          </span>
                        </div>
                      </div>

                      <h3 className="text-sm font-extrabold text-white">
                        {inc.probable_source || "Corroborated Incident"}
                      </h3>
                      <div className="text-[11px] text-slate-400 mt-1">
                        Location: {inc.location.lat.toFixed(4)}, {inc.location.lng.toFixed(4)}
                      </div>

                      {/* Evidence coverage */}
                      <div className="mt-3 flex items-center justify-between text-xs bg-slate-950/60 p-2 rounded-lg border border-slate-800">
                        <span className="text-slate-400">Evidence Coverage:</span>
                        <span className="font-mono font-bold text-emerald-400">
                          {inc.evidence_coverage?.available_count || 0}/5 Sources
                        </span>
                      </div>

                      {/* Forecast trend */}
                      {inc.forecast?.available && (
                        <div className="mt-2 text-xs text-slate-400 flex items-center justify-between bg-slate-950/40 p-2 rounded-lg border border-slate-800/80">
                          <span>+24h PM2.5 Projection:</span>
                          <span className="font-mono font-semibold text-teal-300">
                            {inc.forecast.forecast_24h?.toFixed(0)} ug/m³
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-slate-400">
                      <div>
                        {inc.assigned_to ? (
                          <span className="text-slate-300 font-medium">
                            {inc.assigned_to}
                          </span>
                        ) : (
                          <span className="text-slate-500 italic">Unassigned</span>
                        )}
                      </div>
                      <span className="text-[11px] text-slate-500">
                        {new Date(inc.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-slate-900/30 border border-dashed border-slate-800 rounded-2xl p-12 text-center space-y-3">
                <div className="h-12 w-12 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-500 mx-auto">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                  </svg>
                </div>
                <h4 className="text-sm font-semibold text-slate-300">
                  No Authority Incidents Logged Yet
                </h4>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  Events can be escalated into authority incidents from the Events feed, or automatically alerted when minimum evidence diversity is achieved.
                </p>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Deep Event Inspection Modal */}
      <EventDetailModal
        event={selectedEvent}
        onClose={() => setSelectedEvent(null)}
        onEscalateToIncident={handleEscalateEvent}
      />

      {/* Authority Incident Detail Modal */}
      <IncidentDetailModal
        incident={selectedIncident}
        onClose={() => setSelectedIncident(null)}
        onRefresh={loadData}
      />
    </div>
  );
}
