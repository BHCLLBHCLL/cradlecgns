BOX_ANSA_CORRECTIONS_SUMMARY.md -> PDF 转换说明
=============================================

方法 1：浏览器打印（推荐，无需额外安装）
---------------------------------------
1. 已生成 BOX_ANSA_CORRECTIONS_SUMMARY.html
2. 用 Chrome / Edge 打开该 HTML 文件
3. 按 Ctrl+P 打开打印
4. 目标打印机选择 "另存为 PDF" 或 "Microsoft Print to PDF"
5. 点击保存，得到 PDF

方法 2：Pandoc + LaTeX
---------------------------------------
安装 MiKTeX (https://miktex.org) 或 TeX Live 后执行：
  pandoc BOX_ANSA_CORRECTIONS_SUMMARY.md -o BOX_ANSA_CORRECTIONS_SUMMARY.pdf

方法 3：运行批处理
---------------------------------------
  md_to_pdf.bat
（若 pandoc+LaTeX 可用则直接生成 PDF，否则打开 HTML 供手动打印）
