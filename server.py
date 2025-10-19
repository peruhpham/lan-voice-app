import socket
import threading
import time

# === CẤU HÌNH SERVER ===
HOST = '0.0.0.0'  # Lắng nghe trên tất cả các giao diện mạng
PORT = 12345        # Cổng mà server sẽ lắng nghe
HEADER_SIZE = 10    # Kích thước cố định của header (chứa độ dài tin nhắn)

# === BIẾN TOÀN CỤC ===
# Dictionary lưu trữ các client đang kết nối
# Cấu trúc: {socket_connection: username}
# Dùng socket_connection làm key là an toàn nhất vì nó là duy nhất.
clients = {}
# Lock (khóa) để bảo vệ quyền truy cập vào dictionary 'clients'
# vì nhiều luồng (mỗi client 1 luồng) sẽ cùng lúc đọc/ghi vào nó.
clients_lock = threading.Lock()

# ==================================
# === CÁC HÀM TIỆN ÍCH (NETWORK) ===
# ==================================

def recv_all(sock, n):
    """
    Hàm tiện ích để đảm bảo nhận ĐỦ 'n' bytes từ socket.
    Hàm sock.recv() mặc định không đảm bảo nhận đủ 'n' bytes trong 1 lần gọi.
    """
    data = bytearray()
    try:
        while len(data) < n:
            # Nhận phần dữ liệu còn thiếu
            packet = sock.recv(n - len(data))
            if not packet:
                # Nếu không nhận được gì (socket đã đóng), trả về None
                return None
            data.extend(packet)
        return bytes(data)
    except Exception:
        # Nếu có lỗi (ví dụ: client ngắt kết nối đột ngột)
        return None

def send_message(sock, message_bytes):
    """
    Hàm gửi tin nhắn (dạng bytes) theo giao thức: [HEADER][PAYLOAD]
    - HEADER: 10 bytes, chứa độ dài của PAYLOAD, căn trái.
    - PAYLOAD: Dữ liệu tin nhắn thực tế (dạng bytes).
    """
    try:
        # 1. Tạo header: Lấy độ dài của tin nhắn, chuyển thành chuỗi,
        #    và định dạng nó thành 10 bytes (ví dụ: "123      ")
        msg_len = f"{len(message_bytes):<{HEADER_SIZE}}".encode('utf-8')
        
        # 2. Gửi header + payload
        sock.sendall(msg_len + message_bytes)
    except Exception as e:
        print(f"[LỖI GỬI] {sock.getpeername()}: {e}")

def receive_message(sock):
    """
    Hàm nhận tin nhắn theo giao thức: [HEADER][PAYLOAD]
    """
    # 1. Nhận header (10 bytes) trước
    header = recv_all(sock, HEADER_SIZE)
    if not header:
        return None  # Client đã ngắt kết nối
    
    try:
        # 2. Decode header, loại bỏ khoảng trắng, chuyển thành số nguyên (độ dài payload)
        msg_len = int(header.decode('utf-8').strip())
    except Exception:
        return None  # Header không hợp lệ

    # 3. Nhận payload với độ dài chính xác vừa đọc được
    return recv_all(sock, msg_len)

# =======================================
# === CÁC HÀM LOGIC (QUẢN LÝ CLIENTS) ===
# =======================================

def broadcast_user_list():
    """
    Gửi danh sách tất cả user đang online cho MỌI client.
    Được gọi mỗi khi có user tham gia hoặc rời đi.
    """
    # Sử dụng lock để đảm bảo an toàn khi duyệt 'clients'
    with clients_lock:
        # Lấy danh sách tất cả username từ 'clients.values()'
        # Lọc bỏ tên rỗng, không phải chuỗi và thay thế dấu ',' (nếu có)
        safe_names = [name.replace(',', '') for name in clients.values() if isinstance(name, str) and name]
        
        # Tạo chuỗi user_list, ngăn cách bởi dấu ','
        user_list = ",".join(safe_names)
        
        # Tạo payload theo định dạng "USERLIST::user1,user2,user3"
        payload = f"USERLIST::{user_list}".encode('utf-8')
        
        print(f"[USERLIST] Cập nhật: {user_list}")

        # Lặp qua tất cả socket connection (clients.keys())
        # Dùng list() để tạo bản sao, phòng trường hợp 'clients' bị thay đổi khi đang lặp
        for conn in list(clients.keys()):
            try:
                send_message(conn, payload)
            except Exception as e:
                print(f"Lỗi gửi userlist tới {clients[conn]}: {e}")

