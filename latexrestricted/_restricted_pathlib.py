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
from contextlib import AbstractContextManager
from typing import Literal
try:
    from typing import Self
except ImportError:
    pass
from .err import PathSecurityError
from ._anypath import AnyPath
from ._latex_config import latex_config




# Following the approach of `contextlib.chdir()` from Python 3.11+:
# https://github.com/python/cpython/blob/3.12/Lib/contextlib.py#L788-L800
class _CdTeXCwd(AbstractContextManager):
    def __init__(self):
        self._tex_cwd: str = latex_config.tex_cwd
        self._cwd_stack: list[str | None] = []

    def __enter__(self):
        cwd = os.getcwd()
        if cwd == self._tex_cwd:
            self._cwd_stack.append(None)
        else:
            self._cwd_stack.append(cwd)
            os.chdir(self._tex_cwd)

    def __exit__(self, *excinfo):
        last_cwd = self._cwd_stack.pop()
        if last_cwd is not None:
            os.chdir(last_cwd)

_cd_tex_cwd = _CdTeXCwd()




class BaseRestrictedPath(type(AnyPath())):
    '''
    Base class for `RestrictedPath` classes.  This is based on `AnyPath`,
    instead of directly on `pathlib.Path`, for better Python 3.8 compatibility
    and also for `.resolve()` caching.

    Redefines all methods that modify the file system.

      * Most methods for opening, reading, writing, replacing, and deleting
        files as well as methods for creating and deleting directories are
        redefined to depend on the new methods `.tex_readable_dir()`,
        `.tex_readable_file()`, `.tex_writable_dir()`, and
        `.tex_writable_file()`.  These new methods all raise
        `NotImplementedError` in the base class; they must be implemented by
        subclasses.

      * All other methods for modifying the file system are redefined to raise
        `NotImplementedError`.  Most of these methods relate to file
        permissions and links.

    All supported methods that modify the file system operate with the TeX
    working directory as the current working directory.  This is necessary for
    performing path security analysis.  It is best not to modify the current
    working directory.  However, it is possible to create paths when the
    current working directory is another location and use those paths to
    obtain information from the file system (for example, via `.exists()`).
    Such paths will not work correctly to *modify* the file system; they must
    first be converted into absolute paths or paths relative to the TeX
    working directory.
    '''

    __slots__ = ()


    # Ensure paths are made relative to TeX working directory

    def absolute(self, *args, **kwargs):
        with _cd_tex_cwd:
            return super().absolute(*args, **kwargs)

    def resolve(self, *args, **kwargs):
        with _cd_tex_cwd:
            return super().resolve(*args, **kwargs)


    # This must be defined by subclasses.  If false, the file system is
    # accessed with a path as the path is currently defined.  If true, the
    # path is resolved first.  This should be true for subclasses that perform
    # path security analysis using resolved paths.  Otherwise, the file system
    # (symlinks) could be modified after security analysis but before a path
    # is used, so that the security analysis is invalid.
    _access_file_system_with_resolved_paths: bool

    # Default security is based on TeX configuration.  Subclasses can override
    # this, but should typically only do so to increase security to maximum.
    @classmethod
    def tex_can_read_anywhere(cls) -> bool:
        return latex_config.can_read_anywhere

    @classmethod
    def tex_can_read_dotfiles(cls) -> bool:
        return latex_config.can_read_dotfiles

    @classmethod
    def tex_can_write_anywhere(cls) -> bool:
        return latex_config.can_write_anywhere

    @classmethod
    def tex_can_write_dotfiles(cls) -> bool:
        return latex_config.can_write_dotfiles

    @classmethod
    def tex_prohibited_write_file_extensions(cls) -> set[str]:
        return latex_config.prohibited_write_file_extensions

    # This determines whether files with extensions in PATHEXT can be written
    # under Windows (including Cygwin).  Subclasses should only override this
    # when absolutely necessary.  If this is disabled, then other measures
    # should be taken to provide some compensating security.  For example,
    # prohibit writing files with these extensions in the TeX working
    # directory and possibly other locations where executables are likely to
    # be run from a shell.
    @classmethod
    def enforce_tex_prohibited_write_file_extensions(cls) -> bool:
        return True

    # Caches use `self.cache_key` which includes the class, so that the
    # returned type is correct.  Values describe whether paths are accessible,
    # and if not, why:
    #     (is_accessible: bool, reason_not_accessible: str | None)
    _tex_readable_dir_cache:  dict[tuple[type[Self], Self], tuple[Literal[True], None] | tuple[Literal[False], str]] = {}
    _tex_readable_file_cache: dict[tuple[type[Self], Self], tuple[Literal[True], None] | tuple[Literal[False], str]] = {}
    _tex_writable_dir_cache:  dict[tuple[type[Self], Self], tuple[Literal[True], None] | tuple[Literal[False], str]] = {}
    _tex_writable_file_cache: dict[tuple[type[Self], Self], tuple[Literal[True], None] | tuple[Literal[False], str]] = {}

    def tex_readable_dir(self) -> tuple[Literal[True], None] | tuple[Literal[False], str]:
        raise NotImplementedError

    def tex_readable_file(self) -> tuple[Literal[True], None] | tuple[Literal[False], str]:
        raise NotImplementedError

    def tex_writable_dir(self) -> tuple[Literal[True], None] | tuple[Literal[False], str]:
        raise NotImplementedError

    def tex_writable_file(self) -> tuple[Literal[True], None] | tuple[Literal[False], str]:
        raise NotImplementedError


    def chmod(self, *args, **kwargs):
        raise NotImplementedError

    def copy(self, *args, **kwargs):
        # Python 3.14
        raise NotImplementedError

    def copytree(self, *args, **kwargs):
        # Python 3.14
        raise NotImplementedError

    def lchmod(self, *args, **kwargs):
        raise NotImplementedError

    def mkdir(self, *args, **kwargs):
        with _cd_tex_cwd:
            is_writable, reason = self.tex_writable_dir()
            if not is_writable:
                raise PathSecurityError(f'Cannot create directory "{self.as_posix()}":  {reason}')
            if self._access_file_system_with_resolved_paths and not self.is_resolved():
                return super(BaseRestrictedPath, self.resolve()).mkdir(*args, **kwargs)
            return super().mkdir(*args, **kwargs)

    def open(self, mode: str = 'r', *args, **kwargs):
        with _cd_tex_cwd:
            if 'r' in mode:
                is_readable, reason = self.tex_readable_file()
                if not is_readable:
                    raise PathSecurityError(f'Cannot read file "{self.as_posix()}":  {reason}')
            elif any(char in mode for char in 'wxa'):
                is_writable, reason = self.tex_writable_file()
                if not is_writable:
                    raise PathSecurityError(f'Cannot write file "{self.as_posix()}":  {reason}')
            else:
                raise NotImplementedError
            if self._access_file_system_with_resolved_paths and not self.is_resolved():
                return super(BaseRestrictedPath, self.resolve()).open(mode=mode, *args, **kwargs)
            return super().open(mode=mode, *args, **kwargs)

    def read_bytes(self, *args, **kwargs):
        with _cd_tex_cwd:
            is_readable, reason = self.tex_readable_file()
            if not is_readable:
                raise PathSecurityError(f'Cannot read file "{self.as_posix()}":  {reason}')
            if self._access_file_system_with_resolved_paths and not self.is_resolved():
                return super(BaseRestrictedPath, self.resolve()).read_bytes(*args, **kwargs)
            return super().read_bytes(*args, **kwargs)

    def read_text(self, *args, **kwargs) -> str:
        with _cd_tex_cwd:
            is_readable, reason = self.tex_readable_file()
            if not is_readable:
                raise PathSecurityError(f'Cannot read file "{self.as_posix()}":  {reason}')
            if self._access_file_system_with_resolved_paths and not self.is_resolved():
                return super(BaseRestrictedPath, self.resolve()).read_text(*args, **kwargs)
            return super().read_text(*args, **kwargs)

    def rename(self, target: Self):
        with _cd_tex_cwd:
            is_writable, reason = self.tex_writable_file()
            if not is_writable:
                raise PathSecurityError(f'Cannot rename file "{self.as_posix()}":  {reason}')
            target_is_writable, target_reason = target.tex_writable_file()
            if not target_is_writable:
                raise PathSecurityError(f'Cannot create renamed file "{target.as_posix()}":  {target_reason}')
            if self._access_file_system_with_resolved_paths and not (self.is_resolved() and target.is_resolved()):
                return super(BaseRestrictedPath, self.resolve()).rename(target.resolve())
            return super().rename(target)

    def replace(self, target: Self):
        with _cd_tex_cwd:
            is_writable, reason = self.tex_writable_file()
            if not is_writable:
                raise PathSecurityError(f'Cannot replace file "{self.as_posix()}":  {reason}')
            target_is_writable, target_reason = target.tex_writable_file()
            if not target_is_writable:
                raise PathSecurityError(f'Cannot create replacement file "{target.as_posix()}":  {target_reason}')
            if self._access_file_system_with_resolved_paths and not (self.is_resolved() and target.is_resolved()):
                return super(BaseRestrictedPath, self.resolve()).replace(target.resolve())
            return super().replace(target)

    def rmdir(self):
        with _cd_tex_cwd:
            is_writable, reason = self.tex_writable_dir()
            if not is_writable:
                raise PathSecurityError(f'Cannot delete directory "{self.as_posix()}":  {reason}')
            if self._access_file_system_with_resolved_paths and not self.is_resolved():
                return super(BaseRestrictedPath, self.resolve()).rmdir()
            return super().rmdir()

    def symlink_to(self, *args, **kwargs):
        raise NotImplementedError

    def hardlink_to(self, *args, **kwargs):
        raise NotImplementedError

    def touch(self, *args, **kwargs):
        with _cd_tex_cwd:
            is_writable, reason = self.tex_writable_file()
            if not is_writable:
                raise PathSecurityError(f'Cannot create file "{self.as_posix()}":  {reason}')
            if self._access_file_system_with_resolved_paths and not self.is_resolved():
                return super(BaseRestrictedPath, self.resolve()).touch(*args, **kwargs)
            return super().touch(*args, **kwargs)

    def unlink(self, *args, **kwargs):
        with _cd_tex_cwd:
            is_writable, reason = self.tex_writable_file()
            if not is_writable:
                raise PathSecurityError(f'Cannot delete file "{self.as_posix()}":  {reason}')
            if self._access_file_system_with_resolved_paths and not self.is_resolved():
                return super(BaseRestrictedPath, self.resolve()).unlink(*args, **kwargs)
            return super().unlink(*args, **kwargs)

    def write_bytes(self, *args, **kwargs):
        with _cd_tex_cwd:
            is_writable, reason = self.tex_writable_file()
            if not is_writable:
                raise PathSecurityError(f'Cannot write file "{self.as_posix()}":  {reason}')
            if self._access_file_system_with_resolved_paths and not self.is_resolved():
                return super(BaseRestrictedPath, self.resolve()).write_bytes(*args, **kwargs)
            return super().write_bytes(*args, **kwargs)

    def write_text(self, *args, **kwargs):
        with _cd_tex_cwd:
            is_writable, reason = self.tex_writable_file()
            if not is_writable:
                raise PathSecurityError(f'Cannot write file "{self.as_posix()}":  {reason}')
            if self._access_file_system_with_resolved_paths and not self.is_resolved():
                return super(BaseRestrictedPath, self.resolve()).write_text(*args, **kwargs)
            return super().write_text(*args, **kwargs)


    @classmethod
    def tex_cwd(cls) -> Self:
        try:
            return cls._tex_cwd
        except AttributeError:
            cls._tex_cwd = cls(latex_config.tex_cwd)
            return cls._tex_cwd

    @classmethod
    def TEXMFOUTPUT(cls) -> Self | None:
        try:
            return cls._TEXMFOUTPUT
        except AttributeError:
            if latex_config.TEXMFOUTPUT is None:
                cls._TEXMFOUTPUT = None
            else:
                cls._TEXMFOUTPUT = cls(latex_config.TEXMFOUTPUT)
            return cls._TEXMFOUTPUT

    @classmethod
    def TEXMF_OUTPUT_DIRECTORY(cls) -> Self | None:
        try:
            return cls._TEXMF_OUTPUT_DIRECTORY
        except AttributeError:
            if latex_config.TEXMF_OUTPUT_DIRECTORY is None:
                cls._TEXMF_OUTPUT_DIRECTORY = None
            else:
                cls._TEXMF_OUTPUT_DIRECTORY = cls(latex_config.TEXMF_OUTPUT_DIRECTORY)
            return cls._TEXMF_OUTPUT_DIRECTORY

    @classmethod
    def tex_openout_roots(cls) -> list[Self]:
        # This is a list of paths because these are the directories that TeX
        # will try to write to in order.  If TEXMF_OUTPUT_DIRECTORY or the
        # current working directory is not writable, then TeX will fall back
        # to TEXMFOUTPUT if it is set.
        try:
            return cls._tex_openout_roots
        except AttributeError:
            cls._tex_openout_roots = []
            TEXMF_OUTPUT_DIRECTORY = cls.TEXMF_OUTPUT_DIRECTORY()
            if TEXMF_OUTPUT_DIRECTORY:
                cls._tex_openout_roots.append(TEXMF_OUTPUT_DIRECTORY)
            else:
                cls._tex_openout_roots.append(cls.tex_cwd())
            TEXMFOUTPUT = cls.TEXMFOUTPUT()
            if TEXMFOUTPUT and TEXMFOUTPUT not in cls._tex_openout_roots:
                cls._tex_openout_roots.append(TEXMFOUTPUT)
            return cls._tex_openout_roots

    @classmethod
    def tex_paranoid_roots(cls) -> set[Self]:
        # All possible paths that TeX can write to when write locations are
        # restricted ("paranoid" mode).
        try:
            return cls._tex_paranoid_roots
        except AttributeError:
            cls._tex_paranoid_roots = set()
            cls._tex_paranoid_roots.add(cls.tex_cwd())
            TEXMF_OUTPUT_DIRECTORY = cls.TEXMF_OUTPUT_DIRECTORY()
            if TEXMF_OUTPUT_DIRECTORY:
                cls._tex_paranoid_roots.add(TEXMF_OUTPUT_DIRECTORY)
            TEXMFOUTPUT = cls.TEXMFOUTPUT()
            if TEXMFOUTPUT:
                cls._tex_paranoid_roots.add(TEXMFOUTPUT)
            return cls._tex_paranoid_roots

    @classmethod
    def tex_paranoid_roots_resolved(cls) -> set[Self]:
        try:
            return cls._tex_paranoid_roots_resolved
        except AttributeError:
            cls._tex_paranoid_roots_resolved = set(p.resolve() for p in cls.tex_paranoid_roots())
            return cls._tex_paranoid_roots_resolved

    @classmethod
    def tex_paranoid_roots_with_resolved(cls) -> set[Self]:
        try:
            return cls._tex_paranoid_roots_with_resolved
        except KeyError:
            cls._tex_paranoid_roots_with_resolved = cls.tex_paranoid_roots() | cls.tex_paranoid_roots_resolved()
            return cls._tex_paranoid_roots_with_resolved

    @classmethod
    def tex_texmfoutput_roots(cls) -> set[Self]:
        try:
            return cls._tex_texmfoutput_roots
        except AttributeError:
            cls._tex_texmfoutput_roots = set()
            TEXMF_OUTPUT_DIRECTORY = cls.TEXMF_OUTPUT_DIRECTORY()
            if TEXMF_OUTPUT_DIRECTORY:
                cls._tex_texmfoutput_roots.add(TEXMF_OUTPUT_DIRECTORY)
            TEXMFOUTPUT = cls.TEXMFOUTPUT()
            if TEXMFOUTPUT:
                cls._tex_texmfoutput_roots.add(TEXMFOUTPUT)
            return cls._tex_texmfoutput_roots




