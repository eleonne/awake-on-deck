# windows-client

## Project purpose

A C# .NET 10 Windows Service that runs in the background on a Windows PC. It listens for a UDP unlock trigger sent by the Steam Deck, then authenticates and unlocks the Windows session programmatically so Steam Remote Play can connect without the PC being stuck at the login/lock screen.

## Repository location

This project lives at `windows-client/` inside the `awake-on-deck` monorepo:

```
awake-on-deck/
├── steamdeck-client/
└── windows-client/        ← this project
    ├── CLAUDE.md
    ├── README.md
    ├── WindowsClient.sln
    └── src/
        └── AwakeOnDeck.WindowsService/
            ├── AwakeOnDeck.WindowsService.csproj
            ├── Program.cs                  # Host builder, service registration
            ├── Worker.cs                   # BackgroundService entry point
            ├── UdpListener.cs              # Listens for UDP trigger packets
            ├── UnlockService.cs            # Orchestrates the unlock sequence
            ├── WinApi/
            │   ├── Advapi32.cs             # LogonUser, ImpersonateLoggedOnUser P/Invoke
            │   ├── Wtsapi32.cs             # WTSQuerySessionInformation, WTSConnectSession P/Invoke
            │   └── Sas.cs                  # SendSAS P/Invoke (sas.dll)
            ├── CredentialManager.cs        # Read/write credentials via Windows Credential Manager
            ├── Models/
            │   └── AppSettings.cs          # Strongly-typed config (IOptions<AppSettings>)
            └── appsettings.json            # Default configuration
```

## Tech stack

- **Language**: C# 14 (.NET 10 ships with C# 14)
- **Runtime**: .NET 10 LTS (self-contained, win-x64 publish)
- **Host**: `Microsoft.Extensions.Hosting.WindowsServices` — integrates with Windows SCM
- **UDP listener**: `System.Net.Sockets.UdpClient` — stdlib, no dependencies
- **P/Invoke targets**: `advapi32.dll`, `wtsapi32.dll`, `sas.dll` — all ship with Windows
- **Credential storage**: Windows Credential Manager via `advapi32.dll` (`CredRead` / `CredWrite`)
- **Config**: `Microsoft.Extensions.Configuration` with `appsettings.json` + environment variable overrides
- **Logging**: `Microsoft.Extensions.Logging` with Windows Event Log sink (`UseWindowsEventLog`)
- **Tests**: xUnit 2.9+ + Moq 4.x (both support .NET 10)

No third-party NuGet packages beyond `Microsoft.Extensions.*`. Keep it that way.

## Project file

`AwakeOnDeck.WindowsService.csproj`:

```xml
<Project Sdk="Microsoft.NET.Sdk.Worker">
  <PropertyGroup>
    <TargetFramework>net10.0-windows</TargetFramework>
    <RuntimeIdentifier>win-x64</RuntimeIdentifier>
    <SelfContained>true</SelfContained>
    <PublishSingleFile>true</PublishSingleFile>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <AllowUnsafeBlocks>false</AllowUnsafeBlocks>
    <LangVersion>latest</LangVersion>
    <WindowsPackageType>None</WindowsPackageType>
  </PropertyGroup>

  <ItemGroup>
    <PackageReference Include="Microsoft.Extensions.Hosting.WindowsServices" Version="10.*" />
  </ItemGroup>
</Project>
```

Note `net10.0-windows` (not `net10.0`) — the `-windows` TFM is required for Windows-specific APIs (`UseWindowsEventLog`, Win32 interop types). Without it, Windows-only APIs will not resolve.

## C# 14 conventions

Use C# 14 features where they improve clarity. Specifically:

