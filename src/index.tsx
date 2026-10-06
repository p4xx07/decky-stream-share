import { callable, definePlugin } from "@decky/api";
import { ButtonItem, PanelSection, PanelSectionRow, TextField, staticClasses } from "@decky/ui";
import { useEffect, useRef, useState } from "react";
import { FaDesktop } from "react-icons/fa";

type Layout = "side" | "wide" | "stack";
type StreamStatus = {
  running: boolean; mode: string; layout: Layout; message: string; log: string;
  capture_diagnostic: string;
  relay_url: string; room_connected: boolean; room_code: string;
  peer_connected: boolean; relay_message: string;
  sent_frames: number; received_frames: number;
  microphone_enabled: boolean; speaker_enabled: boolean;
};
const getStatus = callable<[], StreamStatus>("get_status");
const startView = callable<[mode: string], StreamStatus>("start_view");
const stopView = callable<[], StreamStatus>("stop_view");
const setViewLayout = callable<[layout: Layout], StreamStatus>("set_layout");
const startRoom = callable<[relayUrl: string, joinCode: string], StreamStatus>("start_room");
const stopRoom = callable<[], StreamStatus>("stop_room");
const setMicrophone = callable<[enabled: boolean], StreamStatus>("set_microphone");
const setSpeaker = callable<[enabled: boolean], StreamStatus>("set_speaker");
const layouts: Layout[] = ["side", "wide", "stack"];
const layoutNames: Record<Layout, string> = {
  side: "Equal side by side", wide: "Larger local game", stack: "Top and bottom",
};

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
        const next = await within(getStatus(), 6000, "Decky backend did not respond. Reinstall the latest Stream Share ZIP and reopen Decky.");
        if (active) {
          setStatus(next);
          if (next.room_connected) setRoomError("");
          if (!relayLoaded.current) { setRelayUrl(next.relay_url); relayLoaded.current = true; }
        }
      } catch (caught) {
        if (active) setRoomError(errorMessage(caught));
      } finally { refreshing = false; }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 2000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  const run = async (mode: "pattern" | "live") => {
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

  const connectRoom = async (code: string) => {
    setBusy(true);
    setConnecting(true);
    setRoomError("");
    try {
      setStatus(await within(startRoom(relayUrl, code), 15000,
        "Decky backend did not answer within 15 seconds. Reinstall the latest Stream Share ZIP and reopen Decky."));
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
      <PanelSectionRow>Start a game, connect both Decks to a room, then start split view. Your complete game fits in its pane beside your friend's game.</PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={busy || !!status?.running} onClick={() => void changeLayout()}>Layout: {layoutNames[status?.layout || "side"]} (change)</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={busy || !!status?.running} onClick={() => void run("pattern")}>Check display layer</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={busy || !!status?.running} onClick={() => void run("live")}>Start split view</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={busy || !status?.running} onClick={() => void stop()}>Stop split view</ButtonItem></PanelSectionRow>
      <PanelSectionRow>{status?.message || "Loading status..."}</PanelSectionRow>
      {error && <PanelSectionRow><div>Error: {error}</div></PanelSectionRow>}
      <PanelSectionRow><ButtonItem layout="below" onClick={() => setShowLogs(!showLogs)}>{showLogs ? "Hide logs" : "Show logs"}</ButtonItem></PanelSectionRow>
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
