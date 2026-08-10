import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    # 签名 token 用的密钥（轻量级鉴权，避免引入额外 JWT 依赖）
    TOKEN_SECRET = os.environ.get("TOKEN_SECRET", "dev-token-secret-change-me")
    TOKEN_MAX_AGE = 60 * 60 * 24 * 7  # 7 天

    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(
        BASE_DIR, "instance", "app.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 图标本地化存储目录（契合 PRD：图标存本地，不依赖外链）
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2MB

    # 前端构建产物目录（生产由 Flask 托管）
    FRONTEND_DIST = os.path.join(BASE_DIR, "..", "frontend", "dist")
