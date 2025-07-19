#!/usr/bin/env python3
"""
智能缓存管理系统
提供文档OCR结果的缓存、重试机制和存储管理功能
"""

import os
import json
import hashlib
import pickle
import time
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import tempfile

from PIL import Image


class CacheStatus(Enum):
    """缓存状态枚举"""
    PENDING = "pending"           # 等待处理
    PROCESSING = "processing"     # 正在处理
    COMPLETED = "completed"       # 处理完成
    FAILED = "failed"            # 处理失败
    EXPIRED = "expired"          # 已过期
    CORRUPTED = "corrupted"      # 缓存损坏


class RetryStrategy(Enum):
    """重试策略枚举"""
    NONE = "none"                # 不重试
    SIMPLE = "simple"            # 简单重试
    EXPONENTIAL = "exponential"   # 指数退避
    SMART = "smart"              # 智能重试


@dataclass
class CacheMetadata:
    """缓存元数据"""
    file_path: str
    file_hash: str
    file_size: int
    file_mtime: float
    cache_key: str
    cache_version: str
    created_time: datetime
    last_accessed: datetime
    access_count: int
    processing_config: Dict[str, Any]
    ocr_service: str
    terminology_hash: str
    page_range: Tuple[int, int]
    status: CacheStatus
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    processing_time: float = 0.0
    output_size: int = 0


@dataclass
class CacheConfig:
    """缓存配置"""
    cache_dir: Path = Path("cache")
    max_cache_size_gb: float = 5.0        # 最大缓存大小(GB)
    max_cache_age_days: int = 30          # 最大缓存保存天数
    max_entries: int = 1000               # 最大缓存条目数
    cleanup_interval_hours: int = 24      # 清理间隔(小时)
    enable_compression: bool = True       # 启用压缩
    cache_version: str = "v1.0"          # 缓存版本
    auto_cleanup: bool = True            # 自动清理
    preserve_recent: int = 100           # 保留最近访问的条目数


