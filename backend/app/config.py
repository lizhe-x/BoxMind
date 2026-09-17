from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://boxmind:boxmind@127.0.0.1:5434/boxmind"

    # OpenAI-compatible gateway (getbot.me)
    llm_base_url: str = "https://api.getbot.me/v1"
    llm_api_key: str = ""
    llm_model: str = "kimi-k2.6"
    vision_model: str = "kimi-k2.6"  # 拍照识别(图片输入),走 /v1/chat/completions
    asr_model: str = "qwen3-asr-flash-realtime"  # 语音转写,走 /v1/audio/transcriptions
    tts_model: str = "qwen3-tts-flash"  # 语音合成,走 /v1/audio/speech
    tts_voice: str = "alloy"

    # Embeddings: "local" uses fastembed in-process; "remote" uses the gateway
    # /v1/embeddings endpoint with embedding_model (switch once enabled there).
    embedding_provider: str = "local"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384

    jwt_secret: str = "boxmind-dev-secret-change-in-prod"
    free_credits: int = 50
    media_dir: str = "media"  # 用户图片/音频存储目录(相对 backend/)
    frontend_dist: str = "../frontend/dist"  # 生产构建目录;存在则由后端直接托管前端(单进程对外)

    # 邮箱验证码登录
    code_ttl_seconds: int = 600       # 验证码有效期
    code_resend_seconds: int = 60     # 重发最小间隔
    code_max_attempts: int = 5        # 单码最多尝试次数
    # SMTP 留空 = 开发模式(验证码经接口返回,不真发邮件)。填上则真实发送。
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""               # 发件人,默认用 smtp_user

    class Config:
        env_file = ".env"
        env_prefix = "BOXMIND_"


settings = Settings()
