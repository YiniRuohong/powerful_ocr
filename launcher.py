#!/usr/bin/env python3
"""
启动器 - 自动选择运行模式（CLI或GUI）
"""

import sys
import os
from pathlib import Path


def check_gui_support():
    """检查是否支持GUI模式"""
    try:
        import tkinter
        # 尝试创建一个隐藏的root窗口来测试
        root = tkinter.Tk()
        root.withdraw()
        root.destroy()
        return True
    except Exception:
        return False


def show_mode_selection():
    """显示模式选择"""
    print("🚀 OCR程序启动器")
    print("=" * 50)
    print("请选择运行模式:")
    print("  1. 命令行模式 (CLI)")
    print("  2. Web界面模式 (FastAPI) - 推荐")
    
    gui_available = check_gui_support()
    if gui_available:
        print("  3. 传统界面模式 (Tkinter GUI)")
        print("  4. 自动检测最佳模式")
    else:
        print("  3. 图形界面模式 (GUI) - ❌ 不可用")
    
    print()
    
    while True:
        try:
            if gui_available:
                choice = input("请选择 (1-4，默认为2): ").strip()
                if not choice:
                    choice = "2"
            else:
                choice = input("请选择 (1-2，默认为2): ").strip()
                if not choice:
                    choice = "2"
            
            choice_num = int(choice)
            
            if choice_num == 1:
                return "cli"
            elif choice_num == 2:
                return "web"
            elif choice_num == 3 and gui_available:
                return "tkinter_gui"
            elif choice_num == 4 and gui_available:
                # 自动检测模式 - 优先Web
                return "web"
            else:
                print("❌ 无效选择，请重新输入")
        except ValueError:
            print("❌ 请输入有效数字")


def run_cli_mode():
    """运行命令行模式"""
    print("\n🖥️  启动命令行模式...")
    try:
        from main import main
        main()
    except ImportError as e:
        print(f"❌ 无法导入命令行模块: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 运行时错误: {e}")
        sys.exit(1)


def run_web_mode():
    """运行Web界面模式"""
    print("\n🌐 启动Web界面模式...")
    try:
        import uvicorn
        print("📍 API文档: http://localhost:8000/docs")
        print("🌐 Web界面: http://localhost:8000")
        print("⏹️  按 Ctrl+C 停止服务")
        uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
    except ImportError as e:
        print(f"❌ 无法导入FastAPI模块: {e}")
        print("💡 请运行: uv add fastapi uvicorn")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 运行时错误: {e}")
        sys.exit(1)


def run_tkinter_gui_mode():
    """运行传统Tkinter GUI模式"""
    print("\n🖼️  启动传统界面模式...")
    try:
        from gui_main import main
        main()
    except ImportError as e:
        print(f"❌ 无法导入GUI模块: {e}")
        print("💡 请确保已安装tkinter包")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 运行时错误: {e}")
        sys.exit(1)


def main():
    """主启动函数"""
    # 检查命令行参数
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode in ["cli", "c", "command", "terminal"]:
            run_cli_mode()
            return
        elif mode in ["web", "w", "server", "api"]:
            run_web_mode()
            return
        elif mode in ["gui", "g", "window", "interface", "tkinter", "tk"]:
            if check_gui_support():
                run_tkinter_gui_mode()
                return
            else:
                print("❌ 系统不支持GUI模式，切换到Web模式")
                run_web_mode()
                return
        else:
            print(f"❌ 未知模式: {mode}")
            print("💡 支持的模式: cli, web, gui")
            sys.exit(1)
    
    # 交互式选择模式
    try:
        mode = show_mode_selection()
        
        if mode == "cli":
            run_cli_mode()
        elif mode == "web":
            run_web_mode()
        elif mode == "tkinter_gui":
            run_tkinter_gui_mode()
        else:
            print("❌ 未知模式")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n👋 用户取消操作")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()