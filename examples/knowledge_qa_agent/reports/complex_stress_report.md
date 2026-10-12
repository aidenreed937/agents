# 复杂工业压力场景（多规程多跳/计算映射/强干扰）评估报告

> **评估时间**: 2026-10-08 18:01:52  
> **基座模型**: `Qwen/Qwen3-30B-A3B-Instruct-2507` (架构: 30.5B MoE, 3.3B 激活)  
> **综合通过率**: **6/6 (100.0%)**

---
## 一、 复杂场景用例实测全景

| 用例 ID | 挑战类型 | 问题摘要 | 状态 | 耗时 | 命中依据 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `stress_multihop_01` | **跨规程多跳联合推断** | 现场测得3号主变油色谱总烃达 220 uL/L，同时20... | **PASS** | 58.96s | `[Doc N]` 引用: 2 篇 |
| `stress_negative_01` | **主变 vs PT 强干扰对比** | 请对比 330kV 主变压器与 330kV 电压互感器 ... | **PASS** | 11.17s | `[Doc N]` 引用: 2 篇 |
| `stress_calculation_01` | **数值换算与改良三比值编码** | 某主变特征气体实测值为：C2H2=10 uL/L, C2... | **PASS** | 28.03s | `[Doc N]` 引用: 3 篇 |
| `stress_version_01` | **新旧规程废止冲突仲裁** | 现行 DL/T 596 规程中对 220kV 变压器绕组... | **PASS** | 8.26s | `[Doc N]` 引用: 2 篇 |
| `stress_negative_02` | **CT 互感器抗张冠李戴** | 电流互感器 (CT) 的总烃和乙炔注意值基线分别是多少？... | **PASS** | 8.90s | `[Doc N]` 引用: 2 篇 |
| `stress_multihop_02` | **色谱放电与击穿电压两规程确诊** | 330kV主变油色谱检出乙炔 C2H2 为 8.0 uL... | **PASS** | 21.25s | `[Doc N]` 引用: 1 篇 |

---
## 二、 复杂场景各用例推断与回答剖析

### 用例 `stress_multihop_01`：跨规程多跳联合推断
- **提问**: 现场测得3号主变油色谱总烃达 220 uL/L，同时20℃下绝缘电阻吸收比为 1.15，绕组介损 tanδ 达 1.6%。请结合 DL/T 722 与 DL/T 596 规程，综合研判设备内部存在何种复合隐患，并给出处置建议。
- **判定**: **PASS** (耗时: 58.96s)
- **模型回答**:

