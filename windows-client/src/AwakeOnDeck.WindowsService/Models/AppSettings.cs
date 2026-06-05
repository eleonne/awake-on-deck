namespace AwakeOnDeck.WindowsService.Models;

public sealed record AppSettings
{
    public int ListenPort { get; init; } = 9876;
    public string SharedSecret { get; init; } = string.Empty;
    public int UnlockDelayMs { get; init; } = 500;
}
