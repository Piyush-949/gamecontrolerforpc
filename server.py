"""PhonePad server.

Serves the controller page to a phone and turns the touch input it sends
back over a websocket into either a virtual Xbox 360 pad (vgamepad) or
plain keyboard/mouse events (pynput).
"""

import asyncio
import datetime
import hashlib
import hmac
import ipaddress
import json
import os
import secrets
import socket
import ssl
import sys
import time
from urllib.parse import urlparse

try:
    import vgamepad as vg
    VGAMEPAD_OK = True
except ImportError:
    VGAMEPAD_OK = False

try:
    from pynput.keyboard import Key, Controller as KeyboardController
    from pynput.mouse import Button, Controller as MouseController
    PYNPUT_OK = True
    keyboard = KeyboardController()
    mouse = MouseController()
except ImportError:
    PYNPUT_OK = False

try:
    from aiohttp import web, WSMsgType
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
except ImportError:
    print("Missing packages. Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    import qrcode
except ImportError:
    qrcode = None


PORT = 8080   # page and websocket both live here, over https
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
CERT_DIR = os.path.join(BASE_DIR, "certs")

DEADZONE = 0.12     # keyboard mode only, the page already applies its own
MOUSE_SPEED = 18    # pixels per tick at full stick deflection

mode = "gamepad"
clients = set()

# pairing: the phone has to send this PIN before the server listens to it
PIN = "".join(secrets.choice("0123456789") for _ in range(6))
MAX_TRIES = 5
LOCKOUT_SECONDS = 60
failed = {}   # ip -> [number of wrong tries, locked until (time)]


# keyboard + mouse mode

KEY_MAP = {
    "A": "space",
    "B": "e",
    "X": "r",
    "Y": "f",
    "LB": "q",
    "RB": "tab",
    "BACK": "m",
    "GUIDE": "p",
    "DPAD_UP": "1",
    "DPAD_DOWN": "2",
    "DPAD_LEFT": "3",
    "DPAD_RIGHT": "4",
}
if PYNPUT_OK:
    KEY_MAP["START"] = Key.esc
    KEY_MAP["L3"] = Key.ctrl_l
    KEY_MAP["R3"] = Key.shift_l

held_keys = set()
held_mouse = set()
axis = {"LX": 0.0, "LY": 0.0, "RX": 0.0, "RY": 0.0}


def to_key(k):
    # "space" and "tab" are special keys in pynput, single letters are not
    if isinstance(k, str) and len(k) > 1:
        return Key[k]
    return k


def key_down(k):
    k = to_key(k)
    if k not in held_keys:
        keyboard.press(k)
        held_keys.add(k)


def key_up(k):
    k = to_key(k)
    if k in held_keys:
        keyboard.release(k)
        held_keys.discard(k)


def handle_keyboard(msg):
    if not PYNPUT_OK:
        return
    kind = msg.get("type")

    if kind == "button":
        key = KEY_MAP.get(msg.get("button"))
        if key is None:
            return
        if msg.get("pressed"):
            key_down(key)
        else:
            key_up(key)

    elif kind == "trigger":
        # LT = right click (aim), RT = left click (shoot)
        name = msg.get("trigger")
        btn = Button.right if name == "LT" else Button.left
        active = float(msg.get("value", 0)) > 0.3
        if active and name not in held_mouse:
            mouse.press(btn)
            held_mouse.add(name)
        elif not active and name in held_mouse:
            mouse.release(btn)
            held_mouse.discard(name)


async def keyboard_tick():
    """Left stick -> WASD, right stick -> mouse movement. Runs ~60 times a second."""
    while True:
        await asyncio.sleep(1 / 60)
        if mode != "keyboard" or not PYNPUT_OK:
            continue

        lx, ly = axis["LX"], axis["LY"]
        for key, on in (("w", ly > DEADZONE), ("s", ly < -DEADZONE),
                        ("a", lx < -DEADZONE), ("d", lx > DEADZONE)):
            key_down(key) if on else key_up(key)

        rx, ry = axis["RX"], axis["RY"]
        if abs(rx) > DEADZONE or abs(ry) > DEADZONE:
            mouse.move(int(rx * MOUSE_SPEED), int(-ry * MOUSE_SPEED))


# gamepad mode

pad = None
if VGAMEPAD_OK:
    try:
        pad = vg.VX360Gamepad()
    except Exception as err:
        print(f"Could not create the virtual controller: {err}")
        print("Is ViGEmBus installed? https://github.com/nefarius/ViGEmBus/releases")
        VGAMEPAD_OK = False

XBOX = {}
if VGAMEPAD_OK:
    B = vg.XUSB_BUTTON
    XBOX = {
        "A": B.XUSB_GAMEPAD_A,
        "B": B.XUSB_GAMEPAD_B,
        "X": B.XUSB_GAMEPAD_X,
        "Y": B.XUSB_GAMEPAD_Y,
        "LB": B.XUSB_GAMEPAD_LEFT_SHOULDER,
        "RB": B.XUSB_GAMEPAD_RIGHT_SHOULDER,
        "START": B.XUSB_GAMEPAD_START,
        "BACK": B.XUSB_GAMEPAD_BACK,
        "GUIDE": B.XUSB_GAMEPAD_GUIDE,
        "L3": B.XUSB_GAMEPAD_LEFT_THUMB,
        "R3": B.XUSB_GAMEPAD_RIGHT_THUMB,
        "DPAD_UP": B.XUSB_GAMEPAD_DPAD_UP,
        "DPAD_DOWN": B.XUSB_GAMEPAD_DPAD_DOWN,
        "DPAD_LEFT": B.XUSB_GAMEPAD_DPAD_LEFT,
        "DPAD_RIGHT": B.XUSB_GAMEPAD_DPAD_RIGHT,
    }


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def handle_gamepad(msg):
    if pad is None:
        return
    kind = msg.get("type")

    if kind == "button":
        btn = XBOX.get(msg.get("button"))
        if btn is None:
            return
        if msg.get("pressed"):
            pad.press_button(button=btn)
        else:
            pad.release_button(button=btn)

    elif kind == "axis":
        name = msg.get("axis")
        if name not in axis:
            return
        # the page already sends up as positive, which is what Xbox expects
        axis[name] = clamp(float(msg.get("value", 0)), -1.0, 1.0)
        if name in ("LX", "LY"):
            pad.left_joystick_float(x_value_float=axis["LX"], y_value_float=axis["LY"])
        else:
            pad.right_joystick_float(x_value_float=axis["RX"], y_value_float=axis["RY"])

    elif kind == "trigger":
        value = clamp(float(msg.get("value", 0)), 0.0, 1.0)
        if msg.get("trigger") == "LT":
            pad.left_trigger_float(value_float=value)
        else:
            pad.right_trigger_float(value_float=value)

    else:
        return
    pad.update()


# shared

def release_everything():
    for k in list(held_keys):
        try:
            keyboard.release(k)
        except Exception:
            pass
    held_keys.clear()

    for name in list(held_mouse):
        try:
            mouse.release(Button.right if name == "LT" else Button.left)
        except Exception:
            pass
    held_mouse.clear()

    for name in axis:
        axis[name] = 0.0
    if pad is not None:
        pad.reset()
        pad.update()


def caps_message():
    return json.dumps({
        "type": "caps",
        "gamepad": VGAMEPAD_OK,
        "keyboard": PYNPUT_OK,
        "mode": mode,
    })


def check_pin(ip, pin):
    """Returns (ok, seconds_locked)."""
    tries, until = failed.get(ip, [0, 0])
    now = time.time()
    if until > now:
        return False, int(until - now) + 1

    if hmac.compare_digest(str(pin), PIN):
        failed.pop(ip, None)
        return True, 0

    tries += 1
    if tries >= MAX_TRIES:
        failed[ip] = [0, now + LOCKOUT_SECONDS]
        print(f"too many wrong PINs from {ip}, locked for {LOCKOUT_SECONDS}s")
        return False, LOCKOUT_SECONDS
    failed[ip] = [tries, 0]
    return False, 0


async def on_client(request):
    global mode

    # refuse pages from other sites trying to open the socket
    origin = request.headers.get("Origin")
    if origin and urlparse(origin).netloc != request.host:
        raise web.HTTPForbidden()

    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=4096)
    await ws.prepare(request)
    ip = request.remote
    paired = False

    try:
        async for frame in ws:
            if frame.type != WSMsgType.TEXT:
                continue
            try:
                msg = json.loads(frame.data)
            except ValueError:
                continue
            if not isinstance(msg, dict):
                continue

            kind = msg.get("type")

            if not paired:
                if kind != "auth":
                    continue
                ok, wait = check_pin(ip, msg.get("pin", ""))
                await ws.send_str(json.dumps({"type": "auth", "ok": ok, "wait": wait}))
                if ok:
                    paired = True
                    clients.add(ws)
                    print(f"phone paired: {ip} ({len(clients)} total)")
                    await ws.send_str(caps_message())
                continue

            if kind == "get_mode":
                await ws.send_str(caps_message())
            elif kind == "set_mode":
                new_mode = msg.get("mode")
                if new_mode in ("gamepad", "keyboard") and new_mode != mode:
                    release_everything()
                    mode = new_mode
                    print(f"mode: {mode}")
                    for c in list(clients):
                        await c.send_str(caps_message())
            elif mode == "gamepad":
                handle_gamepad(msg)
            else:
                if kind == "axis" and msg.get("axis") in axis:
                    axis[msg["axis"]] = float(msg.get("value", 0))
                handle_keyboard(msg)
    finally:
        if paired:
            clients.discard(ws)
            if not clients:
                release_everything()
            print(f"phone disconnected: {ip} ({len(clients)} left)")
    return ws


