using System.ComponentModel;
using AwakeOnDeck.WindowsService;
using AwakeOnDeck.WindowsService.Models;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Moq;
using Xunit;

namespace AwakeOnDeck.WindowsService.Tests;

public sealed class UnlockServiceTests
{
    private static UnlockService CreateService(
        IWinApiProvider winApi,
        ICredentialManager credentialManager,
        int unlockDelayMs = 0)
    {
        var settings = Options.Create(new AppSettings { UnlockDelayMs = unlockDelayMs });
        return new UnlockService(
            NullLogger<UnlockService>.Instance,
            settings,
            credentialManager,
            winApi);
    }

    [Fact]
    public async Task UnlockAsync_WhenSessionLocked_SendsSasAndTypesPassword()
    {
        var winApi = new Mock<IWinApiProvider>();
        var credMgr = new Mock<ICredentialManager>();

        winApi.Setup(w => w.IsConsoleSessionLocked()).Returns(true);
        credMgr.Setup(c => c.ReadCredential("AwakeOnDeck")).Returns(("testuser", "testpass"));

        var service = CreateService(winApi.Object, credMgr.Object);
        await service.UnlockAsync();

        winApi.Verify(w => w.SendSas(), Times.Once);
        winApi.Verify(w => w.TypePassword("testpass"), Times.Once);
    }

    [Fact]
    public async Task UnlockAsync_WhenSessionAlreadyActive_SkipsUnlockSequence()
    {
        var winApi = new Mock<IWinApiProvider>();
        var credMgr = new Mock<ICredentialManager>();

        winApi.Setup(w => w.IsConsoleSessionLocked()).Returns(false);

        var service = CreateService(winApi.Object, credMgr.Object);
        await service.UnlockAsync();

        winApi.Verify(w => w.SendSas(), Times.Never);
        winApi.Verify(w => w.TypePassword(It.IsAny<string>()), Times.Never);
    }

    [Fact]
    public async Task UnlockAsync_WhenNoCredentialsStored_LogsErrorAndDoesNotTypePassword()
    {
        var winApi = new Mock<IWinApiProvider>();
        var credMgr = new Mock<ICredentialManager>();

        winApi.Setup(w => w.IsConsoleSessionLocked()).Returns(true);
        credMgr.Setup(c => c.ReadCredential("AwakeOnDeck")).Returns(("", ""));

        var service = CreateService(winApi.Object, credMgr.Object);
        await service.UnlockAsync();

        winApi.Verify(w => w.TypePassword(It.IsAny<string>()), Times.Never);
    }

    [Fact]
    public async Task UnlockAsync_WhenTypePasswordThrows_LogsErrorWithoutCrashing()
    {
        var winApi = new Mock<IWinApiProvider>();
        var credMgr = new Mock<ICredentialManager>();

        winApi.Setup(w => w.IsConsoleSessionLocked()).Returns(true);
        winApi.Setup(w => w.TypePassword(It.IsAny<string>()))
              .Throws(new Win32Exception(5)); // ERROR_ACCESS_DENIED
        credMgr.Setup(c => c.ReadCredential("AwakeOnDeck")).Returns(("user", "pass"));

        var service = CreateService(winApi.Object, credMgr.Object);
        // Must not throw
        await service.UnlockAsync();
    }
}
