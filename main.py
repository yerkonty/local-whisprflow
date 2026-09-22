import sys

from local_whisprflow.app import App


def main():
    try:
        app = App()
    except Exception as exc:
        print(f"Failed to start Local Whisprflow: {exc}")
        sys.exit(1)
    app.run()


if __name__ == "__main__":
    main()
