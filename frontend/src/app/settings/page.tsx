"use client";

import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { CheckCircle2, Clock, FileText, Mail, Save, Users } from "lucide-react";
import React, { useEffect, useState } from "react";

type EmailReportSettings = {
  enabled: boolean;
  recipients: string[];
  frequency: "daily" | "weekly" | "monthly";
  send_day: string;
  send_time: string;
  timezone: string;
  subject: string;
  message: string;
  attachments: {
    google_html: boolean;
    meta_html: boolean;
    summary_csv: boolean;
  };
};

const defaultEmailSettings: EmailReportSettings = {
  enabled: false,
  recipients: [],
  frequency: "weekly",
  send_day: "Monday",
  send_time: "08:00",
  timezone: "Asia/Kuala_Lumpur",
  subject: "Weekly Ad Performance Report - {client_name}",
  message:
    "Hello {client_name},\n\n" +
    "Your advertising performance report is ready.\n\n" +
    "Total Spend: RM {total_spend}\n" +
    "Total Conversions: {total_conversions}\n" +
    "Average CPA: RM {avg_cpa}\n\n" +
    "Detailed reports are attached.",
  attachments: {
    google_html: true,
    meta_html: true,
    summary_csv: false,
  },
};

const weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function parseRecipients(value: string) {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function loadLocalEmailSettings() {
  if (typeof window === "undefined") return defaultEmailSettings;

  try {
    const saved = window.localStorage.getItem("yck-email-report-settings");
    if (!saved) return defaultEmailSettings;
    const parsed = JSON.parse(saved);
    return {
      ...defaultEmailSettings,
      ...parsed,
      attachments: {
        ...defaultEmailSettings.attachments,
        ...(parsed.attachments || {}),
      },
      recipients: Array.isArray(parsed.recipients) ? parsed.recipients : [],
    };
  } catch {
    return defaultEmailSettings;
  }
}

export default function SettingsPage() {
  const [clientInfo, setClientInfo] = useState<{
    customer_id: string;
    facebook_ad_account_id: string;
  } | null>(null);
  const [emailSettings, setEmailSettings] = useState<EmailReportSettings>(defaultEmailSettings);
  const [recipientText, setRecipientText] = useState("");
  const [loadingSettings, setLoadingSettings] = useState(true);
  const [savingSettings, setSavingSettings] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [deliveryStatus, setDeliveryStatus] = useState<string>("Saved schedule is checked hourly when deployed.");

  useEffect(() => {
    let active = true;

    async function fetchData() {
      try {
        const [dashboardResponse, emailResponse] = await Promise.all([
          fetch("/api/data"),
          fetch("/api/email-settings"),
        ]);

        if (dashboardResponse.ok) {
          const data = await dashboardResponse.json();
          setClientInfo({
            customer_id: data.customer_id || "7867388610",
            facebook_ad_account_id: data.facebook_ad_account_id || "act_717673122125428",
          });
        }

        if (emailResponse.ok) {
          const data = await emailResponse.json();
          const nextSettings = {
            ...defaultEmailSettings,
            ...(data.settings || {}),
            attachments: {
              ...defaultEmailSettings.attachments,
              ...(data.settings?.attachments || {}),
            },
          };
          setEmailSettings(nextSettings);
          setRecipientText((nextSettings.recipients || []).join("\n"));
          if (data.delivery?.scheduler) {
            setDeliveryStatus(`${data.delivery.scheduler}: ${data.delivery.status || "available"}.`);
          }
        } else {
          setSettingsError("Email settings API is not available yet. Changes will be kept in this browser until the backend endpoint is deployed.");
        }
      } catch (err) {
        console.error("Failed to fetch settings:", err);
        setSettingsError("Could not load live email settings. Changes will be kept in this browser.");
      } finally {
        setLoadingSettings(false);
      }
    }

    queueMicrotask(() => {
      if (!active) return;
      const localSettings = loadLocalEmailSettings();
      setEmailSettings(localSettings);
      setRecipientText(localSettings.recipients.join("\n"));
      fetchData();
    });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    window.localStorage.setItem("yck-email-report-settings", JSON.stringify(emailSettings));
  }, [emailSettings]);

  function updateEmailSettings(update: Partial<EmailReportSettings>) {
    setSettingsMessage(null);
    setSettingsError(null);
    setEmailSettings((current) => ({ ...current, ...update }));
  }

  async function saveEmailSettings() {
    setSavingSettings(true);
    setSettingsMessage(null);
    setSettingsError(null);

    const recipients = parseRecipients(recipientText);
    const nextSettings = { ...emailSettings, recipients };
    setEmailSettings(nextSettings);

    try {
      const response = await fetch("/api/email-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(nextSettings),
      });
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(payload.error || "Failed to save email settings");
      }

      setSettingsMessage("Email settings saved.");
      if (payload.settings) {
        setEmailSettings({
          ...defaultEmailSettings,
          ...payload.settings,
          attachments: {
            ...defaultEmailSettings.attachments,
            ...(payload.settings.attachments || {}),
          },
        });
        setRecipientText((payload.settings.recipients || []).join("\n"));
      }
    } catch (err) {
      setSettingsError(err instanceof Error ? err.message : "Failed to save email settings");
    } finally {
      setSavingSettings(false);
    }
  }

  return (
    <DashboardLayout>
      <div className="flex flex-col gap-6 pb-10">
        <div className="mt-2">
          <h1 className="text-2xl font-bold text-foreground tracking-tight">Settings</h1>
          <p className="text-sm font-medium text-text-muted mt-1">Manage account connections, report delivery, and platform preferences.</p>
        </div>

        <div className="grid max-w-6xl grid-cols-1 gap-6 xl:grid-cols-[1fr_1.15fr]">
          <section className="bg-surface shadow-sm rounded-2xl p-6 border border-border/60">
            <h2 className="text-lg font-bold text-foreground mb-4">Ad Account Connections</h2>

            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-xl bg-surface-hover/50 border border-border">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-full bg-accent-primary/10 flex items-center justify-center text-accent-primary font-bold">G</div>
                  <div>
                    <h3 className="font-bold text-foreground">Google Ads</h3>
                    <p className="text-xs font-medium text-text-muted">
                      Connected: <span className="text-accent-primary font-bold">MCC Account (ID: {clientInfo?.customer_id || "786-738-8610"})</span>
                    </p>
                  </div>
                </div>
                <button className="px-4 py-2 text-sm font-bold text-accent-red hover:bg-accent-red/10 rounded-xl transition-colors">
                  Disconnect
                </button>
              </div>

              <div className="flex items-center justify-between p-4 rounded-xl bg-surface-hover/50 border border-border">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-full bg-accent-lime/20 flex items-center justify-center text-accent-primary font-bold">M</div>
                  <div>
                    <h3 className="font-bold text-foreground">Meta Ads</h3>
                    <p className="text-xs font-medium text-text-muted">
                      Connected: <span className="text-accent-primary font-bold">Ad Account (ID: {clientInfo?.facebook_ad_account_id || "act_717673122125428"})</span>
                    </p>
                  </div>
                </div>
                <button className="px-4 py-2 text-sm font-bold text-accent-red hover:bg-accent-red/10 rounded-xl transition-colors">
                  Disconnect
                </button>
              </div>
            </div>
          </section>

          <section className="bg-surface shadow-sm rounded-2xl p-6 border border-border/60">
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2 className="flex items-center gap-2 text-lg font-bold text-foreground">
                  <Mail className="h-5 w-5 text-accent-primary" />
                  Email Reports
                </h2>
                <p className="mt-1 text-xs font-medium text-text-muted">{deliveryStatus}</p>
              </div>
              <label className="relative inline-flex cursor-pointer items-center">
                <input
                  type="checkbox"
                  className="peer sr-only"
                  checked={emailSettings.enabled}
                  onChange={(event) => updateEmailSettings({ enabled: event.target.checked })}
                />
                <div className="h-6 w-11 rounded-full bg-surface-hover after:absolute after:left-0.5 after:top-0.5 after:h-5 after:w-5 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all peer-checked:bg-accent-lime peer-checked:after:translate-x-full" />
              </label>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <label className="block">
                <span className="mb-1.5 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-text-muted">
                  <Clock className="h-3.5 w-3.5" />
                  Frequency
                </span>
                <select
                  value={emailSettings.frequency}
                  onChange={(event) => updateEmailSettings({ frequency: event.target.value as EmailReportSettings["frequency"] })}
                  className="h-10 w-full rounded-xl border border-border bg-background px-3 text-sm font-medium text-foreground focus:border-accent-primary focus:outline-none"
                >
                  <option value="weekly">Weekly</option>
                  <option value="daily">Daily</option>
                  <option value="monthly">Monthly</option>
                </select>
              </label>

              <label className="block">
                <span className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-muted">
                  {emailSettings.frequency === "monthly" ? "Day of Month" : "Send Day"}
                </span>
                {emailSettings.frequency === "monthly" ? (
                  <input
                    type="number"
                    min={1}
                    max={28}
                    value={emailSettings.send_day}
                    onChange={(event) => updateEmailSettings({ send_day: event.target.value })}
                    className="h-10 w-full rounded-xl border border-border bg-background px-3 text-sm font-medium text-foreground focus:border-accent-primary focus:outline-none"
                  />
                ) : (
                  <select
                    value={emailSettings.send_day}
                    onChange={(event) => updateEmailSettings({ send_day: event.target.value })}
                    disabled={emailSettings.frequency === "daily"}
                    className="h-10 w-full rounded-xl border border-border bg-background px-3 text-sm font-medium text-foreground focus:border-accent-primary focus:outline-none disabled:text-text-muted"
                  >
                    {weekdays.map((day) => (
                      <option key={day} value={day}>{day}</option>
                    ))}
                  </select>
                )}
              </label>

              <label className="block">
                <span className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-muted">Send Time</span>
                <input
                  type="time"
                  value={emailSettings.send_time}
                  onChange={(event) => updateEmailSettings({ send_time: event.target.value })}
                  className="h-10 w-full rounded-xl border border-border bg-background px-3 text-sm font-medium text-foreground focus:border-accent-primary focus:outline-none"
                />
              </label>
            </div>

            <div className="mt-4">
              <label className="block">
                <span className="mb-1.5 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-text-muted">
                  <Users className="h-3.5 w-3.5" />
                  Recipients
                </span>
                <textarea
                  value={recipientText}
                  onChange={(event) => {
                    setRecipientText(event.target.value);
                    updateEmailSettings({ recipients: parseRecipients(event.target.value) });
                  }}
                  rows={3}
                  placeholder="client@example.com&#10;andrea@example.com"
                  className="w-full resize-none rounded-xl border border-border bg-background px-3 py-2 text-sm font-medium text-foreground focus:border-accent-primary focus:outline-none"
                />
              </label>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-4">
              <label className="block">
                <span className="mb-1.5 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-text-muted">
                  <FileText className="h-3.5 w-3.5" />
                  Subject
                </span>
                <input
                  value={emailSettings.subject}
                  onChange={(event) => updateEmailSettings({ subject: event.target.value })}
                  className="h-10 w-full rounded-xl border border-border bg-background px-3 text-sm font-medium text-foreground focus:border-accent-primary focus:outline-none"
                />
              </label>

              <label className="block">
                <span className="mb-1.5 block text-xs font-bold uppercase tracking-wider text-text-muted">Message</span>
                <textarea
                  value={emailSettings.message}
                  onChange={(event) => updateEmailSettings({ message: event.target.value })}
                  rows={7}
                  className="w-full resize-y rounded-xl border border-border bg-background px-3 py-2 text-sm font-medium leading-relaxed text-foreground focus:border-accent-primary focus:outline-none"
                />
              </label>
            </div>

            <fieldset className="mt-4">
              <legend className="mb-2 text-xs font-bold uppercase tracking-wider text-text-muted">Attachments</legend>
              <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                {[
                  ["google_html", "Google report"],
                  ["meta_html", "Meta report"],
                  ["summary_csv", "Summary CSV"],
                ].map(([key, label]) => (
                  <label key={key} className="flex items-center gap-2 rounded-xl border border-border bg-surface-hover/40 px-3 py-2 text-sm font-bold text-foreground">
                    <input
                      type="checkbox"
                      checked={Boolean(emailSettings.attachments[key as keyof EmailReportSettings["attachments"]])}
                      onChange={(event) =>
                        updateEmailSettings({
                          attachments: {
                            ...emailSettings.attachments,
                            [key]: event.target.checked,
                          },
                        })
                      }
                      className="h-4 w-4 accent-accent-primary"
                    />
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>

            {(settingsError || settingsMessage) && (
              <div className={`mt-4 rounded-xl border px-3 py-2 text-sm font-medium ${
                settingsError ? "border-red-200 bg-red-50 text-red-700" : "border-green-200 bg-green-50 text-green-700"
              }`}>
                {settingsError || settingsMessage}
              </div>
            )}

            <div className="mt-5 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-xs font-medium text-text-muted">
                <CheckCircle2 className="h-4 w-4 text-accent-green" />
                {loadingSettings ? "Loading report settings..." : "Toggle state is saved locally immediately."}
              </div>
              <button
                onClick={saveEmailSettings}
                disabled={savingSettings}
                className="inline-flex items-center gap-2 rounded-xl bg-accent-primary px-4 py-2 text-sm font-bold text-white transition-colors hover:bg-accent-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Save className="h-4 w-4" />
                {savingSettings ? "Saving..." : "Save Email Settings"}
              </button>
            </div>
          </section>
        </div>
      </div>
    </DashboardLayout>
  );
}
