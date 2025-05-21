import os
import time
import signal
import requests
from pywinauto import Desktop

def findCursorWindow():
    desktop = Desktop(backend="uia")
    windows = desktop.windows(title_re=".*Cursor.*", top_level_only=True)
    if not windows:
        raise RuntimeError("No Cursor window found")
    for window in windows:
        try:
            if window.child_window(control_type="Edit", found_index=0).exists(timeout=1):
                return window
        except:
            pass
    return windows[0]

def getWindowTexts(window):
    return [elem.window_text() for elem in window.descendants(control_type="Text")]

def needsUserInput(texts):
    for text in texts:
        trimmed = text.strip().lower()
        if trimmed.endswith("?") or trimmed.startswith("enter"):
            return text
    return None

def buildMessages(systemPrompt, userContent):
    return [
        {"role": "system", "content": systemPrompt},
        {"role": "user",   "content": userContent}
    ]

def buildPromptFromMessages(messages):
    # Convert chat messages to a flat prompt string
    parts = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content")
        parts.append(f"{role}: {content}")
    return "\n".join(parts)

def queryOllama(messages):
    payloadChat = {"model": modelName, "messages": messages, "stream": False}
    # Try chat endpoints
    for endpoint in (apiUrlChat, openAIUrl):
        try:
            resp = requests.post(endpoint, json=payloadChat, timeout=defaultTimeout)
            resp.raise_for_status()
            data = resp.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"].strip()
            return data.get("message", {}).get("content", "").strip()
        except requests.exceptions.ReadTimeout:
            time.sleep(10)
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                continue
            raise
    # Fallback to prompt-based generate endpoint
    promptText = buildPromptFromMessages(messages)
    payloadGenerate = {"model": modelName, "prompt": promptText, "stream": False}
    try:
        resp = requests.post(apiUrlGenerate, json=payloadGenerate, timeout=defaultTimeout)
        resp.raise_for_status()
        return resp.json().get("completion", "").strip()
    except Exception as e:
        print(f"[ERROR] All endpoints failed: {e}")
        return ""

def main():
    window = findCursorWindow()
    window.set_focus()
    print(f"Using window: '{window.window_text()}'")
    while running:
        try:
            texts = getWindowTexts(window)
        except:
            time.sleep(5)
            continue

        sessionText = "\n".join(texts)
        inputPrompt = needsUserInput(texts)

        if inputPrompt:
            messages = buildMessages(systemPrompt, f"Session:\n{sessionText}\nUser: {inputPrompt}")
            answer = queryOllama(messages)
            if answer:
                window.type_keys(answer + "{ENTER}", with_spaces=True)
                print(f"[{time.strftime('%H:%M:%S')}] Responded to input")
            time.sleep(intervalSeconds)
            continue

        if any("Generating" in t for t in texts):
            time.sleep(1)
        else:
            messages = buildMessages(systemPrompt, f"Session:\n{sessionText}\nUser: {promptText}")
            answer = queryOllama(messages)
            if answer:
                window.type_keys(answer + "{ENTER}", with_spaces=True)
            time.sleep(intervalSeconds)

    print("Automation stopped")

if __name__ == "__main__":
    defaultTimeout = 300
    promptText = "Continue according to readme.md and make decisions on your own."
    intervalSeconds = float(os.getenv("CURSOR_INTERVAL", 5))
    modelName = "gemma3:4b"
    apiUrlChat = "http://localhost:11434/api/chat"
    openAIUrl = "http://localhost:11434/v1/chat/completions"
    apiUrlGenerate = "http://localhost:11434/api/generate"
    with open("readme.md", encoding="utf-8", errors="ignore") as file:
        readmeContent = file.read()
    systemPrompt = (
        "You are the autonomous Cursor assistant. Your role is to monitor the Cursor command-line interface, "
        "detect when input is required, and respond with the **bare minimum** required input only (e.g. 'y' or 'n'). "
        "Do not add any extra text, explanations, or commentary; keep all outputs as short as possible.\n\n"
        f"{readmeContent}"
    )
    running = True
    signal.signal(signal.SIGINT, lambda *_: globals().update({"running": False}))
    signal.signal(signal.SIGTERM, lambda *_: globals().update({"running": False}))
    print("Starting auto-cursor")
    main()
