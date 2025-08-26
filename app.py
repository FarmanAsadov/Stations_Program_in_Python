# import tkinter as tk
# from tkinter import ttk, messagebox
# import serial
# import threading
# from serial.tools import list_ports
# import time
# import re
# import json
# import winsound


# ser = None
# reading = False

# response_event = threading.Event()
# last_sms_buffer = []
# last_sent_number = None
# stop_alert_event = threading.Event()

# import sys
# import os

# def resource_path(relative_path):
#     try:
#         base_path = sys._MEIPASS  # PyInstaller exe içi üçün
#     except Exception:
#         base_path = os.path.abspath(".")  # normal Python
#     return os.path.join(base_path, relative_path)

# # .exe harada yerləşibsə, orada stations.txt faylını istifadə et
# exe_dir = os.path.dirname(sys.executable)
# stations_file = os.path.join(exe_dir, "stations.txt")


# log_file_path = resource_path("serial_log.txt")
# log_file = open(log_file_path, "a", encoding="utf-8")

# # Faylları açmaq üçün:
# with open(stations_file, "w", encoding="utf-8") as f:
#     json.dump(stations, f, indent=4, ensure_ascii=False)

# log_file = open(log_file_path, "a", encoding="utf-8")



# def list_serial_ports():
#     ports = list_ports.comports()
#     return [port.device for port in ports]


# def refresh_ports():
#     ports = list_serial_ports()
#     port_dropdown["values"] = ports
#     if ports:
#         port_var.set(ports[0])


# def connect_serial():
#     global ser, reading
#     port = port_var.get()
#     if not port:
#         messagebox.showwarning("Diqqət", "Zəhmət olmasa COM port seçin.")
#         return
#     try:
#         ser = serial.Serial(port, 9600, timeout=1)
#         reading = True
#         status_label.config(text=f"Qoşuldu: {port}", fg="green")
#         threading.Thread(target=read_serial, daemon=True).start()
#     except Exception as e:
#         messagebox.showerror("Xəta", f"Qoşulmaq mümkün olmadı:\n{e}")


# def disconnect_serial():
#     global ser, reading
#     reading = False
#     if ser and ser.is_open:
#         ser.close()
#         status_label.config(text="Bağlandı", fg="red")


# def log_message(msg):
#     log_file.write(msg + "\n")
#     log_file.flush()


# def send_command(cmd):
#     global ser
#     if ser and ser.is_open:
#         try:
#             ser.write((cmd + "\r\n").encode())
#             log_message(f"Sent: {cmd}")

#             # Cavab gözləmə funksiyasını ayrı thread-də işə salırıq
#             threading.Thread(target=wait_for_response, daemon=True).start()

#         except Exception as e:
#             messagebox.showerror("Xəta", f"Komanda göndərmək mümkün olmadı:\n{e}")
#     else:
#         messagebox.showwarning("Diqqət", "Serial port qoşulu deyil!")


# def read_serial():

    
#     global reading
#     capturing_cmgr = False
#     cmgr_message = ""

#     while reading:
#         try:
#             if ser is None or not ser.is_open:
#                 print("Port bağlı deyil və ya mövcud deyil.")
#                 time.sleep(1)
#                 continue  # dövrü davam etdir, oxumağa çalışma

#             line = ser.readline()
#             if line:
#                 line_str = line.decode("utf-8", errors="replace").strip()
#                 log_message(f"Received: {line_str}")

#                 # output_text.config(state=tk.NORMAL)
#                 # output_text.insert(tk.END, line_str + "\n")
#                 # output_text.see(tk.END)
#                 # output_text.config(state=tk.DISABLED)

#                 if line_str.startswith("+CMTI:"):
#                     match = re.search(r'\+CMTI: ".*?",(\d+)', line_str)
#                     if match:
#                         index = match.group(1)
#                         send_command(f"AT+CMGR={index}")

#                 if line_str.startswith("+CMGR:"):
#                     capturing_cmgr = True
#                     cmgr_message = ""
#                 elif capturing_cmgr:
#                     if line_str == "OK" or line_str == "ERROR":
#                         capturing_cmgr = False
#                         if cmgr_message.strip():
#                             last_sms_buffer.append(cmgr_message.strip())
#                             response_event.set()
#                     else:
#                         cmgr_message += line_str + "\n"

#         except Exception as e:
#             print("Oxuma xətası:", e)
#             time.sleep(1)  # xətadan sonra qısa gözləmə, çoxlu error axını olmaması üçün


# def alert_sound_thread():
#     """
#     Dayanmayan xəbərdarlıq səsi çalır, stop_event set olunanda dayanır.
#     """
#     while not stop_alert_event.is_set():
#         winsound.Beep(1000, 500)  # 1000 Hz, 500 ms
#         time.sleep(0.5)


# def wait_for_response(timeout=60, number=None, station_name=None, retry=True):
#     """
#     Cavab gözləyir. Timeout = timeout saniyə.
#     """
#     print("Cavab gözlənir...")
#     response_event.clear()
#     is_received = response_event.wait(timeout=timeout)

