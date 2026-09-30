# Runs an arbitrary executable with an argument array, sidestepping cmd.exe's
# quote-stripping heuristics for /C entirely.
#
# Why this exists: routing a .cmd/.bat target through
# `cmd.exe /d /s /c "<flattened command line>"` requires collapsing the
# executable path and every argument into ONE string. Once that string
# contains more than one quoted segment (e.g. an executable path with a
# space AND a multi-word natural-language argument), cmd.exe's own /C
# quote-stripping rule ("exactly two quotes and the quoted text is an
# executable name, else strip only the first and last quote in the whole
# line") corrupts or fully shreds the extra quoted segment - confirmed by
# reproduction: a multi-word task description came back as one argv token
# per word, with a stray leading/trailing quote character. PowerShell's
# array-splatting operator (@Arguments) passes each element through to
# CreateProcess as its own correctly quoted argument in a single hop, with
# no equivalent ambiguity.
$argumentBytes = [Convert]::FromBase64String($env:DUAL_AGENT_STUDIO_ARGUMENTS)
$argumentJson = [Text.Encoding]::UTF8.GetString($argumentBytes)
[string[]]$ForwardArgs = ConvertFrom-Json $argumentJson

& $env:DUAL_AGENT_STUDIO_EXECUTABLE @ForwardArgs
exit $LASTEXITCODE
