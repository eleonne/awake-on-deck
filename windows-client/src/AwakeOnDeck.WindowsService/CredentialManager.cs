using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;

namespace AwakeOnDeck.WindowsService;

public sealed class CredentialManager : ICredentialManager
{
    private readonly ILogger<CredentialManager> _logger;

    private const uint CRED_TYPE_GENERIC = 1;
    private const uint CRED_PERSIST_LOCAL_MACHINE = 2;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct CREDENTIAL
    {
        public uint Flags;
        public uint Type;
        [MarshalAs(UnmanagedType.LPWStr)]
        public string TargetName;
        [MarshalAs(UnmanagedType.LPWStr)]
        public string? Comment;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
        public uint CredentialBlobSize;
        public IntPtr CredentialBlob;
        public uint Persist;
        public uint AttributeCount;
        public IntPtr Attributes;
        [MarshalAs(UnmanagedType.LPWStr)]
        public string? TargetAlias;
        [MarshalAs(UnmanagedType.LPWStr)]
        public string? UserName;
    }

    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CredReadW(string target, uint type, uint flags, out IntPtr credentialPtr);

    [DllImport("advapi32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CredWriteW(ref CREDENTIAL userCredential, uint flags);

    [DllImport("advapi32.dll")]
    private static extern void CredFree(IntPtr buffer);

    public CredentialManager(ILogger<CredentialManager> logger)
    {
        _logger = logger;
    }

    public (string Username, string Password) ReadCredential(string targetName)
    {
        if (!CredReadW(targetName, CRED_TYPE_GENERIC, 0, out var credPtr))
        {
            int error = Marshal.GetLastWin32Error();
            _logger.LogError("CredRead failed for target '{Target}' (error {Code})", targetName, error);
            return (string.Empty, string.Empty);
        }

        try
        {
            var cred = Marshal.PtrToStructure<CREDENTIAL>(credPtr);
            string username = cred.UserName ?? string.Empty;
            string password = string.Empty;
            if (cred.CredentialBlobSize > 0)
            {
                var bytes = new byte[cred.CredentialBlobSize];
                Marshal.Copy(cred.CredentialBlob, bytes, 0, (int)cred.CredentialBlobSize);
                password = Encoding.Unicode.GetString(bytes);
            }
            _logger.LogInformation("Credentials read from Credential Manager for '{Target}'", targetName);
            return (username, password);
        }
        finally
        {
            CredFree(credPtr);
        }
    }

    public void WriteCredential(string targetName, string username, string password)
    {
        var passwordBytes = Encoding.Unicode.GetBytes(password);
        var handle = GCHandle.Alloc(passwordBytes, GCHandleType.Pinned);
        try
        {
            var cred = new CREDENTIAL
            {
                Type = CRED_TYPE_GENERIC,
                TargetName = targetName,
                UserName = username,
                CredentialBlobSize = (uint)passwordBytes.Length,
                CredentialBlob = handle.AddrOfPinnedObject(),
                Persist = CRED_PERSIST_LOCAL_MACHINE,
            };

            if (!CredWriteW(ref cred, 0))
                throw new Win32Exception(Marshal.GetLastWin32Error());

            _logger.LogInformation("Credentials written to Credential Manager for '{Target}'", targetName);
        }
        finally
        {
            handle.Free();
        }
    }
}
