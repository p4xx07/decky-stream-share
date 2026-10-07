import { callable, definePlugin } from "@decky/api";
import { ButtonItem, PanelSection, PanelSectionRow, TextField, staticClasses } from "@decky/ui";
import { useEffect, useRef, useState } from "react";
import { FaDesktop } from "react-icons/fa";

type Layout = "side" | "wide" | "stack" | "full";
type StreamStatus = {
  running: boolean; mode: string; layout: Layout; message: string; log: string; backend_version?: string;
  capture_diagnostic: string;
  relay_url: string; room_connected: boolean; room_code: string;
  peer_connected: boolean; relay_message: string;
  sent_frames: number; received_frames: number;
  microphone_enabled: boolean; speaker_enabled: boolean;
  gba_prepared: boolean; gba_running: boolean; setup_message: string; gba_diagnostic?: string;
};
const getStatus = callable<[], StreamStatus>("get_status");
const startView = callable<[mode: string], StreamStatus>("start_view");
const stopView = callable<[], StreamStatus>("stop_view");
const setViewLayout = callable<[layout: Layout], StreamStatus>("set_layout");
const startRoom = callable<[relayUrl: string, joinCode: string], StreamStatus>("start_room");
const stopRoom = callable<[], StreamStatus>("stop_room");
const setMicrophone = callable<[enabled: boolean], StreamStatus>("set_microphone");
const setSpeaker = callable<[enabled: boolean], StreamStatus>("set_speaker");
const prepareGba = callable<[], StreamStatus>("prepare_gba");
const disableGba = callable<[], StreamStatus>("disable_gba");
const restoreGba = callable<[], StreamStatus>("restore_gba");
const layouts: Layout[] = ["side", "wide", "stack", "full"];
const layoutNames: Record<Layout, string> = {
  side: "Equal side by side", wide: "Larger local game", stack: "Top and bottom", full: "Full local game",
};
const FRONTEND_BUILD = "0.1.0-alpha.8";

async function within<T>(promise: Promise<T>, milliseconds: number, message: string): Promise<T> {
  let timer: number | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = window.setTimeout(() => reject(new Error(message)), milliseconds);
  });
  try { return await Promise.race([promise, timeout]); }
  finally { if (timer !== undefined) window.clearTimeout(timer); }
}

function errorMessage(caught: unknown): string {
  return caught instanceof Error ? caught.message : String(caught);
}

