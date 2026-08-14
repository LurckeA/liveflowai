# src/liveflowai/__init__.py
import asyncio
from .app import LiveFlowAI

__version__ = "0.1.0"

def main():
    app = LiveFlowAI()
    # Run the async app
    asyncio.run(app.run())