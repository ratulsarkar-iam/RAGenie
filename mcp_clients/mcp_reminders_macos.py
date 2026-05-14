#!/usr/bin/env python3
"""
MCP Server for macOS Reminders integration.
Reads requests from stdin and writes responses to stdout.
"""

import sys
import json
import subprocess


def create_reminder(title: str, notes: str = "", priority: int = 1) -> dict:
    script = f'''
    tell application "Reminders"
        set newReminder to make new reminder at end of list "Reminders" with properties {{name:"{title}", body:"{notes}", priority:{priority}}}
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


def list_reminders(completed: bool = False) -> dict:
    completed_str = "true" if completed else "false"
    script = f'''
    tell application "Reminders"
        set output to ""
        tell list "Reminders"
            repeat with r in reminders
                if completed of r is {completed_str} then
                    set output to output & name of r & "\\n"
                end if
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
        items = [r for r in result.stdout.strip().split("\n") if r]
        return {"status": "ok", "reminders": items}
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

            if action == "create_reminder":
                response = create_reminder(
                    title=params.get("title", "New Reminder"),
                    notes=params.get("notes", ""),
                    priority=params.get("priority", 1)
                )
            elif action == "list_reminders":
                response = list_reminders(params.get("completed", False))
            else:
                response = {"status": "error", "message": f"Unknown action: {action}"}

        except json.JSONDecodeError as e:
            response = {"status": "error", "message": f"Invalid JSON: {e}"}
        except Exception as e:
            response = {"status": "error", "message": str(e)}

        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
