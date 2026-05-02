"use client";

import React, { useMemo, useState } from "react";
import {
  Calendar,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Loader2,
} from "lucide-react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import {
  DashboardDateRange,
  DateRangeSelection,
  formatRangeLabel,
  getPresetRange,
  normalizeDashboardDateRange,
  parseDateInput,
  toDateInputValue,
} from "@/lib/date-range";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface DatePickerProps {
  onRangeChange: (range: DateRangeSelection) => void | Promise<void>;
  currentRange?: DashboardDateRange;
  loading?: boolean;
}

const presets = [
  { label: "Last 7 Days", days: 7 },
  { label: "Last 30 Days", days: 30 },
  { label: "Last 90 Days", days: 90 },
];

const weekdays = ["M", "T", "W", "T", "F", "S", "S"];

function addMonths(date: Date, months: number) {
  const next = new Date(date);
  next.setMonth(next.getMonth() + months);
  return next;
}

function buildCalendarDays(viewDate: Date) {
  const firstOfMonth = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);
  const mondayOffset = (firstOfMonth.getDay() + 6) % 7;
  const gridStart = new Date(firstOfMonth);
  gridStart.setDate(firstOfMonth.getDate() - mondayOffset);

  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(gridStart);
    date.setDate(gridStart.getDate() + index);
    return date;
  });
}

function compareDateInput(a?: string, b?: string) {
  if (!a || !b) return 0;
  return a.localeCompare(b);
}

