"""MySQL database configuration."""

from pydantic import BaseModel, Field


class MySQLConfig(BaseModel):
    """MySQL connection configuration for persisting sensor readings."""

    enabled: bool = Field(default=False, description="Enable MySQL persistence")
    url: str = Field(
        default="mysql+pymysql://pisolar:pisolar@localhost/pisolar",
        description="SQLAlchemy database URL (mysql+pymysql://user:pass@host/db)",
    )
    pool_size: int = Field(
        default=5,
        ge=1,
        description="Number of connections to keep in the connection pool",
    )
    pool_recycle: int = Field(
        default=3600,
        ge=60,
        description="Recycle connections after this many seconds (avoids stale connections)",
    )
