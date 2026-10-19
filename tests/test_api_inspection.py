import webview
import time

class BadApi:
    def __init__(self):
        self.window = None
        self.stitcher = object()

    def hello(self):
        return "world"

class GoodApi:
    def __init__(self):
        self._window = None
        self._stitcher = object()

    def hello(self):
        return "world"

print("Created test APIs")
