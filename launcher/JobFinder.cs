// Lanceur Windows de JobFinder (JobFinder.exe).
//
// Il ne contient pas l'application : il appelle "uv", qui installe automatiquement
// la bonne version de Python et les dépendances (pyproject.toml / uv.lock) au premier
// lancement, puis démarre l'interface. Aucune installation de Python n'est nécessaire.
//
// La fenêtre de console affiche le journal ; la fermer arrête JobFinder.
// Compilation : launcher\build.bat (compilateur C# fourni avec Windows).
using System;
using System.Diagnostics;
using System.IO;

class Launcher
{
    static int Main()
    {
        Console.Title = "JobFinder";
        Console.OutputEncoding = System.Text.Encoding.UTF8;  // accents corrects dans la console
        string root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');

        string uv = FindUv(root);
        if (uv == null)
        {
            Console.WriteLine("uv est introuvable. Installez-le avec cette commande PowerShell :");
            Console.WriteLine();
            Console.WriteLine("  powershell -ExecutionPolicy ByPass -c \"irm https://astral.sh/uv/install.ps1 | iex\"");
            Console.WriteLine();
            Console.WriteLine("ou copiez uv.exe à côté de JobFinder.exe, puis relancez JobFinder.");
            return Pause(1);
        }

        Console.WriteLine("Préparation de l'environnement (le premier lancement peut prendre quelques minutes)...");
        // Navigateur utilisé par le scraper APEC : instantané s'il est déjà installé
        if (Run(uv, "run --project \"" + root + "\" playwright install firefox", root) != 0)
            return Pause(1);

        Console.WriteLine("Démarrage de JobFinder : l'application va s'ouvrir dans votre navigateur.");
        Console.WriteLine("Fermez cette fenêtre pour arrêter JobFinder.");
        int code = Run(uv, "run --project \"" + root + "\" python run.py", root);
        return code == 0 ? 0 : Pause(code);
    }

    // uv.exe à côté du lanceur, sinon dans le PATH, sinon à l'emplacement d'installation par défaut
    static string FindUv(string root)
    {
        string local = Path.Combine(root, "uv.exe");
        if (File.Exists(local)) return local;

        foreach (string dir in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(';'))
        {
            try
            {
                string candidate = Path.Combine(dir.Trim(), "uv.exe");
                if (File.Exists(candidate)) return candidate;
            }
            catch (ArgumentException) { }  // entrée du PATH invalide
        }

        string userInstall = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".local", "bin", "uv.exe");
        return File.Exists(userInstall) ? userInstall : null;
    }

    // Lance une commande dans la même console et attend sa fin
    static int Run(string exe, string arguments, string workingDirectory)
    {
        var info = new ProcessStartInfo(exe, arguments)
        {
            UseShellExecute = false,
            WorkingDirectory = workingDirectory,
        };
        info.EnvironmentVariables["PYTHONUTF8"] = "1";
        info.EnvironmentVariables["UV_LINK_MODE"] = "copy";  // évite un avertissement de uv sous Windows
        using (Process process = Process.Start(info))
        {
            process.WaitForExit();
            return process.ExitCode;
        }
    }

    // En cas d'erreur, la fenêtre reste ouverte pour pouvoir lire le message
    static int Pause(int code)
    {
        Console.WriteLine();
        Console.WriteLine("Appuyez sur une touche pour fermer cette fenêtre.");
        Console.ReadKey();
        return code;
    }
}
