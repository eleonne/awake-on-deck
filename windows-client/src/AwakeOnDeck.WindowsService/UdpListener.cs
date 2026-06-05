using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using AwakeOnDeck.WindowsService.Models;
using Microsoft.Extensions.Options;

namespace AwakeOnDeck.WindowsService;

public sealed class UdpListener
{
    private readonly ILogger<UdpListener> _logger;
    private readonly AppSettings _settings;

    public event EventHandler? TriggerReceived;

    public UdpListener(ILogger<UdpListener> logger, IOptions<AppSettings> settings)
    {
        _logger = logger;
        _settings = settings.Value;
    }

    public async Task RunAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                using var udp = new UdpClient(_settings.ListenPort);
                _logger.LogInformation("UDP listener bound on port {Port}", _settings.ListenPort);
                await ListenLoopAsync(udp, cancellationToken);
            }
            catch (OperationCanceledException)
            {
                throw;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "UDP socket error; restarting listener in 2 seconds");
                try
                {
                    await Task.Delay(TimeSpan.FromSeconds(2), cancellationToken);
                }
                catch (OperationCanceledException)
                {
                    throw;
                }
            }
        }
    }

    private async Task ListenLoopAsync(UdpClient udp, CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            UdpReceiveResult result;
            try
            {
                result = await udp.ReceiveAsync(cancellationToken);
            }
            catch (OperationCanceledException)
            {
                throw;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error receiving UDP packet");
                throw; // outer loop restarts
            }

            var payload = Encoding.UTF8.GetString(result.Buffer);
            _logger.LogInformation("Received UDP packet from {Remote}: length={Len}",
                result.RemoteEndPoint, result.Buffer.Length);

            if (ValidatePacket(payload))
            {
                _logger.LogInformation("Valid trigger received from {Remote}", result.RemoteEndPoint);
                TriggerReceived?.Invoke(this, EventArgs.Empty);
            }
        }
    }

    /// <summary>
    /// Validates the raw packet payload.
    /// Expected formats:
    ///   - No secret: "unlock" or "unlock:*"
    ///   - With secret: "unlock:{timestamp}:{hmac-sha256-hex}"
    /// </summary>
    public bool ValidatePacket(string payload)
    {
        if (!payload.StartsWith("unlock", StringComparison.Ordinal))
        {
            _logger.LogWarning("Rejected packet: does not start with 'unlock'");
            return false;
        }

        if (string.IsNullOrEmpty(_settings.SharedSecret))
        {
            // No secret — accept anything that starts with "unlock"
            return true;
        }

        // Expect: unlock:<timestamp>:<hmac-sha256-hex>
        var parts = payload.Split(':');
        if (parts.Length < 3)
        {
            _logger.LogWarning("Rejected packet: SharedSecret is configured but packet has no HMAC suffix");
            return false;
        }

        // Signed message is "unlock:<timestamp>"
        var message = $"{parts[0]}:{parts[1]}";
        var receivedHmac = parts[2].ToLowerInvariant();

        var key = Encoding.UTF8.GetBytes(_settings.SharedSecret);
        var msgBytes = Encoding.UTF8.GetBytes(message);
        var expectedHmac = Convert.ToHexString(HMACSHA256.HashData(key, msgBytes)).ToLowerInvariant();

        if (!CryptographicOperations.FixedTimeEquals(
                Encoding.ASCII.GetBytes(expectedHmac),
                Encoding.ASCII.GetBytes(receivedHmac)))
        {
            _logger.LogWarning("Rejected packet: HMAC validation failed");
            return false;
        }

        return true;
    }
}
