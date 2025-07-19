#!/usr/bin/env python3
"""
重试机制和断点续传管理器
提供智能重试、断点恢复和错误处理功能
"""

import time
import random
import json
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime, timedelta
import threading
import traceback

from cache_manager import CacheManager, CacheStatus


class RetryReason(Enum):
    """重试原因枚举"""
    NETWORK_ERROR = "network_error"         # 网络错误
    API_RATE_LIMIT = "api_rate_limit"      # API限流
    API_ERROR = "api_error"                # API错误
    TIMEOUT = "timeout"                    # 超时
    MEMORY_ERROR = "memory_error"          # 内存错误
    FILE_ERROR = "file_error"              # 文件错误
    PROCESSING_ERROR = "processing_error"   # 处理错误
    UNKNOWN_ERROR = "unknown_error"        # 未知错误


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3                   # 最大重试次数
    base_delay: float = 1.0               # 基础延迟(秒)
    max_delay: float = 300.0              # 最大延迟(秒)
    exponential_base: float = 2.0         # 指数退避倍数
    jitter: bool = True                   # 添加随机抖动
    retry_on_errors: List[RetryReason] = None  # 可重试的错误类型
    enable_circuit_breaker: bool = True   # 启用熔断器
    circuit_failure_threshold: int = 5    # 熔断器失败阈值
    circuit_recovery_time: int = 300      # 熔断器恢复时间(秒)


@dataclass
class RetryAttempt:
    """重试尝试记录"""
    attempt_number: int
    timestamp: datetime
    error_type: RetryReason
    error_message: str
    delay_before_retry: float
    success: bool = False


@dataclass
class ProcessingState:
    """处理状态记录"""
    file_path: str
    cache_key: str
    total_pages: int
    completed_pages: List[int]
    failed_pages: List[int]
    current_page: Optional[int]
    start_time: datetime
    last_update: datetime
    retry_attempts: List[RetryAttempt]
    config: Dict[str, Any]
    ocr_service: str
    terminology_terms: str
    page_range: Tuple[int, int]
    partial_results: Dict[int, str]  # 页码 -> OCR结果