class StringRestrictedPath(BaseRestrictedPath):
    '''
    Restrict paths by analyzing them as strings.  This follows the approach
    taken in TeX's file system security.  For example, see
    https://www.tug.org/texinfohtml/kpathsea.html#Safe-filenames-1 and
    https://tug.org/svn/texlive/trunk/Build/source/texk/kpathsea/progname.c?revision=57915&view=markup#l414.
    Restrictions depend on LaTeX configuration.  Restrictions are determined
    by `openout_any` and `openin_any` settings in `texmf.cnf` for TeX Live,
    and from `[Core]AllowUnsafeInputFiles` and `[Core]AllowUnsafeOutputFiles`
    in `miktex.ini` for MiKTeX.  These variables are accessed via
    `latex_config`.

    When reading or writing locations are restricted to the TeX working
    directory plus $TEXMF_OUTPUT_DIRECTORY and $TEXMFOUTPUT, paths are
    restricted using the following criteria:

      * All relative paths are relative to the TeX working directory.  (This
        is already enforced by `BaseRestrictedPath`.)

      * All absolute paths must be under $TEXMF_OUTPUT_DIRECTORY and
        $TEXMFOUTPUT.

      * Paths cannot contain `..` to access a parent directory, even if the
        parent directory is a valid location.

    Because paths are analyzed as strings, it is still possible to access
    locations outside the TeX working directory, $TEXMF_OUTPUT_DIRECTORY, and
    $TEXMFOUTPUT via symlinks in these locations.  Symlinks are not resolved
    in determining whether paths are valid, since paths are analyzed as
    strings without consulting the file system.

    Depending on LaTeX configuration, reading or writing file names starting
    with `.` (dotfiles) may be disabled.

    Under Windows (including Cygwin), writing files with file extensions in
    `PATHEXT` is also disabled.
    '''

    __slots__ = ()

    _access_file_system_with_resolved_paths = False

    def tex_readable_dir(self) -> tuple[Literal[True], None] | tuple[Literal[False], str]:
        try:
            return self._tex_readable_dir_cache[self.cache_key]
        except KeyError:
            if self.tex_can_read_anywhere():
                self._tex_readable_dir_cache[self.cache_key] = (True, None)
            elif '..' in self.parts:
                self._tex_readable_dir_cache[self.cache_key] = (
                    False,
                    'security settings do not permit paths containing ".."'
                )
            elif self.is_absolute() and not any(self.is_relative_to(p) for p in self.tex_texmfoutput_roots()):
                self._tex_readable_dir_cache[self.cache_key] = (
                    False,
                    'security settings do not permit access to this location'
                )
            else:
                self._tex_readable_dir_cache[self.cache_key] = (True, None)
            return self._tex_readable_dir_cache[self.cache_key]

    def tex_readable_file(self) -> tuple[Literal[True], None] | tuple[Literal[False], str]:
        try:
            return self._tex_readable_file_cache[self.cache_key]
        except KeyError:
            if self.tex_can_read_dotfiles() or not self.name.startswith('.'):
                self._tex_readable_file_cache[self.cache_key] = self.parent.tex_readable_dir()
            else:
                self._tex_readable_file_cache[self.cache_key] = (
                    False,
                    'security settings do not permit access to dotfiles'
                )
            return self._tex_readable_file_cache[self.cache_key]

    def tex_writable_dir(self) -> tuple[Literal[True], None] | tuple[Literal[False], str]:
        try:
            return self._tex_writable_dir_cache[self.cache_key]
        except KeyError:
            if self.tex_can_write_anywhere():
                self._tex_writable_dir_cache[self.cache_key] = (True, None)
            elif '..' in self.parts:
                self._tex_writable_dir_cache[self.cache_key] = (
                    False,
                    'security settings do not permit paths containing ".."'
                )
            elif self.is_absolute() and not any(self.is_relative_to(p) for p in self.tex_texmfoutput_roots()):
                self._tex_writable_dir_cache[self.cache_key] = (
                    False,
                    'security settings do not permit access to this location'
                )
            else:
                self._tex_writable_dir_cache[self.cache_key] = (True, None)
            return self._tex_writable_dir_cache[self.cache_key]

    def tex_writable_file(self) -> tuple[Literal[True], None] | tuple[Literal[False], str]:
        try:
            return self._tex_writable_file_cache[self.cache_key]
        except KeyError:
            if self.enforce_tex_prohibited_write_file_extensions():
                name_lower = self.name.lower()
                for ext in self.tex_prohibited_write_file_extensions():
                    if name_lower.endswith(ext):
                        self._tex_writable_file_cache[self.cache_key] = (
                            False,
                            f'security settings prevent writing files with extension "{ext}"'
                        )
                        return self._tex_writable_file_cache[self.cache_key]
            if self.tex_can_write_dotfiles() or not self.name.startswith('.'):
                self._tex_writable_file_cache[self.cache_key] = self.parent.tex_writable_dir()
            else:
                self._tex_writable_file_cache[self.cache_key] = (
                    False,
                    'security settings do not permit access to dotfiles'
                )
            return self._tex_writable_file_cache[self.cache_key]


