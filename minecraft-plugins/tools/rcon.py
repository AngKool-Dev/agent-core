import socket
import struct
import sys


def pack(req_id, ptype, payload):
    data = struct.pack("<ii", req_id, ptype) + payload.encode("utf-8") + b"\x00\x00"
    return struct.pack("<i", len(data)) + data


def unpack(sock):
    raw = b""
    while len(raw) < 4:
        chunk = sock.recv(4 - len(raw))
        if not chunk:
            return None
        raw += chunk
    (length,) = struct.unpack("<i", raw)
    body = b""
    while len(body) < length:
        chunk = sock.recv(length - len(body))
        if not chunk:
            return None
        body += chunk
    rid, rtype = struct.unpack("<ii", body[:8])
    return rid, rtype, body[8:-2].decode("utf-8", errors="replace")


def main():
    host, port, password = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    command = sys.argv[4] if len(sys.argv) > 4 else "list"
    sock = socket.create_connection((host, port), timeout=15)
    sock.sendall(pack(1, 3, password))
    rid, _, _ = unpack(sock)
    if rid == -1:
        print("RCON auth failed")
        sys.exit(2)
    sock.sendall(pack(2, 2, command))
    out = []
    while True:
        pkt = unpack(sock)
        if pkt is None:
            break
        out.append(pkt[2])
        if len(pkt[2]) < 4000:
            break
    sock.close()
    print("\n".join(out))


if __name__ == "__main__":
    main()
