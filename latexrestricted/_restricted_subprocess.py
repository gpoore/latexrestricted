# -*- coding: utf-8 -*-
#
# Copyright (c) 2024, Geoffrey M. Poore
# All rights reserved.
#
# Licensed under the LaTeX Project Public License version 1.3c:
# https://www.latex-project.org/lppl.txt
#


from __future__ import annotations

import shutil
import subprocess
import sys
from .err import UnapprovedExecutableError, ExecutableNotFoundError, ExecutablePathSecurityError
from ._anypath import AnyPath
from ._latex_config import latex_config




_always_approved_executables = set([
    'kpsewhich',
    'miktex-kpsewhich',
    'initexmf',
])

_cache: dict[str, set[AnyPath]] = {}




def restricted_run(args: list[str], allow_restricted_executables: bool = False) -> subprocess.CompletedProcess:
    '''
    Run a command securely, consistent with TeX restricted shell escape.

     *  By default, the executable must be in the list of always approved
        executables in this file.  If `allow_restricted_executables == True`,
        then the executable must be in the list of allowed restricted shell
        escape commands as returned by `kpsewhich` or `initexmf`.

     *  The executable must be in the same directory as `kpsewhich` or
        `initexmf`, as previously located during LaTeX config evaluation, or
        the executable must exist on PATH, as found by `shutil.which()`.

        The executable must not be in a location writable by LaTeX.  For added
        security, locations writable by LaTeX cannot be under the executable
        parent directory.

     *  The executable cannot be a batch file (no *.bat or *.cmd):
        https://docs.python.org/3/library/subprocess.html#security-considerations.
        This is enforced in a somewhat redundant fashion by requiring *.exe
        under Windows and completely prohibiting *.bat and *.cmd everywhere.

     *  The subprocess must run with `shell=False`.
    '''

    if not isinstance(args, list) or not args or not all(isinstance(x, str) for x in args):
        raise TypeError('"args" must be a list of strings')
    if not isinstance(allow_restricted_executables, bool):
        raise TypeError('"allow_restricted_executables" must be a bool')

    executable = args[0]
    if executable not in _always_approved_executables:
        if not allow_restricted_executables:
            raise UnapprovedExecutableError(
                'Cannot use executables other than "kpsewhich" and "initexmf" '
                'when "allow_restricted_executables" is False'
            )
        if not latex_config.can_restricted_shell_escape:
            raise UnapprovedExecutableError(
                f'Executable "{executable}" cannot be used when (restricted) shell escape is disabled'
            )
        if executable not in latex_config.restricted_shell_escape_commands:
            raise UnapprovedExecutableError(
                f'Executable "{executable}" is not in the approved list from LaTeX configuration'
            )

    if latex_config.texlive_bin:
        which_executable = shutil.which(executable, path=latex_config.texlive_bin)
    elif latex_config.miktex_bin:
        which_executable = shutil.which(executable, path=latex_config.miktex_bin)
    else:
        raise TypeError
    if not which_executable:
        which_executable = shutil.which(executable)
    if not which_executable:
        raise ExecutableNotFoundError(f'Executable "{executable}" was not found')

    which_executable_path = AnyPath(which_executable)
    which_executable_resolved = which_executable_path.resolve()
    if sys.platform == 'win32' and not which_executable_resolved.name.lower().endswith('.exe'):
        raise UnapprovedExecutableError(
            f'Executable "{executable}" resolved to "{which_executable_resolved.as_posix()}", but *.exe is required'
        )
    if any(which_executable_resolved.name.lower().endswith(ext) for ext in ('.bat', '.cmd')):
        # This should be redundant
        raise UnapprovedExecutableError(
            f'Executable "{executable}" resolved to "{which_executable_resolved.as_posix()}", '
            'but *.bat and *.cmd are not permitted'
        )

    try:
        prohibited_path_roots = _cache['prohibited_path_roots']
    except KeyError:
        _cache['prohibited_path_roots'] = set([AnyPath(latex_config.tex_cwd)])
        for var in (latex_config.TEXMF_OUTPUT_DIRECTORY, latex_config.TEXMFOUTPUT):
            if var:
                var_path = AnyPath(var)
                _cache['prohibited_path_roots'].update([var_path, var_path.resolve()])
        prohibited_path_roots = _cache['prohibited_path_roots']

    if any(e.is_relative_to(p) or p.is_relative_to(e)
           for e in set([which_executable_path.parent, which_executable_resolved.parent])
           for p in prohibited_path_roots):
        raise ExecutablePathSecurityError(
            f'Executable "{executable}" is located under the current directory, TEXMFOUTPUT, '
            'or TEXMF_OUTPUT_DIRECTORY, or one of these locations is under the same directory '
            'as the executable'
        )

    # Use resolved executable path for subprocess to guarantee that the
    # correct executable is invoked.
    resolved_args = [which_executable_resolved.as_posix()] + args[1:]
    proc = subprocess.run(resolved_args, shell=False, capture_output=True)
    return proc
