"""Small Flask keep-alive/health-check server for a Discord bot.

Install dependency:
    pip install flask

Use in your bot's main file:
    from keep_alive import keep_alive
    keep_alive()

Note: this endpoint does not guarantee that a hosting provider will keep
your service awake if the provider's policy puts it to sleep.
"""

import os
from threading import Thread

from flask import Flask

app = Flask(__name__)


@app.get("/")
def home():
    return "Bot is active!", 200


@app.get("/health")
def health():
    return "OK", 200


def _run():
    try:
        port = int(os.environ.get("PORT", "8080"))
    except (TypeError, ValueError):
        port = 8080

    app.run(host="0.0.0.0", port=port, use_reloader=False)


def keep_alive():
    """Start the web server in a background thread."""
    thread = Thread(target=_run, name="keep-alive-web", daemon=True)
    thread.start()


if __name__ == "__main__":
    _run()
