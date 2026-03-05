#!/bin/bash
# =============================================================================
# NOVA Nanobody Filter - Environment Installation Script
# 纳米抗体过滤器 - 环境安装脚本
#
# Usage / 使用方法:
#   chmod +x install.sh
#   ./install.sh              # Full installation (may be slow)
#   ./install.sh --minimal    # Minimal installation (faster, recommended)
#   ./install.sh --docker     # Docker mode (quiet + non-interactive)
#
# This script creates a conda environment and installs pip packages using uv.
# 此脚本创建 conda 环境并使用 uv 安装 pip 包。
#
# Performance / 性能优化:
#   - Uses mamba if available (10-100x faster than conda)
#   - Uses uv for pip packages (10-100x faster than pip)
#   - 如果可用，使用 mamba（比 conda 快 10-100 倍）
#   - 使用 uv 安装 pip 包（比 pip 快 10-100 倍）
#
# References / 参考:
#   - environment.yml: Full conda environment
#   - environment-minimal.yml: Minimal conda packages (recommended)
#   - requirements.txt: Full pip packages
#   - requirements-minimal.txt: Minimal pip packages (abnativ, promb, TNP, PyTorch)
#   - docs/en/README.md: English documentation
#   - docs/cn/README.md: Chinese documentation
# =============================================================================

set -e  # Exit on error / 出错时退出

# Suppress conda plugin warnings (e.g., menuinst)
# 抑制 conda 插件警告（如 menuinst）
#export CONDA_NO_PLUGINS=true # disabled for now to avoid issues with conda-libmamba-solver

# Get script directory / 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Environment name (must match environment.yml) / 环境名称（必须与 environment.yml 匹配）
export ENV_NAME=metanano

# =============================================================================
# Output control / 输出控制
# =============================================================================
QUIET_MODE=false
YES_MODE=false

# Logging functions / 日志函数
log_info() {
    if [ "$QUIET_MODE" = false ]; then
        echo "$@"
    fi
}

log_header() {
    if [ "$QUIET_MODE" = false ]; then
        echo ""
        echo "=============================================="
        echo "$@"
        echo "=============================================="
        echo ""
    fi
}

log_error() {
    # Always show errors / 始终显示错误
    echo "ERROR: $@" >&2
}

log_success() {
    if [ "$QUIET_MODE" = false ]; then
        echo "✓ $@"
    fi
}

# Parse arguments / 解析参数
USE_MINIMAL=false
MAX_RETRIES=3
for arg in "$@"; do
    case $arg in
        --minimal|-m)
            USE_MINIMAL=true
            shift
            ;;
        --quiet|-q)
            QUIET_MODE=true
            shift
            ;;
        --yes|-y)
            YES_MODE=true
            shift
            ;;
        --docker|-d)
            # Docker mode: quiet + yes + minimal
            # Docker 模式：静默 + 自动确认 + 最小化
            QUIET_MODE=true
            YES_MODE=true
            USE_MINIMAL=true
            shift
            ;;
        --retries=*)
            MAX_RETRIES="${arg#*=}"
            shift
            ;;
        --help|-h)
            echo "Usage: ./install.sh [OPTIONS]"
            echo "用法: ./install.sh [选项]"
            echo ""
            echo "Options / 选项:"
            echo "  --minimal, -m     Use minimal environment (faster, recommended)"
            echo "                    使用最小环境（更快，推荐）"
            echo "  --quiet, -q       Quiet mode (minimal output)"
            echo "                    静默模式（最小输出）"
            echo "  --yes, -y         Non-interactive mode (auto-confirm all prompts)"
            echo "                    非交互模式（自动确认所有提示）"
            echo "  --docker, -d      Docker mode (combines --quiet --yes --minimal)"
            echo "                    Docker 模式（组合 --quiet --yes --minimal）"
            echo "  --retries=N       Number of retry attempts (default: 3)"
            echo "                    重试次数（默认：3）"
            echo "  --help, -h        Show this help message"
            echo "                    显示此帮助信息"
            exit 0
            ;;
    esac
done

# Select environment file / 选择环境文件
if [ "$USE_MINIMAL" = true ]; then
    ENV_FILE="$SCRIPT_DIR/environment-minimal.yml"
    log_info "Using minimal environment (recommended)"
    log_info "使用最小环境（推荐）"
else
    ENV_FILE="$SCRIPT_DIR/environment.yml"
    log_info "Using full environment (may be slow due to many packages)"
    log_info "使用完整环境（由于包较多可能较慢）"
fi

