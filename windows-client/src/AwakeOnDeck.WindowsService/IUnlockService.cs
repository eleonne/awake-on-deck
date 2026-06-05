namespace AwakeOnDeck.WindowsService;

public interface IUnlockService
{
    void CheckStartupRequirements();
    Task UnlockAsync();
}
