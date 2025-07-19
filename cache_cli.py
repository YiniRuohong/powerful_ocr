#!/usr/bin/env python3
"""
缓存管理命令行工具
提供缓存状态查看、清理等管理功能
"""

import argparse
import json
from pathlib import Path
from cache_manager import get_cache_manager
from retry_manager import create_retry_manager


def show_cache_stats():
    """显示缓存统计信息"""
    cache_manager = get_cache_manager()
    stats = cache_manager.get_stats()
    
    print("📊 缓存统计信息")
    print("=" * 50)
    print(f"总缓存条目: {stats['total_entries']}")
    print(f"总缓存大小: {stats['total_size_mb']:.2f} MB")
    print(f"最旧缓存: {stats['oldest_cache']}")
    print(f"最新缓存: {stats['newest_cache']}")
    print(f"总处理时间: {stats['total_processing_time']:.2f} 秒")
    print(f"总访问次数: {stats['total_access_count']}")
    
    print("\n📈 状态分布:")
    for status, count in stats['status_counts'].items():
        print(f"  {status}: {count}")
    
    print("\n⚙️ 配置:")
    config = stats['config']
    print(f"  最大缓存大小: {config['max_cache_size_gb']} GB")
    print(f"  最大缓存天数: {config['max_cache_age_days']} 天")
    print(f"  最大条目数: {config['max_entries']}")


def cleanup_cache():
    """清理缓存"""
    cache_manager = get_cache_manager()
    print("🧹 开始清理缓存...")
    
    stats = cache_manager.cleanup()
    
    print("✅ 缓存清理完成!")
    print(f"删除过期缓存: {stats['removed_expired']}")
    print(f"删除损坏缓存: {stats['removed_corrupted']}")
    print(f"删除旧缓存: {stats['removed_old']}")
    print(f"删除失败缓存: {stats['removed_failed']}")
    print(f"总删除数: {stats['total_removed']}")
    print(f"释放空间: {stats['bytes_freed']/1024/1024:.2f} MB")


def clear_all_cache():
    """清空所有缓存"""
    cache_manager = get_cache_manager()
    
    # 确认操作
    response = input("⚠️ 确定要清空所有缓存吗？这个操作不可恢复。(y/N): ").strip().lower()
    if response not in ['y', 'yes']:
        print("❌ 操作已取消")
        return
    
    if cache_manager.clear_all():
        print("✅ 所有缓存已清空")
    else:
        print("❌ 清空缓存失败")


def show_recovery_status():
    """显示恢复状态"""
    cache_manager = get_cache_manager()
    retry_manager = create_retry_manager(cache_manager)
    
    status = retry_manager.get_recovery_status()
    
    print("🔄 恢复状态信息")
    print("=" * 50)
    print(f"活跃处理: {len(status['active_processing'])}")
    print(f"失败处理: {len(status['failed_processing'])}")
    print(f"总状态文件: {status['total_states']}")
    
    if status['active_processing']:
        print("\n🟢 活跃处理:")
        for proc in status['active_processing']:
            print(f"  文件: {proc['file_path']}")
            print(f"  进度: {proc['progress']}")
            print(f"  最后更新: {proc['last_update']}")
            print()
    
    if status['failed_processing']:
        print("\n🔴 失败处理:")
        for proc in status['failed_processing']:
            print(f"  文件: {proc['file_path']}")
            print(f"  进度: {proc['progress']}")
            print(f"  失败页面: {proc['failed_pages']}")
            print(f"  重试次数: {proc['retry_attempts']}")
            print()


def cleanup_recovery_states():
    """清理旧的恢复状态"""
    cache_manager = get_cache_manager()
    retry_manager = create_retry_manager(cache_manager)
    
    hours = int(input("输入清理多少小时前的状态文件 (默认48): ").strip() or "48")
    
    removed_count = retry_manager.cleanup_old_states(hours)
    print(f"✅ 已清理 {removed_count} 个旧状态文件")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="缓存管理工具")
    parser.add_argument("command", choices=[
        "stats", "cleanup", "clear", "recovery", "cleanup-recovery"
    ], help="要执行的命令")
    
    args = parser.parse_args()
    
    try:
        if args.command == "stats":
            show_cache_stats()
        elif args.command == "cleanup":
            cleanup_cache()
        elif args.command == "clear":
            clear_all_cache()
        elif args.command == "recovery":
            show_recovery_status()
        elif args.command == "cleanup-recovery":
            cleanup_recovery_states()
            
    except Exception as e:
        print(f"❌ 命令执行失败: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())