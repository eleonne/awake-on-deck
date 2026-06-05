using System.ComponentModel;
using System.Runtime.InteropServices;

namespace AwakeOnDeck.WindowsService.WinApi;

internal static partial class User32
{
    private const uint INPUT_KEYBOARD = 1;
    private const uint KEYEVENTF_KEYUP = 0x0002;
    private const uint KEYEVENTF_UNICODE = 0x0004;
    private const ushort VK_RETURN = 0x0D;

    [StructLayout(LayoutKind.Sequential)]
    private struct KEYBDINPUT
    {
        public ushort wVk;
        public ushort wScan;
        public uint dwFlags;
        public uint time;
        public IntPtr dwExtraInfo;
    }

    // INPUT is 40 bytes on x64: 4 (type) + 4 (padding) + 32 (union, padded to largest member)
    [StructLayout(LayoutKind.Explicit, Size = 40)]
    private struct INPUT
    {
        [FieldOffset(0)] public uint type;
        [FieldOffset(8)] public KEYBDINPUT ki;
    }

    [LibraryImport("user32.dll", SetLastError = true)]
    private static partial uint SendInput(uint nInputs, [In] INPUT[] pInputs, int cbSize);

    /// <summary>
    /// Types the password followed by Enter via SendInput.
    /// Must be called from a process running in the interactive session on the target desktop —
    /// use InteractiveProcess.SpawnAndTypePassword to launch such a process from a service.
    /// </summary>
    internal static void TypePasswordOnCurrentDesktop(string password)
    {
        SendKeys(password);
    }

    private static void SendKeys(string text)
    {
        // Two INPUT events per character (key-down + key-up), plus Enter down + up.
        var inputs = new INPUT[text.Length * 2 + 2];
        int i = 0;

        foreach (char c in text)
        {
            inputs[i++] = new INPUT
            {
                type = INPUT_KEYBOARD,
                ki = new KEYBDINPUT { wScan = c, dwFlags = KEYEVENTF_UNICODE }
            };
            inputs[i++] = new INPUT
            {
                type = INPUT_KEYBOARD,
                ki = new KEYBDINPUT { wScan = c, dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP }
            };
        }

        inputs[i++] = new INPUT { type = INPUT_KEYBOARD, ki = new KEYBDINPUT { wVk = VK_RETURN } };
        inputs[i]   = new INPUT { type = INPUT_KEYBOARD, ki = new KEYBDINPUT { wVk = VK_RETURN, dwFlags = KEYEVENTF_KEYUP } };

        uint sent = SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<INPUT>());
        if (sent == 0)
            throw new Win32Exception(Marshal.GetLastWin32Error());
    }
}
