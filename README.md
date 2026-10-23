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
2. Run `pip install -r requirements.txt`.

## Running it

1. Double click `start.bat`.
2. Scan the QR code with your phone. Or open the address it prints (it starts with `https://`) and type the 6 digit PIN shown in the same window. If the page doesn't load, allow Python through the Windows firewall.
3. The first time, the phone browser warns that the connection isn't private. That's expected, see the Encryption section below. Tap Advanced and continue.
4. Turn the phone sideways. The Fullscreen button hides the browser bars and locks landscape where the browser allows it.
5. Start the game after the server is already running, so it sees the controller.

## Encryption

Everything between the phone and the PC (the page, the PIN and every button press) goes over HTTPS / WSS, so nobody on the same wifi can read or copy it. The server makes its own certificate the first time it runs and keeps it in the `certs` folder. It makes a new one if your PC's IP address changes.

Because that certificate isn't from a public authority, the phone shows a warning the first time. Check that the line `certificate starts with: ...` in the server window matches what the browser shows under certificate details if you want to be sure it's your PC. Accept it once and it's remembered.

The `certs` folder holds the private key. Don't share it or zip it up with the project.

A side effect: browsers only allow motion sensors and fullscreen orientation lock on secure pages, so gyro steering works properly now.

## PIN

Every time the server starts it makes a new random PIN. The phone has to send it before the server will listen to anything, so someone else on your wifi can't take over your PC. The QR code already has the PIN in it, so scanning skips the typing. After 5 wrong tries from the same device it is locked out for a minute.

If you'd rather keep the same PIN between runs, start the server with `python server.py --pin 123456` (4 digits or more). The phone remembers the last PIN that worked, so reconnecting after a wifi drop doesn't ask again.

Pages from other websites can't open the connection either, the server checks where the request came from.

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
