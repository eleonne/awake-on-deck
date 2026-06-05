using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;

namespace AwakeOnDeck.WindowsService.WinApi;

/// <summary>
/// Spawns a process inside the interactive session's Winlogon desktop using the token of
/// winlogon.exe running in that session. This avoids needing SeTcbPrivilege (required by
/// WTSQueryUserToken) and works with LocalSystem's always-enabled SE_IMPERSONATE_PRIVILEGE.
/// </summary>
internal static class InteractiveProcess
{
    // ── Structs ──────────────────────────────────────────────────────────────

    [StructLayout(LayoutKind.Sequential)]
    private struct SECURITY_ATTRIBUTES
    {
        public uint nLength;
        public IntPtr lpSecurityDescriptor;
        [MarshalAs(UnmanagedType.Bool)]
        public bool bInheritHandle;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct STARTUPINFOW
    {
        public int cb;
        public string? lpReserved;
        public string? lpDesktop;
        public string? lpTitle;
        public uint dwX, dwY, dwXSize, dwYSize;
        public uint dwXCountChars, dwYCountChars;
        public uint dwFillAttribute, dwFlags;
        public ushort wShowWindow;
        public ushort cbReserved2;
        public IntPtr lpReserved2;
        public IntPtr hStdInput;
        public IntPtr hStdOutput;
        public IntPtr hStdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct PROCESS_INFORMATION
    {
        public IntPtr hProcess;
        public IntPtr hThread;
        public uint dwProcessId;
        public uint dwThreadId;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct PROCESSENTRY32W
    {
        public uint dwSize;
        public uint cntUsage;
        public uint th32ProcessID;
        public IntPtr th32DefaultHeapID;
        public uint th32ModuleID;
        public uint cntThreads;
        public uint th32ParentProcessID;
        public int pcPriClassBase;
        public uint dwFlags;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)]
        public string szExeFile;
    }

    // ── Constants ─────────────────────────────────────────────────────────────

    private const uint TH32CS_SNAPPROCESS = 0x00000002;
    private static readonly IntPtr INVALID_HANDLE_VALUE = new IntPtr(-1);

    private const uint PROCESS_QUERY_INFORMATION = 0x0400;
    private const uint TOKEN_DUPLICATE = 0x0002;
    private const uint TOKEN_QUERY = 0x0008;
    private const uint TOKEN_IMPERSONATE = 0x0004;
    private const uint TOKEN_ALL_ACCESS = 0xF01FF;
    private const int SecurityImpersonation = 2;
    private const int TokenPrimary = 1;

    private const uint CREATE_NO_WINDOW = 0x08000000;
    private const uint LOGON_WITH_PROFILE = 0x00000001;
    private const uint STARTF_USESTDHANDLES = 0x00000100;
    private const uint HANDLE_FLAG_INHERIT = 0x00000001;
    private const uint WAIT_TIMEOUT = 0x00000102;

    // ── P/Invoke ──────────────────────────────────────────────────────────────

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr CreateToolhelp32Snapshot(uint dwFlags, uint th32ProcessID);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool Process32FirstW(IntPtr hSnapshot, ref PROCESSENTRY32W lppe);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool Process32NextW(IntPtr hSnapshot, ref PROCESSENTRY32W lppe);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr OpenProcess(uint dwDesiredAccess,
        [MarshalAs(UnmanagedType.Bool)] bool bInheritHandle, uint dwProcessId);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool ProcessIdToSessionId(uint dwProcessId, out uint pSessionId);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool OpenProcessToken(IntPtr hProcess, uint dwDesiredAccess, out SafeTokenHandle phToken);