> 根据提供的实时诊断数据与静态规程文件，现对3号主变（T2-500KV-MAIN）的运行状态进行综合研判：
> 
> 1. **油色谱分析结果**：  
>    - 总烃（THC）达 384.9 μL/L，远超严重注意值 150 μL/L [Doc 1]；  
>    - 乙炔（C2H2）浓度为 28.6 μL/L，显著高于 5 μL/L 的放电故障阈值 [Doc 1]；  
>    - IEC 三比值编码为 1,0,2，对应高能电弧放电特征 [Doc 1]。
> 
> 2. **瓦斯继电器动作情况**：  
>    - 轻瓦斯继电器接点闭合，集气盒内积聚 45mL 可燃游离气体，且气体检测呈阳性（可燃）[Doc 2]；  
>    - 该现象与油中高浓度乙炔及总烃一致，表明内部存在持续性放电或电弧活动 [Doc 2]。
> 
> 3. **电气绝缘试验结果**：  
>    - 吸收比 $R_{60}/R_{15} = 1.15 < 1.3$，低于规程要求的最低限值 [Doc 1]；  
>    - 绕组介损 $\tan\delta = 1.6\% > 1.5\%$，超出正常范围 [Doc 1]。
> 
> 4. **综合诊断结论**：  
>    - 油色谱显示乙炔与总烃急剧上升，且 IEC 三比值为 1,0,2，明确指示存在**高能电弧放电** [Doc 1]；  
>    - 同时，吸收比低于 1.3 且介损超过 1.5%，符合“绝缘纸严重受潮伴随局部过热”的复合隐患判据 [Doc 1]；  
>    - 轻瓦斯报警与可燃气体积聚进一步佐证内部存在持续性放电故障，且可能已导致绝缘油劣化 [Doc 2]。
> 
> ✅ **确诊根因**：设备内部存在**高能电弧放电与绝缘纸严重受潮的复合型隐患**，二者相互加剧，击穿风险极高 [Doc 1]。
> 
> ❌ **已排除项**：  
> - 顶层油温 68.5℃，绕组热点温升正常，冷却系统运行正常，排除大范围过热或冷却异常导致的热故障 [Doc 3]。
> 
> 📌 **处置建议**：  
> 1. 立即申请紧急停运调度，禁止带电运行 [Doc 1]；  
> 2. 在生产管理系统提交【紧急设备缺陷单】，路径：`/pms/equipment/defect-report`（CLI: `pms-cli defect submit --device T2-500KV-MAIN --level CRITICAL`）[Doc 2]；  
> 3. 启动绝缘油真空脱气处理流程，并安排吊罩检修，对线圈及绝缘结构进行彻底检查 [Doc 2]；  
> 4. 取瓦斯继电器内气体与本体油样进行全分析，确认放电类型与绝缘劣化程度 [Doc 2]。
> 
> 【操作建议与快捷入口】  
> - 提交缺陷单：`pms-cli defect submit --device T2-500KV-MAIN --level CRITICAL`  
> - 实时数据查看：`scada-cli telemetry fetch --device T2-500KV-MAIN --sensor buchholz`  
> - 紧急调度入口：控制台 /pms/equipment/emergency-dispatch [Doc 2]
> 
> ---
> **快捷操作与一键处置入口：**
> - 控制台直达: [/scada/monitoring/dga-realtime](https://console.example.com/scada/monitoring/dga-realtime) (需权限: Dispatcher:Viewer) | CLI: `scada-cli telemetry fetch --device T2-500KV-MAIN --sensor buchholz`
> - 控制台直达: [/pms/equipment/defect-report](https://console.example.com/pms/equipment/defect-report) (需权限: Equipment:Operator) | CLI: `pms-cli defect submit --device T2-500KV-MAIN --level CRITICAL`
> - 控制台直达: [/pms/equipment/emergency-dispatch](https://console.example.com/pms/equipment/emergency-dispatch) (需权限: Safety:Admin)

### 用例 `stress_negative_01`：主变 vs PT 强干扰对比
- **提问**: 请对比 330kV 主变压器与 330kV 电压互感器 (PT) 在总烃注意值基线上的区别，互感器总烃多少算超标？
- **判定**: **PASS** (耗时: 11.17s)
- **模型回答**:

> 330kV 主变压器与 330kV 电压互感器 (PT) 在总烃 (THC) 注意值基线上存在显著差异：
> 
> - **330kV 主变压器**的总烃注意值为 **150 μL/L** [Doc 2]；
> - **330kV 电压互感器 (PT)** 的总烃注意值为 **10 μL/L** [Doc 1]。
> 
> 因此，当 330kV 电压互感器油中总烃含量超过 **10 μL/L** 时，即视为超标 [Doc 1]。
> 
> 特别提醒：严禁将主变压器的总烃注意值（150 μL/L）套用于互感器，因设备结构与储油量差异导致气体生成与扩散特性不同，必须按互感器专用标准执行 [Doc 1]。
> 
> 【操作建议与快捷入口】  
> - 查看互感器气体分析数据：控制台 /pms/equipment/instrument-transformer [权限: pms:equipment:view]  
> - 查阅标准注意值基线：控制台 /pms/standard/attention-limits [权限: Equipment:Admin]
> 
> ---
> **快捷操作与一键处置入口：**
> - 控制台直达: [/pms/standard/attention-limits](https://console.example.com/pms/standard/attention-limits) (需权限: Equipment:Admin)

### 用例 `stress_calculation_01`：数值换算与改良三比值编码
- **提问**: 某主变特征气体实测值为：C2H2=10 uL/L, C2H4=100 uL/L, CH4=200 uL/L, H2=100 uL/L, C2H6=20 uL/L。请计算三项特征气体比值，推算改良三比值编码组合，并查表判定故障类型。
- **判定**: **PASS** (耗时: 28.03s)
- **模型回答**:

> 根据提供的实测气体浓度数据，进行改良三比值法计算与故障类型判定，步骤如下：
> 
> ---
> 
> ### 1. **计算三项特征气体比值**
> 
> - **比值一：C₂H₂ / C₂H₄**  
>   $$
>   \frac{10}{100} = 0.1 \Rightarrow \text{编码为 } 0 \quad \text{（因 0.1 < 0.1，按标准取 0）} [Doc 1]
>   $$
> 
> - **比值二：CH₄ / H₂**  
>   $$
>   \frac{200}{100} = 2.0 \Rightarrow \text{编码为 } 2 \quad \text{（因 1.0 ≤ 2.0 < 3.0，编码为 2）} [Doc 1]
>   $$
> 
> - **比值三：C₂H₄ / C₂H₆**  
>   $$
>   \frac{100}{20} = 5.0 \Rightarrow \text{编码为 } 2 \quad \text{（因 3.0 ≤ 5.0，编码为 2）} [Doc 1]
>   $$
> 
> ---
> 
> ### 2. **确定改良三比值编码组合**
> 
> 三项比值编码分别为：  
> - 比值一：0  
> - 比值二：2  
> - 比值三：2  
> 
> 因此，**编码组合为 (0, 2, 2)** [Doc 1]
> 
> ---
> 
> ### 3. **查表判定故障类型**
> 
> 根据《变压器油中溶解气体分析和判断导则 (DL/T 722)》中“改良三比值法故障类型判断编码表” [Doc 1]：
> 
> > **编码组合 (0, 2, 2)** 对应的故障类型为：**高温过热 (高于 700℃)**  
> > 典型故障现象举例：铁心严重短路、匝间局部过热、穿心螺栓绝缘烧毁。
> 
> ---
> 
> ### 4. **结论与溯源**
> 
> - 乙炔 (C₂H₂) 浓度为 10 μL/L，虽未达到严重超注意值（1.0 μL/L）的阈值，但结合其与乙烯的比值（0.1）及整体三比值编码 (0, 2, 2)，可确认为高温过热故障 [Doc 1]。
> - 该故障类型与乙炔生成机制一致：**乙炔主要在 800℃~1200℃ 极高温度电弧或过热条件下形成**，是高温过热的典型特征气体 [Doc 3]。
> - 尽管当前 C₂H₂ 浓度未达严重超标，但结合三比值法判断，仍属高温过热，需立即关注设备内部是否存在严重局部过热或短路隐患。
> 
> ---
> 
> ### ✅ 最终结论：
> 
> - **改良三比值编码组合为 (0, 2, 2)**  
> - **故障类型判定为：高温过热（高于 700℃）** [Doc 1]  
> - **建议排查方向：铁心严重短路、匝间局部过热、穿心螺栓绝缘烧毁等** [Doc 1]
> 
> ---
> 
> ### 【操作建议与快捷入口】
> 
> - 提交缺陷报告：`pms-cli defect submit --device T2-500KV-MAIN --level CRITICAL`  
> - 查看实时油色谱数据：`scada-cli telemetry fetch --device T2-500KV-MAIN --sensor dga-realtime`  
> - 控制台路径：/pms/equipment/defect-report [Doc 1] /scada/monitoring/dga-realtime [Doc 3]
> 
> ---
> **快捷操作与一键处置入口：**
> - 控制台直达: [/scada/monitoring/dga-realtime](https://console.example.com/scada/monitoring/dga-realtime) (需权限: Dispatcher:Viewer) | CLI: `scada-cli telemetry fetch --device T2-500KV-MAIN --sensor buchholz`
> - 控制台直达: [/pms/equipment/defect-report](https://console.example.com/pms/equipment/defect-report) (需权限: Equipment:Operator) | CLI: `pms-cli defect submit --device T2-500KV-MAIN --level CRITICAL`
> - 控制台直达: [/scada/monitoring/dga-parameters](https://console.example.com/scada/monitoring/dga-parameters) (需权限: Maintenance:Viewer)

### 用例 `stress_version_01`：新旧规程废止冲突仲裁
- **提问**: 现行 DL/T 596 规程中对 220kV 变压器绕组介质损耗因数 tanδ 的合格标准是多少？历史旧版曾允许的 1.5% 目前是否依然有效？
- **判定**: **PASS** (耗时: 8.26s)
- **模型回答**:

> 现行 DL/T 596 规程中对 220kV 变压器绕组介质损耗因数 $\tan\delta$ 的合格标准为：在 20℃ 环境下，$\tan\delta \le 1.0\%$ [Doc 2]。该标准为强制性指标，凡涉及绝缘合格性裁决，必须以现行版最新指标为准 [Doc 1]。
> 
> 历史旧版（1996 年版）曾允许 220kV 变压器 $\tan\delta$ 放宽至 1.5%，但该放宽条款已被现行有效版本明确废止 [Doc 1]。因此，目前 1.5% 的标准已不再有效，不得作为合格判据使用 [Doc 1]。
> 
> 【操作建议与快捷入口】  
> - 查阅最新试验报告与标准版本：[控制台 /pms/standard/version-archive | 权限: pms:standard:view]  
> - 提交或查询绝缘试验报告：[控制台 /pms/insulation/test-report | 权限: pms:test:execute]

### 用例 `stress_negative_02`：CT 互感器抗张冠李戴
- **提问**: 电流互感器 (CT) 的总烃和乙炔注意值基线分别是多少？能否套用主变压器的 150 uL/L 标准？
- **判定**: **PASS** (耗时: 8.90s)
- **模型回答**:

> 根据提供的静态知识文档：
> 
> 电流互感器 (CT) 的总烃注意值基线为 **100 μL/L**，乙炔注意值为 **1 μL/L** [Doc 2]。
> 
> **不能套用主变压器的 150 μL/L 标准**。主变压器（330kV 及以上）的总烃注意值虽为 150 μL/L，但该标准**不适用于电流互感器**。不同设备因结构与运行特性差异，其气体注意值存在显著区别，**严禁将主变压器标准套用于互感器** [Doc 1]。
> 
> 【操作建议与快捷入口】  
> - 查阅完整注意值基线：控制台 /pms/standard/attention-limits [权限: Equipment:Admin]  
> - 提交缺陷报告（如发现异常）：CLI 命令 `pms-cli defect submit --device T2-500KV-MAIN --level CRITICAL`
> 
> ---
> **快捷操作与一键处置入口：**
> - 控制台直达: [/scada/monitoring/dga-realtime](https://console.example.com/scada/monitoring/dga-realtime) (需权限: Dispatcher:Viewer) | CLI: `scada-cli telemetry fetch --device T2-500KV-MAIN --sensor buchholz`
> - 控制台直达: [/pms/equipment/defect-report](https://console.example.com/pms/equipment/defect-report) (需权限: Equipment:Operator) | CLI: `pms-cli defect submit --device T2-500KV-MAIN --level CRITICAL`
> - 控制台直达: [/pms/standard/attention-limits](https://console.example.com/pms/standard/attention-limits) (需权限: Equipment:Admin)

### 用例 `stress_multihop_02`：色谱放电与击穿电压两规程确诊
- **提问**: 330kV主变油色谱检出乙炔 C2H2 为 8.0 uL/L，绝缘油击穿电压降至 36 kV。请结合色谱与绝缘油试验指标判断故障性质与调度决策。
- **判定**: **PASS** (耗时: 21.25s)
- **模型回答**:

> 根据提供的实时诊断数据与静态知识库内容，现对问题进行交叉分析与判定：
> 
> 1. **乙炔（C₂H₂）含量分析**：  
>    实时诊断中显示乙炔（C₂H₂）浓度为 28.6 μL/L，远超注意值 1.0 μL/L，且已进入严重超标范围（>5 μL/L）[probe 1]。根据《电力设备预防性试验规程 (DL/T 596)》中关于“放电故障与绝缘油劣化复合判据”的规定，当色谱中乙炔（C₂H₂）超标（>5 μL/L）时，即提示存在持续性放电活动，破坏绝缘油介电强度 [Doc 1]。
> 
> 2. **绝缘油击穿电压分析**：  
>    问题中明确指出绝缘油击穿电压已降至 36 kV，低于规程中规定的 40 kV 临界值 [Doc 1]。结合乙炔超标现象，构成“放电故障与绝缘油劣化复合判据”的完整证据链。
> 
> 3. **综合诊断结论**：  
>    乙炔（C₂H₂）浓度 28.6 μL/L（远高于 5 μL/L）与击穿电压 36 kV（低于 40 kV）同时满足《DL/T 596》中“放电故障与绝缘油劣化复合判据”的全部条件，可确诊为**持续性高能放电故障**，且已导致绝缘油介电性能显著劣化，存在击穿风险 [Doc 1]。
> 
> 4. **排除其他可能性**：  
>    - 顶层油温 68.5℃，绕组热点温升正常，无明显过热迹象，排除局部过热或绝缘纸受潮导致的复合隐患（该类故障需配合吸收比 <1.3 与介损 >1.5%）[probe 3]；
>    - 轻瓦斯继电器已动作，集气盒内积聚 45mL 可燃气体，且气体测试呈阳性，进一步佐证内部存在持续放电产气过程，与乙炔异常一致 [probe 2]。
> 
> 5. **调度决策建议**：  
>    根据规程要求，存在持续放电且绝缘油击穿电压低于 40 kV，必须立即申请紧急停运调度，防止故障扩大引发绝缘击穿或爆炸事故 [Doc 1]。
> 
> 【操作建议与快捷入口】  
> - 紧急停运申请：`pms-cli defect submit --device T2-500KV-MAIN --level CRITICAL`  
> - 实时数据监控：`scada-cli telemetry fetch --device T2-500KV-MAIN --sensor buchholz`  
> - 预防性试验调度入口：[控制台 /pms/preventive/oil-filter-dispatch] [Doc 1]  
> 
> **最终结论**：该主变存在持续性高能放电故障，绝缘油劣化严重，必须立即申请紧急停运 [Doc 1]。
> 
> ---
> **快捷操作与一键处置入口：**
> - 控制台直达: [/scada/monitoring/dga-realtime](https://console.example.com/scada/monitoring/dga-realtime) (需权限: Dispatcher:Viewer) | CLI: `scada-cli telemetry fetch --device T2-500KV-MAIN --sensor buchholz`
> - 控制台直达: [/pms/equipment/defect-report](https://console.example.com/pms/equipment/defect-report) (需权限: Equipment:Operator) | CLI: `pms-cli defect submit --device T2-500KV-MAIN --level CRITICAL`
