import socket
import threading
import time

HOST = '0.0.0.0'
PORT = 12345
HEADER_SIZE = 10

clients = {}        # conn -> username
clients_lock = threading.Lock()

def recv_all(sock, n):
    data = bytearray()
    try:
        while len(data) < n:
            packet = sock.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return bytes(data)
    except Exception:
        return None

def send_message(sock, message_bytes):
    try:
        msg_len = f"{len(message_bytes):<{HEADER_SIZE}}".encode('utf-8')
        sock.sendall(msg_len + message_bytes)
    except Exception as e:
        print("[LỖI GỬI]", e)

def receive_message(sock):
    header = recv_all(sock, HEADER_SIZE)
    if not header:
        return None
    try:
        msg_len = int(header.decode('utf-8').strip())
    except Exception:
        return None
    return recv_all(sock, msg_len)

def broadcast_user_list():
    with clients_lock:
        safe_names = [name.replace(',', '') for name in clients.values() if isinstance(name, str) and name]
        user_list = ",".join(safe_names)
        payload = f"USERLIST::{user_list}".encode('utf-8')
        for conn in list(clients.keys()):
            try:
                send_message(conn, payload)
            except Exception as e:
                print("Lỗi gửi userlist:", e)

def broadcast_message(message_bytes, exclude_conn=None):
    with clients_lock:
        for conn in list(clients.keys()):
            if conn is exclude_conn:
                continue
            try:
                send_message(conn, message_bytes)
            except Exception as e:
                print("Lỗi broadcast:", e)

def send_to_user_only(username, message_bytes):
    """Gửi message chỉ tới username (không gửi lại cho sender)."""
    with clients_lock:
        for c, name in clients.items():
            if name == username:
                try:
                    send_message(c, message_bytes)
                except Exception as e:
                    print("Lỗi gửi tới target:", e)
                break

def handle_client(conn, addr):
    print(f"[KẾT NỐI MỚI] {addr}")
    username = None
    buffered_messages = []
    try:
        # Chờ USERNAME; nếu client gửi message trước, lưu buffer
        start = time.time()
        while True:
            first = receive_message(conn)
            if not first:
                conn.close()
                return
            if first.startswith(b"USERNAME::"):
                try:
                    username = first.decode('utf-8', errors='ignore').split("::",1)[1].strip()
                    if not username:
                        username = f"{addr[0]}:{addr[1]}"
                except Exception:
                    username = f"{addr[0]}:{addr[1]}"
                break
            else:
                buffered_messages.append(first)
            if time.time() - start > 5:
                username = f"{addr[0]}:{addr[1]}"
                break

        with clients_lock:
            clients[conn] = username
        print(f"Người dùng '{username}' đã tham gia.")
        broadcast_user_list()

        # xử lý buffered messages (nếu client gửi trước username)
        for msg in buffered_messages:
            if msg is None:
                continue
            try:
                if msg.startswith(b"OPENPRIVATE::"):
                    parts = msg.split(b"::", 2)
                    if len(parts) == 3:
                        _, sender_b, target_b = parts
                        target_name = target_b.decode('utf-8', errors='ignore')
                        # chỉ forward OPENPRIVATE tới target (không echo sender)
                        send_to_user_only(target_name, msg)
                elif msg.startswith(b"TEXTMSG::") or msg.startswith(b"VOICEMSG::"):
                    parts = msg.split(b"::", 3)
                    if len(parts) == 4:
                        _, sender_b, receiver_b, content = parts
                        receiver_name = receiver_b.decode('utf-8', errors='ignore')
                        if receiver_name == "ALL":
                            broadcast_message(msg, exclude_conn=None)
                        else:
                            send_to_user_only(receiver_name, msg)
            except Exception:
                pass
        buffered_messages.clear()

        # main loop
        while True:
            data = receive_message(conn)
            if data is None:
                break
            try:
                # OPENPRIVATE: forward only to target
                if data.startswith(b"OPENPRIVATE::"):
                    parts = data.split(b"::", 2)
                    if len(parts) == 3:
                        _, sender_b, target_b = parts
                        target_name = target_b.decode('utf-8', errors='ignore')
                        # forward OPENPRIVATE to target only
                        send_to_user_only(target_name, data)
                    else:
                        print("OPENPRIVATE format sai")
                    continue

                # TEXTMSG / VOICEMSG: send only to receiver (or broadcast if ALL)
                if data.startswith(b"TEXTMSG::") or data.startswith(b"VOICEMSG::"):
                    parts = data.split(b"::", 3)
                    if len(parts) != 4:
                        print("Format message không hợp lệ")
                        continue
                    _, sender_b, receiver_b, content = parts
                    receiver_name = receiver_b.decode('utf-8', errors='ignore')
                    if receiver_name == "ALL":
                        broadcast_message(data, exclude_conn=None)
                    else:
                        send_to_user_only(receiver_name, data)
                else:
                    print(f"Nhận payload không hợp lệ từ {username}, loại: {data[:30]!r}")
            except Exception as e:
                print("Lỗi xử lý message:", e)
                break

    except Exception as e:
        print("Lỗi client:", e)
    finally:
        with clients_lock:
            if conn in clients:
                del clients[conn]
        print(f"Người dùng '{username}' đã rời khỏi.")
        broadcast_user_list()
        try:
            conn.close()
        except Exception:
            pass

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen()
    print(f"[ĐANG LẮNG NGHE] Server tại port {PORT}")
    try:
        while True:
            conn, addr = server_socket.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            thread.start()
    except KeyboardInterrupt:
        print("Đóng server...")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_server()

