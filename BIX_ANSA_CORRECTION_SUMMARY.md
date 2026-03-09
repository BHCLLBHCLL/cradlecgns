# CGNS NGON_n / NFACE_n 单元类型与存储结构说明

本文档说明 CGNS 标准中 NGON_n 与 NFACE_n 单元类型的引入历程及存储结构，供 ANSA 导出修正与兼容性参考。

---

## 一、CGNS 3.1：NGON_n 与 NFACE_n 的引入

### 1.1 引入时间与背景

**CGNS 3.1** 引入了对 **NGON_n** 和 **NFACE_n** 单元类型的支持，用于表示非结构网格中的多面体单元。

### 1.2 单元类型含义

| 单元类型 | 含义 |
|----------|------|
| **NGON_n** | 任意多边形面，由面到顶点的连接关系定义（face-to-vertex connectivity） |
| **NFACE_n** | 多面体单元，由单元到面的连接关系定义（cell-to-face connectivity） |

- **NGON_n**：描述面的顶点序列，支持任意边数的多边形。
- **NFACE_n**：描述体单元所包含的面 ID 列表，支持任意面数的多面体。
- 若仅有 NGON_n 而无 NFACE_n，可表示 3D 空间网格中的 2D 表面单元。

### 1.3 存储结构（CGNS 3.1）

NGON_n 与 NFACE_n 使用以下结构存储：

| 数据节点 | 用途 |
|----------|------|
| **ElementConnectivity** | 存储连接关系数据：NGON_n 为面→顶点索引，NFACE_n 为体→面索引 |
| **ElementRange** | 指定所描述单元的索引范围，格式为 `[start, end]` |

ElementConnectivity 为变长格式：每个单元/面的顶点或面数量不固定，需配合偏移量才能正确解析。

---

## 二、CGNS 3.4：ConnectOffset 的引入

### 2.1 引入时间

**CGNS 3.4** 版本引入了 **ConnectOffset**（连接偏移量）机制。

### 2.2 作用与意义

- **ConnectOffset** 用于在 ElementConnectivity 中快速定位每个单元/面的数据起始位置。
- 对于 NGON_n、NFACE_n 等变长格式，ConnectOffset 使得解析更高效，无需逐项扫描即可访问任意单元。
- 与 ElementRange 配合，可完整描述单元索引范围及在 ElementConnectivity 中的布局。

### 2.3 与 ElementStartOffset 的关系

在 CGNS Elements_t 结构中，与偏移相关的常见命名包括：

- **ElementStartOffset**：在部分实现与文档中用于表示单元在 ElementConnectivity 中的起始偏移。
- **ConnectOffset**：CGNS 3.4 正式引入的偏移量命名，与上述概念一致，用于 NGON/NFACE 等变长结构的索引。

实际文件中可能使用 `ElementStartOffset` 或 `ConnectOffset` 作为节点名，取决于 CGNS 库版本与导出工具。

---

## 三、版本演进汇总

| CGNS 版本 | 新增/变更内容 |
|-----------|----------------|
| **3.1** | 引入 NGON_n、NFACE_n 单元类型；使用 ElementConnectivity + ElementRange 存储 |
| **3.4** | 引入 ConnectOffset，用于变长 ElementConnectivity 的高效索引 |

---

## 四、与 ANSA 修正的关联

- ANSA 导出的 NGON_n/NFACE_n 网格通常包含 **ElementConnectivity**、**ElementRange** 及 **ElementStartOffset**（或 ConnectOffset）。
- 按 CGNS 规范，NGON_n 与 NFACE_n **必须保留** 偏移量结构，不可转换为仅 ElementConnectivity + ElementRange 的形式。
- 修正脚本（如 `convert_elements_zone.py`）对 NGON_n/NFACE_n 会跳过转换，以符合标准要求。

---

*文档基于 CGNS SIDS 规范及版本发布说明整理。*
