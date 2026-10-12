#!/bin/bash
# 一键运行知识库与控制台 Agent 全链路演练项目

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=========================================================="
echo " 现代知识库与控制台 Agent 架构全链路演练 (SOTA 方案对比)"
echo "=========================================================="

# 优先自动探测虚拟环境中的 Python (支持 litellm 与 fastembed 生产栈)
if [ -x "../../.venv/bin/python3" ]; then
  PYTHON_BIN="../../.venv/bin/python3"
elif [ -x ".venv/bin/python3" ]; then
  PYTHON_BIN=".venv/bin/python3"
else
  PYTHON_BIN="$(command -v python3 || echo "/usr/bin/python3")"
fi

"$PYTHON_BIN" main.py
