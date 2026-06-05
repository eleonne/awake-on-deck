using AwakeOnDeck.WindowsService.WinApi;

namespace AwakeOnDeck.WindowsService;

internal sealed class WinApiProvider : IWinApiProvider
{
    public bool IsConsoleSessionLocked() => Wtsapi32.IsConsoleSessionLocked();

    public void SendSas() => Sas.SendSas();

    public void TypePassword(string password)
    {
        uint sessionId = Wtsapi32.GetActiveConsoleSessionId();
        string exePath = Environment.ProcessPath
            ?? throw new InvalidOperationException("Cannot determine process path to spawn helper");
        InteractiveProcess.SpawnAndTypePassword(sessionId, password, exePath);
    }
}