- **Primary constructors** on all classes that receive injected dependencies — no explicit constructor body unless logic is needed
- **`field` keyword** for property-backed fields (C# 14) instead of explicit backing fields
- **Collection expressions** (`[item1, item2]`) instead of `new List<T> { }` or array initializers
- **`nameof`** for all string references to member names (logging, exceptions)
- Pattern matching (`switch` expressions, `is` patterns) over `if/else` chains where it reads clearly
- Do **not** use `unsafe` blocks — `AllowUnsafeBlocks` is false; all P/Invoke via `[LibraryImport]` marshalling only

## Configuration

`appsettings.json`:

```json
{
  "AppSettings": {
    "ListenPort": 9876,
    "SharedSecret": "",
    "UnlockDelayMs": 500
  }
}
```

- `ListenPort`: UDP port to listen on (must match `agent_port` in steamdeck-client config)
- `SharedSecret`: HMAC-SHA256 key; if non-empty, all incoming packets are validated against it
- `UnlockDelayMs`: milliseconds to wait after SendSAS before submitting credentials

`AppSettings.cs` is a plain `record` bound via `IOptions<AppSettings>`. Never read `appsettings.json` directly elsewhere — always inject `IOptions<AppSettings>`.

Credentials (username + password) are **never stored in `appsettings.json`**. They live exclusively in Windows Credential Manager under the target name `AwakeOnDeck`. `CredentialManager.cs` owns all read/write access.

## UDP protocol

Incoming packet format (UTF-8 string):

```
unlock:<hmac-sha256-hex>
```

- If `SharedSecret` is empty, the `:<hmac>` suffix is optional and ignored
- If `SharedSecret` is set, the HMAC is computed as `HMAC-SHA256(key=SharedSecret, message="unlock")`
- Packets that fail HMAC validation are silently dropped and logged at Warning level
- Only packets from the configured source IP (or any IP if unconfigured) are accepted

`UdpListener.cs` is responsible only for receiving and validating packets. It raises a callback delegate on valid trigger — it does not perform the unlock itself.

## Unlock sequence

`UnlockService.cs` orchestrates the following steps in order:

1. **Check session state** — call `WTSQuerySessionInformation` (wtsapi32) to determine if the console session (session ID 1) is locked or at the login screen
2. **SendSAS** — call `SendSAS(FALSE)` via sas.dll to simulate Ctrl+Alt+Del on the console session, dismissing the secure desktop
3. **Wait** `UnlockDelayMs` milliseconds for the credential prompt to appear
4. **LogonUser** — call `LogonUser` (advapi32) with credentials read from Credential Manager to obtain a user token (`LOGON32_LOGON_INTERACTIVE`, `LOGON32_PROVIDER_DEFAULT`)
5. **ImpersonateLoggedOnUser** — attach the token to the console session
6. **Close token handle** — always close the handle in a `finally` block

If the session is already unlocked (active desktop), skip steps 2–5 and return success immediately.

## P/Invoke rules

All P/Invoke declarations live in `WinApi/`. Rules:

- Use `[LibraryImport]` (source-generated marshalling, available since .NET 7, preferred in .NET 10) — do **not** use `[DllImport]`
- `[LibraryImport]` requires `partial` methods and classes — all WinApi wrappers are `internal static partial class`
- Use `SafeHandle` subclasses for all handles — never raw `IntPtr` for anything that needs closing
- String marshalling must be explicit: `[MarshalAs(UnmanagedType.LPWStr)]` or `StringMarshalling.Utf16` in `[LibraryImport]`
- Never call P/Invoke methods directly from `UnlockService.cs` — go through a thin wrapper method in the same `WinApi/` class that throws `Win32Exception` (with `Marshal.GetLastWin32Error()`) on failure

## SendSAS prerequisite

`SendSAS` is silently ignored on modern Windows unless this registry value is set:

```
HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System
SoftwareSASGeneration = DWORD:1
```

The installer sets this value. `UnlockService.cs` must check for it on startup and log an error (not throw) if it is missing — throwing would prevent the service from starting and make the problem harder to diagnose.

## Service account

The service must run as `LocalSystem` (SYSTEM account). This is required for:

- `SendSAS` to reach the console session's secure desktop
- `WTSQuerySessionInformation` on session 1
- Writing to Windows Event Log

Never run the service as a limited user account — it will silently fail.

## Installation

A PowerShell installer script `install.ps1` lives at `windows-client/install.ps1`. It must be run as Administrator. It:

1. Publishes the project as a self-contained single-file exe:
   ```powershell
   dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true
   ```
2. Copies the exe to `C:\ProgramData\AwakeOnDeck\`
3. Sets the `SoftwareSASGeneration` registry value:
   ```powershell
   Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System" `
       -Name "SoftwareSASGeneration" -Value 1 -Type DWord
   ```
4. Registers the Windows service:
   ```powershell
   sc.exe create AwakeOnDeck binPath= "C:\ProgramData\AwakeOnDeck\AwakeOnDeck.WindowsService.exe" start= auto obj= LocalSystem
   ```
5. Prompts the user for their Windows username and password and stores them in Credential Manager
6. Starts the service: `sc.exe start AwakeOnDeck`

An uninstall script `uninstall.ps1` stops and removes the service, deletes the Credential Manager entry, and removes the registry value.

## Logging

- Use `ILogger<T>` injected via primary constructor — never static loggers
- In production (installed service), logs go to Windows Event Log under source `AwakeOnDeck`
- In development (`dotnet run`), logs go to console
- Log levels:
  - `Information`: service start/stop, successful unlock, credential manager operations
  - `Warning`: invalid/rejected UDP packets, session already unlocked (no-op)
  - `Error`: P/Invoke failures, missing registry key, credential read failures
- Never log the password or HMAC secret at any log level

## Running in development

```bash
# From windows-client/src/AwakeOnDeck.WindowsService/
dotnet run
```

The service runs as a console app when not installed as a Windows service. Send a test UDP packet:

```powershell
# PowerShell — send unlock trigger on localhost
$udp = New-Object System.Net.Sockets.UdpClient
$bytes = [System.Text.Encoding]::UTF8.GetBytes("unlock")
$udp.Send($bytes, $bytes.Length, "127.0.0.1", 9876)
$udp.Close()
```

## Testing

```bash
dotnet test
```

- Unit tests for `UdpListener` (packet validation, HMAC check) using Moq to mock the socket
- Unit tests for `UnlockService` with mocked `WinApi` wrappers — never call real P/Invoke in tests
- No integration tests that touch real Win32 APIs or the Credential Manager
- Tests target `net10.0-windows` in the test project csproj
- Tests live in `windows-client/tests/AwakeOnDeck.WindowsService.Tests/`

## Error handling

- P/Invoke failures throw `Win32Exception` with the error code — caught in `UnlockService.cs`, logged at Error, and the unlock attempt is aborted cleanly
- UDP socket errors are caught in `UdpListener.cs`; the listener restarts automatically after a 2-second delay using `await Task.Delay(2000, stoppingToken)` — do not let a transient socket error kill the service
- Unhandled exceptions in `Worker.cs` are caught at the top level, logged, and the service stops gracefully rather than crashing with an unhandled exception dialog
- Use `CancellationToken` propagation throughout — every async method accepts and forwards the token from `BackgroundService.ExecuteAsync`

## Security notes

- The HMAC secret and Windows credentials are the only sensitive values in the system
- The HMAC secret lives in `appsettings.json` (acceptable — it is not a credential, just a shared token)
- Windows credentials live exclusively in Credential Manager (DPAPI-encrypted, machine-scoped)
- The UDP listener binds to `0.0.0.0` by default; consider binding to the LAN interface only in production
- The service does not expose any HTTP endpoints or management interface

## Out of scope for this client

- Wake-on-LAN — handled by steamdeck-client
- Streaming — handled by Steam Remote Play
- Any UI — this is a headless background service