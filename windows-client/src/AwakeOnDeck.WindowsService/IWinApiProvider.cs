namespace AwakeOnDeck.WindowsService;

public interface IWinApiProvider
{
    bool IsConsoleSessionLocked();
    void SendSas();
    void TypePassword(string password);
}
