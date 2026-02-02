import os
import logging
from moviepy import VideoFileClip
from typing import List, Dict, Any

class VideoProcessor:
    """
    Video-Stat-Agent: 剪辑与统计员
    根据识别结果从原始视频截取片段，并更新统计库
    """
    def __init__(
        self, 
        output_dir: str = "output_clips", 
        padding_start: float = 0.5, 
        padding_end: float = 0.5,
        codec: str = "libx264"
    ):
        self.logger = logging.getLogger("VideoProcessor")
        self.output_dir = output_dir
        self.padding_start = padding_start
        self.padding_end = padding_end
        self.codec = codec
        
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def process_idioms(self, video_path: str, idioms: List[Dict[str, Any]]) -> List[str]:
        """
        批量剪辑视频片段
        :param video_path: 原始视频路径
        :param idioms: 识别到的成语列表
        :return: 生成的片段路径列表
        """
        clip_paths = []
        if not idioms:
            return clip_paths

        try:
            self.logger.info(f"开始剪辑视频: {os.path.basename(video_path)}")
            video = VideoFileClip(video_path)
            duration = video.duration
            
            episode_name = os.path.splitext(os.path.basename(video_path))[0]
            
            for idiom in idioms:
                word = idiom['word']
                start = max(0, idiom['start'] - self.padding_start)
                end = min(duration, idiom['end'] + self.padding_end)
                
                # 命名规则: 成语_集数_秒数.mp4
                timestamp_str = f"{int(start)}s"
                output_filename = f"{word}_{episode_name}_{timestamp_str}.mp4"
                # 移除非法文件名字符
                output_filename = "".join([c for c in output_filename if c.isalnum() or c in ('_', '.', '-')])
                output_path = os.path.abspath(os.path.join(self.output_dir, output_filename))
                
                self.logger.info(f"正在截取: {word} ({start:.2f}s - {end:.2f}s)")
                
                # 执行剪辑
                new_clip = video.subclipped(start, end)
                new_clip.write_videofile(
                    output_path, 
                    codec=self.codec, 
                    audio_codec="aac",
                    logger=None
                )
                
                idiom['clip_path'] = output_path
                clip_paths.append(output_path)
                
            video.close()
            self.logger.info(f"视频剪辑完成，共生成 {len(clip_paths)} 个片段")
            
        except Exception as e:
            self.logger.error(f"视频剪辑失败 {video_path}: {str(e)}")
            
        return clip_paths

if __name__ == "__main__":
    # 调试代码
    logging.basicConfig(level=logging.INFO)
    print("VideoProcessor module loaded.")
