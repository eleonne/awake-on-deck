# Using Awake on Deck

Awake on Deck wakes your Windows gaming PC from your handheld, waits for it to come online, and then lets you stream from it with Steam Remote Play. It runs on:

- **Steam Deck** (SteamOS, in Game Mode)
- **Windows handhelds** such as the ROG Ally (from the desktop or the Xbox full-screen experience)

You can use the gamepad (D-pad or left stick) or the touch screen. You never need a mouse.

---

## 1. Prepare your gaming PC

You only need to do this once. Without it, the PC won't respond to the wake signal.

1. **Enable Wake-on-LAN in the BIOS/UEFI.** The option is usually called *Wake on LAN*, *Power On by PCI-E*, or *Resume by LAN*. Also turn off *ErP / Deep Sleep* if your board has it.
2. **Enable Wake-on-LAN on the network adapter in Windows.**
   Open Device Manager → Network adapters → your Ethernet adapter → Properties, then:
   - **Advanced** tab: set *Wake on Magic Packet* to **Enabled**.
   - **Power Management** tab: tick *Allow this device to wake the computer* and *Only allow a magic packet to wake the computer*.
3. **Use a wired (Ethernet) connection on the PC.** Most Wi-Fi adapters can't be woken from sleep or shutdown.
4. **Turn off Fast Startup** if you shut the PC down rather than putting it to sleep (Control Panel → Power Options → *Choose what the power buttons do*).
5. **Write down the PC's IP and MAC address.** Open a Command Prompt on the PC and run:

   ```
   ipconfig /all
   ```

   Under your Ethernet adapter, note:
   - **IPv4 Address**, e.g. `192.168.1.100`
   - **Physical Address** (the MAC), e.g. `AA-BB-CC-11-22-33`

   Your router's DHCP settings let you reserve this IP for the PC so it never changes. Doing that is recommended.
6. **Make sure the PC answers on TCP port 445.** The app checks port 445 (Windows file sharing) to tell whether the PC is awake. Turning on *File and printer sharing* for private networks is enough. If you'd rather use another port that the PC always has open, you can change it in Settings.

Both devices must be on the **same local network**.

---

## 2. Install

### Steam Deck

1. Switch to **Desktop Mode** (Steam button → Power → Switch to Desktop).
2. Open **Konsole** and run:

   ```bash
   curl -sSL https://raw.githubusercontent.com/eleonne/awake-on-deck/main/install.sh | bash
   ```

The installer:

- Downloads the app to `/home/deck/awake-on-deck`
- Installs its dependencies into the app folder, so SteamOS updates won't remove them
- Closes Steam, adds **Awake on Deck** to your library as a non-Steam game, and reopens Steam
- Installs the icon and artwork: the library cover, the banner on the game's page, and the wide image used on the Game Mode home screen

When it finishes, switch back to **Game Mode**. You'll find **Awake on Deck** in your library under *Non-Steam*, with its artwork already applied.

### Windows handheld (ROG Ally, etc.)

Requirements: **Python 3.11+** installed and available on `PATH` as `python`. You can get it from python.org or with `winget install Python.Python.3.12`.

1. Open **PowerShell** and run:

   ```powershell
   irm https://raw.githubusercontent.com/eleonne/awake-on-deck/main/install.ps1 | iex
   ```

   The installer installs Git if it's missing (using winget). It then downloads the app to `%LOCALAPPDATA%\awake-on-deck`, installs the dependencies, and creates an **Awake on Deck** shortcut on your desktop.

2. Optional: add the app to the Xbox full-screen experience:
   1. Open the **Xbox app** and go to **My Library**.
   2. Choose **Add a game on PC**.
   3. Browse to `%LOCALAPPDATA%\awake-on-deck\launch.bat`.

---

## 3. First-time setup

When you launch the app for the first time, it creates a config file with placeholder values. **You must enter your PC's details before waking it will work.**

1. On the home screen, select **Settings**. You can also press **Select** (View) from any screen.
2. **Easiest: let the app find your PC.** Make sure the PC is **turned on**, then select **Find PCs**. After a few seconds you'll see a list of computers on your network, each with its name, IP and MAC address. Pick yours with **A** or by tapping it. The app fills in the PC IP Address, PC MAC Address and WoL Broadcast fields for you and returns to Settings with **Save** selected.
   - Your PC shows up under its Windows computer name (in Windows: Settings → System → About).
   - **Port 445 closed** next to a PC means the app can wake it, but can't tell when it's awake. Turn on *File and printer sharing* on that PC (step 1.6).
   - **MAC unknown** means the MAC field is left empty, and you'll need to type it in.
   - If the PC has both Wi-Fi and Ethernet, it may appear twice. Pick the **wired** one, because Wake-on-LAN needs the Ethernet adapter.
   - Discovery can't see a PC that's asleep or off, so do this once while it's running.
