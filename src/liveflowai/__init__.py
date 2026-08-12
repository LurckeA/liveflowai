# src/liveflowai/__init__.py
from .app import LiveFlowAI

__version__ = "0.1.0"

def main():
    app = LiveFlowAI()
    app.run()