class CircuitBreaker:
    """熔断器实现"""
    
    def __init__(self, failure_threshold: int = 5, recovery_time: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open
        self.lock = threading.Lock()
    
    def call(self, func: Callable, *args, **kwargs):
        """通过熔断器调用函数"""
        with self.lock:
            if self.state == "open":
                if (datetime.now() - self.last_failure_time).seconds < self.recovery_time:
                    raise Exception("Circuit breaker is open")
                else:
                    self.state = "half_open"
            
            try:
                result = func(*args, **kwargs)
                if self.state == "half_open":
                    self.state = "closed"
                    self.failure_count = 0
                return result
            except Exception as e:
                self.failure_count += 1
                self.last_failure_time = datetime.now()
                
                if self.failure_count >= self.failure_threshold:
                    self.state = "open"
                
                raise e


class RetryManager:
    """重试管理器"""
    
    def __init__(self, cache_manager: CacheManager, config: RetryConfig = None):
        self.cache_manager = cache_manager
        self.config = config or RetryConfig()
        
        # 设置默认可重试错误
        if self.config.retry_on_errors is None:
            self.config.retry_on_errors = [
                RetryReason.NETWORK_ERROR,
                RetryReason.API_RATE_LIMIT,
                RetryReason.TIMEOUT,
                RetryReason.API_ERROR
            ]
        
        # 断点续传状态存储
        self.state_dir = Path("recovery_states")
        self.state_dir.mkdir(exist_ok=True)
        
        # 熔断器
        self.circuit_breakers = {}
        
        self.lock = threading.RLock()
    
    def _classify_error(self, error: Exception) -> RetryReason:
        """分类错误类型"""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()
        
        # 网络相关错误
        if any(keyword in error_str for keyword in ['connection', 'network', 'timeout', 'unreachable']):
            return RetryReason.NETWORK_ERROR
        
        # API限流
        if any(keyword in error_str for keyword in ['rate limit', 'too many requests', '429']):
            return RetryReason.API_RATE_LIMIT
        
        # API错误
        if any(keyword in error_str for keyword in ['api', 'invalid', 'unauthorized', '401', '403', '500', '502', '503']):
            return RetryReason.API_ERROR
        
        # 超时错误
        if 'timeout' in error_str or 'timeouterror' in error_type:
            return RetryReason.TIMEOUT
        
        # 内存错误
        if 'memory' in error_str or 'memoryerror' in error_type:
            return RetryReason.MEMORY_ERROR
        
        # 文件错误
        if any(keyword in error_str for keyword in ['file', 'directory', 'permission']) or 'ioerror' in error_type:
            return RetryReason.FILE_ERROR
        
        return RetryReason.UNKNOWN_ERROR
    
    def _should_retry(self, error: Exception, attempt_number: int) -> bool:
        """判断是否应该重试"""
        if attempt_number >= self.config.max_retries:
            return False
        
        error_type = self._classify_error(error)
        return error_type in self.config.retry_on_errors
    
    def _calculate_delay(self, attempt_number: int, error_type: RetryReason) -> float:
        """计算重试延迟"""
        if error_type == RetryReason.API_RATE_LIMIT:
            # API限流使用更长的延迟
            delay = self.config.base_delay * (self.config.exponential_base ** attempt_number) * 2
        else:
            # 标准指数退避
            delay = self.config.base_delay * (self.config.exponential_base ** attempt_number)
        
        # 限制最大延迟
        delay = min(delay, self.config.max_delay)
        
        # 添加随机抖动
        if self.config.jitter:
            jitter = random.uniform(0.5, 1.5)
            delay *= jitter
        
        return delay
    
    def _get_circuit_breaker(self, service_key: str) -> CircuitBreaker:
        """获取服务的熔断器"""
        if service_key not in self.circuit_breakers:
            self.circuit_breakers[service_key] = CircuitBreaker(
                self.config.circuit_failure_threshold,
                self.config.circuit_recovery_time
            )
        return self.circuit_breakers[service_key]
    
    def _save_processing_state(self, state: ProcessingState):
        """保存处理状态"""
        try:
            state_file = self.state_dir / f"{state.cache_key}.json"
            state_data = asdict(state)
            
            # 转换不可序列化的对象
            state_data['start_time'] = state.start_time.isoformat()
            state_data['last_update'] = state.last_update.isoformat()
            
            # 转换重试记录
            retry_data = []
            for attempt in state.retry_attempts:
                attempt_data = asdict(attempt)
                attempt_data['timestamp'] = attempt.timestamp.isoformat()
                attempt_data['error_type'] = attempt.error_type.value
                retry_data.append(attempt_data)
            state_data['retry_attempts'] = retry_data
            
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"⚠️ 保存处理状态失败: {e}")
    
    def _load_processing_state(self, cache_key: str) -> Optional[ProcessingState]:
        """加载处理状态"""
        try:
            state_file = self.state_dir / f"{cache_key}.json"
            if not state_file.exists():
                return None
            
            with open(state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            # 转换日期时间
            state_data['start_time'] = datetime.fromisoformat(state_data['start_time'])
            state_data['last_update'] = datetime.fromisoformat(state_data['last_update'])
            
            # 转换重试记录
            retry_attempts = []
            for attempt_data in state_data['retry_attempts']:
                attempt_data['timestamp'] = datetime.fromisoformat(attempt_data['timestamp'])
                attempt_data['error_type'] = RetryReason(attempt_data['error_type'])
                retry_attempts.append(RetryAttempt(**attempt_data))
            state_data['retry_attempts'] = retry_attempts
            
            return ProcessingState(**state_data)
            
        except Exception as e:
            print(f"⚠️ 加载处理状态失败: {e}")
            return None
    
    def _remove_processing_state(self, cache_key: str):
        """删除处理状态"""
        try:
            state_file = self.state_dir / f"{cache_key}.json"
            if state_file.exists():
                state_file.unlink()
        except Exception as e:
            print(f"⚠️ 删除处理状态失败: {e}")
    
    def execute_with_retry(self, func: Callable, *args, 
                          service_key: str = "default",
                          context: str = "操作",
                          **kwargs) -> Any:
        """带重试的函数执行"""
        attempt = 0
        last_error = None
        
        while attempt <= self.config.max_retries:
            try:
                if self.config.enable_circuit_breaker:
                    circuit_breaker = self._get_circuit_breaker(service_key)
                    return circuit_breaker.call(func, *args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except Exception as e:
                last_error = e
                error_type = self._classify_error(e)
                
                print(f"❌ {context}失败 (尝试 {attempt + 1}/{self.config.max_retries + 1}): {e}")
                
                if not self._should_retry(e, attempt):
                    break
                
                # 计算延迟并等待
                if attempt < self.config.max_retries:
                    delay = self._calculate_delay(attempt, error_type)
                    print(f"⏳ {delay:.1f}秒后重试...")
                    time.sleep(delay)
                
                attempt += 1
        
        # 所有重试都失败了
        raise Exception(f"{context}失败，已重试 {attempt} 次: {last_error}")
    
    def process_with_recovery(self, file_path: Path, config: Dict[str, Any],
                            ocr_service: str, terminology_terms: str,
                            page_range: Tuple[int, int],
                            process_func: Callable,
                            progress_callback: Callable = None) -> str:
        """带断点恢复的处理"""
        
        # 生成缓存键
        cache_key = self.cache_manager._generate_cache_key(
            file_path, config, ocr_service, terminology_terms, page_range
        )
        
        # 检查缓存
        cached_result = self.cache_manager.get_cache(
            file_path, config, ocr_service, terminology_terms, page_range
        )
        if cached_result:
            print(f"✅ 使用缓存结果: {file_path.name}")
            return cached_result
        
        # 加载已有的处理状态
        state = self._load_processing_state(cache_key)
        
        start_page, end_page = page_range
        total_pages = end_page - start_page + 1
        
        if state is None:
            # 创建新的处理状态
            state = ProcessingState(
                file_path=str(file_path),
                cache_key=cache_key,
                total_pages=total_pages,
                completed_pages=[],
                failed_pages=[],
                current_page=None,
                start_time=datetime.now(),
                last_update=datetime.now(),
                retry_attempts=[],
                config=config,
                ocr_service=ocr_service,
                terminology_terms=terminology_terms,
                page_range=page_range,
                partial_results={}
            )
            
            # 标记为正在处理
            self.cache_manager.mark_processing(
                file_path, config, ocr_service, terminology_terms, page_range
            )
        else:
            print(f"🔄 恢复处理: {file_path.name} (已完成 {len(state.completed_pages)}/{total_pages} 页)")
        
        try:
            # 处理每一页
            for page_num in range(start_page, end_page + 1):
                if page_num in state.completed_pages:
                    continue  # 跳过已完成的页面
                
                state.current_page = page_num
                state.last_update = datetime.now()
                self._save_processing_state(state)
                
                if progress_callback:
                    progress_callback('page_start', (page_num - start_page, total_pages))
                
                # 重试处理单页
                page_result = self._process_page_with_retry(
                    page_num, state, process_func, progress_callback
                )
                
                if page_result:
                    state.completed_pages.append(page_num)
                    state.partial_results[page_num] = page_result
                    if page_num in state.failed_pages:
                        state.failed_pages.remove(page_num)
                    
                    if progress_callback:
                        progress_callback('page_complete', page_num - start_page)
                else:
                    state.failed_pages.append(page_num)
                
                self._save_processing_state(state)
            
            # 合并结果
            if len(state.completed_pages) == total_pages:
                # 按页码顺序合并
                results = []
                for page_num in range(start_page, end_page + 1):
                    if page_num in state.partial_results:
                        results.append(state.partial_results[page_num])
                
                combined_result = "\n\n".join(results)
                
                # 保存到缓存
                processing_time = (datetime.now() - state.start_time).total_seconds()
                self.cache_manager.set_cache(
                    file_path, config, ocr_service, terminology_terms, 
                    page_range, combined_result, processing_time
                )
                
                # 清理处理状态
                self._remove_processing_state(cache_key)
                
                print(f"✅ 处理完成: {file_path.name} ({len(state.completed_pages)}/{total_pages} 页)")
                return combined_result
            else:
                # 部分成功
                failed_count = len(state.failed_pages)
                success_count = len(state.completed_pages)
                
                error_msg = f"部分页面处理失败: 成功 {success_count}/{total_pages} 页, 失败页面: {state.failed_pages}"
                
                self.cache_manager.mark_failed(cache_key, error_msg)
                
                raise Exception(error_msg)
                
        except Exception as e:
            error_msg = f"处理失败: {e}"
            self.cache_manager.mark_failed(cache_key, error_msg)
            print(f"❌ {error_msg}")
            raise
    
    def _process_page_with_retry(self, page_num: int, state: ProcessingState,
                               process_func: Callable, progress_callback: Callable = None) -> Optional[str]:
        """带重试的单页处理"""
        attempt = 0
        
        while attempt <= self.config.max_retries:
            try:
                # 调用实际的处理函数
                result = process_func(page_num, state.config, progress_callback)
                
                # 记录成功的重试
                if attempt > 0:
                    retry_attempt = RetryAttempt(
                        attempt_number=attempt,
                        timestamp=datetime.now(),
                        error_type=RetryReason.UNKNOWN_ERROR,
                        error_message="成功",
                        delay_before_retry=0,
                        success=True
                    )
                    state.retry_attempts.append(retry_attempt)
                
                return result
                
            except Exception as e:
                error_type = self._classify_error(e)
                
                print(f"❌ 第 {page_num} 页处理失败 (尝试 {attempt + 1}/{self.config.max_retries + 1}): {e}")
                
                # 记录失败的重试
                delay = 0
                if attempt < self.config.max_retries and self._should_retry(e, attempt):
                    delay = self._calculate_delay(attempt, error_type)
                
                retry_attempt = RetryAttempt(
                    attempt_number=attempt,
                    timestamp=datetime.now(),
                    error_type=error_type,
                    error_message=str(e),
                    delay_before_retry=delay,
                    success=False
                )
                state.retry_attempts.append(retry_attempt)
                
                if not self._should_retry(e, attempt):
                    break
                
                if attempt < self.config.max_retries:
                    print(f"⏳ {delay:.1f}秒后重试第 {page_num} 页...")
                    time.sleep(delay)
                
                attempt += 1
        
        return None
    
    def get_recovery_status(self) -> Dict[str, Any]:
        """获取恢复状态信息"""
        status = {
            "active_processing": [],
            "failed_processing": [],
            "total_states": 0
        }
        
        try:
            for state_file in self.state_dir.glob("*.json"):
                status["total_states"] += 1
                
                try:
                    state = self._load_processing_state(state_file.stem)
                    if state:
                        state_info = {
                            "file_path": state.file_path,
                            "progress": f"{len(state.completed_pages)}/{state.total_pages}",
                            "last_update": state.last_update.isoformat(),
                            "failed_pages": len(state.failed_pages),
                            "retry_attempts": len(state.retry_attempts)
                        }
                        
                        if state.failed_pages:
                            status["failed_processing"].append(state_info)
                        else:
                            status["active_processing"].append(state_info)
                            
                except Exception as e:
                    print(f"⚠️ 读取状态文件失败 {state_file}: {e}")
                    
        except Exception as e:
            print(f"⚠️ 获取恢复状态失败: {e}")
        
        return status
    
    def cleanup_old_states(self, max_age_hours: int = 48) -> int:
        """清理旧的处理状态"""
        removed_count = 0
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        try:
            for state_file in self.state_dir.glob("*.json"):
                try:
                    state = self._load_processing_state(state_file.stem)
                    if state and state.last_update < cutoff_time:
                        state_file.unlink()
                        removed_count += 1
                        print(f"🗑️ 清理旧状态: {state.file_path}")
                        
                except Exception as e:
                    print(f"⚠️ 清理状态文件失败 {state_file}: {e}")
                    
        except Exception as e:
            print(f"⚠️ 清理旧状态失败: {e}")
        
        return removed_count


def create_retry_manager(cache_manager: CacheManager, 
                        max_retries: int = 3,
                        base_delay: float = 1.0) -> RetryManager:
    """创建重试管理器的工厂函数"""
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay
    )
    return RetryManager(cache_manager, config)