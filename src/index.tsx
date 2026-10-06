import { callable, definePlugin } from "@decky/api";
import { ButtonItem, PanelSection, PanelSectionRow, staticClasses } from "@decky/ui";
import { useEffect, useState } from "react";
import { FaDesktop } from "react-icons/fa";

type ProbeStatus = { running: boolean; mode: string; message: string; log: string };
const getStatus = callable<[], ProbeStatus>("get_status");
const startProbe = callable<[mode: string], ProbeStatus>("start_probe");
const stopProbe = callable<[], ProbeStatus>("stop_probe");

function Content() {
  const [status, setStatus] = useState<ProbeStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const next = await getStatus();
        if (active) setStatus(next);
      } catch (caught) {
        if (active) setError(String(caught));
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 2000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);

  const run = async (mode: "pattern" | "live") => {
    setBusy(true);
    setError("");
    try { setStatus(await startProbe(mode)); }
    catch (caught) { setError(String(caught)); }
    finally { setBusy(false); }
  };

  const stop = async () => {
    setBusy(true);
    try { setStatus(await stopProbe()); }
    catch (caught) { setError(String(caught)); }
    finally { setBusy(false); }
  };

  return <>
    <PanelSection title="Split-view feasibility test">
      <PanelSectionRow>Start a game, then run Live game view. Your complete game should appear on the left; the right side is a test pattern. This does not connect to a friend yet.</PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={busy || !!status?.running} onClick={() => void run("pattern")}>Check display layer</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={busy || !!status?.running} onClick={() => void run("live")}>Live game view</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={busy || !status?.running} onClick={() => void stop()}>Stop test</ButtonItem></PanelSectionRow>
      <PanelSectionRow>{status?.message || "Loading status..."}</PanelSectionRow>
      {error && <PanelSectionRow><div>Error: {error}</div></PanelSectionRow>}
      {status?.log && <PanelSectionRow><div style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{status.log}</div></PanelSectionRow>}
    </PanelSection>
  </>;
}

export default definePlugin(() => ({
  name: "Stream Share Probe",
  titleView: <div className={staticClasses.Title}>Stream Share Probe</div>,
  content: <Content />,
  icon: <FaDesktop />,
}));
