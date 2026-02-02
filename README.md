项目文档：凡人修仙传成语统计 Agent (Fairy-Chengyu-Agent)
1. 项目愿景
构建一个基于 Blackwell 架构 (RTX 5060 Ti) 优化的自动化多智能体系统，实现从原始视频到“成语视频库”及“成语词频统计”的增量处理。

2. 技术栈规格 (Gold Standard)
计算环境: CUDA 12.8 / Python 3.11 / PyTorch 2.7.0+ (Nightly)

核心引擎:

STT: WhisperX (单词级对齐版)

Reasoning: Ollama (qwen2.5:7b)

Video: MoviePy / FFmpeg

WebUI: Gradio (多标签页架构)

状态管理: JSON / SQLite (用于增量迭代)

3. 多智能体系统架构 (Multi-Agent Architecture)
系统被划分为 4 个核心 Agent 角色，每个角色负责独立的工作流模块：

角色 A：音频调度官 (Audio-Agent)
职责: 扫描 data/raw_video 目录，检查 db.json 状态。

任务: 将新视频提取为 16000Hz 单声道 WAV。

可调参数: sample_rate, skip_existing。

角色 B：速记笔录员 (STT-Agent)
职责: 加载 WhisperX 进行 ASR。

核心能力: 使用 VAD (语音活动检测) 过滤空白，通过 align 模型获取毫秒级单词时间戳。

可调参数: model_size (tiny/base/large), batch_size, device (cuda)。

角色 C：修仙文案官 (LLM-Agent)
职责: 通过 Ollama 识别文本中的成语。

策略: Batch Prompting（每 10-20 句文本一组）以节省上下文切换开销。

核心逻辑:

判断文本是否包含成语。

修正 Whisper 可能产生的同音错别字（基于语义）。

返回结构化 JSON：{"word": "落荒而逃", "timestamp_index": 5}。

角色 D：剪辑与统计员 (Video-Stat-Agent)
职责:

根据 C 的结果，从原始视频截取片段。

持久化: 更新全局 stats_library（成语出现频次、来源集数）。

文件命名: 成语_集数_秒数.mp4。

可调参数: padding_start, padding_end, codec (h264/av1)。

4. 目录与数据流设计
数据流向：
raw_video/*.mp4 → Audio-Agent → audio_cache/*.wav

audio_cache/*.wav → STT-Agent → transcripts/*.json (包含词级时间戳)

transcripts/*.json → LLM-Agent → filtered_idioms/*.json (过滤后的成语名单)

filtered_idioms/*.json + raw_video/*.mp4 → Video-Stat-Agent → output_clips/*.mp4 & final_report.csv

5. WebUI 交互定义 (Gradio Tabs)
Tab 1: 任务面板 (Mission Control)

配置 5060 Ti 的 CUDA 参数。

一键启动/暂停流水线。

可视化进度条（当前处理到哪一集，哪一秒）。

Tab 2: 成语词云 (Statistical View)

展示 Top 20 出现频次的成语。

点击成语，直接播放对应的视频预览。

Tab 3: 调试室 (Debug Logger)

查看 Ollama 的原始推理回复。

手动修正 STT 文本错误。

6. 增量迭代逻辑 (The Incremental Logic)
系统启动时读取 metadata.db。

对比 data/raw_video 文件夹。

如果发现新文件，计算其哈希值（MD5）。

只将新哈希对应的文件加入待处理队列。

若中间步骤失败，保留已生成的 .wav 或 .json，下次从中断环节启动。

7. 已实现模块说明
- [db_manager.py](db_manager.py): 基于 SQLite 的状态管理中心，支持文件 MD5 哈希校验，实现增量处理逻辑。
- [audio_extractor.py](audio_extractor.py): 音频提取 Agent，利用 MoviePy 将视频转换为 16000Hz 单声道 WAV。
- [stt_engine.py](stt_engine.py): STT Agent，集成 WhisperX 实现单词级时间戳对齐，适配 CUDA 加速。
- [llm_processor.py](llm_processor.py): LLM Agent，通过 Ollama (qwen2.5:7b) 进行成语提取与语义纠错。
- [video_processor.py](video_processor.py): 视频剪辑 Agent，自动根据成语时间戳截取片段并重命名。
- [pipeline.py](pipeline.py): 核心流水线控制器，协调各 Agent 顺序执行。
- [app.py](app.py): 基于 Gradio 的 WebUI 交互界面，包含任务控制、统计展示与日志调试。

8. 使用指南
1. 环境激活：`conda activate frxxz-idiom-extractor`
2. 启动服务：`python app.py`
3. 访问 WebUI：浏览器打开 `http://127.0.0.1:7860`
4. 数据准备：将原始视频放入 `data/raw_video` 目录。
5. 点击“启动自动化流水线”开始处理。

9. 后续优化建议
- **并发处理**: 在 STT 和 LLM 阶段引入多线程或异步处理以进一步提升 5060 Ti 的利用率。
- **UI 增强**: 在 Tab 2 增加成语词云的可视化展示。
- **错误纠偏**: 允许在 Tab 3 手动修正 LLM 的识别结果并反馈给统计库。