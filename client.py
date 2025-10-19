import socket
import threading
import sounddevice as sd
import numpy as np
import customtkinter as ctk
import time
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
import os
import sys
import subprocess
import tempfile

# ================== CẤU HÌNH AUDIO / NETWORK ==================
SAMPLE_RATE = 44100
CHANNELS = 1
DTYPE = np.int16
CHUNK = 1024
HEADER_SIZE = 10

# ================== LỚP GIAO DIỆN CHÍNH ==================
class VoiceChatClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LAN Text & Voice Message Chat")
        self.geometry("780x480")

        # === Giao diện mặc định light, có thể toggle sau ===
        ctk.set_appearance_mode("light")  # chế độ sáng/tối
        ctk.set_default_color_theme("blue")
        self.appearance_mode = "light"  # lưu chế độ hiện tại

        # trạng thái
        self.is_connected = False
        self.is_recording = False
        self.recorded_frames = []
        self.username = ""
        self.socket = None
        self.receive_thread = None
        self.private_chats = {}  # chứa các khung chat riêng {username/group: Frame}
        self.current_chat = "ALL"

        # Layout chính (2 cột: trái controls, phải chat)
        self.grid_columnconfigure(0, weight=1, minsize=300)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        # === CỘT TRÁI ===
        self.left_frame = ctk.CTkFrame(self, width=300)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.left_frame.pack_propagate(False)

        # Controls (IP, username)
        self.controls_frame = ctk.CTkFrame(self.left_frame)
        self.controls_frame.pack(pady=10, padx=10, fill="x")
        self.ip_label = ctk.CTkLabel(self.controls_frame, text="IP Server:")
        self.ip_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.ip_entry = ctk.CTkEntry(self.controls_frame, placeholder_text="192.168.1.100")
        self.ip_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.user_label = ctk.CTkLabel(self.controls_frame, text="Tên bạn:")
        self.user_label.grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.user_entry = ctk.CTkEntry(self.controls_frame, placeholder_text="Nhập tên")
        self.user_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.controls_frame.grid_columnconfigure(1, weight=1)

        # Nút kết nối
        self.connect_button = ctk.CTkButton(self.left_frame, text="Kết nối", command=self.toggle_connection)
        self.connect_button.pack(pady=8, padx=10, fill="x")

        # Nút gửi file mới (chức năng thêm)
        self.send_file_button = ctk.CTkButton(self.left_frame, text="Gửi tệp...", command=self.choose_and_send_file, state="disabled")
        self.send_file_button.pack(pady=(0,8), padx=10, fill="x")

        # Toggle chế độ sáng/tối (mới)
        self.theme_button = ctk.CTkButton(self.left_frame, text="Chuyển chế độ Sáng/Tối", command=self.toggle_theme)
        self.theme_button.pack(pady=(0,8), padx=10, fill="x")

        # Hiển thị trạng thái và thời gian (mới)
        self.status_label = ctk.CTkLabel(self.left_frame, text="Trạng thái: Chưa kết nối", text_color="gray")
        self.status_label.pack(pady=5, padx=10)
        self.datetime_label = ctk.CTkLabel(self.left_frame, text="", text_color="gray")  # hiển thị ngày giờ đầy đủ
        self.datetime_label.pack(pady=(0,10), padx=10)
        self.update_datetime()  # bắt đầu luồng cập nhật ngày giờ

        # Danh sách user
        self.user_list_label = ctk.CTkLabel(self.left_frame, text="Đang hoạt động (0):", anchor="w")
        self.user_list_label.pack(pady=(10,0), padx=10, fill="x")
        self.user_list_frame = ctk.CTkScrollableFrame(self.left_frame)
        self.user_list_frame.pack(fill="both", expand=True, pady=5, padx=10)
        self.user_widgets = []

        # === KHUNG CHAT CHÍNH (PHẢI) ===
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, padx=(0,10), pady=10, sticky="nsew")
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        # TabView chứa các khung chat riêng
        self.chat_tabs = ctk.CTkTabview(self.right_frame)
        self.chat_tabs.grid(row=0, column=0, columnspan=4, padx=10, pady=10, sticky="nsew")

        # tab chat nhóm
        self.group_tab = self.chat_tabs.add("ALL (Nhóm)")
        self.private_chats["ALL"] = self._create_chat_area(self.group_tab, "ALL")

        # controls gửi tin
        self.message_entry = ctk.CTkEntry(self.right_frame, placeholder_text="Nhập tin nhắn...", state="disabled")
        self.message_entry.grid(row=1, column=0, padx=6, pady=(0,10), sticky="ew", columnspan=2)
        self.message_entry.bind("<Return>", self.send_text_message)

        self.send_button = ctk.CTkButton(self.right_frame, text="Gửi", width=80, state="disabled", command=self.send_text_message)
        self.send_button.grid(row=1, column=2, padx=6, pady=(0,10))

        self.record_button = ctk.CTkButton(self.right_frame, text="🎤", width=60, state="disabled", command=self.toggle_recording)
        self.record_button.grid(row=1, column=3, padx=6, pady=(0,10))

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Khởi tạo sounddevice để tránh lỗi khi lần đầu dùng
        try:
            sd.play(np.zeros(100, dtype=DTYPE), samplerate=SAMPLE_RATE)
            sd.stop()
        except Exception:
            pass

    # ================== THEME ==================
    def toggle_theme(self):
        """Chuyển chế độ sáng/tối (dark <-> light)"""
        if self.appearance_mode == "dark":
            ctk.set_appearance_mode("light")
            self.appearance_mode = "light"
        else:
            ctk.set_appearance_mode("dark")
            self.appearance_mode = "dark"

    # ================== NGÀY GIỜ ==================
    def update_datetime(self):
        """Cập nhật label ngày giờ mỗi giây (format: YYYY-MM-DD HH:MM:SS)"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.datetime_label.configure(text=now)
        # gọi lại sau 1s
        self.after(1000, self.update_datetime)

    # ================== TẠO KHUNG CHAT MỚI ==================
    def _create_chat_area(self, parent, title):
        chat_frame = ctk.CTkScrollableFrame(parent, label_text=f"Cuộc trò chuyện: {title}")
        chat_frame.pack(fill="both", expand=True, padx=10, pady=10)
        return chat_frame

    def _ensure_chat_tab(self, username):
        """Tạo tab riêng nếu chưa có"""
        if username not in self.private_chats:
            tab = self.chat_tabs.add(username)
            self.private_chats[username] = self._create_chat_area(tab, username)
        self.chat_tabs.set(username)
        self.current_chat = username

    # ================== HIỂN THỊ TIN NHẮN / VOICE / FILE ==================
    def add_message_widget(self, sender, content, chat_name="ALL", is_voice=False, is_file=False):
        """
        Thêm tin nhắn vào chat.
        - is_voice: content = (audio_bytes, duration)
        - is_file: content = (filename, file_bytes)
        - text: content = str
        """
        frame = self.private_chats.get(chat_name)
        if not frame:
            # ensure tab exists and return the frame
            self._ensure_chat_tab(chat_name)
            frame = self.private_chats[chat_name]

        msg_frame = ctk.CTkFrame(frame, fg_color="transparent")
        is_self = (sender == self.username)
        msg_frame.pack(fill="x", pady=3, padx=5, anchor="e" if is_self else "w")

        bubble_color = "#6DF32F" if is_self else "#D8CAB8"
        bubble = ctk.CTkFrame(msg_frame, fg_color=bubble_color, corner_radius=10)
        bubble.pack(side="right" if is_self else "left", padx=10, pady=2)

        # Hiển thị tên nếu không phải mình
        if not is_self:
            ctk.CTkLabel(bubble, text=sender, font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=6, pady=(4,0))

        # Nội dung tin nhắn
        if is_voice:
            audio_data, duration = content
            play_btn = ctk.CTkButton(bubble,
                                     text=f"▶ ({duration:.1f}s)",
                                     width=120,
                                     command=lambda d=audio_data: self.play_voice_message(d))
            play_btn.pack(padx=6, pady=(0,6))
        elif is_file:
            filename, file_bytes = content
            # nút Lưu / Mở file
            file_label = ctk.CTkLabel(bubble, text=f"[Tệp] {filename}", wraplength=450, justify="left")
            file_label.pack(anchor="w", padx=6, pady=(4,0))

            action_frame = ctk.CTkFrame(bubble, fg_color="transparent")
            action_frame.pack(anchor="w", padx=6, pady=(0,4))

            save_btn = ctk.CTkButton(action_frame, text="Lưu...", width=80,
                                     command=lambda fn=filename, b=file_bytes: self.save_received_file(fn, b))
            save_btn.pack(side="left", padx=(0,6))
            open_btn = ctk.CTkButton(action_frame, text="Mở", width=80,
                                     command=lambda fn=filename, b=file_bytes: self.open_received_file(fn, b))
            open_btn.pack(side="left")
        else:
            ctk.CTkLabel(bubble, text=content,
                         wraplength=450,
                         justify="left").pack(anchor="w", padx=6, pady=(0,4))

        # Thời gian gửi + dấu ✓ cho tin mình
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        suffix = " ✓" if is_self else ""
        ctk.CTkLabel(bubble,
                     text=f"{time_str}{suffix}",
                     font=ctk.CTkFont(size=10, slant="italic"),
                     text_color="gray").pack(anchor="e", padx=6, pady=(0,4))

        # cuộn xuống cuối
        self.after(100, lambda: frame._parent_canvas.yview_moveto(1.0))



    # ================== GỬI TIN VĂN BẢN ==================
    def send_text_message(self, event=None):
        msg = self.message_entry.get().strip()
        if not msg or not self.is_connected:
            return

        current_tab = self.chat_tabs.get()
        receiver = "ALL" if current_tab.startswith("ALL") else current_tab

        full = f"TEXTMSG::{self.username}::{receiver}::{msg}"
        self._send_message(full.encode('utf-8'))

        # Hiển thị local CHỈ khi là private (tránh duplicate ở group)
        self.add_message_widget(self.username, msg, chat_name=receiver)
        # if receiver != "ALL":
        #     self.add_message_widget(self.username, msg, chat_name=receiver)

        self.message_entry.delete(0, "end")

    # ================== GỬI FILE ==================
    def choose_and_send_file(self):
        """Mở hộp thoại chọn tệp và gửi file đã chọn"""
        if not self.is_connected:
            messagebox.showwarning("Chưa kết nối", "Vui lòng kết nối tới server trước khi gửi tệp.")
            return
        file_path = filedialog.askopenfilename(title="Chọn tệp để gửi",
                                               filetypes=[("All files", "*.*")])
        if not file_path:
            return
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            filename = os.path.basename(file_path)
            current_tab = self.chat_tabs.get()
            receiver = "ALL" if current_tab.startswith("ALL") else current_tab
            # Lưu ý: đơn giản dùng separator "::" cho metadata; tránh tên file chứa "::"
            payload = b"FILE::" + self.username.encode('utf-8') + b"::" + receiver.encode('utf-8') + b"::" + filename.encode('utf-8') + b"::" + data
            self._send_message(payload)

            self.add_message_widget(self.username, (filename, data), chat_name=receiver, is_file=True)
            # Hiển thị local CHỈ khi gửi private (tránh trùng group)
            # if receiver != "ALL":
            #     self.add_message_widget(self.username, (filename, data), chat_name=receiver, is_file=True)
        except Exception as e:
            messagebox.showerror("Lỗi gửi tệp", str(e))

    # ================== NHẬN DỮ LIỆU TỪ SOCKET ==================
    def _recv_all(self, n):
        """Đọc chính xác n bytes từ socket (nếu socket đóng trả về None)"""
        data = bytearray()
        while len(data) < n:
            packet = self.socket.recv(n - len(data))
            if not packet:
                return None
            data.extend(packet)
        return bytes(data)

    def _send_message(self, message_bytes):
        """Gửi message với header cố định HEADER_SIZE biểu diễn độ dài payload"""
        try:
            msg_len = f"{len(message_bytes):<{HEADER_SIZE}}".encode('utf-8')
            # Gửi header + payload
            self.socket.sendall(msg_len + message_bytes)
        except Exception:
            # Nếu lỗi khi gửi, ngắt kết nối an toàn
            self.disconnect()

    def _receive_message(self):
        header = self._recv_all(HEADER_SIZE)
        if not header:
            return None
        try:
            msg_len = int(header.decode('utf-8').strip())
        except:
            return None
        return self._recv_all(msg_len)

    def receive_data(self):
        """Luồng nhận dữ liệu: xử lý USERLIST, TEXTMSG, VOICEMSG, FILE"""
        while self.is_connected:
            try:
                data = self._receive_message()
                if not data:
                    print("🔌 Mất kết nối với server.")
                    break

                # --- xử lý các loại tin nhắn ---
                if data.startswith(b"USERLIST::"):
                    text = data.decode('utf-8', errors='ignore')
                    users = text.split("::", 1)[1].split(',') if "::" in text else []
                    self.after(0, lambda u=users: self.update_user_list_display(u))

                elif data.startswith(b"TEXTMSG::"):
                    parts = data.split(b"::", 3)
                    if len(parts) == 4:
                        sender = parts[1].decode(errors='ignore')
                        receiver = parts[2].decode(errors='ignore')
                        msg = parts[3].decode(errors='ignore')
                        # nếu receiver là ALL -> chat nhóm; nếu receiver là mình -> private tab sender
                        chat_name = "ALL" if receiver == "ALL" else (sender if receiver == self.username else receiver)
                        self.after(0, lambda s=sender, m=msg, c=chat_name: self.add_message_widget(s, m, c))
                        if receiver == self.username and chat_name not in self.private_chats:
                            self.after(0, lambda: self._ensure_chat_tab(sender))

                elif data.startswith(b"VOICEMSG::"):
                    parts = data.split(b"::", 3)
                    if len(parts) == 4:
                        sender = parts[1].decode(errors='ignore')
                        receiver = parts[2].decode(errors='ignore')
                        audio_bytes = parts[3]
                        # duration tính từ số bytes
                        duration = len(audio_bytes) / (SAMPLE_RATE * np.dtype(DTYPE).itemsize * CHANNELS)
                        chat_name = "ALL" if receiver == "ALL" else (sender if receiver == self.username else receiver)
                        content = (audio_bytes, duration)
                        self.after(0, lambda s=sender, c=content, cn=chat_name: self.add_message_widget(s, c, cn, True))
                        if receiver == self.username and chat_name not in self.private_chats:
                            self.after(0, lambda: self._ensure_chat_tab(sender))

                elif data.startswith(b"FILE::"):
                    # Định dạng payload: FILE::sender::receiver::filename::file_bytes
                    # Lưu ý: đơn giản hóa - không hỗ trợ filename chứa "::"
                    parts = data.split(b"::", 4)
                    if len(parts) == 5:
                        sender = parts[1].decode(errors='ignore')
                        receiver = parts[2].decode(errors='ignore')
                        filename = parts[3].decode(errors='ignore')
                        file_bytes = parts[4]
                        chat_name = "ALL" if receiver == "ALL" else (sender if receiver == self.username else receiver)
                        content = (filename, file_bytes)
                        self.after(0, lambda s=sender, c=content, cn=chat_name: self.add_message_widget(s, c, cn, False, True))
                        if receiver == self.username and chat_name not in self.private_chats:
                            self.after(0, lambda: self._ensure_chat_tab(sender))

                else:
                    # Không rõ định dạng - in debug
                    text = data.decode(errors='ignore')
                    print("Unknown payload:", text[:200])

            except OSError as e:
                print(f"⚠️ Socket đã đóng hoặc bị lỗi: {e}")
                break
            except Exception as e:
                print(f"❌ Lỗi khác trong receive_data: {e}")
                break

        print("🛑 Dừng luồng nhận dữ liệu.")
        self.is_connected = False
        # cập nhật giao diện khi bị ngắt
        self.after(0, lambda: self.update_status("Đã ngắt kết nối", "gray"))

    # ================== AUDIO ==================
    def play_voice_message(self, audio_data):
        threading.Thread(target=self._play_audio_thread, args=(audio_data,), daemon=True).start()

    def _play_audio_thread(self, audio_data):
        arr = np.frombuffer(audio_data, dtype=DTYPE)
        # nếu mono recorded dạng (n,1), flatten về (n,)
        if arr.ndim > 1 and arr.shape[1] == 1:
            arr = arr.reshape(-1)
        sd.play(arr, samplerate=SAMPLE_RATE)
        sd.wait()
    # ================== GHI ÂM ==================
    def toggle_recording(self):
        """Bắt đầu / dừng ghi âm"""
        if self.is_recording:
            # dừng ghi
            self.is_recording = False
            self.record_button.configure(text="🎤", fg_color="#3B8ED0")
            if self.recorded_frames:
                # nối các frame lại thành 1 mảng numpy
                audio_np = np.concatenate(self.recorded_frames, axis=0).astype(DTYPE)
                # flatten nếu (n,1)
                if audio_np.ndim > 1 and audio_np.shape[1] == 1:
                    audio_flat = audio_np.reshape(-1)
                else:
                    audio_flat = audio_np
                receiver_tab = self.chat_tabs.get()
                receiver = "ALL" if receiver_tab.startswith("ALL") else receiver_tab
                audio_bytes = audio_flat.tobytes()
                payload = b"VOICEMSG::" + self.username.encode('utf-8') + b"::" + receiver.encode('utf-8') + b"::" + audio_bytes
                # send voice payload
                self._send_message(payload)

                # Hiển thị local CHỈ khi là private (tránh trùng ở group)
                duration = len(audio_bytes) / (SAMPLE_RATE * np.dtype(DTYPE).itemsize * CHANNELS)
                self.add_message_widget(self.username, (audio_bytes, duration), chat_name=receiver, is_voice=True)
                # if receiver != "ALL":
                #     self.add_message_widget(self.username, (audio_bytes, duration), chat_name=receiver, is_voice=True)

                self.recorded_frames.clear()
        else:
            # bắt đầu ghi
            self.is_recording = True
            self.record_button.configure(text="■", fg_color="red")
            self.recorded_frames.clear()
            threading.Thread(target=self._record_audio_thread, daemon=True).start()

    def _record_audio_thread(self):
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE, blocksize=CHUNK) as stream:
                while self.is_recording:
                    data, _ = stream.read(CHUNK)
                    arr = np.asarray(data, dtype=DTYPE)
                    # normalize shape to (n,1) for mono, to keep consistent
                    if CHANNELS == 1 and arr.ndim == 1:
                        arr = arr.reshape(-1, 1)
                    self.recorded_frames.append(arr)
        except Exception as e:
            print("Recording error:", e)
            self.is_recording = False
            self.after(0, lambda: self.record_button.configure(text="🎤", fg_color=("#3B8ED0")))

    # ================== KẾT NỐI / NGẮT KẾT NỐI ==================
    def toggle_connection(self):
        if self.is_connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        host = self.ip_entry.get()
        self.username = self.user_entry.get()
        if not host or not self.username:
            self.update_status("Nhập IP & tên", "orange")
            return
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, 12345))
            self.is_connected = True
            # gửi USERNAME để server biết
            self._send_message(f"USERNAME::{self.username}".encode())
            self.update_status(f"Đã kết nối tới {host}", "green")
            self.connect_button.configure(text="Ngắt kết nối")
            self.message_entry.configure(state="normal")
            self.send_button.configure(state="normal")
            self.record_button.configure(state="normal")
            self.send_file_button.configure(state="normal")  # kích hoạt nút gửi file
            # bắt đầu luồng nhận
            threading.Thread(target=self.receive_data, daemon=True).start()
        except Exception as e:
            self.update_status(f"Lỗi: {e}", "red")

    def disconnect(self):
        self.is_connected = False
        try:
            if self.socket:
                try:
                    self.socket.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                self.socket.close()
        except Exception as e:
            print(f"⚠️ Lỗi khi đóng socket: {e}")
        finally:
            self.update_status("Đã ngắt kết nối", "gray")
            self.connect_button.configure(text="Kết nối")
            self.message_entry.configure(state="disabled")
            self.send_button.configure(state="disabled")
            self.record_button.configure(state="disabled")
            self.send_file_button.configure(state="disabled")
            print("✅ Socket đã được đóng hoàn toàn.\n")

    # ================== HELPER: SAVE & OPEN FILE NHẬN ĐƯỢC ==================
    def save_received_file(self, filename, file_bytes):
        """Mở hộp thoại lưu file cho file nhận được"""
        try:
            save_path = filedialog.asksaveasfilename(initialfile=filename, title="Lưu tệp", defaultextension=os.path.splitext(filename)[1])
            if not save_path:
                return
            with open(save_path, "wb") as f:
                f.write(file_bytes)
            messagebox.showinfo("Lưu tệp", f"Đã lưu: {save_path}")
        except Exception as e:
            messagebox.showerror("Lỗi lưu tệp", str(e))

    def open_received_file(self, filename, file_bytes):
        """
        Lưu tạm file vào thư mục temp rồi mở bằng chương trình mặc định của hệ điều hành.
        Hành vi khác nhau trên Windows/Linux/Mac được xử lý.
        """
        try:
            # tạo file tạm
            suffix = os.path.splitext(filename)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            # mở file tuỳ OS
            if sys.platform.startswith("win"):
                os.startfile(tmp_path)
            elif sys.platform.startswith("darwin"):
                subprocess.call(["open", tmp_path])
            else:
                # Linux / *nix
                subprocess.call(["xdg-open", tmp_path])
        except Exception as e:
            messagebox.showerror("Lỗi mở tệp", str(e))

    # ================== CẬP NHẬT GIAO DIỆN ==================
    def update_status(self, text, color):
        self.status_label.configure(text=f"Trạng thái: {text}", text_color=color)

    def update_user_list_display(self, users):
        # xóa widgets cũ
        for w in self.user_widgets:
            w.destroy()
        self.user_widgets.clear()
        # lọc bỏ tên mình và rỗng
        users = [u for u in users if u and u != self.username]
        self.user_list_label.configure(text=f"Đang hoạt động ({len(users)}):")
        for u in users:
            b = ctk.CTkButton(self.user_list_frame, text=f"👤 {u}",
                               command=lambda name=u: self._ensure_chat_tab(name))
            b.pack(fill="x", pady=2, padx=5)
            self.user_widgets.append(b)

    def on_closing(self):
        self.disconnect()
        self.destroy()

# ================== BẮT ĐẦU ỨNG DỤNG ==================
if __name__ == "__main__":
    app = VoiceChatClient()
    app.mainloop()









