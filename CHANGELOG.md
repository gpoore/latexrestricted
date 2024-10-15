# Changelog — `latexrestricted` Python package


## v0.5.0 (dev)

*  Switched from `platform.system()` to `sys.platform` for better performance
   in detecting operating system.

   Performance reference:  https://github.com/python/cpython/issues/95531.



## v0.4.0 (2024-08-16)

* Under Windows with TeX Live, the `SELFAUTOLOC` environment variable is no
  longer used to locate `kpsewhich`.  Under these conditions, a shell escape
  executable will often be launched with TeX Live's executable wrapper
  `runscript.exe`.  This uses `kpathsea` internally, which overwrites
  `SELFAUTOLOC` so that it refers to the location of the executable wrapper,
  not the location of the TeX executable that initially invoked shell escape.
  Under these conditions, `kpsewhich` is now located by searching path with
  Python's `shutil.which()` for a `tlmgr` executable with accompanying
  `kpsewhich`, and there is no way to guarantee that the correct `kpsewhich`
  is used on systems with multiple TeX Live installations.



## v0.3.0 (2024-08-11)

*  Fixed `__slots__` bug in `AnyPath`.

*  Replaced all `$TEXMF*` with `TEXMF*` in error messages and documentation
   for better consistency.



## v0.2.0 (2024-08-10)

*  Added check for unsafe `TEXMFOUTPUT` value in TeX Live config.



## v0.1.0 (2024-07-27)

*  Initial release.