# http + startup

async def index(request):
    return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def load_or_make_cert(ip):
    """Self-signed certificate for this PC's address. Reused until the IP changes or it nears expiry."""
    crt = os.path.join(CERT_DIR, "phonepad.crt")
    key = os.path.join(CERT_DIR, "phonepad.key")

    if os.path.exists(crt) and os.path.exists(key):
        with open(crt, "rb") as f:
            old = x509.load_pem_x509_certificate(f.read())
        san = old.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        ips = [str(i) for i in san.get_values_for_type(x509.IPAddress)]
        expires = old.not_valid_after_utc
        soon = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=30)
        if ip in ips and expires > soon:
            return crt, key

    os.makedirs(CERT_DIR, exist_ok=True)
    private = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "PhonePad")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName([
            x509.IPAddress(ipaddress.ip_address(ip)),
            x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
            x509.DNSName("localhost"),
        ]), critical=False)
        .sign(private, hashes.SHA256())
    )
    with open(key, "wb") as f:
        f.write(private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
    with open(crt, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    return crt, key


def fingerprint(crt_path):
    with open(crt_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())
    digest = hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()
    return ":".join(digest[i:i + 2] for i in range(0, 16, 2)).upper()


async def main():
    ip = local_ip()
    url = f"https://{ip}:{PORT}"

    crt, key = load_or_make_cert(ip)
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ssl_ctx.load_cert_chain(crt, key)

    print("PhonePad")
    print(f"  open on your phone: {url}")
    print(f"  PIN: {PIN}")
    print(f"  certificate starts with: {fingerprint(crt)}")
    print(f"  gamepad mode:  {'ok' if VGAMEPAD_OK else 'unavailable (ViGEmBus not installed)'}")
    print(f"  keyboard mode: {'ok' if PYNPUT_OK else 'unavailable (pip install pynput)'}")
    if qrcode:
        qr = qrcode.QRCode(border=1)
        qr.add_data(f"{url}/?pin={PIN}")   # scanning the code skips typing the PIN
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    print()

    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/ws", on_client)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT, ssl_context=ssl_ctx).start()

    await keyboard_tick()


if __name__ == "__main__":
    # python server.py --pin 123456 keeps the same PIN between runs
    if "--pin" in sys.argv:
        given = sys.argv[sys.argv.index("--pin") + 1:][:1]
        if given and given[0].isdigit() and len(given[0]) >= 4:
            PIN = given[0]
        else:
            print("--pin needs at least 4 digits")
            sys.exit(1)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        release_everything()
        print("stopped")
