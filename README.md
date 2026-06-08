# Awake on Deck

A Steam Deck app that wakes your Windows PC via Wake-on-LAN and hands off to Steam Remote Play — all from your couch, fully navigable with the gamepad.

## How it works

1. You press **Wake & Connect** on the Deck
2. The app sends a Wake-on-LAN magic packet to your PC
3. It polls your PC over TCP until it responds
4. Steam Remote Play takes over

## Requirements

- Steam Deck (SteamOS)
- Windows PC on the same local network
- Wake-on-LAN enabled in your PC's BIOS and network adapter settings

## Installation

On your Steam Deck:

1. Switch to **Desktop Mode** (Steam button → Power → Switch to Desktop)
2. Open a terminal (Konsole) and run:

```bash
curl -sSL https://raw.githubusercontent.com/eleonne/awake-on-deck/main/install.sh | bash
```

The installer will:
- Clone the repository to `/home/deck/awake-on-deck`
- Install Python dependencies into the project folder
- Add **Awake on Deck** to your Steam library as a non-Steam game
- Apply the app icon and artwork automatically

After installation, switch back to Game Mode. **Awake on Deck** will appear in your Steam library.

## Configuration

On first launch the app creates a config file at `~/.config/steamdeck-client/config.json` with default values. Open **Settings** from the home screen to configure:

| Setting | Description |
|---|---|
| PC IP Address | Local IP of your Windows PC |
| PC MAC Address | MAC address of your PC's network adapter |
| WoL Broadcast | Broadcast address for your subnet (e.g. `192.168.1.255`) |
| WoL Port | UDP port for the magic packet (default `9`) |
| Poll Timeout (s) | How long to wait for the PC to come online (default `90`) |
| Poll Interval (s) | Seconds between connection attempts (default `3`) |
| Poll TCP Port | Port used to check if the PC is online (default `445`) |

Navigate with the D-pad, confirm with **A**, cancel with **B**.

## Updating

Re-run the install script from Desktop Mode at any time:

```bash
bash /home/deck/awake-on-deck/install.sh
```

## Controls

| Button | Action |
|---|---|
| D-pad / Left stick | Navigate |
| A | Confirm / activate |
| B | Back / cancel |
| Select | Open settings |