# Get conda base path / 获取 conda 基础路径
CONDA_BASE_PREFIX=$(conda info --base 2>/dev/null)

log_header "NOVA Nanobody Filter - Environment Setup / 纳米抗体过滤器 - 环境设置"

# Configure conda for better network reliability
# 配置 conda 以提高网络可靠性
log_info "Configuring conda for better network reliability..."
log_info "配置 conda 以提高网络可靠性..."
conda config --set remote_read_timeout_secs 600 2>/dev/null || true
conda config --set remote_connect_timeout_secs 30 2>/dev/null || true
conda config --set fetch_threads 2 2>/dev/null || true

# Detect package manager: prefer mamba > micromamba > conda with libmamba > conda
# 检测包管理器：优先使用 mamba > micromamba > 带 libmamba 的 conda > conda
detect_package_manager() {
    if command -v mamba &> /dev/null; then
        echo "mamba"
    elif command -v micromamba &> /dev/null; then
        echo "micromamba"
    else
        # Check if libmamba solver is available
        # 检查 libmamba 求解器是否可用
        if conda config --show solver 2>/dev/null | grep -q "libmamba"; then
            echo "conda-libmamba"
        elif conda list -n base 2>/dev/null | grep -q "conda-libmamba-solver"; then
            echo "conda-libmamba"
        else
            echo "conda"
        fi
    fi
}

PKG_MANAGER=$(detect_package_manager)

log_info ""
log_info "Using package manager: $PKG_MANAGER"
log_info "使用包管理器: $PKG_MANAGER"

# Set up the create/update commands based on package manager
# 根据包管理器设置创建/更新命令
# Add quiet flag if in quiet mode / 如果在静默模式下添加静默标志
QUIET_FLAG=""
if [ "$QUIET_MODE" = true ]; then
    QUIET_FLAG="--quiet"
fi

case $PKG_MANAGER in
    "mamba")
        CREATE_CMD="mamba env create $QUIET_FLAG"
        UPDATE_CMD="mamba env update $QUIET_FLAG"
        ;;
    "micromamba")
        CREATE_CMD="micromamba env create $QUIET_FLAG"
        UPDATE_CMD="micromamba env update $QUIET_FLAG"
        ;;
    "conda-libmamba")
        CREATE_CMD="conda env create --solver=libmamba $QUIET_FLAG"
        UPDATE_CMD="conda env update --solver=libmamba $QUIET_FLAG"
        ;;
    *)
        CREATE_CMD="conda env create $QUIET_FLAG"
        UPDATE_CMD="conda env update $QUIET_FLAG"
        if [ "$QUIET_MODE" = false ]; then
            log_info ""
            log_info "WARNING: Using default conda solver (slow)."
            log_info "警告：使用默认 conda 求解器（较慢）。"
            log_info "For faster installation, install mamba:"
            log_info "为了更快安装，请安装 mamba："
            log_info "  conda install -n base -c conda-forge mamba"
            log_info ""
        fi
        ;;
esac

# Check if environment file exists / 检查环境文件是否存在
if [ ! -f "$ENV_FILE" ]; then
    log_error "Environment file not found: $ENV_FILE"
    log_error "未找到环境文件: $ENV_FILE"
    exit 1
fi

log_info "Environment file: $ENV_FILE"
log_info "环境文件: $ENV_FILE"

# Function to run command with retries / 带重试的命令执行函数
run_with_retry() {
    local cmd="$1"
    local attempt=1
    
    while [ $attempt -le $MAX_RETRIES ]; do
        log_info ""
        log_info "Attempt $attempt of $MAX_RETRIES..."
        log_info "尝试 $attempt / $MAX_RETRIES..."
        
        if eval "$cmd"; then
            return 0
        fi
        
        if [ $attempt -lt $MAX_RETRIES ]; then
            log_info ""
            log_info "Command failed. Cleaning cache and retrying in 5 seconds..."
            log_info "命令失败。清理缓存并在 5 秒后重试..."
            conda clean --all -y 2>/dev/null || true
            sleep 5
        fi
        
        attempt=$((attempt + 1))
    done
    
    log_error "Command failed after $MAX_RETRIES attempts."
    log_error "命令在 $MAX_RETRIES 次尝试后失败。"
    if [ "$QUIET_MODE" = false ]; then
        echo ""
        echo "Troubleshooting tips / 故障排除提示:"
        echo "  1. Check your network connection / 检查网络连接"
        echo "  2. Try using a VPN or different network / 尝试使用 VPN 或不同网络"
        echo "  3. Use minimal installation: ./install.sh --minimal"
        echo "     使用最小安装: ./install.sh --minimal"
        echo "  4. Clean conda cache: conda clean --all"
        echo "     清理 conda 缓存: conda clean --all"
    fi
    return 1
}

