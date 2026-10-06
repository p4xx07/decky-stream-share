# Stream Share PC relay

Unzip this folder on the PC that will stay on during play. Install Python 3.10 or newer, then open a terminal in this folder.

**Windows:**

```powershell
py -m pip install -r requirements.txt
py server.py
```

**macOS or Linux:**

```sh
python3 -m pip install -r requirements.txt
python3 server.py
```

The relay listens at `http://127.0.0.1:57322`. Keep that terminal running.

The relay ZIP also contains `d.zip`, the matching Deck plugin. On the Deck, use Decky settings → Developer → Install Plugin from URL with `http://<PC-LAN-IP>:57322/d.zip` when both devices are on the same LAN.

**Test with one Deck and this computer:** open `http://127.0.0.1:57322/client` in a browser on the computer. Create a room on the Deck, enter its code on the browser page, press **Join Deck room**, then **Send test image**. Start split view on the Deck. The Deck's game appears in the browser and the test image appears on the Deck. **Share Mac screen** can send your computer screen instead. Browser microphone audio is not implemented yet.

For Decks on different home networks, install `cloudflared` on the PC and run this in a second terminal:

```sh
cloudflared tunnel --url http://localhost:57322
```

Copy the temporary `https://...trycloudflare.com` URL into **both Decks**. Create a room on one Deck and join its code on the other. [Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) URLs change when restarted; they are intended for testing.

For Decks on the **same LAN**, start the relay with `--host 0.0.0.0` and enter `http://<PC-LAN-IP>:57322` on both Decks. Only do this on a trusted network. The relay does not require a PC display or Steam installation.

If the URL fails, visit `<relay URL>/health` in a browser. It should return `{"ok": true, ...}`. Local firewalls and sleep settings can prevent access.
