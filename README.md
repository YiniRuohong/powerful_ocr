# Powerful OCR - 智能PDF文字识别工具

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-009688.svg)](https://fastapi.tiangolo.com/)

一个功能强大的PDF文字识别工具，采用灵活的多OCR架构：支持**阿里云DashScope**、**Mistral**、**自定义OpenAI格式**等多种OCR服务 + **Google Gemini智能纠错**，提供高精度的文字识别和智能格式化功能。

## ✨ 主要特性

- 🔥 **多OCR服务支持**：DashScope、Mistral、自定义OpenAI格式API，可灵活选择
- 🧠 **智能纠错架构**：Gemini AI进行OCR后文本纠错与结构识别
- 📋 **交互式界面**：OCR服务选择、文件选择、页数范围配置、专有名词纠错
- 📊 **实时进度追踪**：显示页数进度和Token消耗统计（分OCR和纠错）
- 📝 **Markdown输出**：自动识别文档结构并格式化为标准Markdown
- 🎯 **专有名词纠错**：支持自定义术语库进行精准纠错
- 🖥️ **多运行模式**：智能启动器支持CLI和GUI模式
- 📁 **批量处理**：支持单文件或批量处理多个PDF文件

## 🚀 快速开始

### 系统要求

- **Python**: ≥3.13 (项目使用最新特性)
- **Poppler**: PDF处理依赖
  - macOS: `brew install poppler`
  - Ubuntu/Debian: `sudo apt install poppler-utils`

### 安装步骤

1. **克隆项目**
   ```bash
   git clone https://github.com/YiniRuohong/powerful_ocr.git
   cd powerful_ocr
   ```

2. **安装依赖**
   ```bash
   uv sync
   ```

3. **配置API密钥**
   
   复制 `.env.example` 为 `.env` 并配置API密钥：
   ```bash
   cp .env.example .env
   ```
   
   编辑 `.env` 文件，配置所需的API服务：
   ```env
   # Gemini纠错服务 (必需)
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_BASE_URL=your_gemini_base_url_here
   
   # OCR服务 (至少配置一个)
   DASHSCOPE_API_KEY=your_dashscope_api_key_here
   MISTRAL_API_KEY=your_mistral_api_key_here
   CUSTOM_OCR_API_KEY=your_custom_ocr_api_key_here
   CUSTOM_OCR_BASE_URL=your_custom_ocr_base_url_here
   ```

4. **准备PDF文件**
   
   将PDF文件放入 `input/` 目录（程序会自动创建）

## 📖 使用方法

### 本地运行

#### 智能启动器（推荐）

```bash
# 自动选择最佳运行模式
python launcher.py

# 强制使用命令行模式
python launcher.py cli

# 强制使用Web界面模式
python launcher.py web

# 强制使用图形界面模式
python launcher.py gui
```

#### 直接运行

```bash
# 命令行模式（交互式）
python main.py

# Web界面模式
python backend.py

# 图形界面模式
python gui_main.py
```

### 🐳 Docker部署

#### 快速启动

```bash
# 使用docker-compose一键启动
docker-compose up -d

# 访问Web界面
open http://localhost:8000
```

#### 手动Docker构建

```bash
# 构建镜像
docker build -t powerful-ocr .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/input:/app/input \
  -v $(pwd)/ocr_output:/app/ocr_output \
  -v $(pwd)/terminology:/app/terminology \
  --env-file .env \
  --name powerful-ocr \
  powerful-ocr
```

#### 从GitHub Registry拉取

```bash
# 拉取最新镜像
docker pull ghcr.io/YiniRuohong/powerful-ocr:latest

# 运行容器
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/input:/app/input \
  -v $(pwd)/ocr_output:/app/ocr_output \
  -v $(pwd)/terminology:/app/terminology \
  --env-file .env \
  --name powerful-ocr \
  ghcr.io/YiniRuohong/powerful-ocr:latest
```

### 使用流程

1. **选择OCR服务**
   - 程序启动时显示可用的OCR服务
   - 选择最适合的OCR提供商（DashScope/Mistral/自定义）

2. **选择专有名词文件**（可选）
   - 在 `terminology/` 目录放置 `.txt` 文件
   - 每行一个专有名词，用于提高纠错精度

3. **选择PDF文件**
   - 程序自动扫描 `input/` 目录
   - 支持单文件或批量处理

4. **设置页数范围**
   - 自动检测PDF总页数
   - 灵活配置处理范围

5. **查看处理结果**
   - `ocr_output/` 目录中查看结果
   - 单页文件：`{文件名}_page_{页码}.md`
   - 合并文件：`{文件名}_combined.md`

## 📁 项目结构

```
powerful_ocr/
├── main.py              # 核心OCR处理程序
├── backend.py           # FastAPI Web服务器
├── gui_main.py          # 图形界面版本
├── launcher.py          # 智能启动器
├── web/                 # Web界面文件
├── input/               # PDF文件输入目录
├── terminology/         # 专有名词文件目录
├── ocr_output/          # 处理结果输出目录
├── .env                 # API配置文件
├── CLAUDE.md           # 开发指南
└── README.md           # 项目说明
```

## 🔧 配置说明

### API配置

#### 必需配置
| 配置项 | 说明 | 必需 |
|--------|------|------|
| `GEMINI_API_KEY` | Google Gemini API密钥 | ✅ |
| `GEMINI_BASE_URL` | Gemini API服务地址 | ✅ |

#### OCR服务配置（至少选择一个）
| 配置项 | 说明 | 服务商 |
|--------|------|--------|
| `DASHSCOPE_API_KEY` | 阿里云DashScope API密钥 | 阿里云 |
| `MISTRAL_API_KEY` | Mistral API密钥 | Mistral AI |
| `MISTRAL_BASE_URL` | Mistral API地址（可选，默认官方API） | Mistral AI |
| `CUSTOM_OCR_API_KEY` | 自定义OCR服务API密钥 | 自定义 |
| `CUSTOM_OCR_BASE_URL` | 自定义OCR服务地址 | 自定义 |

### 专有名词配置

在 `terminology/` 目录创建 `.txt` 文件，每行一个专有名词：

```text
人工智能
机器学习
深度学习
神经网络
```

## 📊 功能特性详解

### 多OCR服务架构优势

1. **阿里云DashScope**: 专业OCR模型，高精度文字识别，特别适合中英文混合文档
2. **Mistral Pixtral**: 强大的多模态模型，优秀的多语言支持和复杂布局理解
3. **自定义服务**: 灵活支持GPT-4V、Claude 3等任何OpenAI兼容的视觉API
4. **Gemini纠错**: 智能错误修正和结构识别，统一的后处理流程

### OCR服务选择指南

- **精度优先**: 推荐DashScope，专门优化的OCR模型
- **多语言文档**: 推荐Mistral，强大的多模态理解能力
- **成本控制**: 可选择性价比最优的服务
- **特殊需求**: 使用自定义服务接入专用模型

### 实时进度监控

```
🔧 OCR服务: Mistral (pixtral-12b-2409)
处理 document.pdf [3/10页] [Token: 5,678]
📊 第 3 页 OCR Token消耗: 2,100 (输入: 1,800, 输出: 300)
📊 第 3 页 Gemini Token消耗: 1,450 (输入: 950, 输出: 500)
✓ 第 3 页处理完成
```

### 智能格式化

- 自动识别标题层级（H1-H6）
- 保持段落结构和换行
- 识别列表、引用等特殊格式
- 输出标准Markdown格式

## 🛠️ 开发相关

### 包管理

```bash
# 安装依赖
uv sync

# 添加新依赖
uv add <package-name>

# 更新依赖
uv sync --upgrade
```

### 虚拟环境

```bash
# 激活虚拟环境（如需要）
source .venv/bin/activate
```

### 🚀 CI/CD & 自动部署

项目配置了GitHub Actions自动构建和部署流程：

#### 自动构建Docker镜像

每次推送代码到主分支时，自动：
1. 构建Docker镜像
2. 运行测试
3. 推送到GitHub Container Registry
4. 创建版本标签

#### 部署到云服务器

```bash
# 在服务器上拉取最新镜像并重启
docker-compose pull
docker-compose up -d
```

#### 环境变量配置

在GitHub仓库的Settings -> Secrets中配置以下环境变量：

- `DOCKER_USERNAME`: Docker Hub用户名
- `DOCKER_PASSWORD`: Docker Hub密码
- `GHCR_TOKEN`: GitHub Container Registry访问令牌

#### 版本管理

```bash
# 创建新版本标签
git tag v1.0.0
git push origin v1.0.0

# 自动触发构建并推送到registry
```

## 📈 性能优化

- 支持300 DPI高清PDF转换
- 智能图像压缩和格式优化
- 流式API调用减少内存占用
- 批量处理提高效率

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📝 版本历史

- **v3.0.0** - 多OCR服务架构，支持DashScope/Mistral/自定义服务，GUI界面增强
- **v2.0.0** - 双AI架构，实时Token统计，Markdown输出
- **v1.0.0** - 基础OCR功能

## 📄 许可证

本项目基于 MIT 许可证开源 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🆘 常见问题

### Q: 没有可用的OCR服务？
A: 检查 `.env` 文件，确保至少配置了一个OCR服务的API密钥（DASHSCOPE_API_KEY、MISTRAL_API_KEY或自定义服务）

### Q: 如何选择OCR服务？
A: 
- **中英文文档**: 推荐DashScope，专业OCR模型精度高
- **多语言文档**: 推荐Mistral，多模态理解能力强
- **成本控制**: 比较各服务token价格选择最优方案
- **特殊需求**: 使用自定义服务接入GPT-4V等模型

### Q: Poppler安装失败？
A: 确保系统包管理器已更新，macOS用户可尝试 `brew doctor` 检查brew状态

### Q: API密钥配置错误？
A: 检查 `.env` 文件格式，确保没有多余空格和引号，参考 `.env.example` 示例

### Q: 处理大文件很慢？
A: 建议分批处理，或调整页数范围减少单次处理量

### Q: OCR识别精度不理想？
A: 
1. 尝试切换不同的OCR服务
2. 确保PDF文件清晰度足够
3. 使用专有名词文件提高纠错精度
4. 检查文档语言是否匹配OCR服务特长

---

⭐ 如果这个项目对你有帮助，请给个Star支持！