
-----

# Ứng dụng Chat Voice và Text qua mạng LAN

Đây là một dự án ứng dụng chat client-server đơn giản, cho phép người dùng trong cùng một mạng nội bộ (LAN) có thể trò chuyện, gửi tin nhắn thoại và chia sẻ tệp tin với nhau.

## Mục lục

  - [Tính năng chính](https://www.google.com/search?q=%23t%C3%ADnh-n%C4%83ng-ch%C3%ADnh)
  - [Công nghệ sử dụng](https://www.google.com/search?q=%23c%C3%B4ng-ngh%E1%BB%87-s%E1%BB%AD-d%E1%BB%A5ng)
  - [Nguyên lý hoạt động](https://www.google.com/search?q=%23nguy%C3%AAn-l%C3%BD-ho%E1%BA%A1t-%C4%91%E1%BB%99ng)
      - [Mô hình Client-Server](https://www.google.com/search?q=%23m%C3%B4-h%C3%ACnh-client-server)
      - [Giao thức truyền tin (Custom Protocol)](https://www.google.com/search?q=%23giao-th%E1%BB%A9c-truy%E1%BB%81n-tin-custom-protocol)
      - [Luồng xử lý tin nhắn](https://www.google.com/search?q=%23lu%E1%BB%93ng-x%E1%BB%AD-l%C3%BD-tin-nh%E1%BA%AFn)
  - [Hướng dẫn cài đặt và sử dụng](https://www.google.com/search?q=%23h%C6%B0%E1%BB%9Bng-d%E1%BA%ABn-c%C3%A0i-%C4%91%E1%BA%B7t-v%C3%A0-s%E1%BB%AD-d%E1%BB%A5ng)

## Tính năng chính

  * **Chat Text thời gian thực:** Gửi và nhận tin nhắn văn bản.
  * **Chat Voice (Tin nhắn thoại):** Ghi âm và gửi tin nhắn thoại. Người nhận có thể nhấn nút để nghe lại.
  * **Gửi Tệp tin:** Chia sẻ tệp tin (ảnh, tài liệu, v.v.) với người khác.
  * **Chat Nhóm (ALL):** Gửi tin nhắn đến tất cả mọi người đang hoạt động.
  * **Chat Riêng tư (Private):** Nhấn vào tên người dùng trong danh sách để mở tab chat riêng tư.
  * **Danh sách người dùng:** Tự động cập nhật danh sách người dùng đang trực tuyến.
  * **Giao diện hiện đại:** Sử dụng CustomTkinter với hỗ trợ chế độ Sáng/Tối.

## Công nghệ sử dụng

  * **Ngôn ngữ:** Python 3
  * **Giao diện (Client):** `CustomTkinter` (một phiên bản hiện đại của `Tkinter`).
  * **Mạng (Network):**
      * `socket`: Lập trình mạng TCP/IP cấp thấp.
      * `threading`: Xử lý đa luồng, cho phép server phục vụ nhiều client cùng lúc và client nhận tin nhắn ở chế độ nền.
  * **Âm thanh (Audio):**
      * `sounddevice`: Ghi âm (input) và phát (output) âm thanh.
      * `numpy`: Xử lý mảng dữ liệu âm thanh.

## Nguyên lý hoạt động

Hệ thống hoạt động theo mô hình Client-Server qua giao thức TCP.

### Mô hình Client-Server

1.  **Server (`server.py`):**

      * Khởi chạy và lắng nghe kết nối tại một cổng cố định (ví dụ: `12345`).
      * Sử dụng `threading`, mỗi khi có một client kết nối, server sẽ tạo một luồng (thread) mới (`handle_client`) để xử lý riêng cho client đó.
      * Duy trì một dictionary (`clients = {conn: username}`) để quản lý tất cả các kết nối và tên người dùng tương ứng.

2.  **Client (`client.py`):**

      * Là một ứng dụng GUI.
      * Người dùng nhập IP của server và tên đăng nhập.
      * Khi nhấn "Kết nối", client tạo một `socket` kết nối đến server.
      * Client ngay lập tức gửi tin nhắn `USERNAME::ten_cua_toi` để đăng ký với server.
      * Client khởi chạy một luồng nền (`receive_data`) để liên tục lắng nghe và nhận dữ liệu từ server mà không làm đơ giao diện.

### Giao thức truyền tin (Custom Protocol)

Để phân biệt các loại dữ liệu, hệ thống sử dụng một giao thức văn bản đơn giản dựa trên 2 thành phần:

1.  **Header (10 bytes):** Mỗi tin nhắn gửi đi đều có 10 bytes đầu tiên chứa độ dài (dưới dạng text) của payload (nội dung chính).
2.  **Payload (Nội dung):** Dữ liệu thực tế, sử dụng `::` làm dấu phân cách.

**Các loại Payload phổ biến:**

  * **Đăng nhập:** `USERNAME::tencuaban`
  * **Danh sách User (Server gửi):** `USERLIST::user1,user2,user3`
  * **Tin nhắn Text:** `TEXTMSG::nguoi_gui::nguoi_nhan::noi_dung_tin_nhan`
  * **Tin nhắn Voice:** `VOICEMSG::nguoi_gui::nguoi_nhan::[du_lieu_bytes_am_thanh]`
  * **Tin nhắn File:** `FILE::nguoi_gui::nguoi_nhan::ten_file::[du_lieu_bytes_cua_file]`

(Trong đó `nguoi_nhan` có thể là "ALL" hoặc một username cụ thể).

### Luồng xử lý tin nhắn

Đây là phần quan trọng nhất để hiểu cách hệ thống hoạt động mà không bị lặp tin nhắn.

**Luồng gửi tin từ Client A (đến "ALL"):**

1.  Client A (người gửi) nhấn nút "Gửi" (hoặc dừng ghi âm).
2.  Client A tạo payload, ví dụ: `VOICEMSG::ClientA::ALL::[audio_bytes]`.
3.  Client A tính độ dài payload, tạo header 10-byte.
4.  Client A gửi `[HEADER][PAYLOAD]` đến Server.
5.  **Ngay lập tức**, Client A tự hiển thị tin nhắn của mình lên giao diện (`add_message_widget`).

**Luồng xử lý tại Server:**

6.  Server (luồng của Client A) nhận được tin nhắn (`receive_message`).
7.  Server phân tích payload, thấy người nhận là "ALL".
8.  Server gọi hàm `broadcast_message(data, exclude_conn=conn_A)`.
9.  Hàm này lặp qua `clients` dictionary và gửi `[HEADER][PAYLOAD]` cho **TẤT CẢ** client **TRỪ** `conn_A` (người gửi).

**Luồng nhận tin tại Client B:**

10. Luồng nền `receive_data` của Client B nhận được `[HEADER][PAYLOAD]` từ server.
11. Client B phân tích payload (`VOICEMSG::ClientA::ALL::...`).
12. Client B thấy người gửi là "ClientA" và người nhận là "ALL".
13. Client B sử dụng `self.after(0, ...)` để gọi hàm `add_message_widget` (một cách an toàn từ luồng phụ) và hiển thị tin nhắn của Client A lên tab "ALL".

> **Tại sao không bị lặp?**
> Tin nhắn chỉ bị lặp nếu Server gửi lại tin nhắn cho chính người gửi (Client A). Bằng cách sử dụng `exclude_conn=conn_A` ở server, chúng ta đảm bảo server chỉ "chuyển tiếp" tin nhắn đi, và Client A chỉ hiển thị tin nhắn của mình 1 lần duy nhất (ngay tại thời điểm gửi).

## Hướng dẫn cài đặt và sử dụng

### Yêu cầu

Cần cài đặt các thư viện Python (sử dụng pip):

```bash
pip install customtkinter sounddevice numpy
```

### Các bước thực hiện

1.  **Chạy Server:**

      * Mở terminal, chạy file `server.py`:
        ```bash
        python server.py
        ```
      * Server sẽ khởi động và in ra: `[ĐANG LẮNG NGHE] Server tại 0.0.0.0:12345`.
      * **Lưu ý:** Bạn cần tìm địa chỉ IP LAN của máy này (ví dụ: `192.168.1.100`) bằng cách dùng lệnh `ipconfig` (Windows) hoặc `ifconfig` (Linux/Mac).

2.  **Chạy Client:**

      * Trên cùng máy hoặc một máy khác trong cùng mạng LAN, mở terminal và chạy file `client.py`:
        ```bash
        python client.py
        ```
      * **IP Server:** Nhập địa chỉ IP LAN của máy chủ (ví dụ: `192.168.1.100`).
      * **Tên bạn:** Nhập tên hiển thị (ví dụ: "Alice").
      * Nhấn "Kết nối".
      * Lặp lại bước này trên các máy khác (với tên khác, ví dụ: "Bob") để bắt đầu chat.