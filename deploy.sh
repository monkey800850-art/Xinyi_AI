#!/bin/bash
set -euo pipefail

# 设置环境变量
export FLASK_ENV=production
export FLASK_APP=app.py
export PYTHONPATH=/home/x1560/Xinyi_AI

# 启动 Flask 应用（以生产模式运行）
echo "[INFO] 启动 Flask 应用，生产模式"
python3 -c 'import runpy; ns = runpy.run_path("app.py"); app = ns["create_app"](); app.run(debug=False, use_reloader=False, host="0.0.0.0", port=5000)'
