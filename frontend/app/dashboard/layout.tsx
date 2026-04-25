"use client";

import { useState } from "react";
import Sidebar from "../components/Sidebar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(true);

  return (
    <div className="min-h-screen bg-cream-200">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <main
        className="transition-all duration-300 p-4"
        style={{ marginLeft: collapsed ? "88px" : "236px" }}
      >
        <div className="bg-cream-100 rounded-2xl min-h-[calc(100vh-32px)] shadow-sm border border-cream-200/60 p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
