"""企业级差旅报销智能体 API 服务端启动器
使用方式:
    .venv/bin/python examples/enterprise_expense_agent/server.py --port 8000
"""
import sys
import os
import argparse
import uvicorn

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(CURRENT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def main():
    parser = argparse.ArgumentParser(description="Enterprise Expense Agent API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Auto reload")
    args = parser.parse_args()

    print("==================================================")
    print("Starting Enterprise Expense Agent API Server...")
    print(f"Server URL : http://{args.host}:{args.port}")
    print(f"Swagger API: http://{args.host}:{args.port}/docs")
    print("==================================================")

    uvicorn.run(
        "enterprise_expense_agent.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()
