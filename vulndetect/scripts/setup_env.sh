#!/bin/bash
# vulndetect/scripts/setup_env.sh
# VulnDetect 环境初始化——GPU 检测 + venv + 依赖安装
set -e

echo "=== VulnDetect Environment Setup ==="

# Check GPU
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
    echo "CUDA available: $(python3 -c 'import torch; print(torch.cuda.is_available())' 2>/dev/null || echo 'torch not yet installed')"
else
    echo "WARNING: nvidia-smi not found"
fi

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Created virtual environment: venv/"
fi

source venv/bin/activate

# Install PyTorch with CUDA 12.1
echo "Installing PyTorch..."
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install remaining dependencies
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

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
