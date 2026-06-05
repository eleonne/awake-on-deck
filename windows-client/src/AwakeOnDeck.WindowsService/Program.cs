using AwakeOnDeck.WindowsService;
using AwakeOnDeck.WindowsService.Models;
using AwakeOnDeck.WindowsService.WinApi;
using Microsoft.Extensions.Hosting.WindowsServices;

// When spawned as a helper by the service (via InteractiveProcess.SpawnAndTypePassword),
// run in the interactive session on the Winlogon desktop and type the password via SendInput.
// Session 0 isolation prevents the service itself from calling SendInput into the user session.
if (args.Contains("--type-password"))
{
    string password = Console.ReadLine() ?? string.Empty;
    if (!string.IsNullOrEmpty(password))
        User32.TypePasswordOnCurrentDesktop(password);
    return;
}

IHost host = Host.CreateDefaultBuilder(args)
    .UseWindowsService(options => { options.ServiceName = "AwakeOnDeck"; })
    .ConfigureServices((context, services) =>
    {
        services.Configure<AppSettings>(context.Configuration.GetSection("AppSettings"));
        services.AddSingleton<IWinApiProvider, WinApiProvider>();
        services.AddSingleton<ICredentialManager, CredentialManager>();
        services.AddSingleton<IUnlockService, UnlockService>();
        services.AddSingleton<UdpListener>();
        services.AddHostedService<Worker>();
    })
    .ConfigureLogging((_, logging) =>
    {
        if (WindowsServiceHelpers.IsWindowsService())
        {
            logging.AddEventLog(settings =>
            {
                settings.SourceName = "AwakeOnDeck";
            });
        }
        else
        {
            logging.AddConsole();
        }
    })
    .Build();

await host.RunAsync();
