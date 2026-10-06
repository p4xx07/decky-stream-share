const manifest = {"name":"Stream Share"};
const API_VERSION = 2;
const internalAPIConnection = window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
if (!internalAPIConnection) {
    throw new Error('[@decky/api]: Failed to connect to the loader as as the loader API was not initialized. This is likely a bug in Decky Loader.');
}
let api;
try {
    api = internalAPIConnection.connect(API_VERSION, manifest.name);
}
catch {
    api = internalAPIConnection.connect(1, manifest.name);
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version 1. Some features may not work.`);
}
if (api._version != API_VERSION) {
    console.warn(`[@decky/api] Requested API version ${API_VERSION} but the running loader only supports version ${api._version}. Some features may not work.`);
}
const callable = api.callable;
const definePlugin = (fn) => {
    return (...args) => {
        return fn(...args);
    };
};

var DefaultContext = {
  color: undefined,
  size: undefined,
  className: undefined,
  style: undefined,
  attr: undefined
};
var IconContext = SP_REACT.createContext && /*#__PURE__*/SP_REACT.createContext(DefaultContext);

var _excluded = ["attr", "size", "title"];
function _objectWithoutProperties(e, t) { if (null == e) return {}; var o, r, i = _objectWithoutPropertiesLoose(e, t); if (Object.getOwnPropertySymbols) { var n = Object.getOwnPropertySymbols(e); for (r = 0; r < n.length; r++) o = n[r], -1 === t.indexOf(o) && {}.propertyIsEnumerable.call(e, o) && (i[o] = e[o]); } return i; }
function _objectWithoutPropertiesLoose(r, e) { if (null == r) return {}; var t = {}; for (var n in r) if ({}.hasOwnProperty.call(r, n)) { if (-1 !== e.indexOf(n)) continue; t[n] = r[n]; } return t; }
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
function ownKeys(e, r) { var t = Object.keys(e); if (Object.getOwnPropertySymbols) { var o = Object.getOwnPropertySymbols(e); r && (o = o.filter(function (r) { return Object.getOwnPropertyDescriptor(e, r).enumerable; })), t.push.apply(t, o); } return t; }
function _objectSpread(e) { for (var r = 1; r < arguments.length; r++) { var t = null != arguments[r] ? arguments[r] : {}; r % 2 ? ownKeys(Object(t), true).forEach(function (r) { _defineProperty(e, r, t[r]); }) : Object.getOwnPropertyDescriptors ? Object.defineProperties(e, Object.getOwnPropertyDescriptors(t)) : ownKeys(Object(t)).forEach(function (r) { Object.defineProperty(e, r, Object.getOwnPropertyDescriptor(t, r)); }); } return e; }
function _defineProperty(e, r, t) { return (r = _toPropertyKey(r)) in e ? Object.defineProperty(e, r, { value: t, enumerable: true, configurable: true, writable: true }) : e[r] = t, e; }
function _toPropertyKey(t) { var i = _toPrimitive(t, "string"); return "symbol" == typeof i ? i : i + ""; }
function _toPrimitive(t, r) { if ("object" != typeof t || !t) return t; var e = t[Symbol.toPrimitive]; if (void 0 !== e) { var i = e.call(t, r); if ("object" != typeof i) return i; throw new TypeError("@@toPrimitive must return a primitive value."); } return ("string" === r ? String : Number)(t); }
function Tree2Element(tree) {
  return tree && tree.map((node, i) => /*#__PURE__*/SP_REACT.createElement(node.tag, _objectSpread({
    key: i
  }, node.attr), Tree2Element(node.child)));
}
function GenIcon(data) {
  return props => /*#__PURE__*/SP_REACT.createElement(IconBase, _extends({
    attr: _objectSpread({}, data.attr)
  }, props), Tree2Element(data.child));
}
function IconBase(props) {
  var elem = conf => {
    var attr = props.attr,
      size = props.size,
      title = props.title,
      svgProps = _objectWithoutProperties(props, _excluded);
    var computedSize = size || conf.size || "1em";
    var className;
    if (conf.className) className = conf.className;
    if (props.className) className = (className ? className + " " : "") + props.className;
    return /*#__PURE__*/SP_REACT.createElement("svg", _extends({
      stroke: "currentColor",
      fill: "currentColor",
      strokeWidth: "0"
    }, conf.attr, attr, svgProps, {
      className: className,
      style: _objectSpread(_objectSpread({
        color: props.color || conf.color
      }, conf.style), props.style),
      height: computedSize,
      width: computedSize,
      xmlns: "http://www.w3.org/2000/svg"
    }), title && /*#__PURE__*/SP_REACT.createElement("title", null, title), props.children);
  };
  return IconContext !== undefined ? /*#__PURE__*/SP_REACT.createElement(IconContext.Consumer, null, conf => elem(conf)) : elem(DefaultContext);
}

// THIS FILE IS AUTO GENERATED
function FaDesktop (props) {
  return GenIcon({"attr":{"viewBox":"0 0 576 512"},"child":[{"tag":"path","attr":{"d":"M528 0H48C21.5 0 0 21.5 0 48v320c0 26.5 21.5 48 48 48h192l-16 48h-72c-13.3 0-24 10.7-24 24s10.7 24 24 24h272c13.3 0 24-10.7 24-24s-10.7-24-24-24h-72l-16-48h192c26.5 0 48-21.5 48-48V48c0-26.5-21.5-48-48-48zm-16 352H64V64h448v288z"},"child":[]}]})(props);
}

const getStatus = callable("get_status");
const startView = callable("start_view");
const stopView = callable("stop_view");
const setViewLayout = callable("set_layout");
const startRoom = callable("start_room");
const stopRoom = callable("stop_room");
const setMicrophone = callable("set_microphone");
const setSpeaker = callable("set_speaker");
const layouts = ["side", "wide", "stack"];
const layoutNames = {
    side: "Equal side by side", wide: "Larger local game", stack: "Top and bottom",
};
async function within(promise, milliseconds, message) {
    let timer;
    const timeout = new Promise((_, reject) => {
        timer = window.setTimeout(() => reject(new Error(message)), milliseconds);
    });
    try {
        return await Promise.race([promise, timeout]);
    }
    finally {
        if (timer !== undefined)
            window.clearTimeout(timer);
    }
}
function errorMessage(caught) {
    return caught instanceof Error ? caught.message : String(caught);
}
function Content() {
    const [status, setStatus] = SP_REACT.useState(null);
    const [busy, setBusy] = SP_REACT.useState(false);
    const [error, setError] = SP_REACT.useState("");
    const [roomError, setRoomError] = SP_REACT.useState("");
    const [connecting, setConnecting] = SP_REACT.useState(false);
    const [relayUrl, setRelayUrl] = SP_REACT.useState("");
    const [joinCode, setJoinCode] = SP_REACT.useState("");
    const relayLoaded = SP_REACT.useRef(false);
    SP_REACT.useEffect(() => {
        let active = true;
        let refreshing = false;
        const refresh = async () => {
            if (refreshing)
                return;
            refreshing = true;
            try {
                const next = await within(getStatus(), 6000, "Decky backend did not respond. Reinstall the latest Stream Share ZIP and reopen Decky.");
                if (active) {
                    setStatus(next);
                    if (next.room_connected)
                        setRoomError("");
                    if (!relayLoaded.current) {
                        setRelayUrl(next.relay_url);
                        relayLoaded.current = true;
                    }
                }
            }
            catch (caught) {
                if (active)
                    setRoomError(errorMessage(caught));
            }
            finally {
                refreshing = false;
            }
        };
        void refresh();
        const timer = window.setInterval(() => void refresh(), 2000);
        return () => { active = false; window.clearInterval(timer); };
    }, []);
    const run = async (mode) => {
        setBusy(true);
        setError("");
        try {
            setStatus(await startView(mode));
        }
        catch (caught) {
            setError(String(caught));
        }
        finally {
            setBusy(false);
        }
    };
    const stop = async () => {
        setBusy(true);
        try {
            setStatus(await stopView());
        }
        catch (caught) {
            setError(String(caught));
        }
        finally {
            setBusy(false);
        }
    };
    const changeLayout = async () => {
        setBusy(true);
        setError("");
        try {
            const current = status?.layout || "side";
            const next = layouts[(layouts.indexOf(current) + 1) % layouts.length];
            setStatus(await setViewLayout(next));
        }
        catch (caught) {
            setError(String(caught));
        }
        finally {
            setBusy(false);
        }
    };
    const connectRoom = async (code) => {
        setBusy(true);
        setConnecting(true);
        setRoomError("");
        try {
            setStatus(await within(startRoom(relayUrl, code), 15000, "Decky backend did not answer within 15 seconds. Reinstall the latest Stream Share ZIP and reopen Decky."));
        }
        catch (caught) {
            setRoomError(errorMessage(caught));
        }
        finally {
            setConnecting(false);
            setBusy(false);
        }
    };
    const disconnectRoom = async () => {
        setBusy(true);
        setRoomError("");
        try {
            setStatus(await stopRoom());
        }
        catch (caught) {
            setRoomError(errorMessage(caught));
        }
        finally {
            setBusy(false);
        }
    };
    const toggleAudio = async (which) => {
        setBusy(true);
        setError("");
        try {
            setStatus(which === "microphone"
                ? await setMicrophone(!status?.microphone_enabled)
                : await setSpeaker(!status?.speaker_enabled));
        }
        catch (caught) {
            setError(String(caught));
        }
        finally {
            setBusy(false);
        }
    };
    return SP_JSX.jsxs(SP_JSX.Fragment, { children: [SP_JSX.jsxs(DFL.PanelSection, { title: "Stream Share", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: "Start a game, connect both Decks to a room, then start split view. Your complete game fits in its pane beside your friend's game." }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsxs(DFL.ButtonItem, { layout: "below", disabled: busy || !!status?.running, onClick: () => void changeLayout(), children: ["Layout: ", layoutNames[status?.layout || "side"], " (change)"] }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { layout: "below", disabled: busy || !!status?.running, onClick: () => void run("pattern"), children: "Check display layer" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { layout: "below", disabled: busy || !!status?.running, onClick: () => void run("live"), children: "Start split view" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { layout: "below", disabled: busy || !status?.running, onClick: () => void stop(), children: "Stop split view" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: status?.message || "Loading status..." }), status?.capture_diagnostic && SP_JSX.jsx(DFL.PanelSectionRow, { children: status.capture_diagnostic }), error && SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsxs("div", { children: ["Error: ", error] }) }), status?.log && SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx("div", { style: { whiteSpace: "pre-wrap", overflowWrap: "anywhere" }, children: status.log }) })] }), SP_JSX.jsxs(DFL.PanelSection, { title: "PC relay", children: [SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.TextField, { label: "PC relay URL", value: relayUrl, onChange: event => { relayLoaded.current = true; setRelayUrl(event.target.value); } }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.TextField, { label: "Friend's room code", value: joinCode, onChange: event => setJoinCode(event.target.value) }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { layout: "below", disabled: busy || !!status?.room_connected, onClick: () => void connectRoom(""), children: "Create room" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { layout: "below", disabled: busy || !!status?.room_connected || !joinCode.trim(), onClick: () => void connectRoom(joinCode), children: "Join room" }) }), SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsx(DFL.ButtonItem, { layout: "below", disabled: busy || !status?.room_connected, onClick: () => void disconnectRoom(), children: "Leave room" }) }), status?.room_code && SP_JSX.jsxs(DFL.PanelSectionRow, { children: ["Room code: ", status.room_code] }), SP_JSX.jsx(DFL.PanelSectionRow, { children: connecting ? "Connecting to PC relay…" : (status?.relay_message || "Not connected") }), roomError && SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsxs("div", { style: { color: "#ffb4a9", overflowWrap: "anywhere" }, children: ["Error: ", roomError] }) }), !!status?.room_connected && SP_JSX.jsxs(DFL.PanelSectionRow, { children: ["Video frames: sent ", status.sent_frames, ", received ", status.received_frames] }), !!status?.room_connected && SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsxs(DFL.ButtonItem, { layout: "below", disabled: busy, onClick: () => void toggleAudio("microphone"), children: ["Microphone: ", status.microphone_enabled ? "On" : "Off"] }) }), !!status?.room_connected && SP_JSX.jsx(DFL.PanelSectionRow, { children: SP_JSX.jsxs(DFL.ButtonItem, { layout: "below", disabled: busy, onClick: () => void toggleAudio("speaker"), children: ["Friend audio: ", status.speaker_enabled ? "On" : "Off"] }) })] })] });
}
var index = definePlugin(() => ({
    name: "Stream Share",
    titleView: SP_JSX.jsx("div", { className: DFL.staticClasses.Title, children: "Stream Share" }),
    content: SP_JSX.jsx(Content, {}),
    icon: SP_JSX.jsx(FaDesktop, {}),
}));

export { index as default };
//# sourceMappingURL=index.js.map
