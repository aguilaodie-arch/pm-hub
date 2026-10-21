import uvicorn
from app.config import settings

if __name__ == "__main__":
    print(f"产品需求管理平台已启动: http://{settings.host}:{settings.port}")
    print(f"原型文件根目录: {settings.publish_root}")
    print(f"AI 已配置: {settings.ai_enabled}")
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
