# PhonePad

Use your phone as a wireless Xbox controller for PC games. Nothing to install on the phone, you just open a web page in its browser.

```
phone browser  --wifi-->  python server on PC  -->  virtual Xbox 360 pad  -->  game
```

There is also a keyboard + mouse mode for games that don't support controllers.

## What you need

- Windows 10 or 11 with Python 3.8+
- The [ViGEmBus driver](https://github.com/nefarius/ViGEmBus/releases/latest) (only for gamepad mode)
- Phone and PC on the same wifi

## Setup

1. Install ViGEmBus and restart if it asks.
2. Run `install.bat` (or `pip install -r requirements.txt`).

## Running it

1. Double click `start.bat`.
2. Scan the QR code with your phone. Or open the address it prints (it starts with `https://`) and type the 6 digit PIN shown in the same window. If the page doesn't load, allow Python through the Windows firewall.
3. The first time the browser says the site isn't safe, see Encryption below. Tap Advanced and continue.
4. Turn the phone sideways. The Fullscreen button hides the browser bars and locks landscape where the browser allows it.
5. Start the game after the server is already running, so it sees the controller.

## Encryption

The page, the PIN and all the button presses go over https, so people on the same wifi can't read them. The server makes its own certificate the first time you run it and saves it in `certs/` (it makes a new one if your PC's IP changes).

Since it's not from a real certificate authority, your phone will say the site isn't safe the first time. Just tap Advanced and continue. If you want to be sure it's your PC, the server prints the start of the certificate fingerprint when it starts.

Don't push or share the `certs` folder, the private key is in there.

## PIN

Each time the server starts it picks a random 6 digit PIN and the phone has to send it before anything works. The QR code has the PIN in the link so scanning skips typing it. 5 wrong tries from one device locks it out for a minute.

Want the same PIN every time? Run `python server.py --pin 123456` (4+ digits). The phone remembers the last PIN that worked so a wifi drop doesn't ask again.

## Controls

Layout is the same as a normal pad: sticks at the outer edges, d-pad and face buttons toward the middle, triggers and bumpers along the top.

| Control | What it does |
|---|---|
| Sticks | Move / camera. Hold one without moving for about half a second to click it (L3 / R3) |
| LT / RT | Analog sliders, slide your finger sideways for partial press |
| LB / RB, A B X Y, d-pad | Normal buttons |
| Select / Start / center button | Back / Start / Guide |
| Gyro | Tilt the phone to steer with the right stick's X axis |

Driving layout: tap the Drive button in the middle when you get in a vehicle. The left stick and d-pad turn into a steering wheel, and the right half gets brake and gas pedals (press lower on a pedal for more). Tap Exit vehicle when you get out. Gyro steers the wheel while it's showing.

In keyboard + mouse mode:

| Control | Key |
|---|---|
| Left stick | W A S D |
| Right stick | Mouse movement |
| LT / RT | Right click / left click |
| A B X Y | Space, E, R, F |
| LB / RB | Q, Tab |
| D-pad | 1, 2, 3, 4 |
| Select / Start / center | M, Esc, P |
| Stick click | Left Ctrl / Left Shift |

The keys are listed at the top of `server.py` (`KEY_MAP`) if you want to change them. The labels show on the buttons while you're in this mode.

## Troubleshooting

- **No controller in game**: ViGEmBus isn't installed, or the game was started before the server.
- **Page won't load**: check both devices are on the same network and try the IP by hand, `https://<pc ip>:8080` (it has to be https).
- **Laggy**: sit closer to the router, 5 GHz helps.
- **Gyro does nothing on iPhone**: Safari only asks for motion permission after a tap, so press the Gyro button once.

## Files

```
server.py          https + websocket server
static/index.html  the controller page
requirements.txt
install.bat
start.bat
```

Port used: 8080 (https, page and websocket).
