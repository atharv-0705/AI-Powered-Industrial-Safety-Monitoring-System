import React, { useState, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  Search,
  CheckCircle2,
  ExternalLink,
  ShieldAlert,
  ArrowUpDown,
  RefreshCw,
} from "lucide-react";
import { SeverityBadge } from "@/components/common/SeverityBadge";
import { apiService } from "@/services/api";
import { IncidentRecord } from "@/types/safety";
import {
  formatDateTime,
  formatViolationName,
  formatSeverityColor,
} from "@/lib/utils";

export const Events: React.FC = () => {
  const [incidents, setIncidents] = useState<IncidentRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Filters
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedSeverity, setSelectedSeverity] = useState<string>("ALL");
  const [selectedType, setSelectedType] = useState<string>("ALL");
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");
  const [sortField, setSortField] = useState<"timestamp" | "risk_score">("timestamp");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  // Pagination
  const [currentPage, setCurrentPage] = useState<number>(1);
  const rowsPerPage = 10;

  const loadIncidents = async () => {
    setLoading(true);
    const res = await apiService.getIncidents({ limit: 100 });
    setIncidents(res.data);
    setLoading(false);
  };

  useEffect(() => {
    loadIncidents();
  }, []);

  const handleResolve = async (id?: number | null) => {
    if (!id) return;
    await apiService.resolveIncident(id);
    setIncidents((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, resolved: true, resolved_at: Date.now() / 1000 } : item
      )
    );
  };

  // Filtered and Sorted dataset
  const filteredIncidents = useMemo(() => {
    return incidents
      .filter((inc) => {
        // Search query filter
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          const matchType = inc.event_type.toLowerCase().includes(q);
          const matchTrack = String(inc.track_id).includes(q);
          const matchCam = (inc.camera_name || inc.camera_id || "").toLowerCase().includes(q);
          const matchSummary = (inc.vlm_summary || "").toLowerCase().includes(q);
          if (!matchType && !matchTrack && !matchCam && !matchSummary) return false;
        }

        // Severity filter
        if (selectedSeverity !== "ALL" && inc.risk_level !== selectedSeverity) {
          return false;
        }

        // Event type filter
        if (selectedType !== "ALL" && inc.event_type !== selectedType) {
          return false;
        }

        // Status filter
        if (selectedStatus === "RESOLVED" && !inc.resolved) return false;
        if (selectedStatus === "UNREVIEWED" && inc.resolved) return false;

        return true;
      })
      .sort((a, b) => {
        const factor = sortOrder === "asc" ? 1 : -1;
        if (sortField === "risk_score") {
          return (a.risk_score - b.risk_score) * factor;
        }
        return (a.timestamp - b.timestamp) * factor;
      });
  }, [incidents, searchQuery, selectedSeverity, selectedType, selectedStatus, sortField, sortOrder]);

  // Paginated slice
  const totalPages = Math.max(1, Math.ceil(filteredIncidents.length / rowsPerPage));
  const paginatedRows = useMemo(() => {
    const start = (currentPage - 1) * rowsPerPage;
    return filteredIncidents.slice(start, start + rowsPerPage);
  }, [filteredIncidents, currentPage, rowsPerPage]);

  const toggleSort = (field: "timestamp" | "risk_score") => {
    if (sortField === field) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortOrder("desc");
    }
  };

  return (
    <div className="space-y-4">
      {/* 1. HEADER & CONTROLS BAR */}
      <div className="p-4 rounded-xl bg-[#111C2E] border border-[#25334A] space-y-3.5 shadow-md">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-extrabold text-white tracking-wide uppercase flex items-center gap-2">
              <ShieldAlert className="w-5 h-5 text-amber-400" />
              Safety Incident & Violation Audit Records
            </h2>
            <p className="text-xs text-slate-400 font-medium">
              Forensic evidence-backed log of all safety rule breaches, falls, and PPE alerts.
            </p>
          </div>

          <button
            onClick={loadIncidents}
            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold flex items-center gap-1.5 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh Records
          </button>
        </div>

        {/* Filter Inputs Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-2.5 pt-2 border-t border-slate-800 text-xs">
          {/* Search Input */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5 pointer-events-none" />
            <input
              type="text"
              placeholder="Search Worker ID, Type..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full pl-8 pr-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-blue-500 font-sans"
            />
          </div>

          {/* Severity Filter */}
          <select
            value={selectedSeverity}
            onChange={(e) => {
              setSelectedSeverity(e.target.value);
              setCurrentPage(1);
            }}
            className="px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
          >
            <option value="ALL">All Severities</option>
            <option value="CRITICAL">Critical (80-100)</option>
            <option value="HIGH">High (60-79)</option>
            <option value="MEDIUM">Medium (30-59)</option>
            <option value="LOW">Low (0-29)</option>
          </select>

          {/* Event Type Filter */}
          <select
            value={selectedType}
            onChange={(e) => {
              setSelectedType(e.target.value);
              setCurrentPage(1);
            }}
            className="px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
          >
            <option value="ALL">All Incident Types</option>
            <option value="FALL">Potential Fall</option>
            <option value="MISSING_HELMET">Missing Helmet</option>
            <option value="MISSING_VEST">Missing Vest</option>
            <option value="RESTRICTED_ZONE">Restricted Zone Entry</option>
            <option value="DANGEROUS_CLIMB">Dangerous Climb</option>
          </select>

          {/* Status Filter */}
          <select
            value={selectedStatus}
            onChange={(e) => {
              setSelectedStatus(e.target.value);
              setCurrentPage(1);
            }}
            className="px-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
          >
            <option value="ALL">All Statuses</option>
            <option value="UNREVIEWED">Unreviewed / Active</option>
            <option value="RESOLVED">Resolved</option>
          </select>

          {/* Summary Count Tag */}
          <div className="flex items-center justify-end px-3 py-1.5 rounded-lg bg-slate-900/60 border border-slate-800 text-slate-400 font-mono">
            <span>{filteredIncidents.length} matching</span>
          </div>
        </div>
      </div>

      {/* 2. INCIDENTS TABLE */}
      <div className="rounded-xl bg-[#111C2E] border border-[#25334A] overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#0F172A] border-b border-[#25334A] text-slate-400 font-mono uppercase text-[10px] tracking-wider select-none">
              <tr>
                <th className="py-3 px-3.5">ID</th>
                <th
                  onClick={() => toggleSort("timestamp")}
                  className="py-3 px-3.5 cursor-pointer hover:text-slate-200"
                >
                  <div className="flex items-center gap-1">
                    Timestamp
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="py-3 px-3.5">Violation Type</th>
                <th className="py-3 px-3.5">Camera / Location</th>
                <th className="py-3 px-3.5">Worker ID</th>
                <th className="py-3 px-3.5">Severity</th>
                <th
                  onClick={() => toggleSort("risk_score")}
                  className="py-3 px-3.5 cursor-pointer hover:text-slate-200"
                >
                  <div className="flex items-center gap-1">
                    Risk Score
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="py-3 px-3.5">Status</th>
                <th className="py-3 px-3.5 text-right">Actions</th>
              </tr>
            </thead>

            <tbody className="divide-y divide-slate-800/60">
              {paginatedRows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-12 text-center text-slate-500">
                    No safety incident records match the current filters.
                  </td>
                </tr>
              ) : (
                paginatedRows.map((item) => {
                  const sevStyles = formatSeverityColor(item.risk_level);
                  return (
                    <tr
                      key={item.id}
                      className="hover:bg-slate-800/40 transition-colors group font-sans"
                    >
                      {/* ID */}
                      <td className="py-3 px-3.5 font-mono font-bold text-slate-300">
                        #{item.id}
                      </td>

                      {/* Timestamp */}
                      <td className="py-3 px-3.5 font-mono text-slate-400">
                        {formatDateTime(item.timestamp)}
                      </td>

                      {/* Event Type */}
                      <td className="py-3 px-3.5 font-semibold text-slate-200">
                        {formatViolationName(item.event_type)}
                      </td>

                      {/* Camera / Location */}
                      <td className="py-3 px-3.5 text-slate-300 font-mono text-[11px]">
                        {item.camera_id || "CAM-01"}
                      </td>

                      {/* Track ID */}
                      <td className="py-3 px-3.5 font-mono font-bold text-cyan-400">
                        #{item.track_id}
                      </td>

                      {/* Severity */}
                      <td className="py-3 px-3.5">
                        <SeverityBadge severity={item.risk_level} size="sm" />
                      </td>

                      {/* Risk Score */}
                      <td className="py-3 px-3.5 font-mono font-extrabold text-sm">
                        <span className={sevStyles.text}>
                          {item.risk_score.toFixed(1)}
                        </span>
                      </td>

                      {/* Status */}
                      <td className="py-3 px-3.5">
                        {item.resolved ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-950/70 border border-emerald-700/50 text-emerald-400">
                            <CheckCircle2 className="w-3 h-3" />
                            Resolved
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-red-950/70 border border-red-700/50 text-red-300 animate-pulse">
                            Unreviewed
                          </span>
                        )}
                      </td>

                      {/* Action Buttons */}
                      <td className="py-3 px-3.5 text-right space-x-1.5">
                        <Link
                          to={`/events/${item.id}`}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-blue-600/20 hover:bg-blue-600 text-blue-300 hover:text-white font-medium text-xs border border-blue-500/40 transition"
                          title="View Evidence & VLM Explanation"
                        >
                          <span>Details</span>
                          <ExternalLink className="w-3 h-3" />
                        </Link>

                        {!item.resolved && (
                          <button
                            onClick={() => handleResolve(item.id)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-emerald-700 text-slate-300 hover:text-white font-medium text-xs border border-slate-700 transition"
                            title="Mark Incident Resolved"
                          >
                            Resolve
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="p-3 border-t border-[#25334A] bg-[#0F172A] flex items-center justify-between text-xs text-slate-400 font-mono">
          <span>
            Page {currentPage} of {totalPages} ({filteredIncidents.length} total records)
          </span>

          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
              className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 transition"
            >
              Previous
            </button>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages}
              className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-200 transition"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
