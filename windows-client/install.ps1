#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$InstallDir = "C:\ProgramData\AwakeOnDeck"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectPath = "$PSScriptRoot\src\AwakeOnDeck.WindowsService"
$ServiceName = "AwakeOnDeck"
$ExeName     = "AwakeOnDeck.WindowsService.exe"
$ExePath     = "$InstallDir\$ExeName"

Write-Host "=== AwakeOnDeck Installer ===" -ForegroundColor Cyan

# 1. Publish self-contained single-file exe
Write-Host "Publishing project..." -ForegroundColor Yellow
dotnet publish "$ProjectPath" -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -o "$InstallDir"
Write-Host "  Published to $InstallDir" -ForegroundColor Green

# 2. Set SoftwareSASGeneration registry value
Write-Host "Setting SoftwareSASGeneration registry value..." -ForegroundColor Yellow
$RegPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
Set-ItemProperty -Path $RegPath -Name "SoftwareSASGeneration" -Value 1 -Type DWord
Write-Host "  SoftwareSASGeneration = 1" -ForegroundColor Green

# 3. Stop and remove existing service if present
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Host "Stopping existing service..." -ForegroundColor Yellow
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    & sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 2
    Write-Host "  Existing service removed." -ForegroundColor Green
}

# 4. Register the Windows service
Write-Host "Registering Windows service..." -ForegroundColor Yellow
& sc.exe create $ServiceName binPath= "`"$ExePath`"" start= auto obj= LocalSystem DisplayName= "Awake on Deck"
& sc.exe description $ServiceName "Listens for Wake-on-LAN unlock triggers from the Steam Deck and unlocks the Windows session."
Write-Host "  Service registered." -ForegroundColor Green

# 5. Store credentials in Windows Credential Manager
Write-Host ""
Write-Host "Enter your Windows login credentials." -ForegroundColor Cyan
Write-Host "These will be stored in Windows Credential Manager (DPAPI-encrypted) and never written to a config file." -ForegroundColor Cyan
$credential = Get-Credential -Message "Windows credentials for auto-unlock (stored securely in Credential Manager)"
$username   = $credential.UserName
$password   = $credential.GetNetworkCredential().Password

# Inline PowerShell CredWrite using P/Invoke
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class CredentialStore
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct CREDENTIAL
    {
        public uint Flags;
        public uint Type;
        [MarshalAs(UnmanagedType.LPWStr)] public string TargetName;
        [MarshalAs(UnmanagedType.LPWStr)] public string Comment;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
        public uint CredentialBlobSize;
        public IntPtr CredentialBlob;
        public uint Persist;
        public uint AttributeCount;
        public IntPtr Attributes;
        [MarshalAs(UnmanagedType.LPWStr)] public string TargetAlias;
        [MarshalAs(UnmanagedType.LPWStr)] public string UserName;
    }

    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool CredWriteW(ref CREDENTIAL userCredential, uint flags);

    public static void Write(string target, string user, string pass)
    {
        byte[] blob = Encoding.Unicode.GetBytes(pass);
        GCHandle handle = GCHandle.Alloc(blob, GCHandleType.Pinned);
        try
        {
            var cred = new CREDENTIAL
            {
                Type = 1,
                TargetName = target,
                UserName = user,
                CredentialBlobSize = (uint)blob.Length,
                CredentialBlob = handle.AddrOfPinnedObject(),
                Persist = 2
            };
            if (!CredWriteW(ref cred, 0))
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
        }
        finally { handle.Free(); }
    }
}
'@

[CredentialStore]::Write("AwakeOnDeck", $username, $password)
Write-Host "  Credentials stored in Credential Manager." -ForegroundColor Green

# 6. Start the service
Write-Host "Starting service..." -ForegroundColor Yellow
Start-Service -Name $ServiceName
Write-Host "  Service started." -ForegroundColor Green

Write-Host ""
Write-Host "AwakeOnDeck installed and running." -ForegroundColor Green
Write-Host "Logs: Event Viewer > Windows Logs > Application > Source: AwakeOnDeck" -ForegroundColor Cyan
Write-Host "To send a test packet from PowerShell:" -ForegroundColor Cyan
Write-Host '  $u = New-Object System.Net.Sockets.UdpClient' -ForegroundColor Gray
Write-Host '  $b = [Text.Encoding]::UTF8.GetBytes("unlock")' -ForegroundColor Gray
Write-Host '  $u.Send($b, $b.Length, "127.0.0.1", 9876)' -ForegroundColor Gray
Write-Host '  $u.Close()' -ForegroundColor Gray
