import mysql.connector
from mysql.connector import Error
import hashlib
import os
import logging
from datetime import datetime
from typing import List, Tuple, Dict, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("system.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class DBManager:
    """
    状态管理与增量迭代逻辑核心类 (MySQL 8.0+ 版本)
    负责管理视频处理状态、文件哈希校验以及成语统计数据的持久化
    """
    def __init__(self, host="localhost", user="root", password="248812", database="frxxz_idiom"):
        self.config = {
            'host': host,
            'user': user,
            'password': password,
            'database': database,
            'auth_plugin': 'mysql_native_password' # 兼容某些配置
        }
        self.logger = logging.getLogger("DBManager")
        self._ensure_database()
        self._init_db()

    def _get_connection(self, include_db=True):
        config = self.config.copy()
        if not include_db:
            config.pop('database')
        return mysql.connector.connect(**config)

    def _ensure_database(self):
        """确保数据库存在"""
        try:
            conn = self._get_connection(include_db=False)
            cursor = conn.cursor()
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.config['database']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            conn.commit()
            cursor.close()
            conn.close()
            self.logger.info(f"数据库 {self.config['database']} 确认就绪")
        except Error as e:
            self.logger.error(f"创建数据库失败: {str(e)}")
            raise

    def _init_db(self):
        """初始化数据库表结构"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # 视频处理状态表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS videos (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        file_path VARCHAR(512) UNIQUE,
                        file_hash VARCHAR(64),
                        status VARCHAR(32) DEFAULT 'pending', 
                        last_updated DATETIME,
                        audio_path VARCHAR(512),
                        transcript_path VARCHAR(512),
                        idioms_path VARCHAR(512)
                    ) ENGINE=InnoDB
                ''')
                # 成语统计与片段表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS idioms_stats (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        word VARCHAR(128),
                        source_video VARCHAR(512),
                        timestamp_start FLOAT,
                        timestamp_end FLOAT,
                        clip_path VARCHAR(512),
                        created_at DATETIME,
                        UNIQUE KEY idiom_occurence (word, source_video, timestamp_start)
                    ) ENGINE=InnoDB
                ''')
                conn.commit()
                self.logger.info("MySQL 表结构初始化完成")
        except Error as e:
            self.logger.error(f"数据库初始化失败: {str(e)}")
            raise

    def get_file_hash(self, file_path: str) -> str:
        """计算文件的 MD5 哈希值"""
        hasher = hashlib.md5()
        try:
            if not os.path.exists(file_path):
                return ""
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            self.logger.error(f"计算哈希失败 {file_path}: {str(e)}")
            return ""

    def sync_folder(self, folder_path: str):
        """同步文件夹中的视频文件到数据库"""
        self.logger.info(f"开始扫描目录: {folder_path}")
        valid_extensions = ('.mp4', '.mkv', '.avi', '.mov')
        
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(valid_extensions):
                    full_path = os.path.abspath(os.path.join(root, file))
                    self.register_video(full_path)

    def register_video(self, file_path: str):
        """注册或更新视频文件状态"""
        file_hash = self.get_file_hash(file_path)
        if not file_hash:
            return

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, file_hash, status FROM videos WHERE file_path = %s", (file_path,))
                row = cursor.fetchone()
                
                now = datetime.now()
                if row:
                    if row['file_hash'] != file_hash:
                        self.logger.info(f"检测到文件内容变化: {file_path}, 重置状态为 pending")
                        cursor.execute(
                            "UPDATE videos SET file_hash = %s, status = 'pending', last_updated = %s WHERE id = %s", 
                            (file_hash, now, row['id'])
                        )
                    else:
                        self.logger.debug(f"文件已存在且未变化: {file_path} (当前状态: {row['status']})")
                else:
                    self.logger.info(f"注册新视频文件: {file_path}")
                    cursor.execute(
                        "INSERT INTO videos (file_path, file_hash, status, last_updated) VALUES (%s, %s, 'pending', %s)",
                        (file_path, file_hash, now)
                    )
                conn.commit()
        except Error as e:
            self.logger.error(f"注册视频失败 {file_path}: {str(e)}")

    def update_video_status(self, file_path: str, status: str, **kwargs):
        """更新视频处理进度及相关文件路径"""
        allowed_fields = ['audio_path', 'transcript_path', 'idioms_path']
        set_clauses = ["status = %s", "last_updated = %s"]
        params = [status, datetime.now()]

        for key, value in kwargs.items():
            if key in allowed_fields:
                set_clauses.append(f"{key} = %s")
                params.append(value)
        
        params.append(file_path)
        query = f"UPDATE videos SET {', '.join(set_clauses)} WHERE file_path = %s"
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                self.logger.info(f"状态更新成功: {os.path.basename(file_path)} -> {status}")
        except Error as e:
            self.logger.error(f"更新状态失败 {file_path}: {str(e)}")

    def get_videos_by_status(self, status: str) -> List[Dict]:
        """获取指定状态的视频列表"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT * FROM videos WHERE status = %s", (status,))
                return cursor.fetchall()
        except Error as e:
            self.logger.error(f"查询视频列表失败: {str(e)}")
            return []

    def add_idiom_record(self, word: str, source_video: str, start: float, end: float, clip_path: str):
        """记录识别到的成语片段"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO idioms_stats 
                    (word, source_video, timestamp_start, timestamp_end, clip_path, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE clip_path = VALUES(clip_path)
                ''', (word, source_video, start, end, clip_path, datetime.now()))
                conn.commit()
        except Error as e:
            self.logger.error(f"记录成语失败: {str(e)}")

    def get_idiom_stats(self) -> List[Tuple[str, int]]:
        """获取成语频次统计"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT word, COUNT(*) as freq FROM idioms_stats GROUP BY word ORDER BY freq DESC")
                return cursor.fetchall()
        except Error as e:
            self.logger.error(f"获取统计数据失败: {str(e)}")
            return []

if __name__ == "__main__":
    # 简单测试
    db = DBManager()
    print("DBManager initialized.")
