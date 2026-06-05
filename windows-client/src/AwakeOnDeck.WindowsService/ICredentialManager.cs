namespace AwakeOnDeck.WindowsService;

public interface ICredentialManager
{
    (string Username, string Password) ReadCredential(string targetName);
    void WriteCredential(string targetName, string username, string password);
}
