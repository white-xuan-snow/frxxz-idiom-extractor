import gradio as gr
import os
import logging
import pandas as pd
import torch
import functools
from pipeline import Pipeline
from db_manager import DBManager

# 全局修复 PyTorch 2.6+ 权重加载限制
_original_torch_load = torch.load
@functools.wraps(_original_torch_load)
def _patched_torch_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load

# 配置全局日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WebUI")

class IdiomApp:
    def __init__(self):
        self.pipeline = Pipeline()
        self.db = self.pipeline.db
        self.raw_video_dir = "data/raw_video"

    def start_pipeline(self):
        logger.info("用户点击启动流水线")
        self.pipeline.run_full_pipeline(self.raw_video_dir)
        return "流水线任务执行完毕！请检查输出目录。"

    def get_stats(self):
        stats = self.db.get_idiom_stats()
        if not stats:
            return pd.DataFrame(columns=["成语", "出现频次"])
        return pd.DataFrame(stats, columns=["成语", "出现频次"])

    def get_idiom_clips(self, word):
        """获取某个成语的所有片段路径"""
        try:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT clip_path FROM idioms_stats WHERE word = %s", (word,))
                rows = cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"查询片段失败: {str(e)}")
            return []

    def build_ui(self):
        with gr.Blocks(title="凡人修仙传成语统计 Agent", theme=gr.themes.Soft()) as demo:
            gr.Markdown("# 凡人修仙传成语统计 Agent (RTX 5060 Ti Optimized)")
            
            with gr.Tabs():
                # Tab 1: 任务面板
                with gr.TabItem("任务面板 (Mission Control)"):
                    with gr.Row():
                        with gr.Column():
                            video_dir_input = gr.Textbox(label="原始视频目录", value=self.raw_video_dir)
                            start_btn = gr.Button("🚀 启动自动化流水线", variant="primary")
                        with gr.Column():
                            status_output = gr.Textbox(label="系统状态", interactive=False)
                    
                    gr.Markdown("### 处理进度可视化")
                    progress_df = gr.DataFrame(label="视频处理状态", value=self.get_video_status_df)
                    refresh_btn = gr.Button("🔄 刷新进度")

                # Tab 2: 成语词云与统计
                with gr.TabItem("成语统计 (Statistical View)"):
                    with gr.Row():
                        with gr.Column(scale=1):
                            stats_table = gr.DataFrame(label="成语频次 Top 20", value=self.get_stats)
                            refresh_stats_btn = gr.Button("🔄 刷新统计")
                        with gr.Column(scale=2):
                            idiom_select = gr.Dropdown(label="选择成语进行预览", choices=[])
                            video_preview = gr.Video(label="成语片段预览")
                            
                    refresh_stats_btn.click(self.update_stats_view, outputs=[stats_table, idiom_select])
                    idiom_select.change(self.play_idiom_clip, inputs=[idiom_select], outputs=[video_preview])

                # Tab 3: 调试室
                with gr.TabItem("调试室 (Debug Logger)"):
                    log_output = gr.Code(label="系统日志 (system.log)", language="python", lines=20)
                    refresh_log_btn = gr.Button("🔄 读取最新日志")
                    
                    def read_logs():
                        if os.path.exists("system.log"):
                            with open("system.log", "r", encoding='utf-8') as f:
                                return f.readlines()[-50:] # 返回最后50行
                        return "暂无日志"
                    
                    refresh_log_btn.click(read_logs, outputs=[log_output])

            # 事件绑定
            start_btn.click(self.start_pipeline, outputs=[status_output])
            refresh_btn.click(self.get_video_status_df, outputs=[progress_df])

        return demo

    def get_video_status_df(self):
        try:
            with self.db._get_connection() as conn:
                df = pd.read_sql_query("SELECT file_path, status, last_updated FROM videos", conn)
                # 只取文件名显示
                df['file_path'] = df['file_path'].apply(lambda x: os.path.basename(x))
                return df
        except Exception as e:
            logger.error(f"获取视频状态失败: {str(e)}")
            return pd.DataFrame(columns=["file_path", "status", "last_updated"])

    def update_stats_view(self):
        df = self.get_stats()
        choices = df["成语"].tolist() if not df.empty else []
        return df, gr.Dropdown(choices=choices)

    def play_idiom_clip(self, word):
        clips = self.get_idiom_clips(word)
        if clips:
            return clips[0] # 播放第一个匹配的片段
        return None

if __name__ == "__main__":
    app = IdiomApp()
    demo = app.build_ui()
    demo.launch(server_name="127.0.0.1", server_port=7860)
