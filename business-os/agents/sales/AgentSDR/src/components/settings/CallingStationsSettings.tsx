"use client";
/* eslint-disable react-hooks/set-state-in-effect */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { RiAddLine, RiCloudLine, RiGlobalLine, RiLinkM, RiLoader4Line, RiPauseCircleLine, RiPencilLine, RiPlayCircleLine, RiDeleteBinLine } from "@remixicon/react";
import * as Badge from "@/components/alignui/badge";
import * as Button from "@/components/alignui/button";
import * as Modal from "@/components/alignui/modal";
import * as Select from "@/components/alignui/select";
import { Frame, FramePanel } from "@/components/analytics/kit/Frame";
import { FormError, TextField } from "@/components/calls/fields";
import { errorMessage, timeAgo } from "@/components/crm/crm-utils";
import { EmptyState } from "@/components/page/EmptyState";
import { Callout } from "@/components/settings/SettingsKit";
import { SettingsPage } from "@/components/settings/SettingsPage";
import { DocsLink } from "@/components/page/DocsLink";
import {
  cancelStationLink,
  createCallingProxy,
  createCallingStation,
  deleteCallingProxy,
  deleteCallingStation,
  listCallingProxies,
  listCallingStations,
  startStationLink,
  updateCallingProxy,
  updateCallingStation,
} from "@/lib/calls/client";
import {
  PROXY_PROTOCOLS,
  STATION_LAUNCHERS,
  usesGoLogin,
  type CallingProxy,
  type CallingStation,
  type ProxyProtocol,
  type StationLauncher,
  type StationStatus,
} from "@/lib/calls/stationContract";
import { hoursInvalid, hoursSummary, StationHoursEditor } from "@/components/calling/ai/StationHoursEditor";
import type { StationAiSettings, StationAiSettingsResponse } from "@/lib/calls/aiCampaigns/api";
import { listStationAiSettings, updateStationAiSettings } from "@/lib/calls/aiCampaigns/client";
import type { WeeklyHours } from "@/lib/channels/rules";
import { cn } from "@/utils/cn";

const LAUNCHER_LABEL: Record<StationLauncher, string> = {
  cloak: "CloakBrowser",
  local: "Local Chromium",
  gologin_sdk: "GoLogin (this server)",
  gologin_cloud: "GoLogin Cloud",
};

const STATUS_LABEL: Record<StationStatus, string> = {
  onboarding: "Not linked yet",
  active: "Active",
  paused: "Paused",
  logged_out: "Logged out",
  banned: "Banned",
};
const STATUS_COLOR: Record<StationStatus, React.ComponentProps<typeof Badge.Root>["color"]> = {
  onboarding: "gray",
  active: "green",
  paused: "orange",
  logged_out: "red",
  banned: "red",
};


/** Fast while something is happening (a link code to show, a call to follow), slow otherwise. */
const POLL_BUSY_MS = 3000;
const POLL_IDLE_MS = 15000;

/** Radix selects cannot hold an empty value, so "no IP" is this. */
const NO_PROXY = "none";

type Draft = {
  name: string;
  phone: string;
  launcher: StationLauncher;
  gologinProfileId: string;
  proxyId: string;
  /** AI campaign calls a day from this number; blank = the organization's rule. */
  callsPerDay: string;
  /** Its own calling hours; null = the organization's rule. */
  callingHours: WeeklyHours | null;
};
const EMPTY_DRAFT: Draft = { name: "", phone: "", launcher: "cloak", gologinProfileId: "", proxyId: NO_PROXY, callsPerDay: "", callingHours: null };
const FALLBACK_HOURS: WeeklyHours = { timezone: "Asia/Kolkata", days: [1, 2, 3, 4, 5, 6], start: "12:00", end: "19:00" };

type ProxyDraft = {
  label: string;
  protocol: ProxyProtocol;
  host: string;
  port: string;
  username: string;
  password: string;
  country: string;
  timezone: string;
  provider: string;
  notes: string;
};
const EMPTY_PROXY_DRAFT: ProxyDraft = {
  label: "",
  protocol: "http",
  host: "",
  port: "",
  username: "",
  password: "",
  country: "IN",
  timezone: "Asia/Kolkata",
  provider: "",
  notes: "",
};

