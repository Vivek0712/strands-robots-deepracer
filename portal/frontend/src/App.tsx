// Pit Wall shell: one socket, one store, three views (1 Stage, 2 Operator, 3 Settings) and the two
// booth kiosks on ?kiosk=simon|judge. Keys: 1/2/3 switch views, space = push-to-talk, Esc = STOP ALL.
// Physics stops the car; the decider explains; this app is the narrator's screen.

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePortal } from "./ws";
import { usePtt, readAudioEnabled, writeAudioEnabled } from "./usePtt";
import { Stage } from "./views/Stage";
import { Operator } from "./views/Operator";
import { Settings } from "./views/Settings";
import { ApprovalModal } from "./components/ApprovalModal";
import { JudgeKiosk } from "./panels/Judge";
import { SimonKiosk } from "./panels/Simon";
import kk from "./panels/Kiosk.module.css";
import { SAFETY_LINE, SAFETY_DETAIL } from "./types";

type View = "stage" | "operator" | "settings";
type Kiosk = "simon" | "judge" | null;
const VIEWS: { id: View; key: string; label: string }[] = [
  { id: "stage", key: "1", label: "Stage" },
  { id: "operator", key: "2", label: "Operator" },
  { id: "settings", key: "3", label: "Settings" },
];

function kioskFromUrl(): Kiosk {
  const k = new URLSearchParams(location.search).get("kiosk");
  return k === "simon" || k === "judge" ? k : null;
}
function viewFromHash(): View {
  const h = location.hash.replace("#", "");
  return h === "operator" || h === "settings" ? h : "stage";
}
function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}

export default function App() {
  const { store, send } = usePortal();
  const kiosk = useMemo(kioskFromUrl, []);
  const [view, setViewState] = useState<View>(viewFromHash);
  const setView = useCallback((v: View) => { setViewState(v); history.replaceState(null, "", v === "stage" ? "#" : `#${v}`); }, []);
  const [pttHeld, setPtt] = useState(false);
  const [audioEnabled, setAudioState] = useState(readAudioEnabled);
  const setAudioEnabled = (on: boolean) => { writeAudioEnabled(on); setAudioState(on); };
  const ptt = usePtt(send, pttHeld, audioEnabled);

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); send({ op: "stop_all" }); return; }
      if (isTyping(e.target)) return;
      if (e.code === "Space" && !e.repeat) { e.preventDefault(); setPtt(true); return; }
      if (!kiosk && !e.metaKey && !e.ctrlKey && !e.altKey) {
        const v = VIEWS.find((x) => x.key === e.key);
        if (v) setView(v.id);
      }
    };
    const up = (e: KeyboardEvent) => { if (e.code === "Space" && !isTyping(e.target)) { e.preventDefault(); setPtt(false); } };
    const pointer = (e: Event) => setPtt(Boolean((e as CustomEvent<boolean>).detail));
    const blur = () => setPtt(false);
    const hash = () => setViewState(viewFromHash());
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("pitwall:ptt", pointer);
    window.addEventListener("blur", blur);
    window.addEventListener("hashchange", hash);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("pitwall:ptt", pointer);
      window.removeEventListener("blur", blur);
      window.removeEventListener("hashchange", hash);
    };
  }, [send, kiosk, setView]);

  const body = store.state?.body ?? "sim";
  const session = store.state?.session;

  const topbar = (
    <header className="topbar">
      <div className="brand">Pit Wall<small>agentic DeepRacer on strands-robots{kiosk ? ` · ${kiosk === "simon" ? "Simon Says" : "Frame Judge"} kiosk` : ""}</small></div>
      {!kiosk && (
        <nav className="nav" aria-label="views">
          {VIEWS.map((v) => <button key={v.id} className={view === v.id ? "on" : ""} onClick={() => setView(v.id)} aria-current={view === v.id}><kbd>{v.key}</kbd>{v.label}</button>)}
        </nav>
      )}
      <div className="topmeta">
        {kiosk && (
          <span className="nav">
            <button className={body === "sim" ? "on" : ""} onClick={() => send({ op: "body", active: "sim" })}>SIM</button>
            <button className={body === "car" ? "on" : ""} onClick={() => send({ op: "body", active: "car" })}>CAR</button>
          </span>
        )}
        <span>{session ?? "—"}</span>
        {view !== "stage" && <span>{store.state?.runtime ?? ""}</span>}
        <span className={`chip ${store.conn === "open" ? "ok" : store.conn === "connecting" ? "warn" : "bad"}`} style={{ padding: "2px 10px", fontSize: 13 }}><span className="dot" />{store.conn}</span>
      </div>
    </header>
  );

  if (kiosk) {
    const footer = (
      <footer className="footer">
        <span className="safety"><b>{SAFETY_LINE}</b> <span>{SAFETY_DETAIL}</span></span>
        <span className="keys">space = talk · esc = stop all</span>
      </footer>
    );
    return (
      <div className="app">
        {topbar}
        <main className={`${kk.page} ${kiosk === "simon" ? kk.simon : kk.judge}`}>
          {kiosk === "simon" ? <SimonKiosk body={body} /> : <JudgeKiosk session={session} body={body} />}
        </main>
        {footer}
      </div>
    );
  }

  return (
    <div className={`app ${view === "stage" ? "" : "scroll"}`} data-view={view}>
      {topbar}
      {view === "stage" && <Stage store={store} send={send} pttHeld={pttHeld} ptt={ptt} />}
      {view === "operator" && <Operator store={store} send={send} pttHeld={pttHeld} ptt={ptt} />}
      {view === "settings" && <Settings store={store} audioEnabled={audioEnabled} setAudioEnabled={setAudioEnabled} />}
      {view === "stage" && <ApprovalModal pending={store.pending} send={send} />}
    </div>
  );
}