#     if is_received and last_sms_buffer:
#         message = last_sms_buffer.pop(0)
#         root.after(0, show_status, message)
#         return  # Cavab gəldi, retry etmə

#     # Cavab gəlməyibsə
#     if not is_received and retry and number:
#         print(f"{number} cavab vermədi, STATUS mesajı yenidən göndərilir...")
#         send_sms(number, "STATUS")
#         threading.Thread(
#             target=wait_for_response, 
#             args=(timeout, number, station_name, False), 
#             daemon=True
#         ).start()
#     elif not is_received:
#         # Əgər cavab gəlməyibsə və retry False-dursa alert göstər
#         root.after(0, lambda: send_sms_status(number))


# def show_status(msg):
#     global station_widgets
#     status_label.config(text="Cavab alındı", fg="green")

#     if last_sent_number and last_sent_number in station_widgets:
#         label = station_widgets[last_sent_number]["response_label"]
#         label.config(text=msg)
#     else:
#         print("Cavab hansı stansiyaya aiddir, təyin edilə bilmədi.")


# def send_sms(number, message):
#     global last_sent_number
#     last_sent_number = number  # sonuncu göndərilən nömrəni yadda saxla

#     if ser and ser.is_open:
#         ser.write(b"AT+CMGF=1\r\n")
#         time.sleep(0.5)
#         ser.write(f'AT+CMGS="{number}"\r\n'.encode())
#         time.sleep(0.5)
#         ser.write((message + chr(26)).encode())
#         time.sleep(1)
#     else:
#         print("Serial port açıq deyil")
#         messagebox.showwarning("Diqqət", "Serial port qoşulu deyil!")


# def send_sms_status(number):
#     """
#     Cavab gəlmədikdə stansiya işləmədiyini göstərən mesaj və dayandırıla bilən səs.
#     """
#     stop_alert_event.clear()
#     # Səsi ayrı thread-də işə sal
#     t = threading.Thread(target=alert_sound_thread, daemon=True)
#     t.start()

#     # Mesaj qutusunu göstərəcəyik
#     messagebox.showwarning(
#         f"Stansiya işləmir: {number}",
#         f"{number} stansiyası 2 dəqiqə ərzində cavab vermədi!\nOK düyməsini basın səsi dayandırmaq üçün."
#     )

#     # OK basıldıqda səsi dayandır
#     stop_alert_event.set()
#     t.join()

# def load_stations():
#     # Fayl yoxdursa yaradılır
#     if not os.path.exists(stations_file):
#         with open(stations_file, "w", encoding="utf-8") as f:
#             json.dump([], f, indent=4, ensure_ascii=False)
#         return []
#     else:
#         with open(stations_file, "r", encoding="utf-8") as f:
#             try:
#                 return json.load(f)
#             except json.JSONDecodeError:
#                 return []


# def draw_station_cards(stations):
#     global station_widgets
#     station_widgets = {}

#     for widget in stations_frame.winfo_children():
#         widget.destroy()

#     columns = 5  # 5 sütunlu layout

#     for i, station in enumerate(stations):
#         card = tk.Frame(
#             stations_frame, bg="white", bd=2, relief="solid", padx=10, pady=10
#         )
#         # row və column təyini
#         row = i // columns
#         col = i % columns
#         card.grid(row=row, column=col, padx=10, pady=10, sticky="n")

#         tk.Label(
#             card,
#             text=f"Stansiya: {station['station']}",
#             font=("Arial", 12, "bold"),
#             bg="white",
#             fg="#000",
#         ).pack(anchor="w")
#         tk.Label(
#             card,
#             text=f"Yer: {station['location']}",
#             font=("Arial", 11),
#             fg="#000",
#             bg="white",
#         ).pack(anchor="w")
#         tk.Label(
#             card,
#             text=f"Nömrə: {station['phone']}",
#             font=("Arial", 11),
#             fg="#000",
#             bg="white",
#         ).pack(anchor="w")

#         response_label = tk.Label(
#             card,
#             text="",
#             font=("Arial", 10),
#             fg="blue",
#             bg="white",
#             justify="left",
#             wraplength=150,  # qutunun eni ilə uyğun
#         )
#         response_label.pack(anchor="w", pady=(10, 0))

#         station_widgets[station["phone"]] = {
#             "card": card,
#             "response_label": response_label,
#         }

#         # Status və Sil düymələri
#         button_frame = tk.Frame(card, bg="white")
#         button_frame.pack(anchor="e", pady=(10, 0))

#         status_btn = tk.Button(
#             button_frame,
#             text="Status",
#             bg="#007bff",
#             fg="#000",
#             width=10,
#             command=lambda number=station["phone"]: (
#                  station_widgets[number]["response_label"].config(text=""),  # Label-i boşalt
#                 send_sms(number, "STATUS"),
#                 threading.Thread(target=wait_for_response, args=(60, number, True), daemon=True).start()
#             ),
#         )
#         status_btn.grid(row=0, column=0, padx=5)

