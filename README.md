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
2. Run  `pip install -r requirements.txt`.

## Running it

1. Double click `start.bat`.
2. Open the address it prints on your phone, or scan the QR code. If the page doesn't load, allow Python through the Windows firewall.
3. Turn the phone sideways. The Fullscreen button hides the browser bars and locks landscape where the browser allows it.
4. Start the game after the server is already running, so it sees the controller.

## Controls

Layout is the same as a normal pad: sticks at the outer edges, d-pad and face buttons toward the middle, triggers and bumpers along the top.

| Control | What it does |
|---|---|
| Sticks | Move / camera. Hold one without moving for about half a second to click it (L3 / R3) |
| LT / RT | Analog sliders, slide your finger sideways for partial press |
| LB / RB, A B X Y, d-pad | Normal buttons |
| Select / Start / center button | Back / Start / Guide |
| Gyro | Tilt the phone to steer with the right stick's X axis |

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

## Troubleshooting

- **No controller in game**: ViGEmBus isn't installed, or the game was started before the server.
- **Page won't load**: check both devices are on the same network and try the IP by hand, `http://<pc ip>:8080`.
- **Laggy**: sit closer to the router, 5 GHz helps.
- **Gyro does nothing on iPhone**: Safari only asks for motion permission after a tap, so press the Gyro button once.

## Files

```
server.py         
static/index.html 
requirements.txt
start.bat
```

Ports used: 8080 (page) and 8765 (websocket).