export function DatePicker({ onRangeChange, currentRange, loading = false }: DatePickerProps) {
  const normalizedRange = useMemo(
    () => normalizeDashboardDateRange(currentRange),
    [currentRange],
  );
  const [isOpen, setIsOpen] = useState(false);
  const [draftStart, setDraftStart] = useState(normalizedRange.startDate);
  const [draftEnd, setDraftEnd] = useState(normalizedRange.endDate);
  const [viewDate, setViewDate] = useState(() => parseDateInput(normalizedRange.endDate) || new Date());

  const calendarDays = useMemo(() => buildCalendarDays(viewDate), [viewDate]);
  const monthLabel = new Intl.DateTimeFormat("en-GB", {
    month: "long",
    year: "numeric",
  }).format(viewDate);
  const currentLabel = loading ? "Refreshing..." : formatRangeLabel(normalizedRange);
  const canApply = Boolean(draftStart && draftEnd && compareDateInput(draftStart, draftEnd) <= 0);

  function selectDate(date: Date) {
    const value = toDateInputValue(date);

    if (!draftStart || draftEnd) {
      setDraftStart(value);
      setDraftEnd("");
      return;
    }

    if (compareDateInput(value, draftStart) < 0) {
      setDraftEnd(draftStart);
      setDraftStart(value);
      return;
    }

    setDraftEnd(value);
  }

  function applyRange(range: DateRangeSelection) {
    setIsOpen(false);
    void onRangeChange(range);
  }

  function togglePicker() {
    if (!isOpen) {
      setDraftStart(normalizedRange.startDate);
      setDraftEnd(normalizedRange.endDate);
      setViewDate(parseDateInput(normalizedRange.endDate) || new Date());
    }
    setIsOpen(!isOpen);
  }

  function applyCustomRange() {
    if (!canApply) return;

    applyRange({
      startDate: draftStart,
      endDate: draftEnd,
      label: "Custom Range",
    });
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={togglePicker}
        disabled={loading}
        className="flex items-center gap-2 bg-surface border border-border/60 rounded-xl px-4 py-2 text-sm font-bold shadow-sm hover:bg-muted/50 transition-colors disabled:cursor-wait disabled:opacity-70"
      >
        {loading ? (
          <Loader2 className="w-4 h-4 animate-spin text-accent-primary" />
        ) : (
          <Calendar className="w-4 h-4 text-accent-primary" />
        )}
        <span>{currentLabel}</span>
        <ChevronDown className={cn("w-4 h-4 text-text-muted transition-transform", isOpen && "rotate-180")} />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-30 bg-foreground/5"
            onClick={() => setIsOpen(false)}
          />
          <div
            role="dialog"
            aria-label="Choose date range"
            className="absolute right-0 mt-2 w-[360px] max-w-[calc(100vw-2rem)] bg-surface border border-border shadow-xl rounded-2xl p-4 z-40 animate-in fade-in zoom-in duration-150"
          >
            <div className="grid grid-cols-3 gap-2">
              {presets.map((preset) => (
                (() => {
                  const presetRange = getPresetRange(preset.days);
                  const isActive =
                    normalizedRange.startDate === presetRange.startDate &&
                    normalizedRange.endDate === presetRange.endDate;

                  return (
                    <button
                      key={preset.label}
                      type="button"
                      onClick={() => applyRange(presetRange)}
                      className={cn(
                        "rounded-lg px-3 py-2 text-xs font-bold transition-colors",
                        isActive
                          ? "bg-accent-lime/20 text-accent-primary"
                          : "bg-surface-hover text-text-muted hover:text-foreground",
                      )}
                    >
                      {preset.days} days
                    </button>
                  );
                })()
              ))}
            </div>

            <div className="mt-4 flex items-center justify-between">
              <button
                type="button"
                onClick={() => setViewDate(addMonths(viewDate, -1))}
                className="rounded-lg p-2 text-text-muted hover:bg-surface-hover hover:text-foreground"
                aria-label="Previous month"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <p className="text-sm font-bold text-foreground">{monthLabel}</p>
              <button
                type="button"
                onClick={() => setViewDate(addMonths(viewDate, 1))}
                className="rounded-lg p-2 text-text-muted hover:bg-surface-hover hover:text-foreground"
                aria-label="Next month"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>

            <div className="mt-3 grid grid-cols-7 gap-1 text-center">
              {weekdays.map((day, index) => (
                <div key={`${day}-${index}`} className="py-1 text-[10px] font-black uppercase text-text-muted">
                  {day}
                </div>
              ))}
              {calendarDays.map((date) => {
                const value = toDateInputValue(date);
                const isOutsideMonth = date.getMonth() !== viewDate.getMonth();
                const isStart = value === draftStart;
                const isEnd = value === draftEnd;
                const isInRange =
                  draftStart &&
                  draftEnd &&
                  compareDateInput(value, draftStart) >= 0 &&
                  compareDateInput(value, draftEnd) <= 0;

                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => selectDate(date)}
                    className={cn(
                      "h-9 rounded-lg text-xs font-bold transition-colors",
                      isOutsideMonth ? "text-text-muted/40" : "text-foreground",
                      isInRange && "bg-accent-lime/20 text-accent-primary",
                      (isStart || isEnd) && "bg-accent-primary text-white hover:bg-accent-primary",
                      !isStart && !isEnd && "hover:bg-surface-hover",
                    )}
                  >
                    {date.getDate()}
                  </button>
                );
              })}
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <label className="flex flex-col gap-1 text-[10px] font-black uppercase tracking-wide text-text-muted">
                Start
                <input
                  type="date"
                  value={draftStart}
                  onChange={(event) => setDraftStart(event.target.value)}
                  className="h-10 rounded-lg border border-border bg-background px-3 text-xs font-bold text-foreground outline-none focus:border-accent-primary"
                />
              </label>
              <label className="flex flex-col gap-1 text-[10px] font-black uppercase tracking-wide text-text-muted">
                End
                <input
                  type="date"
                  value={draftEnd}
                  min={draftStart}
                  onChange={(event) => setDraftEnd(event.target.value)}
                  className="h-10 rounded-lg border border-border bg-background px-3 text-xs font-bold text-foreground outline-none focus:border-accent-primary"
                />
              </label>
            </div>

            <div className="mt-4 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="rounded-lg px-4 py-2 text-sm font-bold text-text-muted hover:bg-surface-hover hover:text-foreground"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={applyCustomRange}
                disabled={!canApply}
                className="rounded-lg bg-accent-primary px-4 py-2 text-sm font-bold text-white shadow-sm transition-colors hover:bg-accent-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Apply Range
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
