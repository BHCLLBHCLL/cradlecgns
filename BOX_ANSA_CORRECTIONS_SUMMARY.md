# box_ansa.cgns 有效修正点总结

本文档系统梳理针对 **box_ansa.cgns** 的修正项、对应脚本及推荐流程，便于复现与后续维护。

---

## 一、开发情况概览

### 1. 背景与目标

- **来源**：box_ansa.cgns 与 box_ngons.cgns 均由 ANSA 同一网格导出。
- **问题**：ansa 导出在 BC 类型、整数位宽、PointList 形状等方面与 ngons/Star-CCM+ 期望不一致，易导致导入失败或内存错误。
- **目标**：在符合 CGNS 规范的前提下，将 box_ansa.cgns 修正为可被 Star-CCM+、ANSA 正常导入的形态。

### 2. 脚本与工具一览

| 脚本 | 用途 |
|------|------|
| `view_cgns_shapes.py` | 查看 CGNS 中各 dataset 的 shape/dtype |
| `compare_cgns.py` | 对比两个 CGNS 文件结构、shape、dtype 及风险项 |
| `fix_pointlist_shape.py` | ZoneBC 下 PointList 内 `" data"` 的 shape 从 (n,) 改为 (n,1) |
| `fix_box_surfs_data.py` | 将 ZoneBC/box_surfs/ data 从参考文件（如 box_ngons）复制，使 BC 类型与长度一致 |
| `fix_bc_type_null.py` | 将 BCType 为 Null/NULL 的项改为 BCTypeNull（CGNS 合法类型） |
| `convert_elements_to_int64.py` | 将 Element*、Zone data 等整数改为 int64（不含 PointList） |
| `fix_connectivity_signs.py` | ElementConnectivity 中负数取绝对值（可选，见备注） |
| `convert_elements_zone.py` | 将带 ElementStartOffset 的 Elements_t 转为仅 ElementConnectivity+ElementRange（固定类型/MIXED；NGON_n/NFACE_n 跳过） |
| `set_cgns_version.py` | 设置 CGNSLibraryVersion = 4.2（Star-CCM+、ANSA 可正常导入） |
| `upgrade_to_cgns_42.py` | 一键将 CGNS 转为 4.2 标准（整合版本、PointList、BCType、int64 等修正） |

### 3. 文档与备注

- **CGNS_COMPARISON_REPORT.md**：ansa vs ngons 差异与内存风险分析。
- **备注**：以下两点待后续验证——① 数据类型是否必须为 64 位；② connectivity 是否允许为负数。

---

## 二、CGNS NGON_n / NFACE_n 单元类型与存储结构说明

### 2.1 CGNS 3.1：NGON_n 与 NFACE_n 的引入

**CGNS 3.1** 引入了对 **NGON_n** 和 **NFACE_n** 单元类型的支持，用于表示非结构网格中的多面体单元。使用 **ElementConnectivity** 和 **ElementRange** 存储：

| 数据节点 | 用途 |
|----------|------|
| **ElementConnectivity** | 存储连接关系：NGON_n 为面→顶点索引，NFACE_n 为体→面索引 |
| **ElementRange** | 指定所描述单元的索引范围，格式为 `[start, end]` |

- **NGON_n**：任意多边形面，由面到顶点的连接关系定义；描述面的顶点序列，支持任意边数的多边形。
- **NFACE_n**：多面体单元，由单元到面的连接关系定义；描述体单元所包含的面 ID 列表，支持任意面数的多面体。
- ElementConnectivity 为变长格式，每个单元/面的顶点或面数量不固定，需配合偏移量才能正确解析。

### 2.2 CGNS 3.4：ConnectOffset 的引入

**CGNS 3.4** 版本引入了 **ConnectOffset**（连接偏移量）机制：

- 用于在 ElementConnectivity 中快速定位每个单元/面的数据起始位置。
- 对于 NGON_n、NFACE_n 等变长格式，ConnectOffset 使得解析更高效，无需逐项扫描即可访问任意单元。
- 与 ElementRange 配合，可完整描述单元索引范围及在 ElementConnectivity 中的布局。
- 实际文件中可能使用 `ElementStartOffset` 或 `ConnectOffset` 作为节点名，取决于 CGNS 库版本与导出工具。

### 2.3 版本演进汇总

| CGNS 版本 | 新增/变更内容 |
|-----------|----------------|
| **3.1** | 引入 NGON_n、NFACE_n；使用 ElementConnectivity + ElementRange 存储 |
| **3.4** | 引入 ConnectOffset，用于变长 ElementConnectivity 的高效索引 |

按 CGNS 规范，NGON_n 与 NFACE_n **必须保留** 偏移量结构，不可转换为仅 ElementConnectivity + ElementRange 的形式。修正脚本（如 `convert_elements_zone.py`）对 NGON_n/NFACE_n 会跳过转换。

---

## 三、box_ansa.cgns 有效修正点汇总

以下为对 **box_ansa.cgns** 实际生效的修正点，按推荐执行顺序排列。

### 修正点 1：边界类型不能为 Null，需为合法 BCType_t