class SafeStringRestrictedPath(StringRestrictedPath):
    __slots__ = ()

    @classmethod
    def tex_can_read_anywhere(cls):
        return False

    @classmethod
    def tex_can_read_dotfiles(cls):
        return False

    @classmethod
    def tex_can_write_anywhere(cls):
        return False

    @classmethod
    def tex_can_write_dotfiles(cls):
        return False


class SafeWriteStringRestrictedPath(StringRestrictedPath):
    __slots__ = ()

    @classmethod
    def tex_can_write_anywhere(cls):
        return False

    @classmethod
    def tex_can_write_dotfiles(cls):
        return False




class ResolvedRestrictedPath(BaseRestrictedPath):
    '''
    Restrict paths by resolving any symlinks with the file system and then
    comparing resolved paths to permitted read/write locations.  Restrictions
    are determined by `openout_any` and `openin_any` settings in `texmf.cnf`
    for TeX Live, and from `[Core]AllowUnsafeInputFiles` and
    `[Core]AllowUnsafeOutputFiles` in `miktex.ini` for MiKTeX.  These
    variables are accessed via `latex_config`.

    When reading or writing locations are restricted to the TeX working
    directory plus $TEXMF_OUTPUT_DIRECTORY and $TEXMFOUTPUT, paths are
    restricted using the following criteria:

      * Resolved paths must be under the TeX working directory,
        $TEXMF_OUTPUT_DIRECTORY, or $TEXMFOUTPUT.

      * All relative paths are resolved relative to the TeX working directory.
        (This is already enforced by `BaseRestrictedPath`.)

      * Unlike `StringRestrictedPath`, paths are allowed to contain `..`, and
        $TEXMF_OUTPUT_DIRECTORY and $TEXMFOUTPUT can be accessed via relative
        paths.  This is possible since paths are fully resolved with the file
        system before being compared with permitted read/write locations.

    Because paths are resolved before being compared with permitted read/write
    locations, it is not possible to access locations outside the TeX working
    directory, $TEXMF_OUTPUT_DIRECTORY, and $TEXMFOUTPUT via symlinks in those
    locations.

    Depending on LaTeX configuration, reading or writing file names starting
    with `.` (dotfiles) may be disabled.

    Under Windows (including Cygwin), writing files with file extensions in
    `PATHEXT` is also disabled.
    '''

    __slots__ = ()

    _access_file_system_with_resolved_paths = True

    def tex_readable_dir(self) -> tuple[Literal[True], None] | tuple[Literal[False], str]:
        try:
            return self._tex_readable_dir_cache[self.cache_key]
        except KeyError:
            if self.tex_can_read_anywhere():
                self._tex_readable_dir_cache[self.cache_key] = (True, None)
            else:
                resolved = self.resolve()
                if any(resolved.is_relative_to(p) for p in self.tex_paranoid_roots_resolved()):
                    self._tex_readable_dir_cache[self.cache_key] = (True, None)
                else:
                    self._tex_readable_dir_cache[self.cache_key] = (
                        False,
                        'security settings do not permit access to this location'
                    )
            return self._tex_readable_dir_cache[self.cache_key]

    def tex_readable_file(self) -> tuple[Literal[True], None] | tuple[Literal[False], str]:
        try:
            return self._tex_readable_file_cache[self.cache_key]
        except KeyError:
            # Must always resolve files in case they are symlinks.  Always use
            # `self.resolve().parent` instead of `self.parent`.
            resolved = self.resolve()
            if self.tex_can_read_dotfiles() or not any(p.name.startswith('.') for p in (self, resolved)):
                self._tex_readable_file_cache[self.cache_key] = resolved.parent.tex_readable_dir()
            else:
                self._tex_readable_file_cache[self.cache_key] = (
                    False,
                    'security settings do not permit access to dotfiles'
                )
            return self._tex_readable_file_cache[self.cache_key]

    def tex_writable_dir(self) -> tuple[Literal[True], None] | tuple[Literal[False], str]:
        try:
            return self._tex_writable_dir_cache[self.cache_key]
        except KeyError:
            if self.tex_can_write_anywhere():
                self._tex_writable_dir_cache[self.cache_key] = (True, None)
            else:
                resolved = self.resolve()
                if any(resolved.is_relative_to(p) for p in self.tex_paranoid_roots_resolved()):
                    self._tex_writable_dir_cache[self.cache_key] = (True, None)
                else:
                    self._tex_writable_dir_cache[self.cache_key] = (
                        False,
                        'security settings do not permit access to this location'
                    )
            return self._tex_writable_dir_cache[self.cache_key]

    def tex_writable_file(self) -> tuple[Literal[True], None] | tuple[Literal[False], str]:
        try:
            return self._tex_writable_file_cache[self.cache_key]
        except KeyError:
            resolved = self.resolve()
            if self.enforce_tex_prohibited_write_file_extensions():
                name_lower = self.name.lower()
                resolved_name_lower = resolved.name.lower()
                for ext in self.tex_prohibited_write_file_extensions():
                    if name_lower.endswith(ext) or resolved_name_lower.endswith(ext):
                        self._tex_writable_file_cache[self.cache_key] = (
                            False,
                            f'security settings prevent writing files with extension "{ext}"'
                        )
                        return self._tex_writable_file_cache[self.cache_key]
            if self.tex_can_write_dotfiles() or not any(p.name.startswith('.') for p in (self, resolved)):
                self._tex_writable_file_cache[self.cache_key] = resolved.parent.tex_writable_dir()
            else:
                self._tex_writable_file_cache[self.cache_key] = (
                    False,
                    'security settings do not permit access to dotfiles'
                )
            return self._tex_writable_file_cache[self.cache_key]


class SafeResolvedRestrictedPath(ResolvedRestrictedPath):
    __slots__ = ()

    @classmethod
    def tex_can_read_anywhere(cls):
        return False

    @classmethod
    def tex_can_read_dotfiles(cls):
        return False

    @classmethod
    def tex_can_write_anywhere(cls):
        return False

    @classmethod
    def tex_can_write_dotfiles(cls):
        return False


class SafeWriteResolvedRestrictedPath(ResolvedRestrictedPath):
    __slots__ = ()

    @classmethod
    def tex_can_write_anywhere(cls):
        return False

    @classmethod
    def tex_can_write_dotfiles(cls):
        return False
