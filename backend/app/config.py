from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://boxmind:boxmind@127.0.0.1:5434/boxmind"

    # Which LLM backend: "gateway" (OpenAI-compatible HTTP, below) or "claude_code" (spawns the local
    # `claude -p` CLI, billed to its Claude subscription; test server only, see services/llm_claude.py).
    llm_provider: str = "gateway"
    claude_bin: str = ""                 # path to the claude CLI; empty = PATH, then ~/.local/bin/claude
    claude_model: str = "sonnet"         # chat / interpret / agent
    claude_vision_model: str = "sonnet"  # photo intake (reads the image with the Read tool)
    claude_concurrency: int = 3          # max simultaneous claude processes

    # OpenAI-compatible gateway (/chat/completions). OpenRouter is the production one; any compatible endpoint works.
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: str = ""            # empty = read OPENROUTER_API_KEY from the environment
    llm_model: str = "moonshotai/kimi-k2.6"
    vision_model: str = "moonshotai/kimi-k2.6"  # 拍照识别(图片输入),走 /v1/chat/completions
    # OpenRouter provider routing: ordered preference (comma-separated slugs) and whether others may serve
    # the request when those fail. Empty = let the router choose.
    llm_provider_order: str = ""
    llm_allow_fallbacks: bool = True
    # "off" sends reasoning.enabled=false (Kimi K2.x think by default; our outputs are short JSON). "" = model default.
    llm_reasoning: str = ""
    asr_model: str = "qwen3-asr-flash-realtime"  # 语音转写,走 /v1/audio/transcriptions
    tts_model: str = "qwen3-tts-flash"  # 语音合成,走 /v1/audio/speech
    tts_voice: str = "alloy"

    # Embeddings: "local" uses fastembed in-process; "remote" uses the gateway
    # /v1/embeddings endpoint with embedding_model (switch once enabled there);
    # "st" uses sentence-transformers in-process (torch; evaluation only unless adopted).
    embedding_provider: str = "local"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384
    # Where fastembed keeps downloaded weights. Empty = fastembed's default (a temp dir
    # the OS may purge, which forces the ~500 MB download again).
    embedding_cache_dir: str = ""
    # Some models want a role prefix on the text ("query: " / "passage: " for the e5 family). Empty = none.
    embedding_query_prefix: str = ""
    embedding_passage_prefix: str = ""
    # Item search: "hybrid" = vector + trigram fused by RRF (services/search.py); "vector" = cosine only.
    search_mode: str = "hybrid"

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
    # App Store 审核演示账号:该邮箱不发邮件,固定验证码直接可登录。两项都非空才生效。
    review_email: str = ""
    review_code: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="BOXMIND_")


settings = Settings()
