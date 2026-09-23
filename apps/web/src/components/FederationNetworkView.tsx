"use client";

import React, { useEffect, useState } from "react";
import {
  aggregateFederationRound,
  createFederationRound,
  fetchCurrentFederationModel,
  fetchFederationNodes,
  fetchFederationRounds,
  runFederationInference,
  trainFederationRound,
} from "../lib/api";
import {
  CityNode,
  FederatedInferenceResponse,
  FederatedRound,
  ModelParams,
} from "../types/api";

export default function FederationNetworkView() {
  const [nodes, setNodes] = useState<CityNode[]>([]);
  const [rounds, setRounds] = useState<FederatedRound[]>([]);
  const [currentModel, setCurrentModel] = useState<ModelParams | null>(null);
  const [loading, setLoading] = useState(true);
  const [roundInProgress, setRoundInProgress] = useState(false);
  const [roundLog, setRoundLog] = useState<string[]>([]);

  // Inference state
  const [inferPm25, setInferPm25] = useState(115.0);
  const [inferPm10, setInferPm10] = useState(210.0);
  const [inferNo2, setInferNo2] = useState(65.0);
  const [inferWindSpeed, setInferWindSpeed] = useState(1.8);
  const [inferResult, setInferResult] = useState<FederatedInferenceResponse | null>(null);
  const [inferLoading, setInferLoading] = useState(false);

  const loadData = async () => {
    try {
      const [n, r, m] = await Promise.all([
        fetchFederationNodes().catch(() => []),
        fetchFederationRounds().catch(() => []),
        fetchCurrentFederationModel().catch(() => null),
      ]);
      setNodes(n);
      setRounds(r);
      setCurrentModel(m);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRunFederatedRound = async () => {
    setRoundInProgress(true);
    setRoundLog(["[1/4] Initializing new federated round across city nodes..."]);
    try {
      // 1. Create round
      const newRound = await createFederationRound({
        participating_nodes: ["delhi", "haryana", "uttar_pradesh"],
      });
      setRoundLog((prev) => [
        ...prev,
        `[2/4] Round ${newRound.round_id} created. Triggering isolated data-local training...`,
      ]);

      // 2. Train round locally
      const trainedRound = await trainFederationRound(newRound.round_id, {
        epochs: 5,
        learning_rate: 0.01,
      });
      setRoundLog((prev) => [
        ...prev,
        `[3/4] Local training complete across ${Object.keys(trainedRound.node_updates).length} nodes. Model updates received.`,
      ]);

      // 3. Aggregate FedAvg
      const aggregatedRound = await aggregateFederationRound(newRound.round_id);
      const newVer = aggregatedRound.metrics?.new_global_version || "v2";
      setRoundLog((prev) => [
        ...prev,
        `[4/4] Sample-weighted FedAvg aggregation complete! Deployed global model: ${newVer}.`,
      ]);

      await loadData();
    } catch (err: any) {
      setRoundLog((prev) => [...prev, `[ERROR] Federation round failed: ${err.message}`]);
    } finally {
      setRoundInProgress(false);
    }
  };

  const handleRunInference = async () => {
    setInferLoading(true);
    try {
      const res = await runFederationInference({
        pm25: inferPm25,
        pm10: inferPm10,
        no2: inferNo2,
        wind_speed: inferWindSpeed,
      });
      setInferResult(res);
    } catch (err) {
      console.error(err);
    } finally {
      setInferLoading(false);
    }
  };

  const latestRound = rounds.length > 0 ? rounds[0] : null;

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Privacy Guarantee Banner */}
      <div className="bg-slate-900/90 border border-cyan-500/40 rounded-2xl p-5 shadow-xl shadow-cyan-950/20 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-96 h-96 bg-cyan-500/5 rounded-full blur-3xl pointer-events-none" />
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="p-2.5 rounded-xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 mt-0.5">
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-bold uppercase tracking-wider text-cyan-400">
                  Data-Local Training with Federated Aggregation (D-018)
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-800/60">
                  Raw local records shared: NO
                </span>
              </div>
              <h2 className="text-lg font-extrabold text-white tracking-tight">
                Cross-Jurisdiction Interoperability Network
              </h2>
              <p className="text-xs text-slate-300 max-w-2xl leading-relaxed mt-1">
                Observations from Delhi, Haryana, and Uttar Pradesh remain strictly confined to each city&apos;s local partition. Only mathematical parameter weights ($W_k, b_k$) and sample counts cross the coordinator boundary.
              </p>
            </div>
          </div>

          <button
            type="button"
            disabled={roundInProgress}
            onClick={handleRunFederatedRound}
            className={`px-5 py-3 rounded-xl font-bold text-xs flex items-center gap-2 transition-all shadow-lg cursor-pointer ${
              roundInProgress
                ? "bg-slate-800 text-slate-500 cursor-not-allowed"
                : "bg-gradient-to-r from-cyan-600 via-blue-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 text-white shadow-cyan-900/30"
            }`}
          >
            {roundInProgress ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Federation Round Running...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Trigger Federated Round #{(rounds.length || 0) + 1}
              </>
            )}
          </button>
        </div>

        {/* Live Step Logs */}
        {roundLog.length > 0 && (
          <div className="mt-4 pt-3 border-t border-slate-800 text-xs font-mono text-cyan-300 space-y-1 bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
            {roundLog.map((log, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className="text-slate-500">&gt;</span>
                <span>{log}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Overview Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
          <span className="text-xs text-slate-400 block mb-1">Global Model Version</span>
          <span className="text-2xl font-mono font-extrabold text-cyan-400">
            {currentModel?.model_version || "v1"}
          </span>
          <span className="text-[10px] text-slate-500 block mt-1">
            FedAvg aggregated weights
          </span>
        </div>

        <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
          <span className="text-xs text-slate-400 block mb-1">Active City Nodes</span>
          <span className="text-2xl font-mono font-extrabold text-white">
            {nodes.length}
          </span>
          <span className="text-[10px] text-slate-500 block mt-1">
            Delhi, Haryana, UP
          </span>
        </div>

        <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
          <span className="text-xs text-slate-400 block mb-1">Total Rounds Executed</span>
          <span className="text-2xl font-mono font-extrabold text-indigo-400">
            {rounds.length}
          </span>
          <span className="text-[10px] text-slate-500 block mt-1">
            Sample-weighted aggregation
          </span>
        </div>

        <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
          <span className="text-xs text-slate-400 block mb-1">Latest Round Status</span>
          <span className="text-2xl font-mono font-extrabold text-emerald-400">
            {latestRound?.status || "READY"}
          </span>
          <span className="text-[10px] text-slate-500 block mt-1">
            {latestRound ? latestRound.round_id : "Awaiting round"}
          </span>
        </div>
      </div>

      {/* Participating City Nodes Grid */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
            <span>Participating Regional City Nodes</span>
            <span className="text-[11px] font-mono text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800/40">
              Canonical Contract (D-019)
            </span>
          </h3>
          <span className="text-xs text-slate-500">
            Isolated local datasets &bull; Zero raw row transmission
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {nodes.map((node) => {
            const update = latestRound?.node_updates?.[node.node_id];
            return (
              <div
                key={node.node_id}
                className="bg-slate-900/80 border border-slate-800 hover:border-slate-700/80 p-5 rounded-2xl transition-all space-y-4 shadow-lg shadow-black/20"
              >
                {/* Node Header */}
                <div className="flex items-start justify-between">
                  <div>
                    <span className="text-[10px] font-mono text-slate-500 uppercase block">
                      Node ID: {node.node_id}
                    </span>
                    <h4 className="text-base font-bold text-white tracking-tight capitalize">
                      {node.node_id.replace("_", " ")}
                    </h4>
                    <span className="text-xs text-slate-400 block mt-0.5">
                      {node.state}, {node.country}
                    </span>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold ${
                      node.status === "SYNCED" || node.status === "ACTIVE"
                        ? "bg-emerald-950 text-emerald-300 border border-emerald-800/50"
                        : "bg-amber-950 text-amber-300 border border-amber-800/50"
                    }`}
                  >
                    {node.status}
                  </span>
                </div>

                {/* Region Description */}
                <p className="text-xs text-slate-400 leading-relaxed bg-slate-950/50 p-2.5 rounded-lg border border-slate-800/60">
                  {node.region}
                </p>

                {/* Node Training Metrics */}
                <div className="grid grid-cols-2 gap-2 text-xs bg-slate-950/70 p-3 rounded-xl border border-slate-800">
                  <div>
                    <span className="text-slate-500 block text-[10px]">Local Partition</span>
                    <span className="font-mono text-slate-300 font-bold">
                      {update ? `${update.sample_count} samples` : "Partitioned"}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-500 block text-[10px]">Deployed Model</span>
                    <span className="font-mono text-cyan-400 font-bold">
                      {node.model_version}
                    </span>
                  </div>
                  {update?.training_metrics && (
                    <>
                      <div>
                        <span className="text-slate-500 block text-[10px]">Local MAE</span>
                        <span className="font-mono text-emerald-400 font-bold">
                          {update.training_metrics.mae} ug/m³
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 block text-[10px]">Local R² Score</span>
                        <span className="font-mono text-indigo-400 font-bold">
                          {update.training_metrics.r2}
                        </span>
                      </div>
                    </>
                  )}
                </div>

                {/* Update Hash Digest */}
                <div className="space-y-1">
                  <span className="text-[10px] text-slate-500 block">Parameter Update Digest</span>
                  <div className="font-mono text-[11px] text-slate-400 bg-slate-950 px-2 py-1 rounded border border-slate-800 truncate">
                    {update?.update_hash ? `SHA256: ${update.update_hash}` : "Awaiting next round"}
                  </div>
                </div>

                {/* Supported Signals */}
                <div className="flex flex-wrap gap-1 pt-1">
                  {node.supported_signals.map((sig) => (
                    <span
                      key={sig}
                      className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300"
                    >
                      {sig}
                    </span>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Mathematical Aggregation Display & Inference Sandbox */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* FedAvg Aggregation Card */}
        <div className="bg-slate-900/80 border border-slate-800 p-6 rounded-2xl space-y-4">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
            <svg className="w-4 h-4 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
            Transparent FedAvg Aggregation Formula
          </h3>

          <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono text-xs text-cyan-300 space-y-2">
            <div className="text-slate-400 font-sans text-xs">
              Server-side sample-weighted parameter aggregation (D-018):
            </div>
            <div className="p-2 bg-slate-900 rounded border border-slate-800 text-center text-sm font-bold text-white">
              W_global = ∑ (n_k / N) × W_k
            </div>
            <div className="text-[11px] text-slate-400 space-y-1 pt-1">
              <div>&bull; n_delhi = 72 samples (36.7% weight)</div>
              <div>&bull; n_haryana = 60 samples (30.6% weight)</div>
              <div>&bull; n_up = 64 samples (32.7% weight)</div>
              <div className="text-emerald-400 font-bold">&bull; N_total = 196 historical observations</div>
            </div>
          </div>

          <div className="text-xs text-slate-400 leading-relaxed space-y-1">
            <p>
              <strong className="text-slate-300">Resilience guarantee:</strong> If an individual city node drops offline or fails to respond, the coordinator aggregates the remaining active nodes without halting the network.
            </p>
          </div>
        </div>

        {/* Federated Risk Inference Sandbox */}
        <div className="bg-slate-900/80 border border-slate-800 p-6 rounded-2xl space-y-4">
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 flex items-center justify-between">
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Next-Hour Federated Risk Inference Sandbox
            </span>
            <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800/40">
              Model: {currentModel?.model_version || "v1"}
            </span>
          </h3>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <label className="text-slate-400 block mb-1">Current PM2.5 (ug/m³)</label>
              <input
                type="number"
                value={inferPm25}
                onChange={(e) => setInferPm25(parseFloat(e.target.value) || 0)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-white font-mono text-xs focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="text-slate-400 block mb-1">PM10 (ug/m³)</label>
              <input
                type="number"
                value={inferPm10}
                onChange={(e) => setInferPm10(parseFloat(e.target.value) || 0)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-white font-mono text-xs focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="text-slate-400 block mb-1">NO2 (ug/m³)</label>
              <input
                type="number"
                value={inferNo2}
                onChange={(e) => setInferNo2(parseFloat(e.target.value) || 0)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-white font-mono text-xs focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div>
              <label className="text-slate-400 block mb-1">Wind Speed (m/s)</label>
              <input
                type="number"
                step="0.1"
                value={inferWindSpeed}
                onChange={(e) => setInferWindSpeed(parseFloat(e.target.value) || 0)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-white font-mono text-xs focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>

          <button
            type="button"
            disabled={inferLoading}
            onClick={handleRunInference}
            className="w-full py-2.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs transition-all shadow-md cursor-pointer"
          >
            {inferLoading ? "Evaluating Risk..." : "Evaluate Next-Hour Risk (Global Model)"}
          </button>

          {/* Inference Result Display */}
          {inferResult && (
            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">Predicted +1h PM2.5:</span>
                <span className="font-mono text-base font-bold text-white">
                  {inferResult.predicted_pm25_next_hour} ug/m³
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">Pollution Risk Index:</span>
                <span className="font-mono font-bold text-cyan-400">
                  {(inferResult.predicted_risk_index * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">Assigned Risk Tier:</span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono ${
                    inferResult.risk_level === "CRITICAL"
                      ? "bg-rose-950 text-rose-300 border border-rose-800"
                      : inferResult.risk_level === "HIGH"
                      ? "bg-amber-950 text-amber-300 border border-amber-800"
                      : inferResult.risk_level === "MODERATE"
                      ? "bg-yellow-950 text-yellow-300 border border-yellow-800"
                      : "bg-emerald-950 text-emerald-300 border border-emerald-800"
                  }`}
                >
                  {inferResult.risk_level}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
