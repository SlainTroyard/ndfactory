#!/bin/bash
# 清理所有训练产物和数据库，保留数据和代码
set -e
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
rm -f vulndetect.db
rm -rf experiments/
rm -rf eval_output_baseline eval_output_sft eval_output_dpo
echo "Cleared: DB, experiments, eval outputs"
echo "Data (data/vulndetect/) and code preserved."