# Check if environment already exists / 检查环境是否已存在
if conda env list 2>/dev/null | grep -q "^$ENV_NAME "; then
    log_info ""
    log_info "Environment '$ENV_NAME' already exists."
    log_info "环境 '$ENV_NAME' 已存在。"
    
    # Handle yes mode / 处理自动确认模式
    if [ "$YES_MODE" = true ]; then
        REPLY="y"
    else
        log_info ""
        read -p "Do you want to update it? (y/N) / 是否要更新？(y/N) " -n 1 -r
        echo ""
    fi
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info ""
        log_info "Updating environment..."
        log_info "更新环境..."
        run_with_retry "$UPDATE_CMD -n $ENV_NAME -f \"$ENV_FILE\" --prune"
    else
        log_info "Skipping environment creation."
        log_info "跳过环境创建。"
    fi
else
    log_info ""
    log_info "Creating conda environment..."
    log_info "创建 conda 环境..."
    log_info "This may take a while... / 这可能需要一些时间..."
    log_info ""
    run_with_retry "$CREATE_CMD -f \"$ENV_FILE\""
fi

# Get conda prefix for the environment / 获取环境的 conda 前缀
export CONDA_PREFIX=$(conda info --envs 2>/dev/null | grep "^$ENV_NAME " | awk '{print $NF}')

if [ -z "$CONDA_PREFIX" ]; then
    log_error "Failed to get CONDA_PREFIX for environment '$ENV_NAME'"
    log_error "无法获取环境 '$ENV_NAME' 的 CONDA_PREFIX"
    exit 1
fi

# =============================================================================
# Activate the environment for pip/uv installation
# 激活环境以进行 pip/uv 安装
# =============================================================================
log_info "Activating conda environment '$ENV_NAME'..."
log_info "激活 conda 环境 '$ENV_NAME'..."

# Source conda.sh to enable conda activate in scripts
# 加载 conda.sh 以在脚本中启用 conda activate
if [ -f "$CONDA_BASE_PREFIX/etc/profile.d/conda.sh" ]; then
    source "$CONDA_BASE_PREFIX/etc/profile.d/conda.sh"
fi

# Activate the target environment / 激活目标环境
conda activate "$ENV_NAME"

log_success "Environment '$ENV_NAME' activated"
log_success "环境 '$ENV_NAME' 已激活"

# =============================================================================
# Install pip packages using uv (10-100x faster than pip)
# 使用 uv 安装 pip 包（比 pip 快 10-100 倍）
# =============================================================================
log_header "Installing pip packages with uv / 使用 uv 安装 pip 包"

# Select requirements file based on environment type / 根据环境类型选择需求文件
if [ "$USE_MINIMAL" = true ]; then
    PIP_REQUIREMENTS="$SCRIPT_DIR/requirements-minimal.txt"
else
    PIP_REQUIREMENTS="$SCRIPT_DIR/requirements.txt"
fi

# uv needs to know which Python to use / uv 需要知道使用哪个 Python
UV_PYTHON="$CONDA_PREFIX/bin/python"
UV_CMD="$CONDA_PREFIX/bin/uv"

# Set uv quiet flag / 设置 uv 静默标志
UV_QUIET=""
if [ "$QUIET_MODE" = true ]; then
    UV_QUIET="--quiet"
fi

