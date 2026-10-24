import argparse
import json
import sys

from .app import request, run_daemon


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="ompbar", description="KDE quick-entry bar for omp"
    )
    parser.add_argument("--daemon", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--daemon-process", action="store_true", help=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("toggle", help="Show or hide the mini bar")
    subparsers.add_parser("status", help=argparse.SUPPRESS)
    subparsers.add_parser("new", help="Start a new conversation")
    subparsers.add_parser("quit", help=argparse.SUPPRESS)
    subparsers.add_parser("open-terminal", help=argparse.SUPPRESS)
    ask_parser = subparsers.add_parser("ask", help=argparse.SUPPRESS)
    ask_parser.add_argument(
        "prompt", nargs="+", help="Question to send through the popup"
    )
    args = parser.parse_args()

    if args.daemon_process:
        return run_daemon()
    if args.daemon:
        response = request("status")
        if not response.get("ok"):
            print(response.get("error", "Could not start ompbar."), file=sys.stderr)
            return 1
        return 0

    command = args.command or "toggle"
    if command == "ask":
        response = request("ask", " ".join(args.prompt))
        if not response.get("ok"):
            print(
                response.get("error")
                or response.get("errorText")
                or "ompbar request failed.",
                file=sys.stderr,
            )
            if response.get("session_id"):
                print(f"session_id={response['session_id']}", file=sys.stderr)
            return 1
        print(response.get("answer", ""))
        print(f"session_id={response.get('session_id', '')}")
        print(f"cwd={response.get('cwd', '')}")
        return 0

    response = request(command)
    if not response.get("ok"):
        print(response.get("error", "ompbar request failed."), file=sys.stderr)
        return 1
    if command == "status":
        print(json.dumps(response, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
