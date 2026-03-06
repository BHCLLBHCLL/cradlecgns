# box_ansa.cgns vs box_ngons.cgns 差异与内存风险报告

两个文件均由 ANSA 中同一网格导出，但存在多处差异，box_ansa.cgns 中部分结构可能引发内存错误。

---

## 1. 结构对比

- **共同路径**: 20 个 dataset
- **仅在 ansa 存在**: 0
- **仅在 ngons 存在**: 0  
- 拓扑相同，差异集中在 shape / dtype。

---

## 2. 详细差异

| 路径 | box_ansa.cgns | box_ngons.cgns |
|------|---------------|----------------|
| Base/box_vol/ data | (3,1) int32 | (3,1) int64 |
| NFaceElements/ElementConnectivity/ data | (24,) int32 | (24,) int64 |
| NFaceElements/ElementRange/ data | (2,) int32 | (2,) int64 |
| NFaceElements/ElementStartOffset/ data | (7,) int32 | (7,) int64 |
| NGonElements/ElementConnectivity/ data | (54,) int32 | (54,) int64 |
| NGonElements/ElementRange/ data | (2,) int32 | (2,) int64 |
| NGonElements/ElementStartOffset/ data | (19,) int32 | (19,) int64 |
| **ZoneBC/box_surfs/ data** | **(4,) int8** | **(6,) int8** |
| ZoneBC/box_surfs/PointList/ data | (12,1) int32 | (12,1) int64 |

---

## 3. box_ansa.cgns 易引入内存错误的位置

### 3.1 【高风险】ZoneBC/box_surfs/ data 长度不一致 (4 vs 6)

- **ansa**: shape=(4,) int8 → 内容 `"Null"` (4 字节)  
- **ngons**: shape=(6,) int8 → 内容 `"BCWall"` (6 字节)

**风险**：若读取器假定 BC 描述符为固定长度 6，在读 ansa 时会多读 2 字节，可能：

- 越界读相邻数据
- 栈/堆缓冲区溢出  
建议在 ANSA 导出时统一 BC 名称长度，或读取器按实际长度处理。

---

### 3.2 【中风险】int32 vs int64

ansa 统一使用 int32，ngons 使用 int64。

**风险**：

1. **索引溢出**：单元/节点数 > 2^31 时，int32 溢出，导致索引错误或越界。
2. **步长错误**：读取器若按 int64 解析，但 ansa 实际为 int32，stride 会加倍，导致错位和越界。
3. **符号问题**：int32 负值在按 int64 读取时可能被错误解释。

**涉及路径**：

- Base/box_vol/ data  
- NFaceElements/ElementConnectivity, ElementRange, ElementStartOffset  
- NGonElements/ElementConnectivity, ElementRange, ElementStartOffset  
- ZoneBC/box_surfs/PointList  

建议导出时优先使用 int64，或读取器根据 CGNS 标注正确识别类型。

---

### 3.3 【中风险】ElementStartOffset 与 ElementConnectivity 一致性

- NFaceElements: offset 长 7 → 6 个体单元，connectivity 长 24 → 总面数 24。
- NGonElements: offset 长 19 → 18 个面，connectivity 长 54。

若读取器依赖 `offset[last] == len(connectivity)`，需确保与 ElementConnectivity 长度一致，否则可能越界。建议在写入/读取时增加一致性校验。

---

### 3.4 【低风险】NFACE_n 中的负数 (本文件未见)

在部分 ANSA 导出中，NFACE_n 的 ElementConnectivity 会用负的 face ID 表示法向。本示例中 ansa 无负值，ngons 同样无负值。但若其他 ansa 文件中出现负值，而读取器假设非负索引，可能产生索引错误。建议读取器对 NFACE_n 正确处理符号。

---

## 4. 修复建议

1. **BC 描述符**：统一为 6 字节或固定最大长度，避免按固定长度硬编码读取。  
2. **整数类型**：导出时使用 int64，或与读取器约定类型与 stride。  
3. **一致性**：导出后检查 ElementStartOffset 与 ElementConnectivity 长度一致性。  
4. **PointList**：若存在 shape (n,) 的 PointList，建议转换为 (n,1)，以兼容常见读取器。

---

*报告由 compare_cgns.py 生成*