def broadcast_message(message_bytes, exclude_conn=None):
    """
    Gửi một tin nhắn (bytes) tới TẤT CẢ client.
    Có thể tùy chọn 'exclude_conn' để không gửi lại cho chính người gửi.
    (Lưu ý: trong code hiện tại, exclude_conn đang được set là None,
     nghĩa là server gửi cho TẤT CẢ, bao gồm cả người gửi).
    """
    with clients_lock:
        for conn in list(clients.keys()):
            # Bỏ qua client trong danh sách loại trừ
            if conn is exclude_conn:
                continue
            try:
                send_message(conn, message_bytes)
            except Exception as e:
                print(f"Lỗi broadcast tới {clients[conn]}: {e}")

def send_to_user_only(username, message_bytes):
    """
    Gửi tin nhắn (bytes) chỉ tới MỘT user cụ thể.
    Hàm này duyệt 'clients' để tìm socket tương ứng với 'username'.
    """
    with clients_lock:
        target_conn = None
        # Duyệt qua (key, value) tức là (conn, name)
        for c, name in clients.items():
            if name == username:
                target_conn = c
                break  # Tìm thấy, thoát vòng lặp
        
        # Nếu tìm thấy socket của user
        if target_conn:
            try:
                send_message(target_conn, message_bytes)
            except Exception as e:
                print(f"Lỗi gửi tới target {username}: {e}")
        else:
            print(f"Không tìm thấy user '{username}' để gửi tin.")

# ================================
# === HÀM XỬ LÝ CLIENT (LUỒNG) ===
# ================================

def handle_client(conn, addr):
    """
    Đây là hàm chính xử lý toàn bộ logic cho MỖI client.
    Mỗi client kết nối sẽ chạy hàm này trong một luồng (thread) riêng.
    """
    print(f"[KẾT NỐI MỚI] {addr}")
    username = None
    # Buffer: Lưu trữ các tin nhắn client gửi đến TRƯỚC KHI client gửi username
    buffered_messages = []
    
    try:
        # --- Giai đoạn 1: Chờ xác thực USERNAME ---
        start = time.time()
        while True:
            # Nhận tin nhắn đầu tiên (hoặc các tin nhắn tiếp theo nếu chưa có username)
            first_msg_bytes = receive_message(conn)
            if not first_msg_bytes:
                # Client ngắt kết nối trước cả khi gửi username
                conn.close()
                return

            # Kiểm tra xem có phải tin nhắn USERNAME không
            if first_msg_bytes.startswith(b"USERNAME::"):
                try:
                    # Tách chuỗi "USERNAME::" để lấy tên
                    username = first_msg_bytes.decode('utf-8', errors='ignore').split("::",1)[1].strip()
                    # Nếu tên rỗng, gán tên mặc định
                    if not username:
                        username = f"{addr[0]}:{addr[1]}"
                except Exception:
                    # Nếu format lỗi, gán tên mặc định
                    username = f"{addr[0]}:{addr[1]}"
                
                # Đã có username, thoát khỏi vòng lặp chờ
                break
            else:
                # Nếu không phải tin USERNAME (ví dụ: client gửi TEXTMSG quá sớm),
                # lưu vào buffer để xử lý sau khi có username.
                buffered_messages.append(first_msg_bytes)
            
            # Đặt thời gian chờ 5s. Nếu sau 5s client không gửi USERNAME,
            # tự gán tên mặc định và tiếp tục.
            if time.time() - start > 5:
                username = f"{addr[0]}:{addr[1]}"
                break

        # --- Giai đoạn 2: Đăng ký client và xử lý buffer ---
        with clients_lock:
            # Thêm client vào dictionary toàn cục
            clients[conn] = username
        
        print(f"Người dùng '{username}' ({addr}) đã tham gia.")
        
        # Thông báo cho MỌI NGƯỜI (bao gồm cả user mới) danh sách user mới
        broadcast_user_list()

        # Xử lý các tin nhắn đã bị đệm (nếu có)
        for msg in buffered_messages:
            if msg is None:
                continue
            try:
                # Phân tích và định tuyến các tin nhắn trong buffer
                if msg.startswith(b"TEXTMSG::") or msg.startswith(b"VOICEMSG::"):
                    parts = msg.split(b"::", 3)
                    if len(parts) == 4:
                        _, sender_b, receiver_b, content = parts
                        receiver_name = receiver_b.decode('utf-8', errors='ignore')
                        
                        if receiver_name == "ALL":
                            # Gửi cho tất cả (bao gồm cả người gửi)
                            broadcast_message(msg, exclude_conn=None) 
                        else:
                            # Gửi riêng tư
                            send_to_user_only(receiver_name, msg)
                # (Logic cho OPENPRIVATE và FILE cũng nên được thêm vào đây nếu cần)
            except Exception:
                pass  # Bỏ qua nếu tin nhắn trong buffer bị lỗi
        buffered_messages.clear() # Xóa buffer sau khi xử lý

        # --- Giai đoạn 3: Vòng lặp chính (nhận và xử lý tin nhắn) ---
        while True:
            # Chờ nhận tin nhắn tiếp theo
            data = receive_message(conn)
            
            # Nếu data là None, client đã ngắt kết nối
            if data is None:
                break
            
            try:
                # --- LOGIC PHÂN TUYẾN (ROUTING) TIN NHẮN ---
                
                # (Hiện tại code client không gửi OPENPRIVATE, nhưng logic server vẫn có)
                if data.startswith(b"OPENPRIVATE::"):
                    parts = data.split(b"::", 2)
                    if len(parts) == 3:
                        _, sender_b, target_b = parts
                        target_name = target_b.decode('utf-8', errors='ignore')
                        # Chỉ forward cho người nhận
                        send_to_user_only(target_name, data)
                    continue # Xử lý xong, chờ tin tiếp theo

                # Xử lý tin nhắn TEXT hoặc VOICE (hoặc FILE)
                if data.startswith(b"TEXTMSG::") or data.startswith(b"VOICEMSG::") or data.startswith(b"FILE::"):
                    # Tách payload: "PREFIX::SENDER::RECEIVER::CONTENT"
                    parts = data.split(b"::", 3)
                    if len(parts) != 4:
                        print(f"Format message không hợp lệ từ {username}")
                        continue

                    _, sender_b, receiver_b, content = parts
                    receiver_name = receiver_b.decode('utf-8', errors='ignore')
                    
                    # Nếu người nhận là "ALL"
                    if receiver_name == "ALL":
                        # Gửi tin nhắn này cho TẤT CẢ MỌI NGƯỜI (loai tru người gửi)
                        print(f"[BROADCAST] từ '{username}'")
                        # Truyền "conn" (socket của người gửi) vào để loại trừ
                        broadcast_message(data, exclude_conn=conn)
                    else:
                        # Nếu là tin nhắn riêng, chỉ gửi cho người nhận
                        print(f"[PRIVATE] từ '{username}' tới '{receiver_name}'")
                        send_to_user_only(receiver_name, data)
                else:
                    # Nhận được một định dạng tin nhắn không xác định
                    print(f"Nhận payload không hợp lệ từ {username}, loại: {data[:30]!r}")
                    
            except Exception as e:
                print(f"Lỗi xử lý message từ {username}: {e}")
                break # Thoát vòng lặp nếu có lỗi nghiêm trọng

    except Exception as e:
        print(f"Lỗi client {addr}: {e}")
    finally:
        # --- Giai đoạn 4: Dọn dẹp (Cleanup) ---
        # Khối finally này LUÔN LUÔN chạy,
        # dù client ngắt kết nối (break) hay bị lỗi (exception).
        
        with clients_lock:
            # Xóa client khỏi dictionary
            if conn in clients:
                del clients[conn]
        
        print(f"Người dùng '{username}' ({addr}) đã rời khỏi.")
        
        # Cập nhật user list cho những người còn lại
        broadcast_user_list()
        
        # Đóng socket của client này
        try:
            conn.close()
        except Exception:
            pass # Bỏ qua nếu socket đã đóng

