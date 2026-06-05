using System.ComponentModel;
using AwakeOnDeck.WindowsService.Models;
using Microsoft.Extensions.Options;
using Microsoft.Win32;

namespace AwakeOnDeck.WindowsService;

public sealed class UnlockService : IUnlockService
{
    private readonly ILogger<UnlockService> _logger;
    private readonly AppSettings _settings;
    private readonly ICredentialManager _credentialManager;
    private readonly IWinApiProvider _winApi;

    private const string SasRegKey = @"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System";
    private const string SasRegValue = "SoftwareSASGeneration";
    private const string CredentialTarget = "AwakeOnDeck";

    public UnlockService(
        ILogger<UnlockService> logger,
        IOptions<AppSettings> settings,
        ICredentialManager credentialManager,
        IWinApiProvider winApi)
    {
        _logger = logger;
        _settings = settings.Value;
        _credentialManager = credentialManager;
        _winApi = winApi;
    }

    public void CheckStartupRequirements()
    {
        try
        {
            using var key = Registry.LocalMachine.OpenSubKey(SasRegKey);
            var value = key?.GetValue(SasRegValue);
            if (value is null || Convert.ToInt32(value) < 1)
            {
                _logger.LogError(
                    "SoftwareSASGeneration registry value is missing or zero. " +
                    "SendSAS will be silently ignored on this machine. Run install.ps1 to fix this.");
            }
            else
            {
                _logger.LogInformation("SoftwareSASGeneration registry value OK ({Value})", value);
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Failed to read SoftwareSASGeneration registry value");
        }
    }

    public async Task UnlockAsync()
    {
        _logger.LogInformation("Unlock sequence starting");

        // Step 1: Check session state
        bool isLocked;
        try
        {
            isLocked = _winApi.IsConsoleSessionLocked();
        }
        catch (Win32Exception ex)
        {
            _logger.LogError(ex, "WTSQuerySessionInformation failed (error {Code})", ex.NativeErrorCode);
            return;
        }

        if (!isLocked)
        {
            _logger.LogWarning("Console session is already active/unlocked — no action needed");
            return;
        }

        // Step 2: SendSAS — simulate Ctrl+Alt+Del to bring up the credential provider UI
        try
        {
            _winApi.SendSas();
        }
        catch (Win32Exception ex)
        {
            _logger.LogError(ex, "SendSAS failed (error {Code})", ex.NativeErrorCode);
            return;
        }

        // Step 3: Wait for the credential prompt to appear
        await Task.Delay(_settings.UnlockDelayMs);

        // Step 4: Read password from Credential Manager and type it into the credential UI
        var (_, password) = _credentialManager.ReadCredential(CredentialTarget);
        if (string.IsNullOrEmpty(password))
        {
            _logger.LogError(
                "No credentials found in Credential Manager under '{Target}'. Run install.ps1 to store credentials.",
                CredentialTarget);
            return;
        }

        try
        {
            _winApi.TypePassword(password);
            _logger.LogInformation("Password sent to credential provider; unlock sequence completed");
        }
        catch (Win32Exception ex)
        {
            _logger.LogError(ex, "Failed to send password to credential provider (error {Code})", ex.NativeErrorCode);
        }
    }
}
