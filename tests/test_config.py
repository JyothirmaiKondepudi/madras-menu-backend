"""B5: settings are validated together, and the app refuses to start with a
missing or invalid one."""
import pytest

from config import ConfigError, database_pool_settings, database_url, load_settings

GOOD_SECRET = "a" * 64
SETTINGS = ["DATABASE_URL", "SECRET_KEY", "JWT_ALGORITHM", "JWT_EXPIRE_MINUTES", "CORS_ORIGINS", "OLLAMA_BASE_URL"]


@pytest.fixture()
def env(monkeypatch):
    """A clean, valid environment each test can break one setting of."""
    for name in SETTINGS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.setenv("SECRET_KEY", GOOD_SECRET)
    return monkeypatch


def test_valid_settings_and_defaults(env):
    settings = load_settings()
    assert settings.JWT_ALGORITHM == "HS256"
    assert settings.JWT_EXPIRE_MINUTES == 720
    assert settings.CORS_ORIGINS == ["http://localhost:3000"]


def test_cors_origins_are_split_on_commas(env):
    env.setenv("CORS_ORIGINS", "https://app.example.com, http://localhost:3000,")
    assert load_settings().CORS_ORIGINS == ["https://app.example.com", "http://localhost:3000"]


@pytest.mark.parametrize("name, value, expected", [
    ("SECRET_KEY", None, "SECRET_KEY: Field required"),
    ("SECRET_KEY", "", "SECRET_KEY: Field required"),  # "SECRET_KEY=" from the example file
    ("SECRET_KEY", "too-short", "SECRET_KEY: String should have at least 32 characters"),
    ("DATABASE_URL", None, "DATABASE_URL: Field required"),
    ("DATABASE_URL", "mysql://localhost/db", "DATABASE_URL"),
    ("JWT_ALGORITHM", "none", "JWT_ALGORITHM"),
    ("JWT_EXPIRE_MINUTES", "abc", "JWT_EXPIRE_MINUTES"),
    ("JWT_EXPIRE_MINUTES", "0", "JWT_EXPIRE_MINUTES"),
    ("CORS_ORIGINS", "localhost:3000", "CORS_ORIGINS"),
    ("OLLAMA_BASE_URL", "localhost:11434", "OLLAMA_BASE_URL"),
])
def test_invalid_setting_is_rejected(env, name, value, expected):
    if value is None:
        env.delenv(name)
    else:
        env.setenv(name, value)
    with pytest.raises(ConfigError, match=expected):
        load_settings()


def test_every_problem_is_reported_at_once(env):
    env.delenv("SECRET_KEY")
    env.setenv("JWT_EXPIRE_MINUTES", "abc")
    with pytest.raises(ConfigError) as exc:
        load_settings()
    assert "SECRET_KEY" in str(exc.value)
    assert "JWT_EXPIRE_MINUTES" in str(exc.value)


def test_error_never_contains_the_secret(env):
    env.setenv("SECRET_KEY", "short-but-secret")
    with pytest.raises(ConfigError) as exc:
        load_settings()
    assert "short-but-secret" not in str(exc.value)


def test_database_url_alone_is_enough_for_scripts(env):
    # seed scripts and Alembic only need the database
    env.delenv("SECRET_KEY")
    assert database_url() == "postgresql://user:pass@localhost:5432/db"
    env.delenv("DATABASE_URL")
    with pytest.raises(ConfigError, match="DATABASE_URL"):
        database_url()


POOL_SETTINGS = ["DB_POOL_SIZE", "DB_MAX_OVERFLOW", "DB_POOL_TIMEOUT", "DB_CONNECTION_TIMEOUT"]


@pytest.fixture()
def pool_env(monkeypatch):
    for name in POOL_SETTINGS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_pool_settings_defaults(pool_env):
    pool = database_pool_settings()
    assert (pool.DB_POOL_SIZE, pool.DB_MAX_OVERFLOW) == (5, 5)
    assert (pool.DB_POOL_TIMEOUT, pool.DB_CONNECTION_TIMEOUT) == (10, 5)


def test_pool_settings_read_from_environment(pool_env):
    pool_env.setenv("DB_POOL_SIZE", "3")
    pool_env.setenv("DB_MAX_OVERFLOW", "0")  # 0 is allowed: no burst connections
    pool = database_pool_settings()
    assert pool.DB_POOL_SIZE == 3
    assert pool.DB_MAX_OVERFLOW == 0


@pytest.mark.parametrize("name, value", [
    ("DB_POOL_SIZE", "abc"),
    ("DB_POOL_SIZE", "0"),
    ("DB_POOL_SIZE", "5,"),  # a trailing comma copied into an env file
    ("DB_MAX_OVERFLOW", "-1"),
    ("DB_POOL_TIMEOUT", "0"),
    ("DB_CONNECTION_TIMEOUT", "ten"),
])
def test_invalid_pool_setting_names_the_setting(pool_env, name, value):
    # a clear ConfigError naming the setting, not a bare ValueError from int()
    pool_env.setenv(name, value)
    with pytest.raises(ConfigError, match=name):
        database_pool_settings()


def test_pool_settings_dont_need_secret_key(pool_env, env):
    # scripts and Alembic build the engine without the app's other settings
    env.delenv("SECRET_KEY")
    assert database_pool_settings().DB_POOL_SIZE == 5
