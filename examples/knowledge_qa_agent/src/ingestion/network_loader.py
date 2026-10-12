"""垂直行业数据网络拉取与工业规程清洗加载器 (Network Ingestion & Industrial Standard Loader)

特性：
1. 支持从公网权威标准库、技术 Wiki 或企业知识中心 HTTP(S) URL 拉取非标页面；
2. 结合 Trafilatura / 内置 DOM 清洗器剥离 HTML 噪音并提取结构化正文；
3. 内建传统电力能源工业权威标准《DL/T 722 变压器油中溶解气体分析和判断导则》真实数据源；
4. 自动标注企业级生产管理系统 (PMS2.0) 与 变电 SCADA 在线遥测路径元数据。
"""
import os
import re
import urllib.request
import urllib.error
from typing import Optional, Dict, Any
from .parser import UniversalDocumentParser, HTMLTrafilaturaParserAdapter


DLT722_STANDARD_CONTENT = """---
title: 电力行业标准 DL/T 722 变压器油中溶解气体分析和判断导则
category: industrial_power_equipment
domain: 能源电力与特种装备运维
version: DL/T 722-2014 / 2020-Rev
---

# 变压器油中溶解气体分析和判断导则 (DL/T 722)

## 1. 范围与应用对象
本导则推荐了利用气相色谱法分析溶解气体和游离气体的浓度，以判断充油电气设备运行状况及建议应进一步采取的措施。
本导则适用于充有矿物绝缘油和以纸或层压纸板为主要绝缘材料的电气设备，其中包括电力变压器、电抗器、电流互感器、电压互感器和充油套管。
控制台路径: /pms/equipment/transformer-ledger
权限要求: Equipment:Viewer

## 2. 术语与特征气体定义
在变压器油中溶解气体分析中，以下定义为核心判断指标：
- **特征气体 (Characteristic Gases)**：对判断充油电气设备内部故障有价值的气体，包括氢气 (H2)、甲烷 (CH4)、乙烷 (C2H6)、乙烯 (C2H4)、乙炔 (C2H2)、一氧化碳 (CO) 和 二氧化碳 (CO2)。
- **总烃 (Total Hydrocarbons, THC)**：烃类气体含量的总和，即甲烷 (CH4)、乙烷 (C2H6)、乙烯 (C2H4) 和乙炔 (C2H2) 四种气体浓度的代数和。在统计计算总烃时，不计入丙烷、丙烯等 C3 组分。
- **游离气体 (Free Gases)**：从绝缘油中析出并积聚在气体继电器（瓦斯继电器）储气室或设备顶部的气体。
控制台路径: /scada/monitoring/dga-parameters
权限要求: Maintenance:Viewer

## 3. 产气机理与特征气体产生规律
电气设备内部的电故障或热故障会导致变压器油和固体绝缘材料（绝缘纸）裂解产生特征气体：
1. **绝缘油过热 (Oil Overheating)**：主要产生甲烷 (CH4) 和乙烯 (C2H4)，次要气体为氢气 (H2) 和乙烷 (C2H6)。随着过热温度升高，乙烯占比显著增大。通常在 500℃ 以上时乙烯成为最主要特征气体。
2. **固体绝缘 (油和纸) 过热**：在产生甲烷和乙烯的同时，产生大量一氧化碳 (CO) 和二氧化碳 (CO2)。通常 CO/CO2 比例大于 0.33 或 CO 绝对浓度明显升高是纸绝缘劣化的典型征兆。
3. **低能量局部放电 (Partial Discharge)**：主要产生氢气 (H2)，其次为甲烷 (CH4)，乙炔 (C2H2) 含量极微或低于检知极限。这是因为 C-H 键在低能电子撞击下最先断裂重新化合为 H2。
4. **火花放电与高能电弧放电 (Arcing & Sparking)**：主要特征气体为乙炔 (C2H2) 和氢气 (H2)，并伴有乙烯 (C2H4)。乙炔是在 800℃~1200℃ 极高温度电弧电离下形成的稳定化合产物。**油中检测出明显浓度的乙炔 (C2H2) 是内部存在高能放电或电弧的特征判据**。
控制台路径: /scada/monitoring/dga-realtime
权限要求: Dispatcher:Viewer

## 4. 充油电气设备运行注意值基线 (Attention Values)
当油中溶解气体含量超过下列注意值时，应引起注意，缩短跟踪检测周期并结合产气速率进行深入确诊：

| 设备类型 | 电压等级与容量 | 总烃 (THC) 注意值 | 氢气 (H2) 注意值 | 乙炔 (C2H2) 注意值 |
| :--- | :--- | :--- | :--- | :--- |
| **变压器与电抗器** | 330kV 及以上 | **150 μL/L** | **150 μL/L** | **1 μL/L** |
| **变压器与电抗器** | 220kV 及以下 | **150 μL/L** | **150 μL/L** | **5 μL/L** |
| **充油电流互感器** | 66kV ~ 500kV | **100 μL/L** | **150 μL/L** | **1 μL/L** |
| **电容型套管** | 110kV 及以上 | **10 μL/L** | **150 μL/L** | **2 μL/L** |

注：新投运或大修后的 330kV 及以上变压器，在投入运行前总烃注意值不得大于 10 μL/L，氢气不得大于 10 μL/L，乙炔不得检出 (0 μL/L)。
控制台路径: /pms/standard/attention-limits
权限要求: Equipment:Admin

## 5. 改良三比值法故障类型判断编码表
当变压器油中气体超过注意值且确认存在产气时，采用 IEC 改良三比值法进行故障诊断：
- 比值一：`C2H2 / C2H4`（乙炔 / 乙烯）
- 比值二：`CH4 / H2`（甲烷 / 氢气）
- 比值三：`C2H4 / C2H6`（乙烯 / 乙烷）

| 编码组合 (比值一, 比值二, 比值三) | 典型故障类型 | 典型故障现象举例与检查建议 |
| :--- | :--- | :--- |
| **0, 0, 1** | **低温过热 (低于 150℃)** | 导线连接绝缘包扎不良、分接开关接触不良、铁心环流轻微发热 |
| **0, 2, 0** | **低温过热 (150℃ ~ 300℃)** | 铁心多点接地、屏蔽接触不良、磁屏蔽过热 |
| **0, 2, 1** | **中温过热 (300℃ ~ 700℃)** | 分接开关接触电阻过大、引线接头焊接不良、短路环开路 |
| **0, 2, 2** | **高温过热 (高于 700℃)** | 铁心严重短路、匝间局部过热、穿心螺栓绝缘烧毁 |
| **1, 0, 1** | **低能放电 (火花放电/局部放电)** | 悬浮电位放电、绝缘纸内部空洞气泡放电、受潮放电 |
| **1, 0, 2 或 2, 0, 2** | **高能电弧放电 (电弧放电)** | 线圈匝间短路击穿、引线对地电弧闪络、分接开关绝缘击穿 |

控制台路径: /pms/equipment/defect-report
权限要求: Equipment:Operator

## 6. 瓦斯继电器动作与现场应急处置规程
当变压器轻瓦斯或重瓦斯继电器发出报警或跳闸动作时：
1. **轻瓦斯动作（信号报警）**：应立即通过放气嘴取气样，同时取本体油样进行色谱分析；若气体可燃且色谱分析总烃及乙炔超标，必须立即申请停电排查。
2. **重瓦斯动作（跳闸断电）**：禁止强送电！必须取瓦斯继电器内游离气体和油样进行全分析，测定绝缘电阻与直流电阻，查明原因并彻底消除缺陷后方可投入运行。
3. 发现电弧放电或乙炔急速上升时，运维人员需立即在生产管理系统提交【紧急设备缺陷单】，并启动绝缘油真空脱气与线圈吊罩检查流程。
控制台路径: /pms/equipment/emergency-dispatch
权限要求: Safety:Admin
"""


