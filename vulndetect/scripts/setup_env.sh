#!/bin/bash
# vulndetect/scripts/setup_env.sh
# VulnDetect 环境初始化——GPU 检测 + venv + 依赖安装
# 从项目根目录或 vulndetect/ 目录运行均可
set -e

# 定位脚本所在目录的父目录（即 vulndetect/）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== VulnDetect Environment Setup ==="
echo "Project dir: $PROJECT_DIR"

# Check GPU
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
else
    echo "WARNING: nvidia-smi not found"
fi

# Create virtual environment in project parent if not exists
VENV_DIR="$PROJECT_DIR/../venv"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "Created virtual environment: $VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# Install PyTorch with CUDA 12.1
echo "Installing PyTorch..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install remaining dependencies
echo "Installing dependencies from $PROJECT_DIR/requirements.txt..."
pip install -r "$PROJECT_DIR/requirements.txt"

# Verify key packages
echo ""
echo "=== Verification ==="
python3 -c "
import torch
import transformers
import bitsandbytes
import peft
print(f'PyTorch: {torch.__version__}')
print(f'CUDA Available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB')
print(f'Transformers: {transformers.__version__}')
print(f'Bitsandbytes: {bitsandbytes.__version__}')
print(f'PEFT: {peft.__version__}')
"

echo ""
echo "=== Setup Complete ==="
echo "To activate the environment: source venv/bin/activate"
