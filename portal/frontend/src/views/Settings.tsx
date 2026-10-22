// SETTINGS: how the laptop reaches the car. Connection status and the connect step log (as `connect`
// events on the websocket), the host/MAC/mDNS settings, the Wi-Fi USB stick for a fresh venue
// network, the decider URL and the voice path. Passwords go to the backend once and never show here.

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import s from "./Settings.module.css";
import { apiGet, apiPost, errText } from "../api";
import type { ApiResult } from "../api";
import type { RunStore } from "../ws";
import { fmtTime } from "../ws";
import { SAFETY_LINE } from "../types";
import type { CarSettings, CarStatus, ConnectPayload, PortalEvent, WifiUsbReport, WifiUsbWriteResult } from "../types";
import { VOICE_LABEL } from "../usePtt";

type Toast = { tone: "ok" | "err" | ""; text: string };
const quiet: Toast = { tone: "", text: "" };

function useGet<T>(url: string, everyMs = 0): { r: ApiResult<T> | null; reload: () => Promise<void> } {
  const [r, setR] = useState<ApiResult<T> | null>(null);
  const reload = useCallback(async () => setR(await apiGet<T>(url)), [url]);
  useEffect(() => {
    void reload();
    if (!everyMs) return;
    const t = window.setInterval(() => void reload(), everyMs);
    return () => window.clearInterval(t);
  }, [reload, everyMs]);
  return { r, reload };
}

function stepsSince(events: PortalEvent[], sinceSeq: number): PortalEvent<ConnectPayload>[] {
  const bySteps = new Map<string, PortalEvent<ConnectPayload>>();
  for (const e of events) {
    if (e.type !== "connect" || e.seq < sinceSeq) continue;
    const c = e as unknown as PortalEvent<ConnectPayload>;
    bySteps.set(c.payload.step, c); // latest status per step, first-seen order
  }
  return [...bySteps.values()];
}

