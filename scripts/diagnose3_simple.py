import pyfbsdk as fb
import socket
import threading

app = fb.FBApplication()
try:
    r = app.ExecuteScript('print(1+1)')
    print("ExecuteScript result:", r)
except Exception as e:
    print("ExecuteScript Error:", type(e).__name__, e)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.close()
print("socket: OK")

t = threading.Thread(target=lambda: None)
t.start()
t.join()
print("threading: OK")
