using System.Security.Cryptography;
using System.Text;
using AwakeOnDeck.WindowsService;
using AwakeOnDeck.WindowsService.Models;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Xunit;

namespace AwakeOnDeck.WindowsService.Tests;

public sealed class UdpListenerTests
{
    private static UdpListener CreateListener(string sharedSecret = "")
    {
        var settings = Options.Create(new AppSettings { SharedSecret = sharedSecret });
        return new UdpListener(NullLogger<UdpListener>.Instance, settings);
    }

    [Fact]
    public void ValidatePacket_NoSecret_AcceptsPlainUnlock()
    {
        var listener = CreateListener();
        Assert.True(listener.ValidatePacket("unlock"));
    }

    [Fact]
    public void ValidatePacket_NoSecret_AcceptsUnlockWithAnyPayload()
    {
        var listener = CreateListener();
        Assert.True(listener.ValidatePacket("unlock:1000000:somearbitraryhex"));
    }

    [Fact]
    public void ValidatePacket_NoSecret_RejectsNonUnlockPayload()
    {
        var listener = CreateListener();
        Assert.False(listener.ValidatePacket("hello"));
    }

    [Fact]
    public void ValidatePacket_WithSecret_AcceptsValidHmac()
    {
        const string secret = "mysecret";
        const string timestamp = "1000000";
        var message = $"unlock:{timestamp}";
        var key = Encoding.UTF8.GetBytes(secret);
        var msgBytes = Encoding.UTF8.GetBytes(message);
        var hmac = Convert.ToHexString(HMACSHA256.HashData(key, msgBytes)).ToLowerInvariant();

        var listener = CreateListener(secret);
        Assert.True(listener.ValidatePacket($"unlock:{timestamp}:{hmac}"));
    }

    [Fact]
    public void ValidatePacket_WithSecret_RejectsWrongHmac()
    {
        const string secret = "mysecret";
        var wrongHmac = new string('d', 64); // 64-char hex but wrong value
        var listener = CreateListener(secret);
        Assert.False(listener.ValidatePacket($"unlock:1000000:{wrongHmac}"));
    }

    [Fact]
    public void ValidatePacket_WithSecret_RejectsMissingHmac()
    {
        var listener = CreateListener("mysecret");
        // Only two parts — no HMAC suffix
        Assert.False(listener.ValidatePacket("unlock:1000000"));
    }
}
