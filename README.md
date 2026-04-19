# ⚡ 智行新能源车服 AI 管家 (Smart EV Service AI Assistant)

这是一个基于大语言模型 (LLM) 和 RAG (检索增强生成) 技术打造的新能源汽车智能管家应用。本项目通过 LangChain 搭建的 ReAct 架构，让 AI 能够按照一定的思考逻辑链（发现问题 -> 寻找工具 -> 查询数据 -> 综合解答）自主调用外部查询工具。它无缝融合了真实的车辆运行遥测数据与详尽的新能源知识库，能在售前或售后场景中为车主提供高度定制化的交互体验。

---

## 🌟 核心与技术亮点

*   **Agent 智能分发**：AI可以通过上下文自主判别什么时候该使用计算工具，什么时候该调取后台数据库查车辆 SOH（健康度）损耗，什么时候该去挂载最新的天气数据。
*   **垂直领域 RAG 知识检索**：在 `data/` 目录中下沉了专门针对新能源汽车的语料（涵盖《极寒炎热天气电池保养指南》、《高压系统故障盲操排查手册》）。借由 Chroma 向量数据库进行高维检索。
*   **车况数据沙盘模拟引擎**：后台开发了基于 `csv` 构建的沙盒运行数据处理链，涵盖了不同测试车编队 (如 VIN1001-1010) 动态衰减和能耗变化特征模拟。

---

## 🏗️ 架构概览

*   **AI 调度中枢**：`LangChain` 框架级支持应用。
*   **执行思维轴**：大模型基座搭配 `ReAct (Reason and Act)` Prompt 配置。
*   **向量记忆节点**：`ChromaDB`，配合 `MD5` 哈希特征对比的增量更新机制，只对发生变化的数据源文件做重新 Chunk 与 Embedding 动作，大幅节约本地化算力。
*   **高性能后端接口**：放弃同步阻塞型服务，依托 `FastAPI` 和 `Uvicorn` 构筑纯异步非阻塞的后台大流量流式 (`StreamingResponse`) 输出。
*   **无状态前端展现**：原生原生栈构筑，内置智能 DOM 记忆切片处理（侧边栏自由无缝切换不同账户 VIN 数据并自动重绘界面渲染），彻底做到轻量、可扩展。

---

## 🚀 功能展示
<img width="1779" height="1023" alt="image" src="https://github.com/user-attachments/assets/5b5ad3cd-391f-49c4-9f4d-bcd3d222be39" />
<img width="1781" height="1024" alt="image" src="https://github.com/user-attachments/assets/268f4735-a931-4d6d-ad3e-8e1fc03893dc" />
<img width="1788" height="1017" alt="image" src="https://github.com/user-attachments/assets/ad6f0642-06b1-4180-b32d-12b726e9c10f" />


---

## 🛠️ 本地部署与运行

开发此项目时使用的是 Python 3.10+ 环境。克隆到本地后的运行极其简单：

```bash
# 1. 命令行进入项目根目录
cd Agent项目

# 2. 激活环境
conda activate Rag

# 3. 驱动服务
# 我们采用 uvicorn 作为 ASGI 服务器进行带有热重载的启动
uvicorn api:app --reload
```
最后，浏览器中打开 `http://127.0.0.1:8000` 

---