# Install pip packages / 安装 pip 包
if [ -f "$PIP_REQUIREMENTS" ]; then
    log_info "Installing pip packages from $(basename $PIP_REQUIREMENTS)..."
    log_info "从 $(basename $PIP_REQUIREMENTS) 安装 pip 包..."
    
    if [ -x "$UV_CMD" ]; then
        # Use uv (fast) / 使用 uv（快速）
        # First install build dependencies required for packages built from source
        # 首先安装从源码构建包所需的构建依赖
        log_info "Installing build dependencies (setuptools, wheel, cython)..."
        log_info "安装构建依赖 (setuptools, wheel, cython)..."
        run_with_retry "$UV_CMD pip install $UV_QUIET --python \"$UV_PYTHON\" setuptools wheel cython"
        
        # Now install the main requirements with --no-build-isolation
        # to use the installed build dependencies for git-based packages
        # 使用 --no-build-isolation 安装主要依赖，以便 git 源码包使用已安装的构建依赖
        log_info "Installing main requirements (using installed build deps)..."
        log_info "安装主要依赖（使用已安装的构建依赖）..."
        run_with_retry "$UV_CMD pip install $UV_QUIET --python \"$UV_PYTHON\" --no-build-isolation -r \"$PIP_REQUIREMENTS\""
    else
        # Fallback to pip / 回退到 pip
        log_info "uv not found, falling back to pip..."
        log_info "未找到 uv，回退到 pip..."
        # First install build dependencies / 首先安装构建依赖
        log_info "Installing build dependencies (setuptools, wheel, cython)..."
        log_info "安装构建依赖 (setuptools, wheel, cython)..."
        run_with_retry "\"$CONDA_PREFIX/bin/pip\" install setuptools wheel cython"
        
        # Now install the main requirements with --no-build-isolation
        # 使用 --no-build-isolation 安装主要依赖
        log_info "Installing main requirements (using installed build deps)..."
        log_info "安装主要依赖（使用已安装的构建依赖）..."
        run_with_retry "\"$CONDA_PREFIX/bin/pip\" install --no-build-isolation -r \"$PIP_REQUIREMENTS\""
    fi
    
    log_success "Pip packages installed successfully!"
    log_success "Pip 包安装成功！"
else
    log_info "No $(basename $PIP_REQUIREMENTS) found, skipping..."
    log_info "未找到 $(basename $PIP_REQUIREMENTS)，跳过..."
fi

# =============================================================================
# Apply patches for installed packages / 应用已安装包的补丁
# =============================================================================
log_info "Applying patches for installed packages..."
log_info "应用已安装包的补丁..."

# TNP process_pdb.py patch (fix Bio imports for Biopython 1.80+)
# TNP process_pdb.py 补丁（修复 Biopython 1.80+ 的 Bio 导入）
if [ -f "$SCRIPT_DIR/patches/TNP/process_pdb.py" ]; then
    cp "$SCRIPT_DIR/patches/TNP/process_pdb.py" "$CONDA_PREFIX/lib/python3.12/site-packages/scripts/"
    log_success "TNP process_pdb.py patch applied"
    log_success "TNP process_pdb.py 补丁已应用"
fi

log_header "Setting environment variables / 设置环境变量"
log_info "CONDA_PREFIX: $CONDA_PREFIX"

# Set environment variables / 设置环境变量
# These are required for CUDA and compilation to work correctly
# 这些是 CUDA 和编译正常工作所必需的

# Export immediately for current session / 立即导出以供当前会话使用
export CUDA_HOME=$CONDA_PREFIX
export CUDA_INCLUDE_DIRS=$CONDA_PREFIX/include
export XLA_FLAGS=$CONDA_PREFIX
export LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$CONDA_PREFIX/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export LDFLAGS="-L$CONDA_PREFIX/lib -L$CONDA_PREFIX/lib64"
export CFLAGS="-I$CONDA_PREFIX/include"
export CXXFLAGS="-I$CONDA_PREFIX/include"
export CPPFLAGS="-I$CONDA_PREFIX/include"
export CC=$CONDA_PREFIX/bin/gcc
export CXX=$CONDA_PREFIX/bin/g++
export PKG_CONFIG_PATH=$CONDA_PREFIX/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}

# Persist for future activations / 持久化以供将来激活时使用
conda env config vars set CUDA_HOME=$CONDA_PREFIX -n $ENV_NAME 2>/dev/null || true
conda env config vars set CUDA_INCLUDE_DIRS=$CONDA_PREFIX/include -n $ENV_NAME 2>/dev/null || true
conda env config vars set XLA_FLAGS=$CONDA_PREFIX -n $ENV_NAME 2>/dev/null || true
conda env config vars set LD_LIBRARY_PATH=$CONDA_PREFIX/lib:$CONDA_PREFIX/lib64 -n $ENV_NAME 2>/dev/null || true
conda env config vars set LDFLAGS="-L$CONDA_PREFIX/lib -L$CONDA_PREFIX/lib64" -n $ENV_NAME 2>/dev/null || true
conda env config vars set CFLAGS="-I$CONDA_PREFIX/include" -n $ENV_NAME 2>/dev/null || true
conda env config vars set CXXFLAGS="-I$CONDA_PREFIX/include" -n $ENV_NAME 2>/dev/null || true
conda env config vars set CPPFLAGS="-I$CONDA_PREFIX/include" -n $ENV_NAME 2>/dev/null || true
conda env config vars set CC=$CONDA_PREFIX/bin/gcc -n $ENV_NAME 2>/dev/null || true
conda env config vars set CXX=$CONDA_PREFIX/bin/g++ -n $ENV_NAME 2>/dev/null || true
conda env config vars set PKG_CONFIG_PATH=$CONDA_PREFIX/lib/pkgconfig -n $ENV_NAME 2>/dev/null || true
conda env config vars set BOOST_ROOT=$CONDA_PREFIX -n $ENV_NAME 2>/dev/null || true
conda env config vars set BOOST_INCLUDEDIR=$CONDA_PREFIX/include -n $ENV_NAME 2>/dev/null || true
conda env config vars set BOOST_LIBRARYDIR=$CONDA_PREFIX/lib -n $ENV_NAME 2>/dev/null || true