3. Or fill in the fields yourself:

   | Setting | What to enter | Default |
   |---|---|---|
   | **PC IP Address** | The PC's IPv4 address from step 1.5 | `192.168.1.1` |
   | **PC MAC Address** | The PC's MAC address from step 1.5 (`-` or `:` separators both work) | `AF-AF-AF-AF-AF-AF` |
   | **WoL Broadcast** | Your network's broadcast address: the PC's IP with the last number replaced by `255` | `192.168.1.255` |
   | **WoL Port** | UDP port for the wake signal. `9` works almost everywhere | `9` |
   | **Poll Timeout (s)** | How long to wait for the PC to come online before giving up | `90` |
   | **Poll Interval (s)** | Seconds between "are you awake?" checks | `3` |
   | **Poll TCP Port** | Port used to check if the PC is awake | `445` |
   | **Resolution** | Screen resolution of the app. Press **A** or tap to switch between `1920x1080` and `1280x720`; the change applies as soon as you save | `1920x1080` |

4. Select **Save**.

### Editing a field

1. Move to the field with the **D-pad** or **left stick** and press **A**, or just tap the field. The field turns blue and shows a cursor.
2. Open the on-screen keyboard:
   - **Steam Deck:** press **Steam + X**
   - **Windows:** use the touch keyboard (or a physical keyboard)
3. Type the new value. Use the keyboard's **Backspace** to delete characters.
4. Press **Enter** on the keyboard to confirm, or **B** to discard your changes. Tapping another field or button also keeps what you typed.

> Numeric fields only accept whole numbers. Any other value is ignored when you save, and the previous value is kept.

---

## 4. Everyday use

1. Launch **Awake on Deck** from your library.
2. The home screen shows the PC's status. The app checks it every 10 seconds:
   - 🟢 **PC Online**: the PC is already awake
   - 🔴 **PC Offline**: the PC is asleep or off
   - ⚪ **Checking...**: the first check is still running
3. Select **Wake & Connect**. The progress screen then shows two steps:
   - **Waking**: the wake signal is sent to the PC
   - **Online**: the app waits for the PC to answer
4. When the PC answers, you're returned to the home screen and it shows **PC Online**.
5. Select **Close**, then start any game from your Steam library. Games installed on the PC show a **Stream** button. Steam Remote Play takes over from there.

To stop waiting partway through, press **B** or select **Cancel**.

### If something goes wrong

If the PC doesn't come online within the timeout, or the wake signal can't be sent, an **Error** screen explains what happened. From there you can:

- Select **Retry** to try again
- Select **Settings** to check your PC's details

The app never quits on its own after an error.

---

## 5. Controls

| Button | Action |
|---|---|
| **D-pad** / **left stick** | Move between buttons and fields. Hold to keep moving |
| **Touch screen** | Tap a button to press it, or tap a field to edit it |
| **A** | Select / start editing a field |
| **B** | Back, cancel, or discard an edit |
| **Select** (View) | Open Settings from any screen |
| **Steam + X** (Deck) | Show the on-screen keyboard while editing |

The app doesn't use the Start/Menu button, so it never conflicts with the Steam overlay.

---

## 6. Troubleshooting

| Symptom | Things to check |
|---|---|
| Always stays at **Waiting for PC to come online...** and then times out | Wake-on-LAN isn't enabled in the BIOS or on the adapter (section 1). The PC is on Wi-Fi. The MAC address is wrong. Fast Startup is still on. |
| PC wakes up, but the app still times out | Port 445 is blocked by the Windows firewall, or the IP address is wrong or has changed. Try a different **Poll TCP Port**, or reserve the PC's IP in your router. |
| Home screen always shows **PC Offline**, even with the PC on | Same as above: the IP or the port check is wrong. |
| **Find PCs** doesn't list your PC | Make sure the PC is on and connected to the same network, with *File and printer sharing* enabled. Guest networks and routers with "AP/client isolation" turned on block discovery. |
| Error mentions failing to send the WoL packet | The handheld isn't connected to the network, or **WoL Broadcast** is malformed. |
| App shows a black screen or closes immediately | Check the log file (below). On the Deck, re-run the installer to reinstall the dependencies. |

### Where files live

| | Steam Deck | Windows |
|---|---|---|
| App | `/home/deck/awake-on-deck` | `%LOCALAPPDATA%\awake-on-deck` |
| Config | `~/AppData/Roaming/awake-on-deck/config.json` | `%APPDATA%\awake-on-deck\config.json` |
| Log | `~/AppData/Local/awake-on-deck/steamdeck-client.log` | `%LOCALAPPDATA%\awake-on-deck\steamdeck-client.log` |

To see more detail in the log, start the app with `LOG_LEVEL=DEBUG` set in its environment.

---

## 7. Updating

Re-run the same installer you used originally. It pulls the latest version and reinstalls the dependencies.

- **Steam Deck** (Desktop Mode): `bash /home/deck/awake-on-deck/install.sh`
- **Windows**: run the `irm ... | iex` command from section 2 again

> The update **discards any local changes** in the app folder. Your settings are not affected, because they live in the config file, outside the app folder.

---

## 8. Uninstalling

**Steam Deck**

1. In Steam, right-click **Awake on Deck** → *Manage* → *Remove non-Steam game from your library*.
2. Delete `/home/deck/awake-on-deck` and `~/AppData/Roaming/awake-on-deck`.

**Windows**

1. Remove the game from the Xbox app library if you added it there.
2. Delete the desktop shortcut, `%LOCALAPPDATA%\awake-on-deck`, and `%APPDATA%\awake-on-deck`.