- **现象**：ZoneBC 下某 BC 的 ` data` 为 `"Null"`（4 字节），不符合 CGNS 对 BCType_t 的要求。
- **规范**：边界类型不能为 NULL，应为已知类型（如 BCTypeNull、BCWall 等）。
- **做法**：
  - **做法 A**：若希望与参考文件一致（如壁面），用 `fix_box_surfs_data.py` 从 box_ngons 复制，得到如 `"BCWall"`（6 字节）。
  - **做法 B**：若仅需满足规范、不指定具体类型，用 `fix_bc_type_null.py` 将 Null/NULL 改为 `"BCTypeNull"`。
- **脚本**：`fix_box_surfs_data.py` 或 `fix_bc_type_null.py`。

### 修正点 2：ZoneBC 下 PointList 的 `" data"` 形状 (n,) → (n,1)

- **现象**：PointList 组内 `" data"` 为 1 维 (n,)，部分读取器按 (n,1) 解析，易产生越界或 stride 错误。
- **做法**：将 shape 从 (n,) 改为 (n,1)。
- **脚本**：`fix_pointlist_shape.py`。

### 修正点 3：整数类型统一为 64 位（Element*、Zone data，不含 PointList）

- **现象**：ansa 中 ElementConnectivity、ElementRange、ElementStartOffset、Base/box_vol/ data 等为 int32，ngons 为 int64。
- **风险**：大网格索引溢出、或按 int64 解析时 stride 错误。
- **做法**：将 Element*、Zone data 等整数 dataset 转为 int64。**PointList 不强制转为 int64**，保留原类型。
- **脚本**：`convert_elements_to_int64.py`。
- **备注**：是否“必须”64 位尚未最终确认，当前以与 ngons/常见读取器一致为准。

### 修正点 4：CGNS 库版本设为 4.2

- **现象**：部分旧文件版本号非 4.2，Star-CCM+、ANSA 导入异常。
- **经验**：改为 4.2 后，Star-CCM+ 与 ANSA 均可正常导入。
- **做法**：设置 CGNSLibraryVersion 节点为 4.2。
- **脚本**：`set_cgns_version.py`。

### 修正点 5（可选）：ElementConnectivity 负值处理

- **现象**：NFACE_n 中 face ID 可为负（表示法向），部分求解器假定非负。
- **做法**：若下游不接受负 ID，可用 `fix_connectivity_signs.py` 将负数取绝对值。
- **脚本**：`fix_connectivity_signs.py`。
- **备注**：connectivity 是否允许为负数需进一步验证；若允许，则不必跑此脚本。

### 修正点 6（可选）：Elements_t 含 ElementStartOffset 的转换

- **现象**：部分导出含 ElementConnectivity + ElementRange + ElementStartOffset，下游仅支持前两者。
- **做法**：固定类型删除 ElementStartOffset；MIXED 拆成多段同质 Elements_t；NGON_n/NFACE_n 按规范保留 ElementStartOffset，不转换。
- **脚本**：`convert_elements_zone.py`。
- **说明**：当前 box 示例为 NGON_n/NFACE_n，脚本会跳过；若以后遇到 MIXED 或误带 offset 的固定类型，可启用。

### 修正点 7（可选）：文件体积与碎片

- **现象**：多次就地修改后，box_ansa.cgns 约 42KB，box_ngons 约 18KB，数据量相同，差异来自 HDF5 内部碎片。
- **做法**：使用 `h5repack` 重写文件，得到紧凑的 box_ansa_repacked.cgns，体积接近 ngons。
- **命令**：`h5repack box_ansa.cgns box_ansa_repacked.cgns`。

---

## 四、推荐修正流程（box_ansa.cgns）

**方式 A：一键升级（推荐）**

```text
python upgrade_to_cgns_42.py box_ansa.cgns -o box_ansa_42.cgns
```

`upgrade_to_cgns_42.py` 整合了版本号、NGON/NFACE 格式、int64、PointList shape、BCType 等修正，适合快速标准化。

**方式 B：分步执行**

按顺序执行即可得到与 box_ngons 兼容、可被 Star-CCM+ 与 ANSA 正常导入的文件：

```text
1. fix_pointlist_shape.py    box_ansa.cgns    # PointList  data (n,) -> (n,1)
2. fix_box_surfs_data.py     [或 fix_bc_type_null.py]  # BC 类型合法且长度一致
3. convert_elements_to_int64.py  box_ansa.cgns # Element*、Zone 整数转 int64（不含 PointList）
4. set_cgns_version.py       box_ansa.cgns    # CGNSLibraryVersion = 4.2
5. （可选）fix_connectivity_signs.py  box_ansa.cgns  # 若需消除负的 face ID
6. （可选）h5repack box_ansa.cgns box_ansa_repacked.cgns  # 压缩与去碎片
```

验证：

```text
python compare_cgns.py   # 若已支持参数，可比较 box_ansa_repacked.cgns 与 box_ngons.cgns
```

---

## 五、与 box_ngons.cgns 的差异收敛情况

完成上述修正并（可选）repack 后：

- **结构**：与 box_ngons 一致（共同路径、无仅一方存在的 dataset）。
- **Shape/dtype**：共同路径上无差异。
- **命名**：若存在 NFacesElements / NFaceElements 等拼写差异，需在 ANSA 导出或后续脚本中统一（当前示例中 repack 后已一致）。

---

*文档基于当晚开发与 box_ansa / box_ngons 对比结果整理。*