class CacheManager:
    """智能缓存管理器"""
    
    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        self.cache_dir = self.config.cache_dir
        self.metadata_file = self.cache_dir / "cache_metadata.json"
        self.lock = threading.RLock()
        
        # 初始化缓存目录
        self._init_cache_dir()
        
        # 加载元数据
        self.metadata: Dict[str, CacheMetadata] = self._load_metadata()
        
        # 启动定期清理
        if self.config.auto_cleanup:
            self._start_cleanup_scheduler()
    
    def _init_cache_dir(self):
        """初始化缓存目录结构"""
        self.cache_dir.mkdir(exist_ok=True)
        
        # 创建子目录
        (self.cache_dir / "data").mkdir(exist_ok=True)      # 缓存数据
        (self.cache_dir / "temp").mkdir(exist_ok=True)      # 临时文件
        (self.cache_dir / "backup").mkdir(exist_ok=True)    # 备份文件
        (self.cache_dir / "logs").mkdir(exist_ok=True)      # 日志文件
    
    def _generate_cache_key(self, file_path: Path, config: Dict[str, Any], 
                           ocr_service: str, terminology_terms: str, 
                           page_range: Tuple[int, int]) -> str:
        """生成缓存键"""
        # 计算文件哈希
        file_hash = self._calculate_file_hash(file_path)
        
        # 计算配置哈希
        config_str = json.dumps(config, sort_keys=True) if config else ""
        terminology_hash = hashlib.md5(terminology_terms.encode()).hexdigest()
        
        # 组合所有参数
        key_data = {
            "file_hash": file_hash,
            "config": config_str,
            "ocr_service": ocr_service,
            "terminology": terminology_hash,
            "page_range": page_range,
            "version": self.config.cache_version
        }
        
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件哈希值"""
        try:
            hash_md5 = hashlib.md5()
            
            # 对于大文件，只计算前1MB + 文件信息的哈希
            file_stat = file_path.stat()
            
            # 添加文件基本信息
            file_info = f"{file_path.name}:{file_stat.st_size}:{file_stat.st_mtime}"
            hash_md5.update(file_info.encode())
            
            # 读取文件开头部分
            with open(file_path, 'rb') as f:
                chunk_size = min(1024 * 1024, file_stat.st_size)  # 最多1MB
                chunk = f.read(chunk_size)
                hash_md5.update(chunk)
            
            return hash_md5.hexdigest()
        except Exception as e:
            # 如果无法读取文件，使用文件信息
            file_stat = file_path.stat()
            fallback_info = f"{file_path.name}:{file_stat.st_size}:{file_stat.st_mtime}"
            return hashlib.md5(fallback_info.encode()).hexdigest()
    
    def _load_metadata(self) -> Dict[str, CacheMetadata]:
        """加载缓存元数据"""
        if not self.metadata_file.exists():
            return {}
        
        try:
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            metadata = {}
            for key, item in data.items():
                try:
                    # 转换日期时间字符串
                    item['created_time'] = datetime.fromisoformat(item['created_time'])
                    item['last_accessed'] = datetime.fromisoformat(item['last_accessed'])
                    item['status'] = CacheStatus(item['status'])
                    
                    metadata[key] = CacheMetadata(**item)
                except Exception as e:
                    print(f"⚠️ 跳过损坏的缓存元数据项: {key} - {e}")
                    continue
            
            return metadata
        except Exception as e:
            print(f"⚠️ 加载缓存元数据失败: {e}")
            return {}
    
    def _save_metadata(self):
        """保存缓存元数据"""
        try:
            # 备份现有元数据
            if self.metadata_file.exists():
                backup_file = self.cache_dir / "backup" / f"metadata_{int(time.time())}.json"
                shutil.copy2(self.metadata_file, backup_file)
            
            # 转换为可序列化格式
            data = {}
            for key, metadata in self.metadata.items():
                item = asdict(metadata)
                item['created_time'] = metadata.created_time.isoformat()
                item['last_accessed'] = metadata.last_accessed.isoformat()
                item['status'] = metadata.status.value
                data[key] = item
            
            # 保存到临时文件，然后原子性替换
            temp_file = self.metadata_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            temp_file.replace(self.metadata_file)
            
        except Exception as e:
            print(f"❌ 保存缓存元数据失败: {e}")
    
    def _get_cache_path(self, cache_key: str, suffix: str = ".pkl") -> Path:
        """获取缓存文件路径"""
        # 使用哈希的前两位作为子目录，避免单目录文件过多
        subdir = cache_key[:2]
        cache_subdir = self.cache_dir / "data" / subdir
        cache_subdir.mkdir(exist_ok=True)
        return cache_subdir / f"{cache_key}{suffix}"
    
    def has_cache(self, file_path: Path, config: Dict[str, Any], 
                  ocr_service: str, terminology_terms: str, 
                  page_range: Tuple[int, int]) -> bool:
        """检查是否存在有效缓存"""
        with self.lock:
            cache_key = self._generate_cache_key(
                file_path, config, ocr_service, terminology_terms, page_range
            )
            
            if cache_key not in self.metadata:
                return False
            
            metadata = self.metadata[cache_key]
            
            # 检查缓存状态
            if metadata.status != CacheStatus.COMPLETED:
                return False
            
            # 检查文件是否仍然存在且未修改
            if not file_path.exists():
                return False
            
            file_stat = file_path.stat()
            if (file_stat.st_size != metadata.file_size or 
                abs(file_stat.st_mtime - metadata.file_mtime) > 1):
                return False
            
            # 检查缓存文件是否存在
            cache_path = self._get_cache_path(cache_key)
            if not cache_path.exists():
                return False
            
            # 检查是否过期
            if self._is_expired(metadata):
                return False
            
            return True
    
    def get_cache(self, file_path: Path, config: Dict[str, Any], 
                  ocr_service: str, terminology_terms: str, 
                  page_range: Tuple[int, int]) -> Optional[str]:
        """获取缓存结果"""
        with self.lock:
            if not self.has_cache(file_path, config, ocr_service, terminology_terms, page_range):
                return None
            
            cache_key = self._generate_cache_key(
                file_path, config, ocr_service, terminology_terms, page_range
            )
            
            try:
                cache_path = self._get_cache_path(cache_key)
                
                if self.config.enable_compression:
                    import gzip
                    with gzip.open(cache_path, 'rb') as f:
                        result = pickle.load(f)
                else:
                    with open(cache_path, 'rb') as f:
                        result = pickle.load(f)
                
                # 更新访问信息
                metadata = self.metadata[cache_key]
                metadata.last_accessed = datetime.now()
                metadata.access_count += 1
                
                self._save_metadata()
                
                print(f"✅ 从缓存加载结果: {cache_key[:8]}... (访问次数: {metadata.access_count})")
                return result
                
            except Exception as e:
                print(f"❌ 读取缓存失败: {e}")
                # 标记缓存为损坏
                if cache_key in self.metadata:
                    self.metadata[cache_key].status = CacheStatus.CORRUPTED
                    self._save_metadata()
                return None
    
    def set_cache(self, file_path: Path, config: Dict[str, Any], 
                  ocr_service: str, terminology_terms: str, 
                  page_range: Tuple[int, int], result: str,
                  processing_time: float = 0.0) -> bool:
        """设置缓存"""
        with self.lock:
            try:
                cache_key = self._generate_cache_key(
                    file_path, config, ocr_service, terminology_terms, page_range
                )
                
                # 保存缓存数据
                cache_path = self._get_cache_path(cache_key)
                
                if self.config.enable_compression:
                    import gzip
                    with gzip.open(cache_path, 'wb') as f:
                        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
                else:
                    with open(cache_path, 'wb') as f:
                        pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
                
                # 创建元数据
                file_stat = file_path.stat()
                terminology_hash = hashlib.md5(terminology_terms.encode()).hexdigest()
                
                metadata = CacheMetadata(
                    file_path=str(file_path),
                    file_hash=self._calculate_file_hash(file_path),
                    file_size=file_stat.st_size,
                    file_mtime=file_stat.st_mtime,
                    cache_key=cache_key,
                    cache_version=self.config.cache_version,
                    created_time=datetime.now(),
                    last_accessed=datetime.now(),
                    access_count=0,
                    processing_config=config or {},
                    ocr_service=ocr_service,
                    terminology_hash=terminology_hash,
                    page_range=page_range,
                    status=CacheStatus.COMPLETED,
                    processing_time=processing_time,
                    output_size=len(result.encode('utf-8'))
                )
                
                self.metadata[cache_key] = metadata
                self._save_metadata()
                
                print(f"💾 缓存保存成功: {cache_key[:8]}... ({len(result)} 字符)")
                
                # 检查是否需要清理
                if len(self.metadata) > self.config.max_entries:
                    self._cleanup_old_entries()
                
                return True
                
            except Exception as e:
                print(f"❌ 保存缓存失败: {e}")
                return False
    
    def mark_processing(self, file_path: Path, config: Dict[str, Any], 
                       ocr_service: str, terminology_terms: str, 
                       page_range: Tuple[int, int]) -> str:
        """标记文件正在处理"""
        with self.lock:
            cache_key = self._generate_cache_key(
                file_path, config, ocr_service, terminology_terms, page_range
            )
            
            file_stat = file_path.stat()
            terminology_hash = hashlib.md5(terminology_terms.encode()).hexdigest()
            
            metadata = CacheMetadata(
                file_path=str(file_path),
                file_hash=self._calculate_file_hash(file_path),
                file_size=file_stat.st_size,
                file_mtime=file_stat.st_mtime,
                cache_key=cache_key,
                cache_version=self.config.cache_version,
                created_time=datetime.now(),
                last_accessed=datetime.now(),
                access_count=0,
                processing_config=config or {},
                ocr_service=ocr_service,
                terminology_hash=terminology_hash,
                page_range=page_range,
                status=CacheStatus.PROCESSING
            )
            
            self.metadata[cache_key] = metadata
            self._save_metadata()
            
            return cache_key
    
    def mark_failed(self, cache_key: str, error_message: str):
        """标记处理失败"""
        with self.lock:
            if cache_key in self.metadata:
                metadata = self.metadata[cache_key]
                metadata.status = CacheStatus.FAILED
                metadata.error_message = error_message
                metadata.retry_count += 1
                self._save_metadata()
    
    def can_retry(self, cache_key: str) -> bool:
        """检查是否可以重试"""
        with self.lock:
            if cache_key not in self.metadata:
                return True
            
            metadata = self.metadata[cache_key]
            return metadata.retry_count < metadata.max_retries
    
    def _is_expired(self, metadata: CacheMetadata) -> bool:
        """检查缓存是否过期"""
        age = datetime.now() - metadata.created_time
        return age > timedelta(days=self.config.max_cache_age_days)
    
    def cleanup(self) -> Dict[str, int]:
        """清理缓存"""
        with self.lock:
            stats = {
                "removed_expired": 0,
                "removed_corrupted": 0,
                "removed_old": 0,
                "removed_failed": 0,
                "total_removed": 0,
                "bytes_freed": 0
            }
            
            to_remove = []
            
            # 检查每个缓存项
            for cache_key, metadata in self.metadata.items():
                should_remove = False
                cache_path = self._get_cache_path(cache_key)
                
                # 检查是否过期
                if self._is_expired(metadata):
                    should_remove = True
                    stats["removed_expired"] += 1
                
                # 检查缓存文件是否存在
                elif not cache_path.exists():
                    should_remove = True
                    stats["removed_corrupted"] += 1
                
                # 检查状态
                elif metadata.status in [CacheStatus.CORRUPTED, CacheStatus.FAILED]:
                    # 失败的项目如果重试次数用完则删除
                    if metadata.status == CacheStatus.FAILED and metadata.retry_count >= metadata.max_retries:
                        should_remove = True
                        stats["removed_failed"] += 1
                    elif metadata.status == CacheStatus.CORRUPTED:
                        should_remove = True
                        stats["removed_corrupted"] += 1
                
                if should_remove:
                    to_remove.append(cache_key)
                    if cache_path.exists():
                        try:
                            stats["bytes_freed"] += cache_path.stat().st_size
                        except:
                            pass
            
            # 如果条目数仍然过多，删除最旧的
            remaining_items = len(self.metadata) - len(to_remove)
            if remaining_items > self.config.max_entries:
                # 按最后访问时间排序，保留最近的
                sorted_items = sorted(
                    [(k, v) for k, v in self.metadata.items() if k not in to_remove],
                    key=lambda x: x[1].last_accessed,
                    reverse=True
                )
                
                keep_count = min(self.config.max_entries, self.config.preserve_recent)
                for cache_key, metadata in sorted_items[keep_count:]:
                    to_remove.append(cache_key)
                    stats["removed_old"] += 1
            
            # 删除缓存项
            for cache_key in to_remove:
                try:
                    cache_path = self._get_cache_path(cache_key)
                    if cache_path.exists():
                        cache_path.unlink()
                    
                    if cache_key in self.metadata:
                        del self.metadata[cache_key]
                    
                    stats["total_removed"] += 1
                    
                except Exception as e:
                    print(f"⚠️ 删除缓存项失败 {cache_key}: {e}")
            
            if stats["total_removed"] > 0:
                self._save_metadata()
                print(f"🧹 缓存清理完成: 删除 {stats['total_removed']} 项, 释放 {stats['bytes_freed']/1024/1024:.1f}MB")
            
            return stats
    
    def _cleanup_old_entries(self):
        """清理旧条目"""
        if len(self.metadata) <= self.config.max_entries:
            return
        
        # 按访问时间排序，删除最旧的
        sorted_items = sorted(
            self.metadata.items(),
            key=lambda x: x[1].last_accessed
        )
        
        remove_count = len(self.metadata) - self.config.max_entries
        
        for i in range(remove_count):
            cache_key, metadata = sorted_items[i]
            
            try:
                cache_path = self._get_cache_path(cache_key)
                if cache_path.exists():
                    cache_path.unlink()
                
                del self.metadata[cache_key]
                
            except Exception as e:
                print(f"⚠️ 删除旧缓存项失败 {cache_key}: {e}")
    
    def _start_cleanup_scheduler(self):
        """启动定期清理调度器"""
        def cleanup_worker():
            while True:
                try:
                    time.sleep(self.config.cleanup_interval_hours * 3600)
                    self.cleanup()
                except Exception as e:
                    print(f"⚠️ 定期清理失败: {e}")
        
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            total_size = 0
            status_counts = {}
            oldest_cache = None
            newest_cache = None
            total_processing_time = 0
            total_access_count = 0
            
            for metadata in self.metadata.values():
                # 计算大小
                cache_path = self._get_cache_path(metadata.cache_key)
                if cache_path.exists():
                    total_size += cache_path.stat().st_size
                
                # 统计状态
                status = metadata.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
                
                # 找最旧和最新的缓存
                if oldest_cache is None or metadata.created_time < oldest_cache:
                    oldest_cache = metadata.created_time
                if newest_cache is None or metadata.created_time > newest_cache:
                    newest_cache = metadata.created_time
                
                # 累计统计
                total_processing_time += metadata.processing_time
                total_access_count += metadata.access_count
            
            return {
                "total_entries": len(self.metadata),
                "total_size_mb": total_size / 1024 / 1024,
                "status_counts": status_counts,
                "oldest_cache": oldest_cache.isoformat() if oldest_cache else None,
                "newest_cache": newest_cache.isoformat() if newest_cache else None,
                "total_processing_time": total_processing_time,
                "total_access_count": total_access_count,
                "config": asdict(self.config)
            }
    
    def clear_all(self) -> bool:
        """清空所有缓存"""
        with self.lock:
            try:
                # 删除所有缓存文件
                data_dir = self.cache_dir / "data"
                if data_dir.exists():
                    shutil.rmtree(data_dir)
                    data_dir.mkdir(exist_ok=True)
                
                # 清空元数据
                self.metadata.clear()
                self._save_metadata()
                
                print("🗑️ 所有缓存已清空")
                return True
                
            except Exception as e:
                print(f"❌ 清空缓存失败: {e}")
                return False


def create_cache_manager(max_cache_size_gb: float = 5.0, 
                        max_cache_age_days: int = 30) -> CacheManager:
    """创建缓存管理器的工厂函数"""
    config = CacheConfig(
        max_cache_size_gb=max_cache_size_gb,
        max_cache_age_days=max_cache_age_days
    )
    return CacheManager(config)


# 全局缓存管理器实例
_global_cache_manager = None


def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器实例"""
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = create_cache_manager()
    return _global_cache_manager