export function Settings({ store, audioEnabled, setAudioEnabled }: { store: RunStore; audioEnabled: boolean; setAudioEnabled: (on: boolean) => void }) {
  // Car connection
  const status = useGet<CarStatus>("/api/car/status", 5000);
  const settings = useGet<CarSettings>("/api/car/settings");
  const [host, setHost] = useState("");
  const [mac, setMac] = useState("");
  const [mdns, setMdns] = useState("");
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    if (loaded || !settings.r?.ok) return;
    setHost(settings.r.data?.host ?? ""); setMac(settings.r.data?.mac ?? ""); setMdns(settings.r.data?.mdns ?? "");
    setLoaded(true);
  }, [settings.r, loaded]);
  const [connT, setConnT] = useState<Toast>(quiet);
  const [sinceSeq, setSinceSeq] = useState(0);
  const steps = useMemo(() => stepsSince(store.events, sinceSeq), [store.events, sinceSeq]);
  const connect = async () => {
    const lastSeq = store.events.length ? store.events[store.events.length - 1].seq : 0;
    setSinceSeq(lastSeq + 1);
    setConnT({ tone: "", text: "connecting…" });
    const r = await apiPost<CarStatus & { accepted?: boolean; reason?: string }>("/api/car/connect", host.trim() ? { host: host.trim() } : {});
    setConnT(errText(r) ? { tone: "err", text: errText(r)! } : { tone: r.ok && r.data?.connected ? "ok" : "err", text: r.ok ? (r.data?.connected ? `connected over ${r.data.how}` : (r.data?.error ?? "not connected")) : "" });
    void status.reload();
  };
  const disconnect = async () => {
    const r = await apiPost<unknown>("/api/car/disconnect");
    setConnT(errText(r) ? { tone: "err", text: errText(r)! } : { tone: "ok", text: "disconnected" });
    void status.reload();
  };
  const [setT, setSetT] = useState<Toast>(quiet);
  const saveSettings = async (e: FormEvent) => {
    e.preventDefault();
    const r = await apiPost<CarSettings>("/api/car/settings", { host: host.trim() || null, mac: mac.trim() || null, mdns: mdns.trim() || null });
    setSetT(errText(r) ? { tone: "err", text: errText(r)! } : { tone: "ok", text: "saved" });
  };

  // Wi-Fi stick
  const [ssid, setSsid] = useState("");
  const [psk, setPsk] = useState("");
  const [wifiT, setWifiT] = useState<Toast>(quiet);
  const [written, setWritten] = useState<string[] | null>(null);
  const [report, setReport] = useState<ApiResult<WifiUsbReport> | null>(null);
  const writeStick = async (e: FormEvent) => {
    e.preventDefault();
    if (!ssid.trim()) { setWifiT({ tone: "err", text: "SSID is required" }); return; }
    setWifiT({ tone: "", text: "writing…" });
    const r = await apiPost<WifiUsbWriteResult>("/api/car/wifi-usb", { ssid: ssid.trim(), password: psk });
    if (!r.ok) { setWifiT({ tone: "err", text: errText(r)! }); setWritten(null); return; }
    const vols = r.data?.written ?? [];
    setWritten(vols);
    setWifiT({ tone: r.data?.accepted === false ? "err" : "ok", text: r.data?.accepted === false ? (r.data?.reason ?? "no writable USB volume mounted") : `written to ${vols.length} volume(s)` });
    setPsk("");
  };
  const readReport = async () => setReport(await apiGet<WifiUsbReport>("/api/car/wifi-usb"));

  // Decider and voice from /api/state
  const st = store.state;
  const rs = st?.runtime_status;
  const deciderUrl = st?.decider_url ?? rs?.decider_url ?? (rs?.decider as { url?: string } | undefined)?.url ?? null;
  const voice = rs?.voice;
  const car = status.r?.ok ? status.r.data : null;

  return (
    <>
      <main className={s.grid}>
        <section className={s.card} aria-label="car connection">
          <h2 className={s.cardTitle}><span>Car connection</span><button className="btnQuiet" onClick={() => void status.reload()}>refresh</button></h2>
          <div className={s.status}>
            <span className={`${s.statusBig} ${car?.connected ? "Proceed" : car?.busy ? "Guide" : "idle"}`}>{car ? (car.connected ? "CONNECTED" : car.busy ? "CONNECTING" : "NOT CONNECTED") : (errText(status.r) ?? "loading…")}</span>
            {car && <span className={`chip ${car.how === "none" ? "off" : "ok"}`}><span className="dot" />{car.how}{car.found_by && <small>via {car.found_by}</small>}</span>}
            {car?.error && <span className="toast err">{car.error}</span>}
          </div>
          {car && (
            <dl className={s.kv}>
              <dt>host</dt><dd>{car.host || "—"}{car.ssh_host ? ` · ssh ${car.ssh_host}` : ""}</dd>
              <dt>rosbridge</dt><dd>{car.rosbridge ? `${car.rosbridge.connected ? "connected" : "down"}${car.rosbridge.rtt_ms != null ? ` · ${car.rosbridge.rtt_ms} ms` : ""}` : `${car.rosbridge_port ? `port ${car.rosbridge_port}` : "—"}${car.rtt_ms != null ? ` · ${car.rtt_ms} ms rtt` : ""}`}</dd>
              <dt>console</dt><dd>{car.console ? `${car.console.ok ? "ok" : "down"}${car.console.fps != null ? ` · ${car.console.fps} fps` : ""}` : (car.console_url ?? "—")}</dd>
              <dt>battery</dt><dd>{(car.battery ?? car.runtime_status?.battery) != null ? `${car.battery ?? car.runtime_status?.battery}/10` : "—"}</dd>
              <dt>deadman</dt><dd>{car.deadman ?? car.runtime_status?.deadman ?? "—"}{car.runtime_status?.armed != null ? ` · ${car.runtime_status.armed ? "armed" : "not armed"}` : ""}</dd>
              <dt>session</dt><dd>{car.session ?? car.runtime_status?.session ?? "—"}</dd>
            </dl>
          )}
          <div className={s.row}>
            <button className="btnPrimary" onClick={connect}>Connect</button>
            <button onClick={disconnect}>Disconnect</button>
            <span className={`toast ${connT.tone}`}>{connT.text}</span>
          </div>
          <div className={s.steps} aria-label="connect steps">
            {steps.length === 0 && <div className="hint">Connect steps (find the car, SSH tunnel or direct, rosbridge, console, heartbeat) stream here as `connect` events.</div>}
            {steps.map((c) => (
              <div key={c.payload.step} className={`${s.step} ${s[c.payload.status]}`}>
                <span className={s.mark} aria-label={c.payload.status} />
                <span className={s.stepName}>{c.payload.step}</span>
                <span className={s.stepStatus}>{c.payload.status} · {fmtTime(c.ts)}</span>
                {c.payload.detail && <span className={s.stepDetail}>{c.payload.detail}</span>}
              </div>
            ))}
          </div>
        </section>

        <section className={s.card} aria-label="car settings">
          <h2 className={s.cardTitle}><span>Car address</span><span className="dim">{errText(settings.r) ?? ""}</span></h2>
          <form onSubmit={saveSettings} className={s.row}>
            <label className={s.field}><span>host override</span><input value={host} onChange={(e) => setHost(e.target.value)} placeholder="192.168.1.23 or deepracer.local" /></label>
            <label className={s.field}><span>MAC</span><input value={mac} onChange={(e) => setMac(e.target.value)} placeholder="aa:bb:cc:dd:ee:ff" /></label>
            <label className={s.field}><span>mDNS name</span><input value={mdns} onChange={(e) => setMdns(e.target.value)} placeholder="deepracer" /></label>
            <button type="submit" className="btnPrimary">Save</button>
            <span className={`toast ${setT.tone}`}>{setT.text}</span>
          </form>
          <div className="hint">The host override wins; otherwise the backend looks the MAC up in the ARP table, then mDNS. Passwords live in the keychain or env, never here.</div>
        </section>

        <section className={s.card} aria-label="car wifi">
          <h2 className={s.cardTitle}><span>Car Wi-Fi (USB stick)</span></h2>
          <form onSubmit={writeStick} className={s.row}>
            <label className={s.field}><span>SSID</span><input value={ssid} onChange={(e) => setSsid(e.target.value)} autoComplete="off" /></label>
            <label className={s.field}><span>password</span><input type="password" value={psk} onChange={(e) => setPsk(e.target.value)} autoComplete="new-password" /></label>
            <button type="submit" className="btnPrimary">Write to USB stick</button>
            <button type="button" onClick={readReport}>Read report</button>
          </form>
          <div className={`toast ${wifiT.tone}`}>{wifiT.text}</div>
          {written && written.length > 0 && <div className="hint">written: <span className="mono">{written.join(", ")}</span></div>}
          <div className="hint">Plug the stick into the running car; blue blinking means it is trying; red means it failed; the report lands on the stick as device-status.txt.</div>
          {report && (report.ok ? (
            Object.keys(report.data?.reports ?? {}).length ? (
              Object.entries(report.data.reports).map(([vol, text]) => (
                <div key={vol}><div className="label">{vol}</div><pre className={s.report}>{text}</pre></div>
              ))
            ) : <div className="hint">{report.data?.volumes?.length ? `no device-status.txt yet on ${report.data.volumes.join(", ")}` : "no USB stick mounted"}</div>
          ) : <div className="toast err">{errText(report)}</div>)}
        </section>

        <section className={s.card} aria-label="decider and voice">
          <h2 className={s.cardTitle}><span>Decider</span></h2>
          <div className={s.url}>{deciderUrl ?? <span className="dim">DECIDER_URL not reported by /api/state</span>}</div>
          <div className="hint">{SAFETY_LINE} The decider answers the envelope and frame questions; the pen, the hop cap, the on-car deadman and the marshal stop the car.</div>
          <h2 className={s.cardTitle} style={{ marginTop: 8 }}><span>Voice</span><span className="dim">{st?.runtime ?? ""}</span></h2>
          <label className={s.toggle}>
            <input type="checkbox" checked={audioEnabled} onChange={(e) => setAudioEnabled(e.target.checked)} />
            Browser audio (microphone to /ws/audio, rover speech on the house speakers)
          </label>
          <dl className={s.kv}>
            <dt>Nova Sonic</dt><dd>{voice ? `${voice.state}${voice.error ? ` · ${voice.error}` : ""}` : "not reported"}</dd>
            {voice && <><dt>status</dt><dd>{VOICE_LABEL[voice.state] ?? voice.state}</dd></>}
            {voice?.listeners != null && <><dt>audio listeners</dt><dd>{voice.listeners}</dd></>}
            <dt>portal</dt><dd>{store.conn} · session {st?.session ?? "—"} · {st?.events ?? 0} events</dd>
            {st?.console_url && <><dt>console</dt><dd>{st.console_url}</dd></>}
          </dl>
        </section>
      </main>
      <footer className="footer">
        <span className="safety"><b>{SAFETY_LINE}</b></span>
        <span className="keys">1 2 3 views</span>
      </footer>
    </>
  );
}
