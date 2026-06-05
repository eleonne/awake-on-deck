using AwakeOnDeck.WindowsService.Models;
using Microsoft.Extensions.Options;

namespace AwakeOnDeck.WindowsService;

public sealed class Worker : BackgroundService
{
    private readonly ILogger<Worker> _logger;
    private readonly UdpListener _udpListener;
    private readonly IUnlockService _unlockService;
    private readonly AppSettings _settings;

    public Worker(
        ILogger<Worker> logger,
        UdpListener udpListener,
        IUnlockService unlockService,
        IOptions<AppSettings> settings)
    {
        _logger = logger;
        _udpListener = udpListener;
        _unlockService = unlockService;
        _settings = settings.Value;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation(
            "AwakeOnDeck service starting, listening on UDP port {Port}", _settings.ListenPort);

        try
        {
            _unlockService.CheckStartupRequirements();
            _udpListener.TriggerReceived += OnTriggerReceived;
            await _udpListener.RunAsync(stoppingToken);
        }
        catch (OperationCanceledException)
        {
            // Normal shutdown — do nothing
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Unhandled exception in Worker; service stopping");
        }
        finally
        {
            _udpListener.TriggerReceived -= OnTriggerReceived;
        }

        _logger.LogInformation("AwakeOnDeck service stopped");
    }

    private void OnTriggerReceived(object? sender, EventArgs e)
    {
        _ = Task.Run(async () =>
        {
            try
            {
                await _unlockService.UnlockAsync();
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Unlock attempt failed");
            }
        });
    }
}
