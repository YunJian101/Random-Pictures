#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Random-Pictures FastAPI 主程序
启动入口
"""

import uvicorn
from backend.main import app

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8081,
        reload=True,
        log_level="info"
    )
