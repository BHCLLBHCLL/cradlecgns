@echo off
REM Convert BOX_ANSA_CORRECTIONS_SUMMARY.md to PDF
REM Requires: pandoc (https://pandoc.org) + LaTeX (MiKTeX/TeX Live) or wkhtmltopdf

cd /d "%~dp0"

REM Try pandoc with pdflatex (install MiKTeX if missing)
pandoc BOX_ANSA_CORRECTIONS_SUMMARY.md -o BOX_ANSA_CORRECTIONS_SUMMARY.pdf 2>nul
if exist BOX_ANSA_CORRECTIONS_SUMMARY.pdf (
    echo Created: BOX_ANSA_CORRECTIONS_SUMMARY.pdf
    exit /b 0
)

REM Fallback: generate HTML and open for manual Print-to-PDF
echo Pandoc PDF failed. Generating HTML...
pandoc BOX_ANSA_CORRECTIONS_SUMMARY.md -o BOX_ANSA_CORRECTIONS_SUMMARY.html -s --metadata title="BOX_ANSA_CORRECTIONS_SUMMARY"
echo Opening HTML. Use browser: Ctrl+P -^> Save as PDF
start BOX_ANSA_CORRECTIONS_SUMMARY.html
