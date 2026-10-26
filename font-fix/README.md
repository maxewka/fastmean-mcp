# Optional Russian UI helper / Русский интерфейс

This is a **source-only, optional** helper for an existing FASTMEAN installation.
It targets legacy ANSI text encoding; it does not install fonts or modify
FASTMEAN's executable. The MCP server works without it.

Windows 11 Application Control / Smart App Control may block this legacy loader
or a locally compiled helper. A previously working setup is not a compatibility
guarantee. If blocked, stop using the helper and continue with MCP. This project
does not change or bypass Windows security policies.

From the repository root, in normal Windows PowerShell:

```powershell
.\Build\Install-font-fix.ps1 -FastmeanExe 'C:\Apps\FASTMEAN\Fastmean.exe'
```

The script downloads the official Locale Emulator v2.5.0.1 ZIP, verifies pinned
SHA256 hashes, extracts only its two DLLs and compiles the included C# source as
x86 using the Windows .NET Framework 4.x compiler. Runtime files go outside the
checkout. An existing destination is never replaced; `-Destination` selects a
new location. No helper is launched by default. Optional `-CreateShortcut`
creates a new desktop shortcut; `-VerifyLaunch` explicitly starts FASTMEAN once
and reports failure without an elevation or alternate-loader fallback.

Manual runtime command:

```text
FastmeanRuRunner.exe "C:\Apps\FASTMEAN\Fastmean.exe" ["C:\Circuits\example.scm"]
```

The helper changes locale behavior inside its own/native child processes. It
preserves the current timezone and supplies two exact in-memory file-type label
read replacements. It writes no registry values, installs no fonts, and changes
no global Windows locale or security settings. Removing its runtime folder and
its optional shortcut uninstalls it. Keep the source, manifest and license files
with any runtime you distribute; see [NOTICE.md](NOTICE.md).

## По-русски

Это необязательный запускатель для исправления кодировки русского интерфейса.
FASTMEAN, готовые EXE и DLL в репозиторий не включены. Скрипт скачивает две DLL
из официального выпуска Locale Emulator с проверкой SHA256 и собирает исходник
C# локально. Установленная FASTMEAN и системные настройки Windows не меняются.

По умолчанию запускатель не запускается. `-CreateShortcut` создаёт отдельный
ярлык; `-VerifyLaunch` явно проверяет запуск, открывая окно FASTMEAN. Windows 11
Application Control / Smart App Control может заблокировать компонент. В таком
случае остановитесь: MCP работает без него. Обход защиты и повышение прав не
выполняются. Для удаления достаточно удалить созданную папку и её ярлык.
