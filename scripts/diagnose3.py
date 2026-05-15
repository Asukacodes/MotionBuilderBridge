"""
diagnose3.py — Paste into Motion Builder Python Shell.
Tests ExecuteScript and finds socket-based execution methods.
"""
import pyfbsdk as fb
import socket
import inspect

app = fb.FBApplication()

print("=== ExecuteScript ===")
print("Signature:", inspect.signature(app.ExecuteScript) if hasattr(inspect, 'signature') else 'no signature')
try:
    r = app.ExecuteScript('print(1+1)')
    print("Result:", r, type(r))
except Exception as e:
    print("Error:", type(e).__name__, e)

print()
print("=== FBSystem ===")
sys = fb.FBSystem()
print("Scene:", sys.Scene)
print("RootModel:", sys.RootModel)
print("FrameRate:", sys.FrameRate)

print()
print("=== Can we create a socket? ===")
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print("socket created OK")
    s.close()
except Exception as e:
    print("socket FAILED:", e)

print()
print("=== threading ===")
import threading
print("Threading available:", threading.available if hasattr(threading, 'available') else True)
t = threading.Thread(target=lambda: print("thread works!"))
t.start()
t.join()
print("thread join OK")
