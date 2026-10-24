import asyncio
import json
import os
import socket
import sys

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
    import websockets
    from aiohttp import web
except ImportError:
    print("Missing packages. Run: pip install -r requirements.txt")
    sys.exit(1)

try:
    import qrcode
except ImportError:
    qrcode = None


HTTP_PORT = 8080
WS_PORT = 8765
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

DEADZONE = 0.12     
MOUSE_SPEED = 18    
mode = "gamepad"
clients = set()



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


async def on_client(ws):
    global mode
    clients.add(ws)
    print(f"phone connected ({len(clients)} total)")
    await ws.send(caps_message())

    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except ValueError:
                continue

            kind = msg.get("type")

            if kind == "get_mode":
                await ws.send(caps_message())
            elif kind == "set_mode":
                new_mode = msg.get("mode")
                if new_mode in ("gamepad", "keyboard") and new_mode != mode:
                    release_everything()
                    mode = new_mode
                    print(f"mode: {mode}")
                    for c in list(clients):
                        await c.send(caps_message())
            elif mode == "gamepad":
                handle_gamepad(msg)
            else:
                if kind == "axis" and msg.get("axis") in axis:
                    axis[msg["axis"]] = float(msg.get("value", 0))
                handle_keyboard(msg)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        clients.discard(ws)
        if not clients:
            release_everything()
        print(f"phone disconnected ({len(clients)} left)")


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


async def main():
    url = f"http://{local_ip()}:{HTTP_PORT}"

    print("PhonePad")
    print(f"  open on your phone: {url}")
    print(f"  gamepad mode:  {'ok' if VGAMEPAD_OK else 'unavailable (ViGEmBus not installed)'}")
    print(f"  keyboard mode: {'ok' if PYNPUT_OK else 'unavailable (pip install pynput)'}")
    if qrcode:
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    print()

    app = web.Application()
    app.router.add_get("/", index)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", HTTP_PORT).start()

    async with websockets.serve(on_client, "0.0.0.0", WS_PORT):
        await keyboard_tick()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        release_everything()
        print("stopped")