# ================================
# === HÀM KHỞI ĐỘNG SERVER ===
# ================================

def start_server():
    # Tạo socket server
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Thiết lập SO_REUSEADDR để cho phép tái sử dụng địa chỉ/port ngay lập tức
    # Tránh lỗi "Address already in use" khi khởi động lại server nhanh
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Gắn socket vào địa chỉ HOST và PORT
    server_socket.bind((HOST, PORT))
    
    # Bắt đầu lắng nghe kết nối
    server_socket.listen()
    print(f"[ĐANG LẮNG NGHE] Server tại {HOST}:{PORT}")

    try:
        # Vòng lặp vô tận để chấp nhận kết nối mới
        while True:
            # Chờ (block) cho đến khi có client kết nối
            # .accept() trả về (conn, addr)
            # conn: là socket MỚI dành riêng cho client này
            # addr: là địa chỉ (IP, port) của client
            conn, addr = server_socket.accept()
            
            # Tạo một luồng (thread) mới để xử lý client này
            # target=handle_client: hàm mà luồng sẽ chạy
            # args=(conn, addr): các đối số truyền vào hàm handle_client
            # daemon=True: khi chương trình chính (server) tắt, các luồng con này cũng tự tắt theo
            thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            
            # Bắt đầu chạy luồng
            thread.start()
            
    except KeyboardInterrupt:
        # Xử lý khi người dùng nhấn Ctrl+C để tắt server
        print("\n[ĐÓNG SERVER] Server đang tắt...")
    finally:
        # Đóng socket chính của server
        server_socket.close()
        print("[ĐÃ ĐÓNG] Server đã đóng hoàn toàn.")

# --- Điểm khởi chạy của chương trình ---
if __name__ == "__main__":
    start_server()











