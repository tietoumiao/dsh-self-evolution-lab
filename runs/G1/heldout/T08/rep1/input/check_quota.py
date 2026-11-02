"""配额自检脚本（上游随包附带，依赖内部 SDK）。"""
import quota_sdk  # noqa: F401


def main():
    client = quota_sdk.Client(endpoint="http://127.0.0.1:9")
    print("remaining:", client.remaining())


if __name__ == "__main__":
    main()
