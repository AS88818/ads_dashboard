"use client";

import React, { useState } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

const rawData = [
  { name: "Mon", google: 4000, meta: 2400 },
  { name: "Tue", google: 3000, meta: 1398 },
  { name: "Wed", google: 2000, meta: 9800 },
  { name: "Thu", google: 2780, meta: 3908 },
  { name: "Fri", google: 1890, meta: 4800 },
  { name: "Sat", google: 2390, meta: 3800 },
  { name: "Sun", google: 3490, meta: 4300 },
];

export function PerformanceChart() {
  const [filter, setFilter] = useState<"combined" | "google" | "meta">("combined");

  return (
    <div className="bg-surface shadow-sm rounded-2xl p-6 h-full w-full flex flex-col border border-border/60">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-bold text-foreground">Campaign Performance</h3>
          <p className="text-xs font-medium text-text-muted mt-1">Comparing Daily Spend</p>
        </div>
        
        {/* Toggle / Filter */}
        <div className="flex items-center bg-surface-hover/80 p-1 rounded-xl border border-border/40">
          <button 
            onClick={() => setFilter("combined")}
            className={`px-4 py-1.5 text-xs font-bold rounded-lg transition-colors ${filter === "combined" ? "bg-white text-foreground shadow-sm" : "text-text-muted hover:text-foreground"}`}
          >
            Combined
          </button>
          <button 
            onClick={() => setFilter("google")}
            className={`px-4 py-1.5 text-xs font-bold rounded-lg transition-colors ${filter === "google" ? "bg-white text-foreground shadow-sm" : "text-text-muted hover:text-foreground"}`}
          >
            Google Ads
          </button>
          <button 
            onClick={() => setFilter("meta")}
            className={`px-4 py-1.5 text-xs font-bold rounded-lg transition-colors ${filter === "meta" ? "bg-white text-foreground shadow-sm" : "text-text-muted hover:text-foreground"}`}
          >
            Meta Ads
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={rawData}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id="colorGoogle" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-accent-lime)" stopOpacity={0.8}/>
                <stop offset="95%" stopColor="var(--color-accent-lime)" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="colorMeta" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-accent-primary)" stopOpacity={0.8}/>
                <stop offset="95%" stopColor="var(--color-accent-primary)" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-border)" opacity={0.5} />
            <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "var(--color-text-muted)" }} dy={10} />
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "var(--color-text-muted)" }} dx={-10} tickFormatter={(val) => `$${val}`} />
            <Tooltip 
              contentStyle={{ backgroundColor: 'var(--color-surface)', borderColor: 'var(--color-border)', borderRadius: '12px', color: 'var(--color-foreground)', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
              itemStyle={{ fontWeight: 600 }}
            />
            
            {(filter === "combined" || filter === "meta") && (
              <Area type="monotone" dataKey="meta" name="Meta Ads" stroke="var(--color-accent-primary)" strokeWidth={3} fillOpacity={1} fill="url(#colorMeta)" />
            )}
            {(filter === "combined" || filter === "google") && (
              <Area type="monotone" dataKey="google" name="Google Ads" stroke="var(--color-accent-lime)" strokeWidth={3} fillOpacity={1} fill="url(#colorGoogle)" />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
