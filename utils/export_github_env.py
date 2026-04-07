import json
import os
import sys


BASE_VAR_KEYS = [
    "PROXY_ADDRESS",
    "MESSAGE_TEMPLATE",
    "HITOKOTO_TYPES",
    "MATCH_MODE",
    "BROWSER_TIMEOUT",
    "FRIEND_LIST_WAIT_TIME",
    "TASK_RETRY_TIMES",
    "LOG_LEVEL",
    "TASKS",
]


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def to_dotenv_value(value: str) -> str:
    # Keep .env single-line values by escaping real line breaks.
    return value.replace("\r", "").replace("\n", "\\n")


def append_github_env_block(env_file, key: str, value: str) -> None:
    env_file.write(f"{key}<<__ENV_EOF__\n")
    env_file.write(value)
    env_file.write("\n__ENV_EOF__\n")


def main() -> None:
    tasks_raw = os.getenv("TASKS", "[]")
    secrets_raw = os.getenv("SECRETS_JSON", "{}")
    github_env = os.getenv("GITHUB_ENV")

    if not github_env:
        fail("GITHUB_ENV is not set")

    try:
        tasks = json.loads(tasks_raw)
    except json.JSONDecodeError as exc:
        fail(f"TASKS is not valid JSON: {exc}")

    try:
        secrets_map = json.loads(secrets_raw)
    except json.JSONDecodeError as exc:
        fail(f"SECRETS_JSON is not valid JSON: {exc}")

    exported_cookie_keys = []
    missing = []
    base_env_map = {key: os.getenv(key, "") for key in BASE_VAR_KEYS}
    dotenv_map = dict(base_env_map)

    with open(github_env, "a", encoding="utf-8") as env_file:
        for key, value in base_env_map.items():
            append_github_env_block(env_file, key, value)

        for task in tasks:
            unique_id = str(task.get("unique_id", "")).strip()
            if not unique_id:
                continue

            secret_key = f"COOKIES_{unique_id}"
            secret_value = secrets_map.get(secret_key)
            if not secret_value:
                missing.append(secret_key)
                continue

            # Keep both env names for compatibility with existing code.
            for env_key in (secret_key, f"cookies_{unique_id}"):
                append_github_env_block(env_file, env_key, secret_value)
                dotenv_map[env_key] = secret_value

            exported_cookie_keys.append(secret_key)

        env_file.write(f"COOKIES_EXPORTED_COUNT={len(exported_cookie_keys)}\n")

    dotenv_lines = [f"{key}={to_dotenv_value(value)}" for key, value in dotenv_map.items()]
    with open(".env", "w", encoding="utf-8") as dotenv_file:
        dotenv_file.write("\n".join(dotenv_lines) + "\n")

    if missing:
        print("::warning::Missing cookie secrets: " + ", ".join(missing))

    print(
        "Injected base vars and exported cookies for "
        f"{len(exported_cookie_keys)} account(s); .env refreshed."
    )


if __name__ == "__main__":
    main()
