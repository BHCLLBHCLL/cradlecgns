Markdown -> HTML/PDF 转换说明
=============================================

已更新文档：CODE_ANALYSIS_SUMMARY.md, BOX_ANSA_CORRECTIONS_SUMMARY.md

方法 1：运行批处理（推荐）
---------------------------------------
  md_to_pdf.bat

  若系统已安装 MiKTeX 或 TeX Live，将直接生成 PDF。
  若未安装 LaTeX，会生成 HTML 文件，用浏览器打开后 Ctrl+P -> 另存为 PDF。

方法 2：Pandoc 直接生成 PDF
---------------------------------------
安装 MiKTeX (https://miktex.org) 或 TeX Live 后执行：

  pandoc CODE_ANALYSIS_SUMMARY.md -o CODE_ANALYSIS_SUMMARY.pdf
  pandoc BOX_ANSA_CORRECTIONS_SUMMARY.md -o BOX_ANSA_CORRECTIONS_SUMMARY.pdf

方法 3：浏览器打印（无需 LaTeX）
---------------------------------------
1. 运行 md_to_pdf.bat 生成 HTML（或手动）：
   pandoc CODE_ANALYSIS_SUMMARY.md -o CODE_ANALYSIS_SUMMARY.html -s
   pandoc BOX_ANSA_CORRECTIONS_SUMMARY.md -o BOX_ANSA_CORRECTIONS_SUMMARY.html -s

2. 用 Chrome / Edge 打开 HTML 文件
3. Ctrl+P -> 目标选择 "另存为 PDF"
4. 保存