log_info "Environment variables configured."
log_info "环境变量已配置。"

# Create lib64 symlink if it doesn't exist / 如果不存在则创建 lib64 符号链接
if [ ! -L "$CONDA_PREFIX/lib64" ] && [ ! -d "$CONDA_PREFIX/lib64" ]; then
    log_info ""
    log_info "Creating lib64 symlink..."
    log_info "创建 lib64 符号链接..."
    ln -s $CONDA_PREFIX/lib $CONDA_PREFIX/lib64 2>/dev/null || true
fi

# =============================================================================
# Build and install DSSP from source
# 从源码构建并安装 DSSP
# =============================================================================
if [ ! -x "$CONDA_PREFIX/bin/mkdssp" ]; then
    log_header "Building DSSP from source / 从源码构建 DSSP"
    
    DSSP_BUILD_DIR=$(mktemp -d)
    log_info "Cloning DSSP repository..."
    log_info "克隆 DSSP 仓库..."
    
    if git clone --depth 1 https://github.com/cmbi/dssp.git "$DSSP_BUILD_DIR/dssp" 2>/dev/null; then
        cd "$DSSP_BUILD_DIR/dssp"
        
        log_info "Running autogen.sh..."
        log_info "运行 autogen.sh..."
        ./autogen.sh
        
        log_info "Running configure..."
        log_info "运行 configure..."
        # Use C++14 (required by Boost 1.85+) and disable -Werror
        # 使用 C++14（Boost 1.85+ 需要）并禁用 -Werror
        CXXFLAGS="-std=c++14 -Wno-error" ./configure --prefix=$CONDA_PREFIX --with-boost=$CONDA_PREFIX
        
        log_info "Building DSSP..."
        log_info "构建 DSSP..."
        make -j$(nproc) CXXFLAGS="-std=c++14 -Wno-error -O2"
        
        log_info "Installing DSSP..."
        log_info "安装 DSSP..."
        make install
        
        cd "$SCRIPT_DIR"
        rm -rf "$DSSP_BUILD_DIR"
        
        log_success "DSSP installed successfully!"
        log_success "DSSP 安装成功！"
    else
        log_error "Failed to clone DSSP repository"
        log_error "克隆 DSSP 仓库失败"
    fi
else
    log_info "DSSP already installed, skipping build..."
    log_info "DSSP 已安装，跳过构建..."
fi

# Create dssp symlink if mkdssp exists but dssp doesn't
# 如果 mkdssp 存在但 dssp 不存在，则创建符号链接
if [ -x "$CONDA_PREFIX/bin/mkdssp" ] && [ ! -e "$CONDA_PREFIX/bin/dssp" ]; then
    log_info "Creating dssp symlink (mkdssp -> dssp)..."
    log_info "创建 dssp 符号链接 (mkdssp -> dssp)..."
    ln -s $CONDA_PREFIX/bin/mkdssp $CONDA_PREFIX/bin/dssp 2>/dev/null || true
fi

log_header "Installation complete! / 安装完成！"

if [ "$QUIET_MODE" = false ]; then
    echo "To activate the environment, run:"
    echo "要激活环境，请运行："
    echo ""
    echo "  conda activate $ENV_NAME"
    echo ""
    echo "Installed tools / 已安装的工具:"
    echo "  [Conda packages / Conda 包]"
    echo "  - MMseqs2: Sequence clustering"
    echo "  - AbNumber: IMGT numbering"
    echo "  - OpenMM: Molecular dynamics"
    echo "  - DSSP: Secondary structure"
    echo ""
    echo "  [Pip packages via uv / 通过 uv 安装的 Pip 包]"
    echo "  - AbnatiV: Nativeness scoring"
    echo "  - promb: Humanness evaluation (OASis)"
    echo "  - TNP: Therapeutic Nanobody Profiler"
    echo "  - PyTorch: Deep learning framework (CUDA 12.8)"
    echo ""
fi

# Exit with success / 成功退出
exit 0
