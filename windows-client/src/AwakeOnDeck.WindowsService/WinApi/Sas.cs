using System.Runtime.InteropServices;

namespace AwakeOnDeck.WindowsService.WinApi;

internal static partial class Sas
{
    [LibraryImport("sas.dll")]
    private static partial void SendSAS([MarshalAs(UnmanagedType.Bool)] bool AsUser);

    /// <summary>
    /// Sends Ctrl+Alt+Del to the console session's secure desktop.
    /// Requires SoftwareSASGeneration registry value >= 1 or the call is silently ignored.
    /// </summary>
    internal static void SendSas()
    {
        SendSAS(false);
    }
}
