@echo off
REM Update HTML/PDF from Markdown (CODE_ANALYSIS_SUMMARY, BOX_ANSA_CORRECTIONS_SUMMARY)
REM Requires: pandoc (https://pandoc.org)
REM PDF needs: LaTeX (MiKTeX/TeX Live) - if missing, HTML is generated for manual Print-to-PDF

cd /d "%~dp0"

set DONE=0

REM CODE_ANALYSIS_SUMMARY
pandoc CODE_ANALYSIS_SUMMARY.md -o CODE_ANALYSIS_SUMMARY.pdf 2>nul
if exist CODE_ANALYSIS_SUMMARY.pdf (
    echo Created: CODE_ANALYSIS_SUMMARY.pdf
    set DONE=1
) else (
    echo Generating CODE_ANALYSIS_SUMMARY.html ...
    pandoc CODE_ANALYSIS_SUMMARY.md -o CODE_ANALYSIS_SUMMARY.html -s --metadata title="cradlecgns Code Analysis Summary"
)

REM BOX_ANSA_CORRECTIONS_SUMMARY
pandoc BOX_ANSA_CORRECTIONS_SUMMARY.md -o BOX_ANSA_CORRECTIONS_SUMMARY.pdf 2>nul
if exist BOX_ANSA_CORRECTIONS_SUMMARY.pdf (
    echo Created: BOX_ANSA_CORRECTIONS_SUMMARY.pdf
) else (
    echo Generating BOX_ANSA_CORRECTIONS_SUMMARY.html ...
    pandoc BOX_ANSA_CORRECTIONS_SUMMARY.md -o BOX_ANSA_CORRECTIONS_SUMMARY.html -s --metadata title="box_ansa Corrections Summary"
)

if %DONE%==0 (
    echo.
    echo PDF: LaTeX not found. HTML updated. Use browser: Ctrl+P -^> Save as PDF
    start CODE_ANALYSIS_SUMMARY.html 2>nul
    start BOX_ANSA_CORRECTIONS_SUMMARY.html 2>nul
)
