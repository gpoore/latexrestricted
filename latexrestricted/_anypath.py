# -*- coding: utf-8 -*-
#
# Copyright (c) 2024, Geoffrey M. Poore
# All rights reserved.
#
# Licensed under the LaTeX Project Public License version 1.3c:
# https://www.latex-project.org/lppl.txt
#


from __future__ import annotations

import pathlib
import sys
try:
    from typing import Self
except ImportError:
    pass




# The `type(...)` is needed to inherit the `_flavour` attribute
class AnyPath(type(pathlib.Path())):
    __slots__ = (
        '_cache_key',
    )

    if sys.version_info[:2] < (3, 9):
        def is_relative_to(self, other: AnyPath) -> bool:
            try:
                self.relative_to(other)
                return True
            except ValueError:
                return False

        def with_stem(self, stem: str):
            return self.with_name(stem + self.suffix)


    # `pathlib.Path.__hash__()` just depends on `self._str_normcase`.  For
    # caching, the class must also be considered.
    @property
    def cache_key(self) -> tuple[type[Self], Self]:
        try:
            return self._cache_key
        except AttributeError:
            self._cache_key = (type(self), self)
            return self._cache_key

    # `ResolvedRestrictedPath` classes use `super().resolve()` frequently to
    # determine whether paths are readable/writable.  `.resolve()` and
    # `.parent()` cache and track resolved paths to minimize file system
    # access.  This also guarantees that a path will always resolve to the
    # same location after it has been approved for reading/writing.
    _resolved_set: set[tuple[type[Self], Self]] = set()
    _resolve_cache: dict[tuple[type[Self], Self], Self] = {}
    _resolve_str_path_cache: dict[str, str] = {}

    def resolve(self) -> Self:
        try:
            return self._resolve_cache[self.cache_key]
        except KeyError:
            try:
                resolved = type(self)(self._resolve_str_path_cache[str(self)])
            except KeyError:
                resolved = super().resolve()
                self._resolve_str_path_cache[str(self)] = str(resolved)
                self._resolve_str_path_cache[str(resolved)] = str(resolved)
            self._resolved_set.add(resolved.cache_key)
            self._resolve_cache[self.cache_key] = resolved
            self._resolve_cache[resolved.cache_key] = resolved
            return resolved

    def is_resolved(self) -> bool:
        return self.cache_key in self._resolved_set

    @property
    def parent(self) -> Self:
        parent = super().parent
        if self.cache_key in self._resolved_set:
            self._resolved_set.add(parent.cache_key)
            self._resolve_cache[parent.cache_key] = parent
        return parent
