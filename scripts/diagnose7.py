import socket
import struct
import json
import select

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10)
sock.connect(('127.0.0.1', 8997))

body = json.dumps({'id': 'test1', 'command': 'ping'}, ensure_ascii=False).encode('utf-8')
sock.sendall(struct.pack('>I', len(body)) + body)
print('Request sent')

# Wait up to 5s for response
r, _, _ = select.select([sock], [], [], 5)
if r:
    header = sock.recv(4)
    print(f'Header bytes: {header.hex()}')
    if len(header) == 4:
        length = struct.unpack('>I', header)[0]
        print(f'Length: {length}')
        payload = b''
        while len(payload) < length:
            chunk = sock.recv(length - len(payload))
            if not chunk:
                break
            payload += chunk
        print('Response:', payload.decode('utf-8'))
else:
    print('No response within 5s')
sock.close()
