# -*- coding: utf-8 -*-
#
# Copyright (c) 2024, Geoffrey M. Poore
# All rights reserved.
#
# Licensed under the LaTeX Project Public License version 1.3c:
# https://www.latex-project.org/lppl.txt
#


from __future__ import annotations

import os
import shutil
import subprocess
import sys
from .err import LatexConfigError
from ._anypath import AnyPath




class LatexConfig(object):
    '''
    Access config settings from `kpsewhich` (TeX Live) or `initexmf` (MiKTeX),
    plus related environment variables.  Also locate files via `kpsewhich`.

    If the environment variable `TEXSYSTEM` is set to `miktex`, then `PATH` is
    searched with `shutil.which()` for an `initexmf` executable with an
    accompanying `kpsewhich`.  This is only guaranteed to give the correct
    executables (and thus return the correct LaTeX config settings) if there
    is only one MiKTeX installation or if the correct MiKTeX installation is
    the first installation on `PATH`.

    Otherwise, TeX Live is assumed.  Under non-Windows operating systems, the
    `SELFAUTOLOC` environment variable is used to locate the correct
    `kpsewhich`.  Under Windows, `SELFAUTOLOC` may be overwritten by the
    `runscript.exe` wrapper for TeX Live shell escape executables, so it
    cannot be trusted.  (If the shell invokes a TeX Live shell escape
    executable in the wrong TeX installation, due to `PATH` precedence, then
    `SELFAUTOLOC` is overwritten with an incorrect value, and this cannot be
    detected.)  Instead, `PATH` is searched for a `tlmgr` executable with
    accompanying `kpsewhich`.  This is only guaranteed to give the correct
    executables (and thus return the correct LaTeX config settings) if there
    is only one TeX Live installation or if the correct TeX Live installation
    is the first installation on `PATH`.

    File read/write permission settings are available via the following
    properties:

      * `can_read_dotfiles`
      * `can_read_anywhere`
      * `can_write_dotfiles`
      * `can_write_anywhere`

    The `*dotfile` settings describe whether files with names starting with a
    dot `.` are allowed to be read/written.  The `*anywhere` settings describe
    whether files anywhere are allowed to be read/written, or only files
    within the current working directory, TEXMFOUTPUT, TEXMF_OUTPUT_DIRECTORY,
    and their subdirectories.  The values of these properties are determined
    from `openout_any` and `openin_any` settings in `texmf.cnf` for TeX Live,
    and from `[Core]AllowUnsafeInputFiles` and `[Core]AllowUnsafeOutputFiles`
    in `miktex.ini` for MiKTeX.

    Shell escape settings are available via the property
    `can_restricted_shell_escape`.  This is based on `shell_escape` in
    `texmf.cnf` for TeX Live, and on `[Core]ShellCommandMode` in `miktex.ini`
    for MiKTeX.

    Python properties and caching are used extensively so that `kpsewhich` and
    `initexmf` subprocesses only run when their output is actually used and
    has not been obtained previously.
    '''

    def __init__(self):
        pass


    _permitted_subprocess_executables = set(['kpsewhich', 'initexmf'])
    _permitted_subprocess_executables.update([f'{executable}.exe' for executable in _permitted_subprocess_executables])

    _tex_cwd_anypath: AnyPath = AnyPath.cwd()
    _tex_cwd_str: str = str(_tex_cwd_anypath)

    @property
    def tex_cwd(self) -> str:
        # This is a property so that it is more difficult to modify/so that
        # any modifications are more obvious. `*RestrictedPath` classes depend
        # on `.tex_cwd`, so modifying it bypasses security.
        return self._tex_cwd_str

    _prohibited_subprocess_executable_roots: set[AnyPath] = set()
    _prohibited_subprocess_executable_roots.add(_tex_cwd_anypath)
    # TeX Live allows `TEXMFOUTPUT` to be set in a `texmf.cnf` config file.
    # In `_init_tex_paths()`, if TeX Live is detected and a `TEXMFOUTPUT`
    # environment variable is not defined, then `kpsewhich` is used to
    # retrieve the value of `TEXMFOUTPUT`, and that value is used to update
    # `_prohibited_subprocess_executable_roots`.
    for env_var in [os.getenv(x) for x in ('TEXMFOUTPUT', 'TEXMF_OUTPUT_DIRECTORY')]:
        if env_var:
            env_var_path = AnyPath(env_var)
            _prohibited_subprocess_executable_roots.add(env_var_path)
            _prohibited_subprocess_executable_roots.add(env_var_path.resolve())

    @classmethod
    def _resolve_and_check_executable(cls, executable_name: str, executable_path: AnyPath) -> AnyPath:
        executable_resolved = executable_path.resolve()
        # There is no check for `executable_path.name`, because
        # `executable_path` is always from `shutil.which(<name>)`.
        if executable_resolved.name not in cls._permitted_subprocess_executables:
            raise LatexConfigError(
                f'Executable "{executable_name}" resolved to "{executable_resolved.as_posix()}", '
                f'but "{executable_resolved.name}" is not one of the permitted executables '
                'for determining LaTeX configuration'
            )
        # Executable path can't be writable by LaTeX.  LaTeX writable path(s)
        # can't be relative to the executable's parent directory, since that
        # could make some of the executable's resources writable.  Path
        # comparisons are performed with all permutations of resolved and
        # unresolved paths to reduce the potential for symlink trickery.
        #
        # Fully eliminating the potential for symlink trickery would require
        # checking all locations writable by LaTeX for symlinks to problematic
        # locations.  That isn't worth doing since TeX path security does not
        # consider symlinks.
        #
        # Initially, this doesn't check for the scenario where `TEXMFOUTPUT`
        # is set in a `texmf.cnf` config file with TeX Live.  There isn't a
        # good way to check for that without running `kpsewhich`.  As part of
        # `_init_tex_paths()`, `_prohibited_subprocess_executable_roots` is
        # updated under that scenario by running `kpsewhich` to get
        # `TEXMFOUTPUT`.  Then this function is invoked to check the
        # `kpsewhich` executable against `TEXMFOUTPUT`.  Giving an error
        # message after already running `kpsewhich` isn't ideal, but there
        # isn't a good alternative.  Also, if `TEXMFOUTPUT` is set to an
        # unsafe value in a `texmf.cnf` config file, then all TeX-related
        # executables are potentially compromised, so running `kpsewhich` has
        # a negligible impact on overall security.
        if any(e.is_relative_to(p) or p.is_relative_to(e)
               for e in set([executable_path.parent, executable_resolved.parent])
               for p in cls._prohibited_subprocess_executable_roots):
            raise LatexConfigError(
                f'Executable "{executable_name}" is located under the current directory, TEXMFOUTPUT, or '
                'TEXMF_OUTPUT_DIRECTORY, or one of these locations is under the same directory as the executable'
            )
        return executable_resolved


    _did_init_tex_paths: bool = False
    _texlive_bin: str | None = None
    _texlive_kpsewhich: str | None = None
    _miktex_bin: str | None
    _miktex_initexmf: str | None = None
    _miktex_kpsewhich: str | None = None

    @classmethod
    def _init_tex_paths(cls):
        env_TEXSYSTEM = os.getenv('TEXSYSTEM')
        if env_TEXSYSTEM and env_TEXSYSTEM.lower() == 'miktex':
            cls._init_tex_paths_miktex()
        else:
            cls._init_tex_paths_texlive()

    @classmethod
    def _init_tex_paths_miktex(cls):
        if sys.platform == 'win32':
            which_initexmf = shutil.which('initexmf.exe')
        else:
            which_initexmf = shutil.which('initexmf')
        if not which_initexmf:
            raise LatexConfigError(
                'Environment variable TEXSYSTEM="miktex", but failed to find "initexmf" executable on PATH'
            )
        which_initexmf_path = AnyPath(which_initexmf)
        which_initexmf_resolved = cls._resolve_and_check_executable('initexmf', which_initexmf_path)
        miktex_bin_path = which_initexmf_resolved.parent
        if sys.platform == 'win32':
            which_kpsewhich = shutil.which('kpsewhich.exe', path=str(miktex_bin_path))
        else:
            which_kpsewhich = shutil.which('kpsewhich', path=str(miktex_bin_path))
        if not which_kpsewhich:
            raise LatexConfigError(
                'Environment variable TEXSYSTEM="miktex", '
                'but failed to find an "initexmf" executable with accompanying "kpsewhich" on PATH'
            )
        which_kpsewhich_path = AnyPath(which_kpsewhich)
        which_kpsewhich_resolved = cls._resolve_and_check_executable('kpsewhich', which_kpsewhich_path)
        if not miktex_bin_path == which_kpsewhich_resolved.parent:
            raise LatexConfigError(
                'Environment variable TEXSYSTEM="miktex", '
                f'but "initexmf" executable from PATH resolved to "{which_initexmf_resolved.as_posix()}" '
                f'while "kpsewhich" resolved to "{which_kpsewhich_resolved.as_posix()}"; '
                '"initexmf" and "kpsewhich" should be in the same location'
            )
        cls._miktex_bin = str(miktex_bin_path)
        cls._miktex_initexmf = str(which_initexmf_resolved)
        cls._miktex_kpsewhich = str(which_kpsewhich_resolved)
        cls._did_init_tex_paths = True

    @classmethod
    def _init_tex_paths_texlive(cls):
        env_SELFAUTOLOC = os.getenv('SELFAUTOLOC')
        if not env_SELFAUTOLOC:
            raise LatexConfigError('Environment variable SELFAUTOLOC is expected for TeX Live, but was not set')
        if sys.platform == 'win32':
            # Under Windows, shell escape executables installed within TeX
            # Live are launched with the `runscript.exe` wrapper.  This uses
            # `kpathsea` internally, which will overwrite any existing value
            # of `SELFAUTOLOC`.  As a result, under Windows, `SELFAUTOLOC` may
            # only give the location of the wrapper executable rather than the
            # location of the TeX executable that is invoking shell escape.
            which_tlmgr = shutil.which('tlmgr')  # No `.exe`; likely `.bat`
            if not which_tlmgr:
                raise LatexConfigError('Failed to find TeX Live "tlmgr" executable on PATH')
            which_tlmgr_resolved = AnyPath(which_tlmgr).resolve()
            texlive_bin_path = which_tlmgr_resolved.parent
            which_kpsewhich = shutil.which('kpsewhich.exe', path=str(texlive_bin_path))
            if not which_kpsewhich:
                raise LatexConfigError(
                    'Failed to find a TeX Live "tlmgr" executable with accompanying "kpsewhich" executable on PATH'
                )
            which_kpsewhich_path = AnyPath(which_kpsewhich)
            which_kpsewhich_resolved = cls._resolve_and_check_executable('kpsewhich', which_kpsewhich_path)
            if not texlive_bin_path == which_kpsewhich_resolved.parent:
                raise LatexConfigError(
                    f'"tlmgr" executable from PATH resolved to "{which_tlmgr_resolved.as_posix()}" '
                    f'while "kpsewhich" resolved to "{which_kpsewhich_resolved.as_posix()}"; '
                    '"tlmgr" and "kpsewhich" should be in the same location'
                )
        else:
            env_SELFAUTOLOC_which_kpsewhich = shutil.which('kpsewhich', path=env_SELFAUTOLOC)
            if not env_SELFAUTOLOC_which_kpsewhich:
                raise LatexConfigError(
                    f'Environment variable SELFAUTOLOC has value "{env_SELFAUTOLOC}", '
                    'but a "kpsewhich" executable was not found at that location'
                )
            which_kpsewhich_path = AnyPath(env_SELFAUTOLOC_which_kpsewhich)
            which_kpsewhich_resolved = cls._resolve_and_check_executable('kpsewhich', which_kpsewhich_path)
            texlive_bin_path = which_kpsewhich_resolved.parent
        cls._texlive_bin = str(texlive_bin_path)
        cls._texlive_kpsewhich = str(which_kpsewhich_resolved)
        cls._did_init_tex_paths = True
        if not os.getenv('TEXMFOUTPUT'):
            # With TeX Live, check for unsafe value of `TEXMFOUTPUT` from
            # `texmf.cnf` config file.
            config_TEXMFOUTPUT = cls._get_texlive_var_value('TEXMFOUTPUT')
            if config_TEXMFOUTPUT:
                config_TEXMFOUTPUT_path = AnyPath(config_TEXMFOUTPUT)
                cls._prohibited_subprocess_executable_roots.add(config_TEXMFOUTPUT_path)
                cls._prohibited_subprocess_executable_roots.add(config_TEXMFOUTPUT_path.resolve())
                cls._resolve_and_check_executable('kpsewhich', which_kpsewhich_path)


    # Locations of TeX executables must be returned as strings, not as
    # `AnyPath`.  All non-private paths should be subclasses of
    # `RestrictedPath`, but it can't be defined without `LatexConfig`.

    @property
    def texlive_bin(self) -> str | None:
        if not self._did_init_tex_paths:
            self._init_tex_paths()
        return self._texlive_bin

    @property
    def texlive_kpsewhich(self) -> str | None:
        if not self._did_init_tex_paths:
            self._init_tex_paths()
        return self._texlive_kpsewhich

    @property
    def miktex_bin(self) -> str | None:
        if not self._did_init_tex_paths:
            self._init_tex_paths()
        return self._miktex_bin

    @property
    def miktex_initexmf(self) -> str | None:
        if not self._did_init_tex_paths:
            self._init_tex_paths()
        return self._miktex_initexmf

    @property
    def miktex_kpsewhich(self) -> str | None:
        if not self._did_init_tex_paths:
            self._init_tex_paths()
        return self._miktex_kpsewhich


    def kpsewhich_find_config_file(self, file: str,) -> str | None:
        if not self._did_init_tex_paths:
            self._init_tex_paths()
        if self.texlive_kpsewhich:
            kpsewhich = self.texlive_kpsewhich
        elif self.miktex_kpsewhich:
            kpsewhich = self.miktex_kpsewhich
        else:
            raise TypeError
        cmd = [kpsewhich, '-f', 'othertext', file]
        proc = subprocess.run(cmd, shell=False, capture_output=True)
        value = proc.stdout.strip().decode(sys.stdout.encoding) or None
        return value

    _kpsewhich_find_file_cache: dict[str, str | None] = {}

    def kpsewhich_find_file(self, file: str, *, cache: bool = False) -> str | None:
        if cache:
            try:
                return self._kpsewhich_find_file_cache[file]
            except KeyError:
                pass
        if not self._did_init_tex_paths:
            self._init_tex_paths()
        if self.texlive_kpsewhich:
            kpsewhich = self.texlive_kpsewhich
        elif self.miktex_kpsewhich:
            kpsewhich = self.miktex_kpsewhich
        else:
            raise TypeError
        cmd = [kpsewhich, file]
        proc = subprocess.run(cmd, shell=False, capture_output=True)
        value = proc.stdout.strip().decode(sys.stdout.encoding) or None
        if cache:
            self._kpsewhich_find_file_cache[file] = value
            return self._kpsewhich_find_file_cache[file]
        return value


    _texlive_var_value_cache: dict[str, str | None] = {}

    @classmethod
    def _get_texlive_var_value(cls, var: str) -> str | None:
        try:
            return cls._texlive_var_value_cache[var]
        except KeyError:
            pass
        if cls._texlive_kpsewhich is None:
            raise TypeError
        cmd = [cls._texlive_kpsewhich, '--var-value', var]
        proc = subprocess.run(cmd, shell=False, capture_output=True)
        value = proc.stdout.strip().decode(sys.stdout.encoding) or None
        if var.lower() in ('openin_any', 'openout_any'):
            # Documentation for `openin_any` and `openout_any` values:
            # https://www.tug.org/texinfohtml/kpathsea.html#Safe-filenames-1
            if value:
                value = value.lower()
            if value in ('y', '1'):
                value = 'a'
            elif value in ('n', '0'):
                value = 'r'
            elif value not in ('a', 'r', 'p'):
                value = 'p'
        elif var.lower() == 'shell_escape_commands':
            if value:
                value = value.rstrip(',%')
        cls._texlive_var_value_cache[var] = value
        return cls._texlive_var_value_cache[var]

    _miktex_config_value_cache: dict[str, str | None] = {}

    @classmethod
    def _get_miktex_config_value(cls, var: str) -> str | None:
        try:
            return cls._miktex_config_value_cache[var]
        except KeyError:
            pass
        if cls._miktex_initexmf is None:
            raise TypeError
        cmd = [cls._miktex_initexmf, '--show-config-value', var]
        proc = subprocess.run(cmd, shell=False, capture_output=True)
        value = proc.stdout.strip().decode(sys.stdout.encoding) or None
        if var.lower() in ('[core]allowunsafeinputfiles', '[core]allowunsafeoutputfiles'):
            if value:
                value = value.lower()
            if value not in ('true', 'false'):
                value = 'false'
        cls._miktex_config_value_cache[var] = value
        return cls._miktex_config_value_cache[var]


    _did_init_read_settings: bool = False
    _can_read_dotfiles: bool = False
    _can_read_anywhere: bool = False

    _did_init_write_settings: bool = False
    _can_write_dotfiles: bool = False
    _can_write_anywhere: bool = False

    # Documentation for `openin_any` and `openout_any` values:
    # https://www.tug.org/texinfohtml/kpathsea.html#Safe-filenames-1

    @classmethod
    def _init_read_settings(cls):
        if not cls._did_init_tex_paths:
            cls._init_tex_paths()
        if cls._texlive_kpsewhich:
            openin_any = cls._get_texlive_var_value('openin_any')
            if openin_any == 'a':
                cls._can_read_dotfiles = True
                cls._can_read_anywhere = True
            elif openin_any == 'r':
                cls._can_read_dotfiles = False
                cls._can_read_anywhere = True
            elif openin_any == 'p':
                cls._can_read_dotfiles = False
                cls._can_read_anywhere = False
            else:
                raise ValueError
        elif cls._miktex_initexmf:
            allow_unsafe_input_files = cls._get_miktex_config_value('[Core]AllowUnsafeInputFiles')
            if allow_unsafe_input_files == 'true':
                cls._can_read_dotfiles = True
                cls._can_read_anywhere = True
            elif allow_unsafe_input_files == 'false':
                cls._can_read_dotfiles = False
                cls._can_read_anywhere = False
            else:
                raise ValueError
        else:
            raise TypeError
        cls._did_init_read_settings = True

    @property
    def can_read_dotfiles(self) -> bool:
        if not self._did_init_read_settings:
            self._init_read_settings()
        return self._can_read_dotfiles

    @property
    def can_read_anywhere(self) -> bool:
        if not self._did_init_read_settings:
            self._init_read_settings()
        return self._can_read_anywhere

    @classmethod
    def _init_write_settings(cls):
        if not cls._did_init_tex_paths:
            cls._init_tex_paths()
        if cls._texlive_kpsewhich:
            openout_any = cls._get_texlive_var_value('openout_any')
            if openout_any == 'a':
                cls._can_write_dotfiles = True
                cls._can_write_anywhere = True
            elif openout_any == 'r':
                cls._can_write_dotfiles = False
                cls._can_write_anywhere = True
            elif openout_any == 'p':
                cls._can_write_dotfiles = False
                cls._can_write_anywhere = False
            else:
                raise ValueError
        elif cls._miktex_initexmf:
            allow_unsafe_output_files = cls._get_miktex_config_value('[Core]AllowUnsafeOutputFiles')
            if allow_unsafe_output_files == 'true':
                cls._can_write_dotfiles = True
                cls._can_write_anywhere = True
            elif allow_unsafe_output_files == 'false':
                cls._can_write_dotfiles = False
                cls._can_write_anywhere = False
            else:
                raise TypeError
        else:
            raise TypeError
        cls._did_init_write_settings = True

    @property
    def can_write_dotfiles(self) -> bool:
        if not self._did_init_write_settings:
            self._init_write_settings()
        return self._can_write_dotfiles

    @property
    def can_write_anywhere(self) -> bool:
        if not self._did_init_write_settings:
            self._init_write_settings()
        return self._can_write_anywhere

    _prohibited_write_file_extensions: frozenset[str] | None
    # Microsoft default PATHEXT and kpathsea default fallback PATHEXT are
    # slightly different, so use a union of the two.
    # https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/start
    _microsoft_default_pathext = '.COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC'
    # https://tug.org/svn/texlive/trunk/Build/source/texk/kpathsea/progname.c?revision=57915&view=markup#l415
    _kpathsea_default_pathext = '.com;.exe;.bat;.cmd;.vbs;.vbe;.js;.jse;.wsf;.wsh;.ws;.tcl;.py;.pyw'
    _fallback_prohibited_write_file_extensions = frozenset(
        ';'.join([_microsoft_default_pathext, _kpathsea_default_pathext]).lower().split(';')
    )
    if sys.platform == 'win32':
        _pathext = os.getenv('PATHEXT')
        if _pathext:
            _prohibited_write_file_extensions = frozenset(x for x in _pathext.lower().split(os.pathsep) if x)
        else:
            _prohibited_write_file_extensions = _fallback_prohibited_write_file_extensions
    elif sys.platform == 'cygwin':
        # This follows kpathsea:
        # https://tug.org/svn/texlive/trunk/Build/source/texk/kpathsea/progname.c?revision=57915&view=markup#l424
        _prohibited_write_file_extensions = _fallback_prohibited_write_file_extensions
    else:
        _prohibited_write_file_extensions = None

    @property
    def prohibited_write_file_extensions(self) -> frozenset[str] | None:
        return self._prohibited_write_file_extensions

    _did_init_shell_escape_settings: bool = False
    _can_restricted_shell_escape: bool

    @classmethod
    def _init_shell_escape_settings(cls):
        if not cls._did_init_tex_paths:
            cls._init_tex_paths()
        if cls._texlive_kpsewhich:
            # https://tug.org/svn/texlive/trunk/Build/source/texk/kpathsea/texmf.cnf?revision=70942&view=markup#l634
            shell_escape = cls._get_texlive_var_value('shell_escape')
            if shell_escape and shell_escape.lower() in ('t', 'p'):
                cls._can_restricted_shell_escape = True
            else:
                cls._can_restricted_shell_escape = False
        elif cls._miktex_initexmf:
            # https://docs.miktex.org/manual/miktex.ini.html
            shell_command_mode = cls._get_miktex_config_value('[Core]ShellCommandMode')
            if shell_command_mode and shell_command_mode.lower() in ('restricted', 'unrestricted'):
                cls._can_restricted_shell_escape = True
            else:
                cls._can_restricted_shell_escape = False
        else:
            raise TypeError
        cls._did_init_shell_escape_settings = True

    @property
    def can_restricted_shell_escape(self):
        if not self._did_init_shell_escape_settings:
            self._init_shell_escape_settings()
        return self._can_restricted_shell_escape


    _var_str_none_cache: dict[str, str | None] = {}

    @property
    def TEXMFHOME(self) -> str | None:
        try:
            return self._var_str_none_cache['TEXMFHOME']
        except KeyError:
            if self.texlive_kpsewhich:
                value = self._get_texlive_var_value('TEXMFHOME')
            elif self.miktex_initexmf:
                value = self._get_miktex_config_value('TEXMFHOME')
            else:
                raise TypeError
            self._var_str_none_cache['TEXMFHOME'] = value
            return self._var_str_none_cache['TEXMFHOME']

    @property
    def TEXMFOUTPUT(self) -> str | None:
        try:
            return self._var_str_none_cache['TEXMFOUTPUT']
        except KeyError:
            value = os.getenv('TEXMFOUTPUT')
            if value is None and self.texlive_kpsewhich:
                # TeX Live allows `TEXMFOUTPUT` to be set in `texmf.cnf`
                value = self._get_texlive_var_value('TEXMFOUTPUT')
            self._var_str_none_cache['TEXMFOUTPUT'] = value
            return self._var_str_none_cache['TEXMFOUTPUT']

    @property
    def TEXMF_OUTPUT_DIRECTORY(self) -> str | None:
        try:
            return self._var_str_none_cache['TEXMF_OUTPUT_DIRECTORY']
        except KeyError:
            value = os.getenv('TEXMF_OUTPUT_DIRECTORY')
            self._var_str_none_cache['TEXMF_OUTPUT_DIRECTORY'] = value
            return self._var_str_none_cache['TEXMF_OUTPUT_DIRECTORY']

    _var_frozenset_cache: dict[str, frozenset[str]] = {}

    @property
    def restricted_shell_escape_commands(self) -> frozenset[str]:
        try:
            return self._var_frozenset_cache['restricted_shell_escape_commands']
        except KeyError:
            commands = set()
            if self.texlive_kpsewhich:
                value = self._get_texlive_var_value('shell_escape_commands')
                if value is not None:
                    commands.update(value.split(','))
            elif self.miktex_initexmf:
                value = self._get_miktex_config_value('[Core]AllowedShellCommands[]')
                if value is not None:
                    commands.update(value.split(';'))
            else:
                raise TypeError
            self._var_frozenset_cache['restricted_shell_escape_commands'] = frozenset(commands)
            return self._var_frozenset_cache['restricted_shell_escape_commands']




latex_config = LatexConfig()