function Content() {
  const [status, setStatus] = useState<StreamStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [statusError, setStatusError] = useState("");
  const [lastAction, setLastAction] = useState("None yet");
  const [roomError, setRoomError] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [showLogs, setShowLogs] = useState(false);
  const [relayUrl, setRelayUrl] = useState("");
  const [joinCode, setJoinCode] = useState("");
  const relayLoaded = useRef(false);

  useEffect(() => {
    let active = true;
    let refreshing = false;
    const refresh = async () => {
      if (refreshing) return;
      refreshing = true;
      try {
        const next = await within(getStatus(), 6000, "Stream Share backend did not answer. Reload it in Decky Settings → Plugins → Stream Share → ⋯.");
        if (active) {
          setStatus(next);
          setStatusError("");
          if (next.room_connected) setRoomError("");
          if (!relayLoaded.current) { setRelayUrl(next.relay_url); relayLoaded.current = true; }
        }
      } catch (caught) {
        if (active) setStatusError(`Status check: ${errorMessage(caught)}`);
      } finally { refreshing = false; }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 2000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  const run = async (mode: "pattern" | "live" | "direct") => {
    setBusy(true);
    setError("");
    try { setStatus(await startView(mode)); }
    catch (caught) { setError(String(caught)); }
    finally { setBusy(false); }
  };

  const stop = async () => {
    setBusy(true);
    try { setStatus(await stopView()); }
    catch (caught) { setError(String(caught)); }
    finally { setBusy(false); }
  };

  const changeLayout = async () => {
    setBusy(true);
    setError("");
    try {
      const current = status?.layout || "side";
      const next = layouts[(layouts.indexOf(current) + 1) % layouts.length];
      setStatus(await setViewLayout(next));
    } catch (caught) { setError(String(caught)); }
    finally { setBusy(false); }
  };

  const setupGba = async (action: "prepare" | "disable" | "restore") => {
    const name = action === "prepare" ? "GBA setup" : action === "disable" ? "Disable GBA sharing" : "Restore ES-DE settings";
    setBusy(true);
    setError("");
    setLastAction(`${name}: running`);
    try {
      const request = action === "prepare" ? prepareGba() : action === "disable" ? disableGba() : restoreGba();
      setStatus(await within(request, 12000, `${name} did not answer within 12 seconds. Check backend status above.`));
      setStatusError("");
      setLastAction(`${name}: completed`);
    } catch (caught) {
      const detail = `${name}: ${errorMessage(caught)}`;
      setError(detail);
      setLastAction(detail);
    }
    finally { setBusy(false); }
  };

  const connectRoom = async (code: string) => {
    setBusy(true);
    setConnecting(true);
    setRoomError("");
    try {
      setStatus(await within(startRoom(relayUrl, code), 15000,
        "Room connection did not answer within 15 seconds. Check backend status above."));
    } catch (caught) { setRoomError(errorMessage(caught)); }
    finally { setConnecting(false); setBusy(false); }
  };

  const disconnectRoom = async () => {
    setBusy(true);
    setRoomError("");
    try { setStatus(await stopRoom()); }
    catch (caught) { setRoomError(errorMessage(caught)); }
    finally { setBusy(false); }
  };

  const toggleAudio = async (which: "microphone" | "speaker") => {
    setBusy(true);
    setError("");
    try {
      setStatus(which === "microphone"
        ? await setMicrophone(!status?.microphone_enabled)
        : await setSpeaker(!status?.speaker_enabled));
    } catch (caught) { setError(String(caught)); }
    finally { setBusy(false); }
  };

  return <>
    <PanelSection title="Stream Share">
      <PanelSectionRow>For EmuDeck GBA: set up once, restart ES-DE, then launch the game. Connect to a room and start the view.</PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={busy || !!status?.running || !!statusError} onClick={() => void setupGba("prepare")}>{status?.gba_prepared ? "Refresh GBA setup" : "Set up GBA sharing"}</ButtonItem></PanelSectionRow>
      <PanelSectionRow>{status?.gba_running ? "Stream Share GBA game detected" : status?.gba_prepared ? "Ready for GBA launch in ES-DE" : "GBA sharing not set up"}</PanelSectionRow>
      {status?.setup_message && <PanelSectionRow>{status.setup_message}</PanelSectionRow>}
      <PanelSectionRow><ButtonItem layout="below" disabled={busy || (!!status?.running && status?.mode !== "direct")} onClick={() => void changeLayout()}>Layout: {layoutNames[status?.layout || "side"]} (change)</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={busy || !!status?.running} onClick={() => void run("pattern")}>Check display layer</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={busy || !!status?.running || !status?.gba_running} onClick={() => void run("direct")}>Start GBA split view</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={busy || !status?.running} onClick={() => void stop()}>Stop split view</ButtonItem></PanelSectionRow>
      <PanelSectionRow>{status?.message || "Loading status..."}</PanelSectionRow>
      {statusError && <PanelSectionRow><div style={{ color: "#ffb4a9", overflowWrap: "anywhere" }}>{statusError}</div></PanelSectionRow>}
      {error && <PanelSectionRow><div>Error: {error}</div></PanelSectionRow>}
      <PanelSectionRow><ButtonItem layout="below" onClick={() => setShowLogs(!showLogs)}>{showLogs ? "Hide logs" : "Show logs"}</ButtonItem></PanelSectionRow>
      {showLogs && <PanelSectionRow>UI {FRONTEND_BUILD}; backend {statusError ? "no response" : status?.backend_version || "unknown"}</PanelSectionRow>}
      {showLogs && <PanelSectionRow>Last action: {lastAction}</PanelSectionRow>}
      {showLogs && <PanelSectionRow>Backend status: {statusError || "connected"}</PanelSectionRow>}
      {showLogs && status?.gba_diagnostic && <PanelSectionRow><div style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{status.gba_diagnostic}</div></PanelSectionRow>}
      {showLogs && <PanelSectionRow><ButtonItem layout="below" disabled={busy || !!status?.running} onClick={() => void run("live")}>Legacy captured view (other games)</ButtonItem></PanelSectionRow>}
      {showLogs && status?.gba_prepared && <PanelSectionRow><ButtonItem layout="below" disabled={busy || !!status?.running} onClick={() => void setupGba("disable")}>Disable GBA sharing for next launch</ButtonItem></PanelSectionRow>}
      {showLogs && <PanelSectionRow><ButtonItem layout="below" disabled={busy} onClick={() => void setupGba("restore")}>Restore ES-DE GBA settings</ButtonItem></PanelSectionRow>}
      {showLogs && status?.capture_diagnostic && <PanelSectionRow>{status.capture_diagnostic}</PanelSectionRow>}
      {showLogs && status?.log && <PanelSectionRow><div style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{status.log}</div></PanelSectionRow>}
    </PanelSection>
    <PanelSection title="PC relay">
      <PanelSectionRow><TextField label="PC relay URL" value={relayUrl} onChange={event => { relayLoaded.current = true; setRelayUrl(event.target.value); }} /></PanelSectionRow>
      <PanelSectionRow><TextField label="Friend's room code" value={joinCode} onChange={event => setJoinCode(event.target.value)} /></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={busy || !!status?.room_connected} onClick={() => void connectRoom("")}>Create room</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={busy || !!status?.room_connected || !joinCode.trim()} onClick={() => void connectRoom(joinCode)}>Join room</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={busy || !status?.room_connected} onClick={() => void disconnectRoom()}>Leave room</ButtonItem></PanelSectionRow>
      {status?.room_code && <PanelSectionRow>Room code: {status.room_code}</PanelSectionRow>}
      <PanelSectionRow>{connecting ? "Connecting to PC relay…" : (status?.relay_message || "Not connected")}</PanelSectionRow>
      {roomError && <PanelSectionRow><div style={{ color: "#ffb4a9", overflowWrap: "anywhere" }}>Error: {roomError}</div></PanelSectionRow>}
      {showLogs && !!status?.room_connected && <PanelSectionRow>Video frames: sent {status.sent_frames}, received {status.received_frames}</PanelSectionRow>}
      {!!status?.room_connected && <PanelSectionRow><ButtonItem layout="below" disabled={busy} onClick={() => void toggleAudio("microphone")}>Microphone: {status.microphone_enabled ? "On" : "Off"}</ButtonItem></PanelSectionRow>}
      {!!status?.room_connected && <PanelSectionRow><ButtonItem layout="below" disabled={busy} onClick={() => void toggleAudio("speaker")}>Friend audio: {status.speaker_enabled ? "On" : "Off"}</ButtonItem></PanelSectionRow>}
    </PanelSection>
  </>;
}

export default definePlugin(() => ({
  name: "Stream Share",
  titleView: <div className={staticClasses.Title}>Stream Share</div>,
  content: <Content />,
  icon: <FaDesktop />,
}));
