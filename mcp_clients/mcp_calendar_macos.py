#!/usr/bin/env python3
"""
MCP Server for macOS Calendar integration.
Reads requests from stdin and writes responses to stdout.
"""

import sys
import json
import subprocess
from datetime import datetime


def create_calendar_event(title: str, notes: str = "", duration_minutes: int = 60) -> dict:
    script = f'''
    tell application "Calendar"
        tell calendar "Home"
            set newEvent to make new event at end of events with properties {{summary:"{title}", description:"{notes}"}}
        end tell
    end tell
    return "created"
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return {"status": "created", "title": title}
        else:
            return {"status": "error", "message": result.stderr.strip()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def list_calendar_events() -> dict:
    script = '''
    tell application "Calendar"
        set output to ""
        tell calendar "Home"
            repeat with e in events
                set output to output & summary of e & "\\n"
            end repeat
        end tell
    end tell
    return output
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10
        )
        return {"status": "ok", "events": result.stdout.strip().split("\n")}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            action = request.get("action", "")
            params = request.get("params", {})

            if action == "create_event":
                response = create_calendar_event(
                    title=params.get("title", "New Event"),
                    notes=params.get("notes", ""),
                    duration_minutes=params.get("duration_minutes", 60)
                )
            elif action == "list_events":
                response = list_calendar_events()
            else:
                response = {"status": "error", "message": f"Unknown action: {action}"}

        except json.JSONDecodeError as e:
            response = {"status": "error", "message": f"Invalid JSON: {e}"}
        except Exception as e:
            response = {"status": "error", "message": str(e)}

        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
