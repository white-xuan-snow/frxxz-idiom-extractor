import os
import logging
from db_manager import DBManager
from audio_extractor import AudioExtractor
from stt_engine import STTEngine
from llm_processor import LLMProcessor
from video_processor import VideoProcessor

class Pipeline:
    """
    任务面板 (Mission Control): 一键启动/暂停流水线
    协调各个 Agent 完成增量处理
    """
    def __init__(self):
        self.logger = logging.getLogger("Pipeline")
        self.db = DBManager()
        self.audio_agent = AudioExtractor()
        self.stt_agent = STTEngine(model_size="base") # 默认 base 兼顾速度与精度
        self.llm_agent = LLMProcessor()
        self.video_agent = VideoProcessor()

    def run_full_pipeline(self, raw_video_dir="data/raw_video"):
        """运行完整增量流水线"""
        self.logger.info("=== 启动自动化流水线 ===")
        
        # 1. 扫描新视频
        self.db.sync_folder(raw_video_dir)
        
        # 2. 获取待处理列表
        # 这里简化处理：依次处理 pending, audio_extracted, stt_done 等状态
        self._process_step_audio()
        self._process_step_stt()
        self._process_step_llm()
        self._process_step_video()
        
        self.logger.info("=== 流水线任务结束 ===")

    def _process_step_audio(self):
        videos = self.db.get_videos_by_status('pending')
        for video in videos:
            path = video['file_path']
            audio_path = self.audio_agent.extract(path)
            if audio_path:
                self.db.update_video_status(path, 'audio_extracted', audio_path=audio_path)

    def _process_step_stt(self):
        videos = self.db.get_videos_by_status('audio_extracted')
        for video in videos:
            path = video['file_path']
            audio_path = video['audio_path']
            try:
                result = self.stt_agent.transcribe(audio_path)
                transcript_path = os.path.join("transcripts", f"{os.path.basename(audio_path)}.json")
                self.stt_agent.save_results(result, transcript_path)
                self.db.update_video_status(path, 'stt_done', transcript_path=transcript_path)
            except Exception as e:
                self.logger.error(f"STT 步骤失败: {str(e)}")

    def _process_step_llm(self):
        videos = self.db.get_videos_by_status('stt_done')
        for video in videos:
            path = video['file_path']
            transcript_path = video['transcript_path']
            try:
                import json
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                idioms = self.llm_agent.process_segments(data['segments'])
                idioms_path = os.path.join("filtered_idioms", f"{os.path.basename(path)}.json")
                self.llm_agent.save_idioms(idioms, idioms_path)
                self.db.update_video_status(path, 'llm_done', idioms_path=idioms_path)
            except Exception as e:
                self.logger.error(f"LLM 步骤失败: {str(e)}")

    def _process_step_video(self):
        videos = self.db.get_videos_by_status('llm_done')
        for video in videos:
            path = video['file_path']
            idioms_path = video['idioms_path']
            try:
                import json
                with open(idioms_path, 'r', encoding='utf-8') as f:
                    idioms = json.load(f)
                
                self.video_agent.process_idioms(path, idioms)
                
                # 记录到统计表
                for idiom in idioms:
                    if 'clip_path' in idiom:
                        self.db.add_idiom_record(
                            word=idiom['word'],
                            source_video=path,
                            start=idiom['start'],
                            end=idiom['end'],
                            clip_path=idiom['clip_path']
                        )
                
                self.db.update_video_status(path, 'completed')
            except Exception as e:
                self.logger.error(f"Video 步骤失败: {str(e)}")

if __name__ == "__main__":
    # logging.basicConfig(level=logging.INFO)
    # pipeline = Pipeline()
    # pipeline.run_full_pipeline()
    print("Pipeline module loaded.")
