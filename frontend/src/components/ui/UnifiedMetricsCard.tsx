import React from "react";
import { TrendingDown, TrendingUp } from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface MetricItemProps {
  title: string;
  value: string | number;
  delta?: number;
  deltaType?: "increase" | "decrease";
  isCurrency?: boolean;
  inverseColors?: boolean;
}

function MetricItem({ title, value, delta, deltaType, isCurrency, inverseColors = false }: MetricItemProps) {
  const isPositiveDelta = deltaType === "increase";
  
  let deltaColorClass = "text-text-muted";
  let deltaBgClass = "bg-surface-hover";
  if (delta !== undefined) {
    if ((isPositiveDelta && !inverseColors) || (!isPositiveDelta && inverseColors)) {
      deltaColorClass = "text-accent-green";
      deltaBgClass = "bg-accent-lime/50"; // Use soft lime for positive bg
    } else {
      deltaColorClass = "text-accent-red";
      deltaBgClass = "bg-accent-salmon/20"; // Soft red for negative bg
    }
  }

  const formattedValue = isCurrency && typeof value === 'number' 
    ? new Intl.NumberFormat('en-MY', { style: 'currency', currency: 'MYR' }).format(value)
    : typeof value === 'number' ? value.toLocaleString() : value;

  return (
    <div className="flex-1 px-6 first:pl-0 last:pr-0 border-r border-border/50 last:border-0">
      <h3 className="text-sm font-semibold text-text-muted mb-2">{title}</h3>
      <div className="flex items-center gap-3">
        <p className="text-3xl font-bold text-foreground">{formattedValue}</p>
        {delta !== undefined && (
          <div className={cn("flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold border border-white/20", deltaBgClass, deltaColorClass)}>
            {isPositiveDelta ? "+" : "-"}{Math.abs(delta)}%
            {isPositiveDelta ? <TrendingUp className="ml-1 h-3 w-3" /> : <TrendingDown className="ml-1 h-3 w-3" />}
          </div>
        )}
      </div>
    </div>
  );
}

interface UnifiedMetricsCardProps {
  metrics: {
    totalSpend: number;
    spendDelta: number;
    blendedCPA: number;
    cpaDelta: number;
    totalConversions: number;
    blendedROAS?: number;
    dateRange?: { start: string; end: string };
  };
  cpaLabel?: string;
}

export function UnifiedMetricsCard({ metrics, cpaLabel = "Blended CPA" }: UnifiedMetricsCardProps) {
  const dateLabel = metrics.dateRange 
    ? `${new Date(metrics.dateRange.start).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })} - ${new Date(metrics.dateRange.end).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}`
    : "Last 30 Days";

  return (
    <div className="bg-surface shadow-sm rounded-2xl p-6 border border-border/60">
      {/* Card Header matching Emitly */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-lg font-bold text-foreground">Performance Over Time</h2>
          <p className="text-xs font-medium text-text-muted mt-1">{dateLabel}</p>
        </div>
      </div>

      {/* Divided Metrics Row */}
      <div className="flex items-center justify-between">
        <MetricItem 
          title="Total Spend" 
          value={metrics.totalSpend} 
          delta={metrics.spendDelta} 
          deltaType="increase" 
          isCurrency 
        />
        <MetricItem 
          title={cpaLabel} 
          value={metrics.blendedCPA} 
          delta={metrics.cpaDelta} 
          deltaType="decrease" 
          isCurrency 
          inverseColors 
        />
        <MetricItem 
          title="Total Conversions" 
          value={metrics.totalConversions} 
          delta={12.8}
          deltaType="increase"
        />
      </div>
    </div>
  );
}