#         del_btn = tk.Button(
#             button_frame,
#             text="Sil",
#             bg="#d9534f",
#             fg="#000",
#             command=lambda s=station: delete_station(s),
#             width=10,
#         )
#         del_btn.grid(row=0, column=1, padx=5)


# def delete_station(station):
#     if messagebox.askyesno("Təsdiq", f"'{station['station']}' stansiyasını silmək istəyirsiniz?"):
#         try:
#             all_stations = load_stations()
#         except:
#             all_stations = []
#         all_stations = [s for s in all_stations if s != station]
#         with open("stations.txt", "w", encoding="utf-8") as f:
#             json.dump(all_stations, f, indent=4, ensure_ascii=False)
#         draw_station_cards(all_stations)


# def open_add_modal():
#     modal = tk.Toplevel(root)
#     modal.title("Yeni Stansiya Əlavə Et")
#     modal.geometry("300x250")
#     modal.grab_set()

#     tk.Label(modal, text="Stansiya Adı:").pack(pady=(10, 0))
#     name_entry = tk.Entry(modal, width=30)
#     name_entry.pack()

#     tk.Label(modal, text="Yer:").pack(pady=(10, 0))
#     location_entry = tk.Entry(modal, width=30)
#     location_entry.pack()

#     tk.Label(modal, text="Nömrə:").pack(pady=(10, 0))
#     phone_entry = tk.Entry(modal, width=30)
#     phone_entry.pack()

#     def submit():
#         name = name_entry.get().strip()
#         location = location_entry.get().strip()
#         phone = phone_entry.get().strip()

#         if not name or not location or not phone:
#             messagebox.showwarning("Xəta", "Bütün sahələri doldurun!")
#             return

#         # Nömrə validasiyası
#         pattern = r"^\+994(51|50|55|70|77|99)\d{7}$"
#         if not re.match(pattern, phone):
#             messagebox.showwarning("Xəta", "Nömrə düzgün formatda deyil! Məsələn: +99477xxxxxxx")
#             return

#         new_station = {"station": name, "location": location, "phone": phone}
#         try:
#             stations = load_stations()
#         except:
#             stations = []

#         stations.append(new_station)

#         with open("stations.txt", "w", encoding="utf-8") as f:
#             json.dump(stations, f, indent=4, ensure_ascii=False)

#         draw_station_cards(stations)
#         modal.destroy()

#     tk.Button(modal, text="Əlavə Et", command=submit, bg="#28a745", fg="#000").pack(
#         pady=20
#     )


# root = tk.Tk()
# root.title("COM Port Monitor")
# width, height = 1250, 600
# screen_width = root.winfo_screenwidth()
# screen_height = root.winfo_screenheight()
# x = (screen_width - width) // 2
# y = (screen_height - height) // 2
# root.geometry(f"{width}x{height}+{x}+{y}")
# root.configure(bg="#f0f0f0")

# port_var = tk.StringVar()
# tk.Label(
#     root,
#     text="COM port seç:",
#     bg="#f0f0f0",
#     fg="#000",
#     font=("Courier New", 16, "bold"),
# ).place(x=10, y=20)

# port_dropdown = ttk.Combobox(root, textvariable=port_var, font=("Arial", 11), width=30)

# port_dropdown.place(x=180, y=20)

# status_label = tk.Label(
#     root, text="Qoşulmayıb", fg="red", bg="#f0f0f0", font=("Arial", 16)
# )
# status_label.place(x=20, y=60)


# tk.Button(root, text="Yenilə", command=refresh_ports, width=10, bg="#d12b2b").place(
#     x=450, y=18
# )

# tk.Button(root, text="Qoşul", command=connect_serial, width=10, bg="#06a96d").place(
#     x=540, y=18
# )

# tk.Button(root, text="Bağla", command=disconnect_serial, width=10, bg="#5c3538").place(
#     x=630, y=18
# )

# tk.Button(
#     root, text="Stansiya əlavə et", command=open_add_modal, bg="#2b7de9", fg="#000"
# ).place(x=1100, y=18)

# canvas_frame = tk.Frame(root, bg="#901414")

# canvas_frame.place(x=50, y=100, width=1150, height=480)

# canvas = tk.Canvas(canvas_frame, bg="#f0f0f0")

# scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)

# stations_frame = tk.Frame(canvas, bg="#f0f0f0")

# stations_frame.bind(
#     "<Configure>",
#     lambda e: (canvas.configure(scrollregion=canvas.bbox("all"))    )  # Scrollu yuxarıya sıfırla
# )

# canvas.create_window((0, 0), window=stations_frame, anchor="nw")

# canvas.configure(yscrollcommand=scrollbar.set)

# canvas.pack(side="left", fill="both", expand=True)

# scrollbar.pack(side="right", fill="y")

# # Mouse wheel ilə scroll
# def _on_mousewheel(event):
#     canvas.yview_scroll(-1 * (event.delta // 120), "units")

# canvas.bind_all("<MouseWheel>", _on_mousewheel)



# stations = load_stations()

# draw_station_cards(stations)

# refresh_ports()

# root.mainloop()

