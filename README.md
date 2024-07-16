# `latexrestricted` — Python library for creating executables compatible with LaTeX restricted shell escape


This Python package is designed to simplify the process of creating Python
executables compatible with [LaTeX](https://www.latex-project.org/) restricted
shell escape.  Restricted shell escape allows LaTeX to run trusted executables
as part of compiling documents.  These executables have restricted access to
the file system and restricted ability to launch subprocesses.

`latexrestricted` provides access to LaTeX configuration and implements
wrappers around Python's
[`pathlib.Path`](https://docs.python.org/3/library/pathlib.html) and
[`subprocess.run()`](https://docs.python.org/3/library/subprocess.html#subprocess.run)
that follow LaTeX security settings.



## Usage considerations


### Importing

`latexrestricted` should be imported as soon as possible during the
initialization of an executable.  When it is imported, it sets the current
working directory as the TeX working directory.  If it is imported after the
current working directory is changed, then the TeX working directory will be
set incorrectly and security restrictions will fail.


### Systems with multiple TeX installations

`latexrestricted` works correctly when used with
[TeX Live](https://www.tug.org/texlive/) on systems with multiple TeX Live or
other TeX installations.

**`latexrestricted` may fail when used with [MiKTeX](https://miktex.org/) on
systems with multiple MiKTeX installations.  It may use the wrong MiKTeX
installation, and there is no way to detect this.**

The user can resolve this by modifying `PATH` to put the correct MiKTeX
installation first, or by manually setting the environment variable
`SELFAUTOLOC` to the correct MiKTeX binary directory.  See
`latex_config.miktex_bin` below for more details.



## LaTeX configuration

```
from latexrestricted import latex_config
```

The `latex_config` instance of the `LatexConfig` class provides access to
LaTeX configuration and related environment variables.

`latex_config` attributes and properties:

* `tex_cwd: str`:  Current working directory when `latexrestricted` was
  first imported.

* `texlive_bin: str | None` and `texlive_kpsewhich: str | None`:  If an
  executable using `latexrestricted` is launched via `\ShellEscape` with TeX
  Live, these will be the paths to the TeX Live `bin/` directory and the TeX
  Live `kpsewhich` executable.  Otherwise, both are `None`.

  TeX Live is detected via the `SELFAUTOLOC` environment variable.  Because
  `SELFAUTOLOC` gives the location of TeX binaries, `texlive_bin` and
  `texlive_kpsewhich` will be correct even on systems with multiple TeX Live
  or other TeX installations.

* `miktex_bin: str | None`, `miktex_initexmf: str | None`, and
  `miktex_kpsewhich: str | None`:  If an executable using `latexrestricted`
  is launched via `\ShellEscape` with MiKTeX, these will be the paths to the
  MiKTeX `bin/` directory and the MiKTeX `initexmf` and `kpsewhich`
  executables.  Otherwise, all are `None`.

  MiKTeX is detected via the `TEXSYSTEM` environment variable.  `TEXSYSTEM`
  only declares that MiKTeX is in use; unlike the TeX Live case with
  `SELFAUTOLOC`, `TEXSYSTEM` does not give the location of TeX binaries.  The
  location of TeX binaries is determined using Python's `shutil.which()` to
  search for `initexmf`.  This gives the location of the first `initexmf`
  executable on `PATH`.  If there are multiple MiKTeX installations, this is
  not guaranteed to be correct.  The user can resolve this by modifying `PATH`
  to put the correct installation first, or by manually setting the
  environment variable `SELFAUTOLOC` to the correct MiKTeX binary directory.

* `can_read_dotfiles: bool`, `can_read_anywhere: bool`,
  `can_write_dotfiles: bool`, `can_write_anywhere: bool`:  These summarize
  the file system security settings for TeX Live (`openin_any` and
  `openout_any` in `texmf.cnf`) and MiKTeX (`[Core]AllowUnsafeInputFiles`
  and `[Core]AllowUnsafeOutputFiles` in `miktex.ini`).  The `*dotfile`
  properties describe whether dotfiles (files with names beginning with `.`)
  can be read/written.  The `*anywhere` properties describe whether files
  anywhere in the file system can be read/written, or only those under the
  current working directory, `$TEXMF_OUTPUT`, and `$TEXMF_OUTPUT_DIRECTORY`.

* `prohibited_write_file_extensions: set[str]`:  File extensions that cannot
  be used in writing files under Windows (including Cygwin).  All file
  extensions are lower case with a leading period (for example, `.exe`).
  These are determined from the `PATHEXT` environment variable, or use a
  default fallback if `PATHEXT` is not defined or when under Cygwin.

* `TEXMFHOME: str | None`:  Value of `TEXMFHOME` obtained from `kpsewhich`
  or `initexmf`.

* `TEXMFOUTPUT: str | None`:  Value of `TEXMFOUTPUT` obtained from environment
  variable if defined and otherwise from `kpsewhich` or `initexmf`.

* `TEXMF_OUTPUT_DIRECTORY: str | None`:  Value of `TEXMF_OUTPUT_DIRECTORY`
  obtained from environment variable.

* `restricted_shell_escape_commands: set[str]`:  Permitted restricted shell
  escape executables.  Obtained from TeX Live's `shell_escape_commands` in
  `texmf.cnf` or MiKTeX's `[Core]AllowedShellCommands[]` in `miktex.ini`.

`latex_config` methods:

* `kpsewhich_find_config_file(file: str)`:  Use `kpsewhich` in a subprocess
  to find a configuration file (`kpsewhich -f othertext <file>`).  Returns
  `kpsewhich` output as a string or `None` if there was no output.

* `kpsewhich_find_file(file: str, *, cache: bool = False)`:  Use `kpsewhich`
  in a subprocess to find a file (`kpsewhich <file>`).  Returns `kpsewhich`
  output as a string or `None` if there was no output.  The optional
  argument `cache` caches `kpsewhich` output to minimize subprocesses.  This
  can be useful when the file system is not being modified and `kpsewhich` is
  simply returning values from its own cache.

If there are errors in determining LaTeX configuration (for example, a TeX
installation cannot be located), then `latexrestricted.LatexConfigError` is
raised.



## Restricted file system access

TeX limits file system access.  The file system security settings for TeX Live
(`openin_any` and `openout_any` in `texmf.cnf`) and MiKTeX
(`[Core]AllowUnsafeInputFiles` and `[Core]AllowUnsafeOutputFiles` in
`miktex.ini`) determine whether dotfiles can be read/written and whether files
anywhere in the file system can be read/written, or only those under the
current working directory, `$TEXMF_OUTPUT`, and `$TEXMF_OUTPUT_DIRECTORY`.

The `latexrestricted` package provides subclasses of Python's
[`pathlib.Path`](https://docs.python.org/3/library/pathlib.html) that respect
these security settings or enforce more stringent security.  Under Python 3.8,
these subclasses backport the methods `.is_relative_to()` and `.with_stem()`
from Python 3.9.  When these subclasses are used to modify the file system,
`latexrestricted.PathSecurityError` is raised if reading/writing a given path
is not permitted.

```
from latexrestricted import <RestrictedPathClass>
```

`RestrictedPath` classes:

* `BaseRestrictedPath`:  This is the base class for `RestrictedPath` classes.
  It cannot be used directly.  Subclasses define methods
  `.tex_readable_dir()`, `.tex_readable_file()`, `.tex_writable_dir()`, and
  `.tex_writable_file()` that determine whether a given path is readable/
  writable.  Most methods for opening, reading, writing, replacing, and
  deleting files as well as methods for creating and deleting directories are
  supported.  Methods related to modifying file permissions and creating links
  are not supported.  Unsupported methods raise `NotImplementedError`.

* `StringRestrictedPath`:  This follows the approach taken in TeX's file
  system security.  TeX configuration determines whether dotfiles are
  readable/writable and which locations are readable/writable.  Paths are
  analyzed as strings; the file system is never consulted.  When read/write
  locations are restricted, paths are restricted using the following criteria:

  - All relative paths are relative to the TeX working directory.

  - All absolute paths must be under `$TEXMF_OUTPUT_DIRECTORY` and
    `$TEXMFOUTPUT`.

  - Paths cannot contain `..` to access a parent directory, even if the
    parent directory is a valid location.

  When read/write locations are restricted, it is still possible to access
  locations outside the TeX working directory, `$TEXMF_OUTPUT_DIRECTORY`, and
  `$TEXMFOUTPUT` if there are symlinks in those locations.

  Under Windows (including Cygwin), writing files with file extensions in
  `PATHEXT` (for example, `.exe`) is also disabled.

* `SafeStringRestrictedPath`:  Same as `StringRestrictedPath`, except that TeX
  configuration is ignored and all security settings are at maximum:  dotfiles
  cannot be read/written, and all reading/writing is limited to the TeX
  working directory, `$TEXMF_OUTPUT_DIRECTORY`, and `$TEXMFOUTPUT`.

* `SafeWriteStringRestrictedPath`:  Same as `StringRestrictedPath`, except
  that TeX configuration for writing is ignored and all security settings
  related to writing are at maximum.

* `ResolvedRestrictedPath`:  This resolves any symlinks in paths using the
  file system before determining whether paths are readable/writable.  TeX
  configuration determines whether dotfiles are readable/writable and which
  locations are readable/writable.  When read/write locations are restricted,
  paths are restricted using the following criteria:

  - Resolved paths must be under the TeX working directory,
    resolved `$TEXMF_OUTPUT_DIRECTORY`, or resolved `$TEXMFOUTPUT`.

  - All relative paths are resolved relative to the TeX working directory.

  - Unlike `StringRestrictedPath`, paths are allowed to contain `..`, and
    `$TEXMF_OUTPUT_DIRECTORY` and `$TEXMFOUTPUT` can be accessed via relative
    paths.  This is possible since paths are fully resolved with the file
    system before being compared with permitted read/write locations.

  Because paths are resolved before being compared with permitted read/write
  locations, it is not possible to access locations outside the TeX working
  directory, `$TEXMF_OUTPUT_DIRECTORY`, and `$TEXMFOUTPUT` via symlinks in
  those locations.

  Under Windows (including Cygwin), writing files with file extensions in
  `PATHEXT` (for example, `.exe`) is also disabled.

* `SafeResolvedRestrictedPath`:  Same as `ResolvedRestrictedPath`,  except
  that TeX configuration is ignored and all security settings are at maximum:
  dotfiles cannot be read/written, and all other reading/writing is limited to
  the TeX working directory, `$TEXMF_OUTPUT_DIRECTORY`, and `$TEXMFOUTPUT`.

* `SafeWriteResolvedRestrictedPath`:  Same as `ResolvedRestrictedPath`, except
  that TeX configuration for writing is ignored and all security settings
  related to writing are at maximum.

The `SafeWrite*` classes should be preferred unless access to additional write
locations is absolutely necessary.  On systems with multiple MiKTeX
installations, there is no guarantee that `latexrestricted` will find the
correct installation and thus use the correct TeX configuration (see
`latex_config.miktex_bin` above for more details).



## Restricted subprocesses

When LaTeX runs with restricted shell escape, only executables specified in
TeX configuration can be executed via `\ShellEscape`.  The `latexrestricted`
package allows these same executables to run in subprocesses via
`restricted_run()`.  This is a wrapper around Python's
[`subprocess.run()`](https://docs.python.org/3/library/subprocess.html#subprocess.run).

```
from latexrestricted import restricted_run
restricted_run(args: list[str], allow_restricted_executables: bool = False)
```

* It is *always* possible to run `kpsewhich` and `initexmf`.  These are
  necessary to access TeX configuration values.

  Running other executables allowed by TeX configuration for restricted shell
  escape requires the optional argument `allow_restricted_executables=true`.
  In this case, TeX configuration is checked to determine whether restricted
  shell escape is enabled, although this should be redundant if
  `latexrestricted` itself is being used in a restricted shell escape
  executable.

* When `allow_restricted_executables=true`, the executable must be in the same
  directory as `kpsewhich` or `initexmf`, as previously located during TeX
  configuration detection, or the executable must exist on `PATH`, as found by
  Python's `shutil.which()`.

  The executable must not be in a location writable by LaTeX.  For added
  security, locations writable by LaTeX cannot be under the executable parent
  directory.

* The executable cannot be a batch file (no `*.bat` or `*.cmd`):
  https://docs.python.org/3/library/subprocess.html#security-considerations.
  This is enforced by requiring `*.exe` under Windows and completely
  prohibiting `*.bat` and `*.cmd` everywhere.

* The subprocess runs with `shell=False`.

`restricted_run()` will raise `latexrestricted.ExecutableNotFoundError` if an
executable (`args[0]`) cannot be found in the same directory as `kpsewhich` or
`initexmf`, or on `PATH`.  It will raise
`latexrestricted.UnapprovedExecutableError` when the executable is not in the
approved list of executables from LaTeX configuration
(`latex_config.restricted_shell_escape_commands`).  It will raise
`latexrestricted.ExecutablePathSecurityError` if the executable is found and
is in the approved list, but is in an insecure location relative to locations
writable by LaTeX.
