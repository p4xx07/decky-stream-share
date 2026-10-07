# Stream Share PC relay

Unzip this folder on the PC that will stay on during play. Install Python 3.10 or newer, then open a terminal in this folder.

**Windows:**

```powershell
py -m pip install -r requirements.txt
py server.py --host 0.0.0.0
```

**macOS or Linux:**

```sh
python3 -m pip install -r requirements.txt
python3 server.py --host 0.0.0.0
```

Keep that terminal running. On the computer, the relay is at `http://127.0.0.1:57322`. Find the computer's local IP in Windows `ipconfig`, macOS Wi-Fi settings, or Linux `hostname -I`. On a Deck on the same Wi-Fi, use `http://<computer-IP>:57322` as the **PC relay URL**. Allow local network access if your computer's firewall asks.

The relay ZIP also contains `d.zip`, the matching Deck plugin. On the Deck, use Decky settings → Developer → Install Plugin from URL with `http://<PC-LAN-IP>:57322/d.zip` when both devices are on the same LAN.

**Test with one Deck and this computer:** open `http://127.0.0.1:57322/client` in a browser on the computer. Create a room on the Deck, enter its code on the browser page, press **Join Deck room**, then **Send test image**. Start split view on the Deck. The Deck's game appears in the browser and the test image appears on the Deck. **Share Mac screen** can send your computer screen instead. Browser microphone audio is not implemented yet.

For Decks on different home networks, install `cloudflared` on the PC and run this in a second terminal:

```sh
cloudflared tunnel --url http://localhost:57322
```

Copy the temporary `https://...trycloudflare.com` URL into **both Decks**. Create a room on one Deck and join its code on the other. [Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) URLs change when restarted; they are intended for testing.

For a stable URL without buying a domain, [Tailscale Funnel](https://tailscale.com/docs/features/tailscale-funnel) is an option. Install and sign in to Tailscale on the relay computer, then run `tailscale funnel --bg 57322`. Tailscale shows an `https://<machine>.<tailnet>.ts.net` address; enter that as the relay URL on both Decks and use `<address>/d.zip` for installation. Funnel has bandwidth limits, so test video quality before using it with friends. The relay must still be running on the computer.

The commands above listen on your local network. Only use them on a trusted network. The relay does not require a PC display or Steam installation.

If the URL fails, visit `<relay URL>/health` in a browser. It should return `{"ok": true, ...}`. Local firewalls and sleep settings can prevent access.
