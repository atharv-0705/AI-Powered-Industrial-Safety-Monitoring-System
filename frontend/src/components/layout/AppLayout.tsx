import React, { useState, useEffect } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { TopNav } from "./TopNav";
import { useSafetyWebSocket } from "@/hooks/useSafetyWebSocket";
import { apiService } from "@/services/api";

export const AppLayout: React.FC = () => {
  const { isConnected, isDemoMode, setIsDemoMode } = useSafetyWebSocket();
  const [selectedCameraId, setSelectedCameraId] = useState<string>("CAM-01");
  const [unresolvedCount, setUnresolvedCount] = useState<number>(3);

  // Poll unresolved counts periodically
  useEffect(() => {
    const fetchCounts = async () => {
      const stats = await apiService.getIncidentStats();
      if (stats.data) {
        setUnresolvedCount(stats.data.unresolved_incidents);
      }
    };
    fetchCounts();
    const timer = setInterval(fetchCounts, 5000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0B1220] text-[#F1F5F9]">
      {/* Permanent Industrial Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Control Bar */}
        <TopNav
          isDemoMode={isDemoMode}
          onToggleDemoMode={() => setIsDemoMode(!isDemoMode)}
          isConnected={isConnected}
          selectedCameraId={selectedCameraId}
          onSelectCamera={setSelectedCameraId}
          unresolvedCount={unresolvedCount}
        />

        {/* Routed Page Container */}
        <main className="flex-1 overflow-y-auto p-5 space-y-5">
          <Outlet context={{ isDemoMode, selectedCameraId }} />
        </main>
      </div>
    </div>
  );
};

