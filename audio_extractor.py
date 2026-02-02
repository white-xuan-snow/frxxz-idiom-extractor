import os
import logging
from moviepy import VideoFileClip
from typing import Optional

class AudioExtractor:
    """
    Audio-Agent: 视频音频提取器
    将新视频提取为 16000Hz 单声道 WAV，用于 STT 处理
    """
    def __init__(self, sample_rate: int = 16000, output_dir: str = "audio_cache"):
        self.logger = logging.getLogger("AudioExtractor")
        self.sample_rate = sample_rate
        self.output_dir = output_dir
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            self.logger.info(f"创建音频缓存目录: {self.output_dir}")

    def extract(self, video_path: str, skip_existing: bool = True) -> Optional[str]:
        """
        从视频中提取音频
        :param video_path: 原始视频路径
        :param skip_existing: 如果已存在是否跳过
        :return: 提取后的音频路径
        """
        if not os.path.exists(video_path):
            self.logger.error(f"视频文件不存在: {video_path}")
            return None

        base_name = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.abspath(os.path.join(self.output_dir, f"{base_name}.wav"))

        if skip_existing and os.path.exists(output_path):
            self.logger.info(f"音频文件已存在，跳过提取: {output_path}")
            return output_path

        try:
            self.logger.info(f"正在从视频提取音频: {os.path.basename(video_path)}")
            # 使用 MoviePy 提取音频
            video = VideoFileClip(video_path)
            
            # 确保提取为单声道 16000Hz
            # MoviePy 的 write_audiofile 会调用 ffmpeg
            video.audio.write_audiofile(
                output_path,
                fps=self.sample_rate,
                nbytes=2,
                codec='pcm_s16le',
                ffmpeg_params=["-ac", "1"], # 单声道
                logger=None # 禁用 moviepy 默认进度条，使用自定义日志
            )
            
            video.close()
            self.logger.info(f"音频提取成功: {output_path}")
            return output_path
        except Exception as e:
            self.logger.error(f"音频提取失败 {video_path}: {str(e)}")
            return None

if __name__ == "__main__":
    # 调试代码
    logging.basicConfig(level=logging.INFO)
    # extractor = AudioExtractor()
    print("AudioExtractor module loaded.")
