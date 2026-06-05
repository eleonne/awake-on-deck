using System.ComponentModel;
using System.Runtime.InteropServices;

namespace AwakeOnDeck.WindowsService.WinApi;

internal static partial class Wtsapi32
{
private const int WTSSessionInfoExClass = 25; // WTS_INFO_CLASS — returns WTSINFOEX with SessionFlags
    private const uint NoConsoleSession = 0xFFFFFFFF;

    // SessionFlags values inside WTSINFOEX_LEVEL1
    private const int WTS_SESSIONSTATE_LOCK = 0;
    private const int WTS_SESSIONSTATE_UNLOCK = 1;

    // Byte offsets inside the WTSINFOEX buffer:
    //   offset 0: Level (DWORD)
    //   offset 4: WTSINFOEX_LEVEL1.SessionId (DWORD)
    //   offset 8: WTSINFOEX_LEVEL1.SessionState (int)
    //   offset 12: WTSINFOEX_LEVEL1.SessionFlags (LONG)
    private const int SessionFlagsOffset = 12;

    // Returns the session ID of the physical console; 0xFFFFFFFF when no session exists.
    [LibraryImport("kernel32.dll")]
    private static partial uint WTSGetActiveConsoleSessionId();

    internal static uint GetActiveConsoleSessionId() => WTSGetActiveConsoleSessionId();

    [LibraryImport("wtsapi32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static partial bool WTSQuerySessionInformationW(
        IntPtr hServer,
        int SessionId,
        int WTSInfoClass,
        out IntPtr ppBuffer,
        out int pBytesReturned);

    [LibraryImport("wtsapi32.dll")]
    private static partial void WTSFreeMemory(IntPtr pMemory);

    /// <summary>
    /// Returns true when the console session is locked or at the login screen.
    /// Returns true (treat as locked) when no console session is active.
    /// </summary>
    internal static bool IsConsoleSessionLocked()
    {
        uint sessionId = WTSGetActiveConsoleSessionId();

        // No active console session — treat as locked so the unlock sequence runs.
        if (sessionId == NoConsoleSession)
            return true;

        if (!WTSQuerySessionInformationW(
                IntPtr.Zero,
                (int)sessionId,
                WTSSessionInfoExClass,
                out var pBuffer,
                out _))
        {
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }

        try
        {
            // SessionFlags at offset 12: 0 = locked, 1 = unlocked, anything else = unknown (treat as locked)
            int sessionFlags = Marshal.ReadInt32(pBuffer, SessionFlagsOffset);
            return sessionFlags != WTS_SESSIONSTATE_UNLOCK;
        }
        finally
        {
            WTSFreeMemory(pBuffer);
        }
    }
}
