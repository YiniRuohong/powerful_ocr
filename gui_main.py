#!/usr/bin/env python3
"""
GUI版本的OCR程序
使用tkinter实现可视化界面
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
import sys
from pathlib import Path
from typing import List, Optional, Callable
import queue
import time

# 导入原有的OCR功能
from main import (
    get_pdf_files, get_terminology_files, load_terminology,
    get_pdf_page_count, process_single_file, ocr_manager,
    DASHSCOPE_API_KEY, GEMINI_API_KEY, GEMINI_BASE_URL
)

# 我们将创建一个带回调的处理函数
def process_single_file_with_callback(pdf_path, start_page, end_page, terminology_terms, ocr_service_key, progress_callback=None):
    """带进度回调的文件处理函数"""
    from main import process_single_file_with_progress_callback
    return process_single_file_with_progress_callback(pdf_path, start_page, end_page, terminology_terms, ocr_service_key, progress_callback)


class OCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("增强版OCR程序")
        self.root.geometry("900x800")
        
        # 设置窗口样式
        self.setup_window_style()
        
        # 消息队列用于线程间通信
        self.message_queue = queue.Queue()
        
        # 变量
        self.selected_pdfs = []
        self.selected_terminology = None
        self.terminology_terms = ""
        self.selected_ocr_service = "dashscope"  # 默认OCR服务
        
        # Token统计变量
        self.total_tokens = 0
        self.ocr_tokens = 0
        self.gemini_tokens = 0
        self.current_page = 0
        self.total_pages = 0
        
        self.setup_ui()
        self.refresh_files()
        
        # 启动消息处理
        self.root.after(50, self.process_queue)  # 更频繁的更新
    
    def setup_window_style(self):
        """设置现代化窗口样式"""
        # 设置现代化颜色方案
        self.colors = {
            'bg': '#FFFFFF',           # 白色背景
            'secondary_bg': '#F8F9FA', # 次级背景（浅灰）
            'accent': '#007AFF',       # iOS风格蓝色
            'success': '#34C759',      # 成功绿色
            'warning': '#FF9500',      # 警告橙色
            'error': '#FF3B30',        # 错误红色
            'text': '#1D1D1F',         # 主文本
            'text_secondary': '#86868B', # 次级文本
            'border': '#E5E5E7',       # 边框颜色
            'hover': '#F2F2F7',        # 悬停效果
        }
        
        self.root.configure(bg=self.colors['bg'])
        
        # 配置现代化样式
        style = ttk.Style()
        
        # 配置按钮样式 - iOS风格
        style.configure('Modern.TButton',
                       background=self.colors['accent'],
                       foreground='white',
                       borderwidth=0,
                       focuscolor='none',
                       font=('SF Pro Display', 13, 'normal') if sys.platform == 'darwin' else ('Segoe UI', 10, 'normal'),
                       padding=(20, 10))
        
        style.map('Modern.TButton',
                  background=[('active', '#0051D5'),  # 深蓝色悬停
                             ('pressed', '#004FC7')],
                  relief=[('pressed', 'flat')])
        
        # 配置次级按钮样式
        style.configure('Secondary.TButton',
                       background=self.colors['secondary_bg'],
                       foreground=self.colors['text'],
                       borderwidth=1,
                       relief='solid',
                       focuscolor='none',
                       font=('SF Pro Display', 13, 'normal') if sys.platform == 'darwin' else ('Segoe UI', 10, 'normal'),
                       padding=(16, 8))
        
        style.map('Secondary.TButton',
                  background=[('active', self.colors['hover']),
                             ('pressed', '#E8E8ED')],
                  bordercolor=[('focus', self.colors['accent'])])
        
        # 配置LabelFrame样式
        style.configure('Modern.TLabelframe',
                       background=self.colors['bg'],
                       borderwidth=1,
                       relief='solid',
                       bordercolor=self.colors['border'])
        
        style.configure('Modern.TLabelframe.Label',
                       background=self.colors['bg'],
                       foreground=self.colors['text'],
                       font=('SF Pro Display', 14, 'bold') if sys.platform == 'darwin' else ('Segoe UI', 11, 'bold'))
        
        # 配置进度条样式
        style.configure('Modern.Horizontal.TProgressbar',
                       background=self.colors['accent'],
                       troughcolor=self.colors['secondary_bg'],
                       borderwidth=0,
                       lightcolor=self.colors['accent'],
                       darkcolor=self.colors['accent'])
        
        # 配置Combobox样式
        style.configure('Modern.TCombobox',
                       fieldbackground=self.colors['secondary_bg'],
                       background=self.colors['bg'],
                       bordercolor=self.colors['border'],
                       arrowcolor=self.colors['text_secondary'],
                       focuscolor=self.colors['accent'],
                       font=('SF Pro Display', 12, 'normal') if sys.platform == 'darwin' else ('Segoe UI', 10, 'normal'))
        
        # 配置Spinbox样式
        style.configure('Modern.TSpinbox',
                       fieldbackground=self.colors['secondary_bg'],
                       bordercolor=self.colors['border'],
                       focuscolor=self.colors['accent'],
                       font=('SF Pro Display', 12, 'normal') if sys.platform == 'darwin' else ('Segoe UI', 10, 'normal'))
    
    def setup_ui(self):
        # 顶部容器 - 现代化标题区域
        header_frame = tk.Frame(self.root, bg=self.colors['bg'], height=80)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        # 主标题 - 使用系统字体
        title_font = ('SF Pro Display', 28, 'bold') if sys.platform == 'darwin' else ('Segoe UI', 22, 'bold')
        title_label = tk.Label(header_frame, 
                              text="智能OCR处理器", 
                              font=title_font,
                              fg=self.colors['text'],
                              bg=self.colors['bg'])
        title_label.pack(pady=(20, 5))
        
        # 副标题 - 更现代的描述
        subtitle_font = ('SF Pro Display', 14, 'normal') if sys.platform == 'darwin' else ('Segoe UI', 11, 'normal')
        subtitle_label = tk.Label(header_frame, 
                                 text="多引擎OCR + AI智能纠错 + Markdown格式化", 
                                 font=subtitle_font,
                                 fg=self.colors['text_secondary'],
                                 bg=self.colors['bg'])
        subtitle_label.pack()
        
        # 添加分隔线
        separator = tk.Frame(self.root, height=1, bg=self.colors['border'])
        separator.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # 主内容容器 - 使用卡片式布局
        main_container = tk.Frame(self.root, bg=self.colors['bg'])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=0)
        
        # 文件选择卡片
        file_card = self.create_card(main_container, "PDF文件选择", "📄")
        file_card.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # PDF文件列表
        pdf_list_frame = tk.Frame(file_card, bg=self.colors['bg'])
        pdf_list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # 列表标题
        list_label = tk.Label(pdf_list_frame, 
                             text="选择要处理的PDF文件", 
                             font=('SF Pro Display', 13, 'normal') if sys.platform == 'darwin' else ('Segoe UI', 10, 'bold'),
                             fg=self.colors['text'],
                             bg=self.colors['bg'])
        list_label.pack(anchor=tk.W, pady=(0, 10))
        
        # 现代化列表框
        self.pdf_listbox = tk.Listbox(pdf_list_frame, 
                                     selectmode=tk.MULTIPLE, 
                                     height=6,
                                     bg=self.colors['secondary_bg'],
                                     fg=self.colors['text'],
                                     selectbackground=self.colors['accent'],
                                     selectforeground='white',
                                     borderwidth=1,
                                     relief='solid',
                                     highlightthickness=0,
                                     font=('SF Pro Text', 12, 'normal') if sys.platform == 'darwin' else ('Segoe UI', 9, 'normal'))
        self.pdf_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # 按钮组 - 现代化水平布局
        pdf_button_frame = tk.Frame(pdf_list_frame, bg=self.colors['bg'])
        pdf_button_frame.pack(fill=tk.X)
        
        # 使用现代化按钮样式
        refresh_btn = ttk.Button(pdf_button_frame, text="刷新列表", command=self.refresh_files, style='Secondary.TButton')
        refresh_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        browse_btn = ttk.Button(pdf_button_frame, text="浏览文件", command=self.browse_pdf, style='Secondary.TButton')
        browse_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        select_all_btn = ttk.Button(pdf_button_frame, text="全选", command=self.select_all_pdfs, style='Secondary.TButton')
        select_all_btn.pack(side=tk.LEFT)
        
        # 配置区域 - 网格布局
        config_container = tk.Frame(main_container, bg=self.colors['bg'])
        config_container.pack(fill=tk.X, pady=(0, 15))
        
        # OCR服务选择卡片
        ocr_card = self.create_card(config_container, "OCR引擎", "⚙️")
        ocr_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # OCR服务内容
        ocr_content = tk.Frame(ocr_card, bg=self.colors['bg'])
        ocr_content.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        self.ocr_var = tk.StringVar()
        self.ocr_combo = ttk.Combobox(ocr_content, textvariable=self.ocr_var, state="readonly", style='Modern.TCombobox')
        self.ocr_combo.pack(fill=tk.X)
        self.ocr_combo.bind('<<ComboboxSelected>>', self.on_ocr_selected)
        
        # 专有名词文件选择卡片
        terminology_card = self.create_card(config_container, "专业词典", "📝")
        terminology_card.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 专有名词内容
        terminology_content = tk.Frame(terminology_card, bg=self.colors['bg'])
        terminology_content.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        self.terminology_var = tk.StringVar(value="不使用专有名词文件")
        self.terminology_combo = ttk.Combobox(terminology_content, textvariable=self.terminology_var, state="readonly", style='Modern.TCombobox')
        self.terminology_combo.pack(fill=tk.X)
        self.terminology_combo.bind('<<ComboboxSelected>>', self.on_terminology_selected)
        
        # 页数范围设置卡片
        page_card = self.create_card(main_container, "页面范围", "📄")
        page_card.pack(fill=tk.X, pady=(0, 15))
        
        # 页数控制内容
        page_content = tk.Frame(page_card, bg=self.colors['bg'])
        page_content.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # 页数控制区域
        page_controls_frame = tk.Frame(page_content, bg=self.colors['bg'])
        page_controls_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 起始页
        start_frame = tk.Frame(page_controls_frame, bg=self.colors['bg'])
        start_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        start_label = tk.Label(start_frame, text="起始页", 
                              font=('SF Pro Text', 12, 'normal') if sys.platform == 'darwin' else ('Segoe UI', 10, 'normal'),
                              fg=self.colors['text'], bg=self.colors['bg'])
        start_label.pack(anchor=tk.W)
        
        self.start_page_var = tk.IntVar(value=1)
        self.start_page_spin = ttk.Spinbox(start_frame, from_=1, to=9999, textvariable=self.start_page_var, 
                                          width=15, style='Modern.TSpinbox')
        self.start_page_spin.pack(fill=tk.X, pady=(5, 0))
        
        # 间隔
        tk.Frame(page_controls_frame, bg=self.colors['bg'], width=20).pack(side=tk.LEFT)
        
        # 结束页
        end_frame = tk.Frame(page_controls_frame, bg=self.colors['bg'])
        end_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        end_label = tk.Label(end_frame, text="结束页", 
                            font=('SF Pro Text', 12, 'normal') if sys.platform == 'darwin' else ('Segoe UI', 10, 'normal'),
                            fg=self.colors['text'], bg=self.colors['bg'])
        end_label.pack(anchor=tk.W)
        
        self.end_page_var = tk.IntVar(value=1)
        self.end_page_spin = ttk.Spinbox(end_frame, from_=1, to=9999, textvariable=self.end_page_var, 
                                        width=15, style='Modern.TSpinbox')
        self.end_page_spin.pack(fill=tk.X, pady=(5, 0))
        
        # 页面信息显示
        self.page_info_label = tk.Label(page_content, text="请先选择PDF文件",
                                       font=('SF Pro Text', 11, 'normal') if sys.platform == 'darwin' else ('Segoe UI', 9, 'normal'),
                                       fg=self.colors['text_secondary'], bg=self.colors['bg'])
        self.page_info_label.pack(anchor=tk.W)
        
        # 绑定PDF选择事件
        self.pdf_listbox.bind('<<ListboxSelect>>', self.on_pdf_selected)
        
        # 控制按钮区域 - 粘在底部的现代化按钮
        control_container = tk.Frame(self.root, bg=self.colors['bg'])
        control_container.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # 主控制按钮
        control_frame = tk.Frame(control_container, bg=self.colors['bg'])
        control_frame.pack(fill=tk.X)
        
        self.start_button = ttk.Button(control_frame, text="开始处理", command=self.start_processing, style='Modern.TButton')
        self.start_button.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.stop_button = ttk.Button(control_frame, text="停止处理", command=self.stop_processing, state=tk.DISABLED, style='Secondary.TButton')
        self.stop_button.pack(side=tk.RIGHT)
        
        # 进度显示卡片
        progress_card = self.create_card(main_container, "处理进度", "📊")
        progress_card.pack(fill=tk.X, pady=(0, 15))
        
        # 进度内容
        progress_content = tk.Frame(progress_card, bg=self.colors['bg'])
        progress_content.pack(fill=tk.X, padx=20, pady=(0, 20))
        
        # 进度标签
        self.progress_label = tk.Label(progress_content, text="准备就绪",
                                      font=('SF Pro Text', 12, 'normal') if sys.platform == 'darwin' else ('Segoe UI', 10, 'normal'),
                                      fg=self.colors['text'], bg=self.colors['bg'])
        self.progress_label.pack(anchor=tk.W, pady=(0, 8))
        
        # 现代化进度条
        self.progress_bar = ttk.Progressbar(progress_content, mode='determinate', style='Modern.Horizontal.TProgressbar')
        self.progress_bar.pack(fill=tk.X, pady=(0, 15))
        
        # Token统计网格布局
        stats_grid = tk.Frame(progress_content, bg=self.colors['bg'])
        stats_grid.pack(fill=tk.X)
        
        # 总用量Token
        total_token_frame = tk.Frame(stats_grid, bg=self.colors['secondary_bg'], relief='solid', bd=1)
        total_token_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        tk.Label(total_token_frame, text="总用量", 
                font=('SF Pro Text', 10, 'normal') if sys.platform == 'darwin' else ('Segoe UI', 8, 'bold'),
                fg=self.colors['text_secondary'], bg=self.colors['secondary_bg']).pack(pady=(8, 2))
        
        self.token_label = tk.Label(total_token_frame, text="0", 
                                   font=('SF Pro Display', 16, 'bold') if sys.platform == 'darwin' else ('Segoe UI', 14, 'bold'),
                                   fg=self.colors['accent'], bg=self.colors['secondary_bg'])
        self.token_label.pack(pady=(0, 8))
        
        # OCR Token
        ocr_token_frame = tk.Frame(stats_grid, bg=self.colors['secondary_bg'], relief='solid', bd=1)
        ocr_token_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2.5)
        
        tk.Label(ocr_token_frame, text="OCR", 
                font=('SF Pro Text', 10, 'normal') if sys.platform == 'darwin' else ('Segoe UI', 8, 'bold'),
                fg=self.colors['text_secondary'], bg=self.colors['secondary_bg']).pack(pady=(8, 2))
        
        self.ocr_token_label = tk.Label(ocr_token_frame, text="0", 
                                       font=('SF Pro Display', 16, 'bold') if sys.platform == 'darwin' else ('Segoe UI', 14, 'bold'),
                                       fg=self.colors['success'], bg=self.colors['secondary_bg'])
        self.ocr_token_label.pack(pady=(0, 8))
        
        # 纠错Token
        gemini_token_frame = tk.Frame(stats_grid, bg=self.colors['secondary_bg'], relief='solid', bd=1)
        gemini_token_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        tk.Label(gemini_token_frame, text="AI纠错", 
                font=('SF Pro Text', 10, 'normal') if sys.platform == 'darwin' else ('Segoe UI', 8, 'bold'),
                fg=self.colors['text_secondary'], bg=self.colors['secondary_bg']).pack(pady=(8, 2))
        
        self.gemini_token_label = tk.Label(gemini_token_frame, text="0", 
                                          font=('SF Pro Display', 16, 'bold') if sys.platform == 'darwin' else ('Segoe UI', 14, 'bold'),
                                          fg=self.colors['warning'], bg=self.colors['secondary_bg'])
        self.gemini_token_label.pack(pady=(0, 8))
        
        # 页面进度显示 - 单独一行
        page_info_frame = tk.Frame(progress_content, bg=self.colors['bg'])
        page_info_frame.pack(fill=tk.X, pady=(15, 0))
        
        self.page_progress_label = tk.Label(page_info_frame, text="页面: 0/0", 
                                           font=('SF Pro Text', 11, 'normal') if sys.platform == 'darwin' else ('Segoe UI', 9, 'normal'),
                                           fg=self.colors['text_secondary'], bg=self.colors['bg'])
        self.page_progress_label.pack(anchor=tk.W)
        
        # 日志输出卡片
        log_card = self.create_card(main_container, "处理日志", "📝")
        log_card.pack(fill=tk.BOTH, expand=True)
        
        # 日志内容
        log_content = tk.Frame(log_card, bg=self.colors['bg'])
        log_content.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        
        # 现代化日志文本框
        self.log_text = scrolledtext.ScrolledText(log_content, 
                                                 height=8, 
                                                 wrap=tk.WORD, 
                                                 font=('SF Mono', 11, 'normal') if sys.platform == 'darwin' else ('Consolas', 9, 'normal'),
                                                 bg=self.colors['secondary_bg'],
                                                 fg=self.colors['text'],
                                                 borderwidth=1,
                                                 relief='solid',
                                                 highlightthickness=0,
                                                 insertbackground=self.colors['accent'])
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 设置现代化日志颜色
        self.log_text.tag_configure("success", foreground=self.colors['success'])
        self.log_text.tag_configure("error", foreground=self.colors['error'])
        self.log_text.tag_configure("info", foreground=self.colors['accent'])
        self.log_text.tag_configure("token", foreground=self.colors['warning'], 
                                   font=('SF Mono', 11, 'bold') if sys.platform == 'darwin' else ('Consolas', 9, 'bold'))
    
    def refresh_files(self):
        """刷新文件列表"""
        # 刷新PDF文件列表
        pdf_files = get_pdf_files()
        self.pdf_listbox.delete(0, tk.END)
        self.pdf_files = pdf_files
        
        for pdf_file in pdf_files:
            self.pdf_listbox.insert(tk.END, pdf_file.name)
        
        # 刷新OCR服务列表
        available_services = ocr_manager.get_available_services()
        ocr_options = []
        ocr_keys = []
        
        for key, service in available_services.items():
            ocr_options.append(service.get_description())
            ocr_keys.append(key)
        
        self.ocr_combo['values'] = ocr_options
        self.ocr_keys = ocr_keys
        
        # 设置默认选择
        if ocr_options:
            self.ocr_combo.set(ocr_options[0])
            self.selected_ocr_service = ocr_keys[0]
        
        # 刷新专有名词文件列表
        terminology_files = get_terminology_files()
        terminology_options = ["不使用专有名词文件"] + [f.name for f in terminology_files]
        self.terminology_combo['values'] = terminology_options
        self.terminology_files = terminology_files
        
        self.log(f"找到 {len(pdf_files)} 个PDF文件，{len(terminology_files)} 个专有名词文件，{len(available_services)} 个可用OCR服务")
    
    def browse_pdf(self):
        """浏览并选择PDF文件"""
        files = filedialog.askopenfilenames(
            title="选择PDF文件",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialdir=Path("input") if Path("input").exists() else Path.cwd()
        )
        
        if files:
            # 将选择的文件复制到input目录
            input_dir = Path("input")
            input_dir.mkdir(exist_ok=True)
            
            for file_path in files:
                src_path = Path(file_path)
                dst_path = input_dir / src_path.name
                
                if not dst_path.exists():
                    import shutil
                    shutil.copy2(src_path, dst_path)
                    self.log(f"已复制文件到input目录: {src_path.name}")
            
            self.refresh_files()
    
    def select_all_pdfs(self):
        """全选PDF文件"""
        self.pdf_listbox.select_set(0, tk.END)
        self.on_pdf_selected()
    
    def on_pdf_selected(self, event=None):
        """PDF文件选择事件"""
        selected_indices = self.pdf_listbox.curselection()
        if not selected_indices:
            self.page_info_label.config(text="请先选择PDF文件")
            return
        
        # 获取第一个选择的文件的页数信息
        first_idx = selected_indices[0]
        pdf_path = self.pdf_files[first_idx]
        page_count = get_pdf_page_count(pdf_path)
        
        if page_count > 0:
            # 只有在结束页为1时才设置为页数，避免覆盖用户修改的值
            if self.end_page_var.get() == 1:
                self.end_page_var.set(min(10, page_count))  # 默认设为10页或文件总页数，取较小值
            self.start_page_spin.config(to=page_count)
            self.end_page_spin.config(to=page_count)
            
            if len(selected_indices) == 1:
                self.page_info_label.config(text=f"文件 '{pdf_path.name}' 共有 {page_count} 页")
            else:
                self.page_info_label.config(text=f"已选择 {len(selected_indices)} 个文件（以第一个文件页数为准）")
        else:
            self.page_info_label.config(text="无法读取PDF页数信息")
    
    def on_ocr_selected(self, event=None):
        """OCR服务选择事件"""
        selected_description = self.ocr_var.get()
        # 根据描述找到对应的服务键
        for i, description in enumerate(self.ocr_combo['values']):
            if description == selected_description:
                self.selected_ocr_service = self.ocr_keys[i]
                break
        
        self.log(f"OCR服务: {selected_description}")
    
    def on_terminology_selected(self, event=None):
        """专有名词文件选择事件"""
        selected = self.terminology_var.get()
        if selected == "不使用专有名词文件":
            self.selected_terminology = None
            self.terminology_terms = ""
        else:
            # 找到对应的文件
            for file in self.terminology_files:
                if file.name == selected:
                    self.selected_terminology = file
                    self.terminology_terms = load_terminology(file)
                    break
        
        self.log(f"专有名词文件: {selected}")
    
    def log(self, message, tag=None):
        """添加日志消息"""
        timestamp = time.strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        if tag:
            self.log_text.insert(tk.END, formatted_message, tag)
        else:
            self.log_text.insert(tk.END, formatted_message)
        
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def start_processing(self):
        """开始处理"""
        # 验证输入
        selected_indices = self.pdf_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("警告", "请先选择要处理的PDF文件")
            return
        
        start_page = self.start_page_var.get()
        end_page = self.end_page_var.get()
        
        if start_page > end_page:
            messagebox.showwarning("警告", "起始页不能大于结束页")
            return
        
        # 禁用开始按钮，启用停止按钮
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # 清空日志
        self.log_text.delete(1.0, tk.END)
        
        # 获取选择的文件
        selected_files = [self.pdf_files[i] for i in selected_indices]
        
        # 在新线程中处理
        self.processing_thread = threading.Thread(
            target=self.process_files_thread,
            args=(selected_files, start_page, end_page),
            daemon=True
        )
        self.processing_thread.start()
    
    def create_progress_callback(self):
        """创建进度回调函数"""
        def callback(msg_type, data, **kwargs):
            """进度回调函数"""
            if msg_type == 'page_start':
                page_idx, total_pages = data
                self.message_queue.put(('page_progress', page_idx + 1, total_pages))
            elif msg_type == 'ocr_token':
                tokens = data
                self.message_queue.put(('ocr_token_update', tokens))
            elif msg_type == 'gemini_token':
                tokens = data
                self.message_queue.put(('gemini_token_update', tokens))
            elif msg_type == 'page_complete':
                page_idx = data
                self.message_queue.put(('page_complete', page_idx))
            elif msg_type == 'streaming_token':
                token_data = data
                self.message_queue.put(('streaming_token', token_data))
            elif msg_type == 'log':
                message = data
                tag = kwargs.get('tag', None)
                self.message_queue.put(('log_tagged', message, tag))
        
        return callback
    
    def process_files_thread(self, selected_files, start_page, end_page):
        """在线程中处理文件"""
        try:
            total_files = len(selected_files)
            progress_callback = self.create_progress_callback()
            
            for i, pdf_path in enumerate(selected_files):
                if hasattr(self, 'stop_processing_flag') and self.stop_processing_flag:
                    break
                
                # 更新文件进度
                file_progress = (i / total_files) * 100
                self.message_queue.put(('file_progress', file_progress, f"正在处理: {pdf_path.name}"))
                
                # 重置Token统计
                self.message_queue.put(('reset_tokens', None))
                
                # 处理单个文件
                try:
                    result = process_single_file_with_callback(
                        pdf_path, start_page, end_page, 
                        self.terminology_terms, self.selected_ocr_service,
                        progress_callback
                    )
                    self.message_queue.put(('log', f"✅ {pdf_path.name} 处理完成", "success"))
                except Exception as e:
                    self.message_queue.put(('log', f"❌ {pdf_path.name} 处理失败: {e}", "error"))
            
            # 处理完成
            self.message_queue.put(('progress', 100, "处理完成"))
            self.message_queue.put(('log', "🎉 全部文件处理完成！", "success"))
            self.message_queue.put(('complete', None))
            
        except Exception as e:
            self.message_queue.put(('error', f"处理过程中发生错误: {e}"))
            self.message_queue.put(('complete', None))
    
    def stop_processing(self):
        """停止处理"""
        self.stop_processing_flag = True
        self.log("⏹️ 正在停止处理...")
    
    def create_card(self, parent, title, icon):
        """创建现代化卡片布局"""
        # 卡片容器
        card = tk.Frame(parent, bg=self.colors['bg'], relief='solid', bd=1, highlightbackground=self.colors['border'])
        
        # 卡片头部
        header = tk.Frame(card, bg=self.colors['bg'], height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        # 标题容器
        title_container = tk.Frame(header, bg=self.colors['bg'])
        title_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)
        
        # 图标和标题
        title_frame = tk.Frame(title_container, bg=self.colors['bg'])
        title_frame.pack(anchor=tk.W)
        
        # 图标
        icon_label = tk.Label(title_frame, text=icon, 
                             font=('SF Pro Display', 16, 'normal') if sys.platform == 'darwin' else ('Segoe UI', 14, 'normal'),
                             fg=self.colors['accent'], bg=self.colors['bg'])
        icon_label.pack(side=tk.LEFT, padx=(0, 8))
        
        # 标题
        title_label = tk.Label(title_frame, text=title, 
                              font=('SF Pro Display', 16, 'bold') if sys.platform == 'darwin' else ('Segoe UI', 13, 'bold'),
                              fg=self.colors['text'], bg=self.colors['bg'])
        title_label.pack(side=tk.LEFT)
        
        # 分隔线
        separator = tk.Frame(card, height=1, bg=self.colors['border'])
        separator.pack(fill=tk.X, padx=20)
        
        return card
    
    def update_token_display(self):
        """更新Token显示 - 现代化风格"""
        # 更新各个Token显示
        self.token_label.config(text=f"{self.total_tokens:,}")
        self.ocr_token_label.config(text=f"{self.ocr_tokens:,}")
        self.gemini_token_label.config(text=f"{self.gemini_tokens:,}")
        
        # 更新页面进度
        if self.total_pages > 0:
            page_display = f"页面: {self.current_page}/{self.total_pages}"
            self.page_progress_label.config(text=page_display)
    
    def process_queue(self):
        """处理消息队列"""
        processed_messages = 0
        max_messages_per_cycle = 10  # 限制每次处理的消息数量
        
        try:
            while processed_messages < max_messages_per_cycle:
                try:
                    msg_type, data, *extra = self.message_queue.get_nowait()
                    processed_messages += 1
                except queue.Empty:
                    break
                
                if msg_type == 'log':
                    self.log(data)
                elif msg_type == 'log_tagged':
                    message, tag = data, extra[0] if extra else None
                    self.log(message, tag)
                elif msg_type == 'progress':
                    progress, label = data, extra[0] if extra else ""
                    self.progress_bar['value'] = progress
                    self.progress_label.config(text=label)
                elif msg_type == 'file_progress':
                    progress, label = data, extra[0] if extra else ""
                    self.progress_bar['value'] = progress
                    self.progress_label.config(text=label)
                elif msg_type == 'page_progress':
                    current_page, total_pages = data, extra[0]
                    self.current_page = current_page
                    self.total_pages = total_pages
                    self.update_token_display()
                elif msg_type == 'reset_tokens':
                    self.total_tokens = 0
                    self.ocr_tokens = 0
                    self.gemini_tokens = 0
                    self.current_page = 0
                    self.total_pages = 0
                    self.update_token_display()
                elif msg_type == 'ocr_token_update':
                    tokens = data
                    self.ocr_tokens += tokens.get('total_tokens', 0)
                    self.total_tokens += tokens.get('total_tokens', 0)
                    self.update_token_display()
                    # 记录Token使用
                    input_tokens = tokens.get('input_tokens', 0)
                    output_tokens = tokens.get('output_tokens', 0)
                    total_tokens = tokens.get('total_tokens', input_tokens + output_tokens)
                    self.log(f"📊 OCR Token: {total_tokens:,} (输入: {input_tokens:,}, 输出: {output_tokens:,})", "token")
                elif msg_type == 'gemini_token_update':
                    tokens = data
                    self.gemini_tokens += tokens.get('total_tokens', 0)
                    self.total_tokens += tokens.get('total_tokens', 0)
                    self.update_token_display()
                    # 记录Token使用
                    input_tokens = tokens.get('input_tokens', 0)
                    output_tokens = tokens.get('output_tokens', 0)
                    total_tokens = tokens.get('total_tokens', input_tokens + output_tokens)
                    self.log(f"📊 Gemini Token: {total_tokens:,} (输入: {input_tokens:,}, 输出: {output_tokens:,})", "token")
                elif msg_type == 'streaming_token':
                    # 实时流式Token更新
                    token_data = data
                    service_name = token_data.get('service', 'Unknown')
                    tokens = token_data.get('tokens', 0)
                    if tokens > 0:
                        self.log(f"⚡ {service_name} 流式Token: +{tokens}", "info")
                elif msg_type == 'page_complete':
                    page_idx = data
                    self.log(f"✅ 第 {page_idx + 1} 页处理完成", "success")
                elif msg_type == 'error':
                    self.log(f"❌ {data}", "error")
                    messagebox.showerror("错误", data)
                elif msg_type == 'complete':
                    self.start_button.config(state=tk.NORMAL)
                    self.stop_button.config(state=tk.DISABLED)
                    if hasattr(self, 'stop_processing_flag'):
                        delattr(self, 'stop_processing_flag')
                
        except Exception as e:
            print(f"Error processing queue: {e}")
        
        # 继续处理队列，更高频率的更新
        self.root.after(50, self.process_queue)


def check_dependencies():
    """检查依赖项"""
    missing_deps = []
    
    # 检查API密钥
    if not DASHSCOPE_API_KEY:
        missing_deps.append("DASHSCOPE_API_KEY 未设置")
    if not GEMINI_API_KEY:
        missing_deps.append("GEMINI_API_KEY 未设置")
    if not GEMINI_BASE_URL:
        missing_deps.append("GEMINI_BASE_URL 未设置")
    
    # 检查必要的包
    try:
        import pdf2image
    except ImportError:
        missing_deps.append("pdf2image 包未安装")
    
    try:
        import pypdf
    except ImportError:
        missing_deps.append("pypdf 包未安装")
    
    try:
        import openai
    except ImportError:
        missing_deps.append("openai 包未安装")
    
    # 检查poppler
    try:
        from pdf2image import convert_from_path
        # 尝试转换一个测试文件（如果没有会报错）
    except Exception as e:
        if "poppler" in str(e).lower():
            missing_deps.append("Poppler 未安装 (macOS: brew install poppler)")
    
    return missing_deps


def main():
    """主函数"""
    # 检查依赖
    missing_deps = check_dependencies()
    
    root = tk.Tk()
    
    if missing_deps:
        # 显示依赖检查结果
        dep_window = tk.Toplevel(root)
        dep_window.title("依赖检查")
        dep_window.geometry("500x300")
        dep_window.transient(root)
        dep_window.grab_set()
        
        ttk.Label(dep_window, text="⚠️ 发现以下问题:", font=("Arial", 12, "bold")).pack(pady=10)
        
        text_widget = scrolledtext.ScrolledText(dep_window, height=10, wrap=tk.WORD)
        text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        for dep in missing_deps:
            text_widget.insert(tk.END, f"• {dep}\n")
        
        text_widget.config(state=tk.DISABLED)
        
        def close_app():
            root.quit()
        
        def continue_anyway():
            dep_window.destroy()
        
        button_frame = ttk.Frame(dep_window)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="退出程序", command=close_app).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="仍然继续", command=continue_anyway).pack(side=tk.LEFT, padx=5)
        
        root.wait_window(dep_window)
    
    # 启动主程序
    try:
        app = OCRApp(root)
        root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()