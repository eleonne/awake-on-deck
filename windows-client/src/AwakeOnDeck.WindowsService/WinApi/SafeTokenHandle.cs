using Microsoft.Win32.SafeHandles;
using System.Runtime.InteropServices;

namespace AwakeOnDeck.WindowsService.WinApi;

public sealed class SafeTokenHandle : SafeHandleZeroOrMinusOneIsInvalid
{
    public SafeTokenHandle() : base(ownsHandle: true) { }

    protected override bool ReleaseHandle()
    {
        return CloseHandle(handle);
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CloseHandle(IntPtr hObject);
}