export function CallingStationsSettings() {
  const [stations, setStations] = useState<CallingStation[] | null>(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  /** "new", or the id of the station being edited. */
  const [formFor, setFormFor] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<CallingStation | null>(null);
  /** Numbers whose wrong-account question the operator put off ("Decide later"), until the page reloads. */
  const [putOff, setPutOff] = useState<ReadonlySet<string>>(new Set());
  const [proxies, setProxies] = useState<CallingProxy[]>([]);
  /** Each number's own AI calls a day and calling hours, and the organization rules they fall back to. */
  const [aiSettings, setAiSettings] = useState<StationAiSettingsResponse | null>(null);
  /** "new", or the id of the IP being edited. */
  const [proxyFormFor, setProxyFormFor] = useState<string | null>(null);
  const [proxyDraft, setProxyDraft] = useState<ProxyDraft>(EMPTY_PROXY_DRAFT);
  const [proxyFormError, setProxyFormError] = useState("");
  const [deletingProxy, setDeletingProxy] = useState<CallingProxy | null>(null);

  const load = useCallback(async () => {
    try {
      const [stationList, proxyList, ai] = await Promise.all([
        listCallingStations(),
        listCallingProxies(),
        // Shown beside each number; the page works without it.
        listStationAiSettings().catch(() => null),
      ]);
      setStations(stationList.stations);
      setProxies(proxyList.proxies);
      if (ai) setAiSettings(ai);
      setError("");
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }, []);

  const hot = stations?.some((station) => station.link !== null || station.busyCallId !== null) ?? false;
  useEffect(() => {
    void load();
    const interval = setInterval(() => void load(), hot ? POLL_BUSY_MS : POLL_IDLE_MS);
    return () => clearInterval(interval);
  }, [load, hot]);

  /** Runs one action on a station and swaps the station it returns into the list. */
  const act = async (station: CallingStation, run: () => Promise<{ station: CallingStation }>) => {
    setBusyId(station.id);
    setError("");
    try {
      const { station: next } = await run();
      setStations((current) => (current ?? []).map((item) => (item.id === next.id ? next : item)));
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusyId(null);
    }
  };

  // A link that ended on another WhatsApp account than the number: ask which is right.
  const wrongAccount =
    stations?.find((station) => station.linkedPhone !== null && station.linkedPhone !== station.phone && station.link === null && !putOff.has(station.id)) ?? null;

  const openAdd = () => {
    setDraft(EMPTY_DRAFT);
    setFormError("");
    setFormFor("new");
  };
  const aiOf = (stationId: string): StationAiSettings | null => aiSettings?.settings.find((item) => item.stationId === stationId) ?? null;
  const openEdit = (station: CallingStation) => {
    const own = aiOf(station.id);
    setDraft({
      name: station.name,
      phone: station.phone,
      launcher: station.launcher,
      gologinProfileId: station.gologinProfileId ?? "",
      proxyId: station.proxyId ?? NO_PROXY,
      callsPerDay: own?.callsPerDay != null ? String(own.callsPerDay) : "",
      callingHours: own?.callingHours ?? null,
    });
    setFormError("");
    setFormFor(station.id);
  };

  const save = async () => {
    setSaving(true);
    setFormError("");
    const gologinProfileId = usesGoLogin(draft.launcher) ? draft.gologinProfileId.trim() || null : null;
    const proxyId = draft.proxyId === NO_PROXY ? null : draft.proxyId;
    const callsPerDay = draft.callsPerDay.trim() === "" ? null : Number(draft.callsPerDay);
    if (callsPerDay !== null && (!Number.isInteger(callsPerDay) || callsPerDay < 1 || callsPerDay > 100)) {
      setSaving(false);
      return setFormError("AI calls a day must be a whole number from 1 to 100, or blank to use the organization's rule.");
    }
    if (draft.callingHours && hoursInvalid(draft.callingHours)) {
      setSaving(false);
      return setFormError("Calling hours need at least one day and an end after the start.");
    }
    try {
      let savedId = formFor;
      if (formFor === "new") {
        const { station } = await createCallingStation({
          name: draft.name.trim(),
          phone: draft.phone.trim(),
          launcher: draft.launcher,
          gologinProfileId,
          proxyId,
        });
        savedId = station.id;
        setStations((current) => [...(current ?? []), station]);
      } else if (formFor) {
        const { station } = await updateCallingStation(formFor, { name: draft.name.trim(), launcher: draft.launcher, gologinProfileId, proxyId });
        setStations((current) => (current ?? []).map((item) => (item.id === station.id ? station : item)));
      }
      // Only touched when it differs, so saving the other fields never rewrites a number's AI limits.
      const before = savedId && savedId !== "new" ? aiOf(savedId) : null;
      if (savedId && savedId !== "new" && (callsPerDay !== (before?.callsPerDay ?? null) || JSON.stringify(draft.callingHours) !== JSON.stringify(before?.callingHours ?? null))) {
        await updateStationAiSettings(savedId, { callsPerDay, callingHours: draft.callingHours });
      }
      setFormFor(null);
      void load();
    } catch (cause) {
      setFormError(errorMessage(cause));
    } finally {
      setSaving(false);
    }
  };

  const openAddProxy = () => {
    setProxyDraft(EMPTY_PROXY_DRAFT);
    setProxyFormError("");
    setProxyFormFor("new");
  };
  const openEditProxy = (proxy: CallingProxy) => {
    setProxyDraft({
      label: proxy.label,
      protocol: proxy.protocol,
      host: proxy.host,
      port: String(proxy.port),
      username: proxy.username ?? "",
      password: "",
      country: proxy.country ?? "",
      timezone: proxy.timezone ?? "",
      provider: proxy.provider ?? "",
      notes: proxy.notes ?? "",
    });
    setProxyFormError("");
    setProxyFormFor(proxy.id);
  };

  const saveProxy = async () => {
    const port = Number(proxyDraft.port);
    if (!proxyDraft.host.trim()) return setProxyFormError("Host is required.");
    if (!Number.isInteger(port) || port < 1 || port > 65535) return setProxyFormError("Port must be a number from 1 to 65535.");
    setSaving(true);
    setProxyFormError("");
    const request = {
      label: proxyDraft.label.trim(),
      protocol: proxyDraft.protocol,
      host: proxyDraft.host.trim(),
      port,
      username: proxyDraft.username.trim() || null,
      country: proxyDraft.country.trim().toUpperCase() || null,
      timezone: proxyDraft.timezone.trim() || null,
      provider: proxyDraft.provider.trim() || null,
      notes: proxyDraft.notes.trim() || null,
      // Left out when blank, so an edit keeps the saved password.
      ...(proxyDraft.password ? { password: proxyDraft.password } : {}),
    };
    try {
      if (proxyFormFor === "new") await createCallingProxy(request);
      else if (proxyFormFor) await updateCallingProxy(proxyFormFor, request);
      setProxyFormFor(null);
      await load();
    } catch (cause) {
      setProxyFormError(errorMessage(cause));
    } finally {
      setSaving(false);
    }
  };

  const confirmDeleteProxy = async () => {
    if (!deletingProxy) return;
    setSaving(true);
    try {
      await deleteCallingProxy(deletingProxy.id);
      setDeletingProxy(null);
      await load();
    } catch (cause) {
      setError(errorMessage(cause));
      setDeletingProxy(null);
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleting) return;
    setSaving(true);
    try {
      await deleteCallingStation(deleting.id);
      setStations((current) => (current ?? []).filter((item) => item.id !== deleting.id));
      setDeleting(null);
      void load();
    } catch (cause) {
      setError(errorMessage(cause));
      setDeleting(null);
    } finally {
      setSaving(false);
    }
  };

  const addButton = (
    <Button.Root variant="primary" mode="filled" size="small" onClick={openAdd}>
      <Button.Icon as={RiAddLine} />
      Add number
    </Button.Root>
  );

  const editingProxy = proxyFormFor && proxyFormFor !== "new" ? proxies.find((proxy) => proxy.id === proxyFormFor) : null;
  const canSaveProxy = proxyDraft.label.trim() && proxyDraft.host.trim() && proxyDraft.port.trim();
  /** An IP is offered to a number while it is free or already that number's. */
  const proxyChoices = proxies.filter((proxy) => proxy.stationId === null || proxy.stationId === formFor);
  const editing = formFor && formFor !== "new" ? stations?.find((station) => station.id === formFor) : null;
  const canSave = draft.name.trim() && (formFor !== "new" || draft.phone.trim()) && (!usesGoLogin(draft.launcher) || draft.gologinProfileId.trim());

  return (
    <SettingsPage
      title="Calling numbers"
      description="WhatsApp numbers the AI agent calls from, with WhatsApp Web running in a remote browser instead of a rep's laptop."
      actions={addButton}
    >
      <div className="space-y-5">
        <Callout tone="info" title="How cloud calling works">
          A calling number is a WhatsApp number linked to a browser profile that a call worker opens for each call. It needs a call worker running
          {" "}and, for GoLogin profiles, the GoLogin integration connected in{" "}
          <Link href="/settings/whatsapp-connection" className="underline">Settings → WhatsApp → Integrations</Link>.{" "}
          <DocsLink page="whatsapp/calling#what-you-need">What you need</DocsLink>
        </Callout>
        {error && <Callout tone="error">{error}</Callout>}

        {stations === null ? (
          !error && (
            <div className="flex justify-center py-12" aria-busy="true" aria-label="Loading calling numbers">
              <RiLoader4Line className="size-5 animate-spin text-text-soft-400" aria-hidden="true" />
            </div>
          )
        ) : stations.length === 0 ? (
          <Frame>
            <FramePanel>
              <EmptyState
                icon={RiCloudLine}
                title="No calling numbers yet"
                description="Add a WhatsApp number and its browser profile, then link it to WhatsApp Web from here."
                action={addButton}
              />
            </FramePanel>
          </Frame>
        ) : (
          <div className="space-y-3">
            {stations.map((station) => (
              <StationCard
                key={station.id}
                station={station}
                ai={aiOf(station.id)}
                rules={aiSettings?.rules ?? null}
                busy={busyId === station.id}
                // Relinking a number logged in as the wrong account starts it logged out.
                onLink={() => void act(station, () => startStationLink(station.id, { fresh: station.linkedPhone !== null && station.linkedPhone !== station.phone }))}
                onCancelLink={() => void act(station, () => cancelStationLink(station.id))}
                onToggle={() => void act(station, () => updateCallingStation(station.id, { status: station.status === "paused" ? "active" : "paused" }))}
                onEdit={() => openEdit(station)}
                onDelete={() => setDeleting(station)}
                onUseLinkedPhone={() => void act(station, () => updateCallingStation(station.id, { phone: station.linkedPhone! }))}
              />
            ))}
          </div>
        )}

        {stations !== null && (
          <section className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-0.5">
                <h2 className="text-label-md text-text-strong-950">IPs</h2>
                <p className="text-paragraph-sm text-text-sub-600">Each number goes out from its own IP. Static Indian ISP proxies; one number per IP.</p>
              </div>
              <Button.Root variant="neutral" mode="stroke" size="small" onClick={openAddProxy}>
                <Button.Icon as={RiAddLine} />
                Add IP
              </Button.Root>
            </div>
            {proxies.length === 0 ? (
              <p className="text-paragraph-sm text-text-soft-400">No IPs yet. Numbers without one use the worker&apos;s own IP.</p>
            ) : (
              <div className="space-y-3">
                {proxies.map((proxy) => (
                  <ProxyCard key={proxy.id} proxy={proxy} onEdit={() => openEditProxy(proxy)} onDelete={() => setDeletingProxy(proxy)} />
                ))}
              </div>
            )}
          </section>
        )}
      </div>

      <Modal.Root open={formFor !== null} onOpenChange={(open) => { if (!open && !saving) setFormFor(null); }}>
        <Modal.Content>
          <Modal.Header icon={RiCloudLine}>
            <Modal.Title>{formFor === "new" ? "Add a calling number" : "Edit calling number"}</Modal.Title>
            <Modal.Description>
              {formFor === "new"
                ? "After adding it, use Link WhatsApp to sign the number into WhatsApp Web."
                : `${editing?.phone ?? "The number"} can't be changed here; delete and add it again for a different number.`}
            </Modal.Description>
          </Modal.Header>
          <Modal.Body className="space-y-3">
            {formError && <FormError>{formError}</FormError>}
            <TextField label="Name" autoFocus value={draft.name} onChange={(name) => setDraft((d) => ({ ...d, name }))} placeholder="Sales line 1" disabled={saving} />
            {formFor === "new" && (
              <TextField label="WhatsApp number" value={draft.phone} onChange={(phone) => setDraft((d) => ({ ...d, phone }))} placeholder="+91 98765 43210" disabled={saving} />
            )}
            <div>
              <label className="mb-1.5 block text-label-sm text-text-strong-950">Browser</label>
              <Select.Root size="small" value={draft.launcher} onValueChange={(launcher) => setDraft((d) => ({ ...d, launcher: launcher as StationLauncher }))} disabled={saving}>
                <Select.Trigger><Select.Value /></Select.Trigger>
                <Select.Content>
                  {STATION_LAUNCHERS.map((launcher) => (
                    <Select.Item key={launcher} value={launcher}>{LAUNCHER_LABEL[launcher]}</Select.Item>
                  ))}
                </Select.Content>
              </Select.Root>
            </div>
            <div>
              <label className="mb-1.5 block text-label-sm text-text-strong-950">IP</label>
              <Select.Root size="small" value={draft.proxyId} onValueChange={(proxyId) => setDraft((d) => ({ ...d, proxyId }))} disabled={saving}>
                <Select.Trigger><Select.Value /></Select.Trigger>
                <Select.Content>
                  <Select.Item value={NO_PROXY}>None (worker&apos;s own IP)</Select.Item>
                  {proxyChoices.map((proxy) => (
                    <Select.Item key={proxy.id} value={proxy.id}>{proxy.label} · {proxy.host}</Select.Item>
                  ))}
                </Select.Content>
              </Select.Root>
            </div>
            {usesGoLogin(draft.launcher) && (
              <TextField
                label="GoLogin profile ID"
                value={draft.gologinProfileId}
                onChange={(gologinProfileId) => setDraft((d) => ({ ...d, gologinProfileId }))}
                placeholder="The profile's ID from GoLogin"
                disabled={saving}
              />
            )}
            <div className="border-t border-stroke-soft-200 pt-3">
              <p className="mb-2 text-label-sm text-text-strong-950">AI campaigns</p>
              <TextField
                label="AI calls a day"
                inputMode="numeric"
                value={draft.callsPerDay}
                onChange={(callsPerDay) => setDraft((d) => ({ ...d, callsPerDay }))}
                placeholder={aiSettings ? `Blank: the organization's rule (${aiSettings.rules.callsPerDay})` : "Blank: the organization's rule"}
                disabled={saving}
              />
              <div className="mt-3">
                <div className="mb-1.5 flex items-center justify-between gap-3">
                  <label className="text-label-sm text-text-strong-950">Calling hours</label>
                  {draft.callingHours ? (
                    <button type="button" disabled={saving} onClick={() => setDraft((d) => ({ ...d, callingHours: null }))} className="text-paragraph-xs text-text-sub-600 underline-offset-2 hover:underline disabled:opacity-50">
                      Use the organization&apos;s hours
                    </button>
                  ) : (
                    <button type="button" disabled={saving} onClick={() => setDraft((d) => ({ ...d, callingHours: aiSettings?.rules.callingHours ?? FALLBACK_HOURS }))} className="text-paragraph-xs text-text-sub-600 underline-offset-2 hover:underline disabled:opacity-50">
                      Set hours for this number
                    </button>
                  )}
                </div>
                {draft.callingHours ? (
                  <StationHoursEditor value={draft.callingHours} onChange={(callingHours) => setDraft((d) => ({ ...d, callingHours }))} disabled={saving} />
                ) : (
                  <p className="text-paragraph-xs text-text-sub-600">{aiSettings ? `The organization's hours: ${hoursSummary(aiSettings.rules.callingHours)}` : "The organization's calling hours (Settings → WhatsApp → Sending rules)."}</p>
                )}
              </div>
            </div>
          </Modal.Body>
          <Modal.Footer>
            <Modal.Close asChild>
              <Button.Root variant="neutral" mode="stroke" size="small" disabled={saving}>Cancel</Button.Root>
            </Modal.Close>
            <Button.Root variant="primary" mode="filled" size="small" disabled={saving || !canSave} onClick={() => void save()}>
              {saving && <RiLoader4Line className="size-4 animate-spin" aria-hidden="true" />}
              {formFor === "new" ? "Add number" : "Save"}
            </Button.Root>
          </Modal.Footer>
        </Modal.Content>
      </Modal.Root>

      <Modal.Root open={proxyFormFor !== null} onOpenChange={(open) => { if (!open && !saving) setProxyFormFor(null); }}>
        <Modal.Content>
          <Modal.Header icon={RiGlobalLine}>
            <Modal.Title>{proxyFormFor === "new" ? "Add an IP" : "Edit IP"}</Modal.Title>
            <Modal.Description>A proxy a calling number&apos;s browser goes out through. It can be assigned to one number.</Modal.Description>
          </Modal.Header>
          <Modal.Body className="space-y-3">
            {proxyFormError && <FormError>{proxyFormError}</FormError>}
            <TextField label="Label" autoFocus value={proxyDraft.label} onChange={(label) => setProxyDraft((d) => ({ ...d, label }))} placeholder="Mumbai ISP 1" disabled={saving} />
            <div className="grid grid-cols-[8rem_1fr_6rem] gap-3">
              <div>
                <label className="mb-1.5 block text-label-sm text-text-strong-950">Protocol</label>
                <Select.Root size="small" value={proxyDraft.protocol} onValueChange={(protocol) => setProxyDraft((d) => ({ ...d, protocol: protocol as ProxyProtocol }))} disabled={saving}>
                  <Select.Trigger><Select.Value /></Select.Trigger>
                  <Select.Content>
                    {PROXY_PROTOCOLS.map((protocol) => (
                      <Select.Item key={protocol} value={protocol}>{protocol}</Select.Item>
                    ))}
                  </Select.Content>
                </Select.Root>
              </div>
              <TextField label="Host" value={proxyDraft.host} onChange={(host) => setProxyDraft((d) => ({ ...d, host }))} placeholder="203.0.113.10" disabled={saving} />
              <TextField label="Port" inputMode="numeric" value={proxyDraft.port} onChange={(port) => setProxyDraft((d) => ({ ...d, port }))} placeholder="1080" disabled={saving} />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <TextField label="Username" autoComplete="off" value={proxyDraft.username} onChange={(username) => setProxyDraft((d) => ({ ...d, username }))} disabled={saving} />
              <TextField
                label="Password"
                type="password"
                autoComplete="new-password"
                value={proxyDraft.password}
                onChange={(password) => setProxyDraft((d) => ({ ...d, password }))}
                placeholder={editingProxy?.hasPassword ? "Saved — leave blank to keep" : ""}
                disabled={saving}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <TextField label="Country" value={proxyDraft.country} onChange={(country) => setProxyDraft((d) => ({ ...d, country }))} placeholder="IN" disabled={saving} />
              <TextField label="Time zone" value={proxyDraft.timezone} onChange={(timezone) => setProxyDraft((d) => ({ ...d, timezone }))} placeholder="Asia/Kolkata" disabled={saving} />
            </div>
            <TextField label="Provider" value={proxyDraft.provider} onChange={(provider) => setProxyDraft((d) => ({ ...d, provider }))} disabled={saving} />
            <TextField label="Notes" value={proxyDraft.notes} onChange={(notes) => setProxyDraft((d) => ({ ...d, notes }))} disabled={saving} />
          </Modal.Body>
          <Modal.Footer>
            <Modal.Close asChild>
              <Button.Root variant="neutral" mode="stroke" size="small" disabled={saving}>Cancel</Button.Root>
            </Modal.Close>
            <Button.Root variant="primary" mode="filled" size="small" disabled={saving || !canSaveProxy} onClick={() => void saveProxy()}>
              {saving && <RiLoader4Line className="size-4 animate-spin" aria-hidden="true" />}
              {proxyFormFor === "new" ? "Add IP" : "Save"}
            </Button.Root>
          </Modal.Footer>
        </Modal.Content>
      </Modal.Root>

      <Modal.Root open={deletingProxy !== null} onOpenChange={(open) => { if (!open && !saving) setDeletingProxy(null); }}>
        <Modal.Content>
          <Modal.Header icon={RiDeleteBinLine}>
            <Modal.Title>Delete {deletingProxy?.label}?</Modal.Title>
            <Modal.Description>The IP is removed from this list. The proxy itself is not cancelled with your provider.</Modal.Description>
          </Modal.Header>
          <Modal.Footer>
            <Modal.Close asChild>
              <Button.Root variant="neutral" mode="stroke" size="small" disabled={saving}>Cancel</Button.Root>
            </Modal.Close>
            <Button.Root variant="error" mode="filled" size="small" disabled={saving} onClick={() => void confirmDeleteProxy()}>
              {saving && <RiLoader4Line className="size-4 animate-spin" aria-hidden="true" />}
              Delete
            </Button.Root>
          </Modal.Footer>
        </Modal.Content>
      </Modal.Root>

      <Modal.Root open={wrongAccount !== null} onOpenChange={(open) => { if (!open && wrongAccount) setPutOff((current) => new Set(current).add(wrongAccount.id)); }}>
        <Modal.Content>
          <Modal.Header icon={RiLinkM}>
            <Modal.Title>Linked to a different WhatsApp number</Modal.Title>
            <Modal.Description>
              {wrongAccount
                ? `${wrongAccount.name}'s WhatsApp Web is logged in as ${wrongAccount.linkedPhone}, not ${wrongAccount.phone}. Calls go out from the logged-in number, so this number won't call until you choose.`
                : ""}
            </Modal.Description>
          </Modal.Header>
          {wrongAccount && (
            <Modal.Body className="space-y-2 text-paragraph-sm text-text-sub-600">
              <p>
                <span className="text-label-sm text-text-strong-950">Use {wrongAccount.linkedPhone}</span> — keep this login and make it this calling number&apos;s number.
              </p>
              <p>
                <span className="text-label-sm text-text-strong-950">Link {wrongAccount.phone} instead</span> — discard this login (the number keeps its browser fingerprint) and link again from the phone with {wrongAccount.phone}. Afterwards, remove the extra device from {wrongAccount.linkedPhone}&apos;s WhatsApp → Linked devices.
              </p>
            </Modal.Body>
          )}
          <Modal.Footer>
            <Button.Root
              variant="neutral"
              mode="ghost"
              size="small"
              disabled={wrongAccount !== null && busyId === wrongAccount.id}
              onClick={() => wrongAccount && setPutOff((current) => new Set(current).add(wrongAccount.id))}
            >
              Decide later
            </Button.Root>
            <Button.Root
              variant="neutral"
              mode="stroke"
              size="small"
              disabled={wrongAccount !== null && busyId === wrongAccount.id}
              onClick={() => wrongAccount && void act(wrongAccount, () => startStationLink(wrongAccount.id, { fresh: true }))}
            >
              Link {wrongAccount?.phone} instead
            </Button.Root>
            <Button.Root
              variant="primary"
              mode="filled"
              size="small"
              disabled={wrongAccount !== null && busyId === wrongAccount.id}
              onClick={() => wrongAccount && void act(wrongAccount, () => updateCallingStation(wrongAccount.id, { phone: wrongAccount.linkedPhone! }))}
            >
              Use {wrongAccount?.linkedPhone}
            </Button.Root>
          </Modal.Footer>
        </Modal.Content>
      </Modal.Root>

      <Modal.Root open={deleting !== null} onOpenChange={(open) => { if (!open && !saving) setDeleting(null); }}>
        <Modal.Content>
          <Modal.Header icon={RiDeleteBinLine}>
            <Modal.Title>Delete {deleting?.name}?</Modal.Title>
            <Modal.Description>
              {deleting?.phone} stops being available for AI agent calls. Its recordings and call history stay. The browser profile itself is not deleted.
            </Modal.Description>
          </Modal.Header>
          <Modal.Footer>
            <Modal.Close asChild>
              <Button.Root variant="neutral" mode="stroke" size="small" disabled={saving}>Cancel</Button.Root>
            </Modal.Close>
            <Button.Root variant="error" mode="filled" size="small" disabled={saving} onClick={() => void confirmDelete()}>
              {saving && <RiLoader4Line className="size-4 animate-spin" aria-hidden="true" />}
              Delete
            </Button.Root>
          </Modal.Footer>
        </Modal.Content>
      </Modal.Root>
    </SettingsPage>
  );
}

function StationCard({ station, ai, rules, busy, onLink, onCancelLink, onToggle, onEdit, onDelete, onUseLinkedPhone }: {
  station: CallingStation;
  /** This number's own AI campaign limits (null fields: the organization's rule). */
  ai: StationAiSettings | null;
  rules: StationAiSettingsResponse["rules"] | null;
  busy: boolean;
  onLink: () => void;
  onCancelLink: () => void;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
  /** Renumber the card to the account WhatsApp Web is logged in as. */
  onUseLinkedPhone: () => void;
}) {
  const linking = station.link !== null;
  // Calls go out from the logged-in account, so a mismatch blocks calling until fixed.
  const wrongAccount = station.linkedPhone !== null && station.linkedPhone !== station.phone;
  const pausable = station.status === "active" || station.status === "paused";
  return (
    <Frame>
      <FramePanel className={cn("space-y-4", busy && "opacity-60")} aria-busy={busy || undefined}>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="truncate text-label-md text-text-strong-950">{station.name}</h3>
              <Badge.Root variant="light" size="medium" color={STATUS_COLOR[station.status]}>{STATUS_LABEL[station.status]}</Badge.Root>
              {station.busyCallId && (
                <Badge.Root variant="light" size="medium" color="blue">
                  <RiLoader4Line className="size-3 animate-spin" aria-hidden="true" />
                  On a call
                </Badge.Root>
              )}
              {station.openOn && !station.busyCallId && (
                <Badge.Root variant="light" size="medium" color="green" title={`WhatsApp Web is kept open on ${station.openOn}, so calls start right away`}>
                  Ready on {station.openOn}
                </Badge.Root>
              )}
            </div>
            <p className="text-paragraph-sm tabular-nums text-text-sub-600">
              {station.phone} · {LAUNCHER_LABEL[station.launcher]}
              {station.gologinProfileId ? ` · ${station.gologinProfileId}` : ""}
            </p>
            <p className="text-paragraph-xs text-text-soft-400">
              {station.lastSeenAt ? `Worker seen ${timeAgo(station.lastSeenAt)}` : "No worker has opened it yet"}
              {station.lastCallAt ? ` · last call ${timeAgo(station.lastCallAt)}` : ""}
            </p>
            <p className="text-paragraph-xs text-text-sub-600">{station.proxyLabel ? `IP: ${station.proxyLabel}` : "Own IP"}</p>
            {rules && (
              <p className="text-paragraph-xs text-text-sub-600">
                AI campaigns: {ai?.callsPerDay != null ? `${ai.callsPerDay} calls a day` : `${rules.callsPerDay} calls a day (rule)`} ·{" "}
                {ai?.callingHours ? hoursSummary(ai.callingHours) : "organization's calling hours"}
              </p>
            )}
            {station.linkedPhone && (
              <p className={cn("text-paragraph-xs tabular-nums", wrongAccount ? "text-error-base" : "text-text-sub-600")}>
                WhatsApp: logged in as {station.linkedPhone}
                {wrongAccount ? " — not this number, so it won't call" : ""}
              </p>
            )}
            {wrongAccount && (
              <div>
                <Button.Root variant="neutral" mode="stroke" size="xxsmall" disabled={busy} onClick={onUseLinkedPhone}>
                  Use {station.linkedPhone} as this number
                </Button.Root>
              </div>
            )}
            {station.launcher === "cloak" && (
              <p className="text-paragraph-xs text-text-soft-400">
                {station.profile.savedAt
                  ? `Profile: saved ${timeAgo(station.profile.savedAt)}${station.profile.bytes !== null ? ` · ${(station.profile.bytes / 1_000_000).toFixed(1)} MB` : ""} · v${station.profile.version}`
                  : "Profile: not saved yet"}
              </p>
            )}
            {station.lastError && <p className="text-paragraph-xs text-error-base">{station.lastError}</p>}
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {linking ? (
              <Button.Root variant="neutral" mode="stroke" size="xsmall" disabled={busy} onClick={onCancelLink}>Cancel linking</Button.Root>
            ) : (
              <Button.Root variant="neutral" mode="stroke" size="xsmall" disabled={busy || station.busyCallId !== null} onClick={onLink}>
                <Button.Icon as={RiLinkM} />
                {station.status === "onboarding" ? "Link WhatsApp" : "Relink WhatsApp"}
              </Button.Root>
            )}
            {pausable && (
              <Button.Root variant="neutral" mode="stroke" size="xsmall" disabled={busy} onClick={onToggle}>
                <Button.Icon as={station.status === "paused" ? RiPlayCircleLine : RiPauseCircleLine} />
                {station.status === "paused" ? "Resume" : "Pause"}
              </Button.Root>
            )}
            <Button.Root variant="neutral" mode="stroke" size="xsmall" disabled={busy} onClick={onEdit}>
              <Button.Icon as={RiPencilLine} />
              Edit
            </Button.Root>
            <Button.Root variant="error" mode="stroke" size="xsmall" disabled={busy} onClick={onDelete}>
              <Button.Icon as={RiDeleteBinLine} />
              Delete
            </Button.Root>
          </div>
        </div>
        {station.link && <LinkPanel link={station.link} />}
      </FramePanel>
    </Frame>
  );
}

function ProxyCard({ proxy, onEdit, onDelete }: { proxy: CallingProxy; onEdit: () => void; onDelete: () => void }) {
  const details = [proxy.country, proxy.timezone, proxy.provider].filter(Boolean).join(" · ");
  const assigned = proxy.stationId !== null;
  return (
    <Frame>
      <FramePanel>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="truncate text-label-md text-text-strong-950">{proxy.label}</h3>
              <Badge.Root variant="light" size="medium" color={assigned ? "blue" : "gray"}>
                {assigned ? `Used by ${proxy.stationName ?? "a number"}` : "Unassigned"}
              </Badge.Root>
            </div>
            <p className="font-mono text-paragraph-sm text-text-sub-600">{proxy.protocol}://{proxy.host}:{proxy.port}</p>
            {details && <p className="text-paragraph-xs text-text-soft-400">{details}</p>}
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <Button.Root variant="neutral" mode="stroke" size="xsmall" onClick={onEdit}>
              <Button.Icon as={RiPencilLine} />
              Edit
            </Button.Root>
            <Button.Root
              variant="error"
              mode="stroke"
              size="xsmall"
              disabled={assigned}
              title={assigned ? "Unassign it from its number first" : undefined}
              onClick={onDelete}
            >
              <Button.Icon as={RiDeleteBinLine} />
              Delete
            </Button.Root>
          </div>
        </div>
      </FramePanel>
    </Frame>
  );
}

function LinkPanel({ link }: { link: NonNullable<CallingStation["link"]> }) {
  const [zoomed, setZoomed] = useState(false);
  return (
    <div className="space-y-4 rounded-xl bg-bg-weak-50 p-4 ring-1 ring-inset ring-stroke-soft-200">
      <div className="space-y-3">
        <p className="text-label-sm text-text-strong-950">Link this number to WhatsApp Web</p>
        {link.code ? (
          <p
            aria-label={`Linking code ${link.code.split("").join(" ")}`}
            className="w-fit rounded-lg bg-bg-white-0 px-4 py-2 font-mono text-title-h4 tracking-[0.25em] text-text-strong-950 ring-1 ring-inset ring-stroke-soft-200"
          >
            {link.code}
          </p>
        ) : (
          <p className="flex items-center gap-2 text-paragraph-sm text-text-sub-600">
            <RiLoader4Line className="size-4 animate-spin" aria-hidden="true" />
            {link.screenshot ? "Waiting for a code. If WhatsApp Web shows a QR instead, scan it." : "Waiting for a call worker to open WhatsApp Web…"}
          </p>
        )}
        <p className="text-paragraph-sm text-text-sub-600">
          On the phone: WhatsApp → Settings → Linked devices → Link a device → Link with phone number instead, then type this code.
        </p>
      </div>
      {link.screenshot && (
        <>
          {/* Full width, so a QR is scannable straight off the screen; click for full size. */}
          <button
            type="button"
            onClick={() => setZoomed(true)}
            aria-label="Open WhatsApp Web's login screen full size"
            className="block w-full cursor-zoom-in overflow-hidden rounded-lg bg-bg-white-0 ring-1 ring-inset ring-stroke-soft-200"
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- a data: URL screenshot from the worker */}
            <img src={link.screenshot} alt="WhatsApp Web's login screen in the cloud browser" className="block w-full" />
          </button>
          <p className="text-paragraph-xs text-text-soft-400">The screenshot refreshes every few seconds. Click it to open it full size.</p>
          <Modal.Root open={zoomed} onOpenChange={setZoomed}>
            <Modal.Content className="max-w-[min(96vw,1400px)]">
              <Modal.Header>
                <Modal.Title>WhatsApp Web login screen</Modal.Title>
              </Modal.Header>
              <Modal.Body>
                {/* eslint-disable-next-line @next/next/no-img-element -- a data: URL screenshot from the worker */}
                <img src={link.screenshot} alt="WhatsApp Web's login screen in the cloud browser, full size" className="block w-full rounded-lg" />
              </Modal.Body>
            </Modal.Content>
          </Modal.Root>
        </>
      )}
    </div>
  );
}
