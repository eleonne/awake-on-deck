#Requires -RunAsAdministrator
[CmdletBinding()]
param(
    [string]$InstallDir = "C:\ProgramData\AwakeOnDeck"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ServiceName = "AwakeOnDeck"
$CredTarget  = "AwakeOnDeck"
$RegPath     = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"

Write-Host "=== AwakeOnDeck Uninstaller ===" -ForegroundColor Cyan

# Stop and remove service
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Host "Stopping and removing service..." -ForegroundColor Yellow
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    & sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 2
    Write-Host "  Service removed." -ForegroundColor Green
} else {
    Write-Host "  Service '$ServiceName' not found — skipping." -ForegroundColor Gray
}

# Remove credentials from Credential Manager
Write-Host "Removing credentials from Credential Manager..." -ForegroundColor Yellow
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class CredentialRemover
{
    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern bool CredDeleteW(string target, uint type, uint flags);
}
'@ -ErrorAction SilentlyContinue

$deleted = [CredentialRemover]::CredDeleteW($CredTarget, 1, 0)
if ($deleted) {
    Write-Host "  Credentials removed." -ForegroundColor Green
} else {
    Write-Host "  No credentials found for '$CredTarget' — skipping." -ForegroundColor Gray
}

# Remove SoftwareSASGeneration registry value
Write-Host "Removing SoftwareSASGeneration registry value..." -ForegroundColor Yellow
if ((Get-ItemProperty -Path $RegPath -Name "SoftwareSASGeneration" -ErrorAction SilentlyContinue) -ne $null) {
    Remove-ItemProperty -Path $RegPath -Name "SoftwareSASGeneration"
    Write-Host "  Registry value removed." -ForegroundColor Green
} else {
    Write-Host "  Registry value not present — skipping." -ForegroundColor Gray
}

# Remove install directory
if (Test-Path $InstallDir) {
    Write-Host "Removing install directory '$InstallDir'..." -ForegroundColor Yellow
    Remove-Item -Path $InstallDir -Recurse -Force
    Write-Host "  Directory removed." -ForegroundColor Green
} else {
    Write-Host "  Install directory '$InstallDir' not found — skipping." -ForegroundColor Gray
}

Write-Host ""
Write-Host "AwakeOnDeck uninstalled." -ForegroundColor Green