class IndustrialNetworkLoader:
    """传统行业规程网络拉取与标准数据集加载器"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    def fetch_url(self, url: str, timeout: int = 10) -> Optional[str]:
        """从指定公网 URL 拉取网页 HTML/Markdown 内容"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) IndustrialKnowledgeBot/1.0"
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                content = response.read().decode(charset, errors="ignore")
                return content
        except Exception as e:
            print(f"[IndustrialNetworkLoader] 网络拉取失败 ({url}): {e}")
            return None

    def ingest_url_to_markdown(self, url: str, target_filename: str) -> str:
        """从网络 URL 拉取，清洗正文并落盘为标准技术规程 Markdown"""
        target_path = os.path.join(self.data_dir, target_filename)
        html_content = self.fetch_url(url)
        if html_content:
            # 优先调用 trafilatura 或内置清洗器
            parser = HTMLTrafilaturaParserAdapter()
            sections = parser._parse_with_builtin_cleaner(html_content, url)
            md_lines = [f"# 从网络权威源拉取: {url}\n"]
            for sec in sections:
                if sec["heading"]:
                    md_lines.append(f"{'#' * max(sec['level'], 1)} {sec['heading']}")
                if sec["content"]:
                    md_lines.append(sec["content"] + "\n")
            with open(target_path, "w", encoding="utf-8") as f:
                f.write("\n\n".join(md_lines))
            print(f"-> 成功从网络抓取并清洗规程保存至: {target_path}")
            return target_path
        else:
            print("-> 网络连接受限或源不可达，自动回退使用权威标准镜像规程。")
            return self.load_default_industrial_standard(target_filename)

    def load_default_industrial_standard(self, filename: str = "industrial_transformer_dlt722.md") -> str:
        """加载或生成标准的《DL/T 722 变压器油中溶解气体分析和判断导则》Markdown 规范"""
        target_path = os.path.join(self.data_dir, filename)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(DLT722_STANDARD_CONTENT.strip())
        print(f"-> 成功就绪电力工业设备标准规程文件: {target_path}")
        return target_path
