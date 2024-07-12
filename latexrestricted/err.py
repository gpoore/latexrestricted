# -*- coding: utf-8 -*-
#
# Copyright (c) 2024, Geoffrey M. Poore
# All rights reserved.
#
# Licensed under the LaTeX Project Public License version 1.3c:
# https://www.latex-project.org/lppl.txt
#


from __future__ import annotations




class LatexRestrictedError(Exception):
    pass

class LatexConfigError(LatexRestrictedError):
    pass

class SecurityError(LatexRestrictedError):
    pass

class PathSecurityError(SecurityError):
    pass

class SubprocessError(LatexRestrictedError):
    pass

class ExecutableNotFoundError(SubprocessError):
    pass

class UnapprovedExecutableError(SubprocessError, SecurityError):
    pass

class ExecutablePathSecurityError(SubprocessError, PathSecurityError):
    pass

