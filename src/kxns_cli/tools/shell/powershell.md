Execute a ${SHELL} command. Use this tool to explore the filesystem, inspect or edit files, run Windows scripts, collect system information, etc., whenever the agent is running on Windows.

Note that you are running on Windows, so make sure to use Windows commands, paths, and conventions.

**Output:**
The stdout and stderr streams are combined and returned as a single string. Extremely long output may be truncated. When a command fails, the exit code is provided in a system tag.

**Guidelines for safety and security:**
- Every tool call starts a fresh ${SHELL} session. Environment variables, `cd` changes, and command history do not persist between calls.
- **IMPORTANT: Do NOT use `cd` alone.** Since each call starts a fresh shell, a standalone `cd` has no effect — the directory change is lost when the call ends. Always chain `cd` with the actual command using `;`, e.g. `cd C:\path; Get-ChildItem`. Using `cd` by itself is a waste of a tool call and will cause subsequent commands to run in the wrong directory.
- Do not launch interactive programs or anything that is expected to block indefinitely; ensure each command finishes promptly. Provide a `timeout` argument for potentially long runs.
- Avoid using `..` to leave the working directory, and never touch files outside that directory unless explicitly instructed.
- Never attempt commands that require elevated (Administrator) privileges unless explicitly authorized.

**Guidelines for efficiency:**
- Chain related commands with `;` and use `if ($?)` or `if (-not $?)` to conditionally execute commands based on the success or failure of previous ones.
- Redirect or pipe output with `>`, `>>`, `|`, and leverage `for /f`, `if`, and `set` to build richer one-liners instead of multiple tool calls.
- Reuse built-in utilities (e.g., `findstr`, `where`) to filter, transform, or locate data in a single invocation.

**Commands available:**
- Shell environment: `cd`, `dir`, `set`, `setlocal`, `echo`, `call`, `where`
- File operations: `type`, `copy`, `move`, `del`, `erase`, `mkdir`, `rmdir`, `attrib`, `mklink`
- Text/search: `find`, `findstr`, `more`, `sort`, `Get-Content`
- System info: `ver`, `systeminfo`, `tasklist`, `wmic`, `hostname`
- Archives/scripts: `tar`, `Compress-Archive`, `powershell`, `python`, `node`
- Other: Any other binaries available on the system PATH; run `where <command>` first if unsure.