    [DllImport("advapi32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool DuplicateTokenEx(
        SafeTokenHandle hExistingToken,
        uint dwDesiredAccess,
        IntPtr lpTokenAttributes,
        int ImpersonationLevel,
        int TokenType,
        out SafeTokenHandle phNewToken);

    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CreateProcessWithTokenW(
        SafeTokenHandle hToken,
        uint dwLogonFlags,
        string? lpApplicationName,
        string lpCommandLine,
        uint dwCreationFlags,
        IntPtr lpEnvironment,
        string? lpCurrentDirectory,
        ref STARTUPINFOW lpStartupInfo,
        out PROCESS_INFORMATION lpProcessInformation);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CreatePipe(
        out IntPtr hReadPipe,
        out IntPtr hWritePipe,
        ref SECURITY_ATTRIBUTES lpPipeAttributes,
        uint nSize);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetHandleInformation(IntPtr hObject, uint dwMask, uint dwFlags);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern uint WaitForSingleObject(IntPtr hHandle, uint dwMilliseconds);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CloseHandle(IntPtr hObject);

    // ── Implementation ────────────────────────────────────────────────────────

    /// <summary>
    /// Finds winlogon.exe running in <paramref name="sessionId"/> and returns a duplicate of
    /// its primary token. Requires only SE_IMPERSONATE_PRIVILEGE (always enabled on LocalSystem).
    /// </summary>
    private static SafeTokenHandle GetWinlogonToken(uint sessionId)
    {
        IntPtr snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
        if (snapshot == INVALID_HANDLE_VALUE)
            throw new Win32Exception(Marshal.GetLastWin32Error());

        try
        {
            var entry = new PROCESSENTRY32W { dwSize = (uint)Marshal.SizeOf<PROCESSENTRY32W>() };
            if (!Process32FirstW(snapshot, ref entry))
                throw new Win32Exception(Marshal.GetLastWin32Error());

            do
            {
                if (!entry.szExeFile.Equals("winlogon.exe", StringComparison.OrdinalIgnoreCase))
                    continue;

                IntPtr hProcess = OpenProcess(PROCESS_QUERY_INFORMATION, false, entry.th32ProcessID);
                if (hProcess == IntPtr.Zero)
                    continue;

                try
                {
                    if (!ProcessIdToSessionId(entry.th32ProcessID, out uint procSession) || procSession != sessionId)
                        continue;

                    if (!OpenProcessToken(hProcess, TOKEN_DUPLICATE | TOKEN_QUERY | TOKEN_IMPERSONATE, out var token))
                        throw new Win32Exception(Marshal.GetLastWin32Error());

                    using (token)
                    {
                        if (!DuplicateTokenEx(token, TOKEN_ALL_ACCESS, IntPtr.Zero,
                                SecurityImpersonation, TokenPrimary, out var dup))
                            throw new Win32Exception(Marshal.GetLastWin32Error());
                        return dup;
                    }
                }
                finally
                {
                    CloseHandle(hProcess);
                }
            }
            while (Process32NextW(snapshot, ref entry));
        }
        finally
        {
            CloseHandle(snapshot);
        }

        throw new InvalidOperationException($"winlogon.exe not found in session {sessionId}");
    }

    /// <summary>
    /// Launches the given exe with --type-password on the Winlogon desktop in the interactive
    /// session, passing the password via stdin. Uses winlogon.exe's token so no TCB privilege
    /// is required from the calling service.
    /// </summary>
    internal static void SpawnAndTypePassword(uint sessionId, string password, string exePath)
    {
        using var token = GetWinlogonToken(sessionId);

        var sa = new SECURITY_ATTRIBUTES
        {
            nLength = (uint)Marshal.SizeOf<SECURITY_ATTRIBUTES>(),
            bInheritHandle = true,
        };

        if (!CreatePipe(out var hRead, out var hWrite, ref sa, 0))
            throw new Win32Exception(Marshal.GetLastWin32Error());

        // Write end must NOT be inheritable so the child sees EOF when we close it.
        SetHandleInformation(hWrite, HANDLE_FLAG_INHERIT, 0);

        var si = new STARTUPINFOW
        {
            cb = Marshal.SizeOf<STARTUPINFOW>(),
            lpDesktop = @"WinSta0\Winlogon",
            dwFlags = STARTF_USESTDHANDLES,
            hStdInput = hRead,
            hStdOutput = IntPtr.Zero,
            hStdError = IntPtr.Zero,
        };

        string cmdLine = $"\"{exePath}\" --type-password";

        bool created = CreateProcessWithTokenW(
            token,
            LOGON_WITH_PROFILE,
            null,
            cmdLine,
            CREATE_NO_WINDOW,
            IntPtr.Zero,
            null,
            ref si,
            out var pi);

        // Parent closes its copy of the read end now that the child has inherited it.
        CloseHandle(hRead);

        if (!created)
        {
            CloseHandle(hWrite);
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }

        // Write password then close the write end so the child sees EOF.
        try
        {
            using var writeHandle = new Microsoft.Win32.SafeHandles.SafeFileHandle(hWrite, ownsHandle: true);
            using var stream = new FileStream(writeHandle, FileAccess.Write);
            using var writer = new StreamWriter(stream, Encoding.UTF8);
            writer.WriteLine(password);
        }
        catch
        {
            WaitForSingleObject(pi.hProcess, 5000);
            CloseHandle(pi.hProcess);
            CloseHandle(pi.hThread);
            throw;
        }

        uint waitResult = WaitForSingleObject(pi.hProcess, 10_000);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);

        if (waitResult == WAIT_TIMEOUT)
            throw new TimeoutException("--type-password helper process did not exit within 10 seconds");
    }
}
