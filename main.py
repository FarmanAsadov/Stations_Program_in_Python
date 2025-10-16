import tkinter as tk
from tkinter import ttk, messagebox
import serial
import threading
from serial.tools import list_ports
import time
import re
import json
import winsound
import sys
import os
import webbrowser

# --- Serial və SMS üçün global dəyişənlər ---
ser = None
reading = False
response_event = threading.Event()
last_sms_buffer = {}
last_sent_number = None
stop_alert_event = threading.Event()
station_widgets = {}
events = {}  # hər stansiya üçün ayrıca Event obyektləri
current_number = None  # <-- BURADA başlanğıc dəyər verilir

# --- .exe üçün fayl yolu ---
exe_dir = os.path.dirname(sys.executable)
stations_file = os.path.join(exe_dir, "stations.txt")
log_file_path = os.path.join(exe_dir, "serial_log.txt")

# --- Log faylı aç ---
log_file = open(log_file_path, "a", encoding="utf-8")


# --- Fayllarla işləmək funksiyaları ---
def load_stations():
    if not os.path.exists(stations_file):
        with open(stations_file, "w", encoding="utf-8") as f:
            json.dump([], f, indent=4, ensure_ascii=False)
        return []
    else:
        with open(stations_file, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []


def save_stations(stations):
    with open(stations_file, "w", encoding="utf-8") as f:
        json.dump(stations, f, indent=4, ensure_ascii=False)


# --- Serial port funksiyaları ---
def list_serial_ports():
    ports = list_ports.comports()
    return [port.device for port in ports]


def refresh_ports():
    ports = list_serial_ports()
    port_dropdown["values"] = ports
    if ports:
        port_var.set(ports[0])


def connect_serial():
    global ser, reading
    port = port_var.get()
    if not port:
        messagebox.showwarning("Diqqət", "Zəhmət olmasa COM port seçin.")
        return
    try:
        ser = serial.Serial(port, 9600, timeout=1)
        reading = True
        status_label.config(text=f"Qoşuldu: {port}", fg="green")

        # Modem hazırla: SMS text mode + yeni SMS-ləri avtomatik seriala göndər
        send_command("AT")          # Test
        time.sleep(0.2)
        send_command("AT+CMGF=1")   # SMS text mode
        time.sleep(0.2)
        send_command("AT+CNMI=2,2,0,0,0")  # Yeni SMS-ləri avtomatik göndər
        time.sleep(0.2)

        threading.Thread(target=read_serial, daemon=True).start()
    except Exception as e:
        messagebox.showerror("Xəta", f"Qoşulmaq mümkün olmadı:\n{e}")



def disconnect_serial():
    global ser, reading
    reading = False
    if ser and ser.is_open:
        ser.close()
        status_label.config(text="Bağlandı", fg="red")


def log_status(station_name, number, message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    # Ümumi log faylına yaz
    log_file.write(f"[{timestamp}] Stansiya: {station_name}, Nömrə: {number}, Mesaj: {message}\n")
    log_file.flush()

    # Stansiya adı üzrə ayrıca fayl
    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', station_name)
    station_log_file = os.path.join(exe_dir, f"{safe_name}.txt")
    with open(station_log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def send_command(cmd):
    global ser
    if ser and ser.is_open:
        try:
            ser.write((cmd + "\r\n").encode())
        except Exception as e:
            messagebox.showerror("Xəta", f"Komanda göndərmək mümkün olmadı:\n{e}")
    else:
        messagebox.showwarning("Diqqət", "Serial port qoşulu deyil!")


# --- Serial oxuma funksiyası ---
# def read_serial():
#     global reading
#     capturing_sms = False
#     current_number = None
#     sms_lines = []

#     while reading:
#         try:
#             if ser is None or not ser.is_open:
#                 time.sleep(1)
#                 continue

#             line = ser.readline()
#             if not line:
#                 continue

#             line_str = line.decode("utf-8", errors="replace").strip()
#             if not line_str:
#                 continue

#             print(">>", line_str)

#             # Yeni SMS notification
#             if line_str.startswith("+CMT:"):
#                 # Nömrəni çıxar
#                 num_match = re.search(r'"\+?(\d+)"', line_str)
#                 if num_match:
#                     current_number = "+" + num_match.group(1)
#                     capturing_sms = True
#                     sms_lines = []
#                     print(f"📥 Yeni SMS nömrədən: {current_number}")
#                 continue

#             # SMS mətni oxunur
#             if capturing_sms:
#                 print(f"📨 SMS mətni: {line_str}")
#                 print(f"📨 SMS_lines: {sms_lines}")
#                 sms_lines.append(line_str)
#                 # Əgər boş line və ya +CMT sətiri gəlirsə SMS bitir
#                 if line_str:
                    
#                     if current_number:
#                         msg = " ".join(sms_lines).strip()
#                         print(f"📨 Cavab gəldi: {msg}")
#                         # UI-də göstər
#                         root.after(0, lambda m=msg, n=current_number: show_status(m, n))
#                         # Log fayla yaz
#                         stations = load_stations()
#                         for station in stations:
#                             if station["phone"].endswith(current_number[-9:]):
#                                 log_status(station["station"], current_number, msg)
#                                 break
#                     # Yeni SMS üçün reset
#                     sms_lines = []
#                     capturing_sms = line_str.startswith("+CMT:")
#                     if capturing_sms:
#                         num_match = re.search(r'"\+?(\d+)"', line_str)
#                         if num_match:
#                             current_number = "+" + num_match.group(1)
#                             print(f"📥 Yeni SMS nömrədən: {current_number}")
#                     else:
#                         current_number = None
#                     continue

#                 # SMS mətni toplama
#                 sms_lines.append(line_str)

#         except Exception as e:
#             print("Oxuma xətası:", e)
#             time.sleep(1)

def read_serial():
    global reading
    capturing_sms = False
    current_number = None
    sms_lines = []

    while reading:
        try:
            if ser is None or not ser.is_open:
                time.sleep(1)
                continue

            line = ser.readline()
            if not line:
                continue

            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str:
                continue

            print(">>", line_str)

            # Yeni SMS notification
            if line_str.startswith("+CMT:"):
                # Əgər əvvəlki SMS-dən line varsa, onu bitir
                if sms_lines and current_number:
                    msg = " ".join(sms_lines).strip()
                    root.after(0, lambda m=msg, n=current_number: show_status(m, n))
                    stations = load_stations()
                    for station in stations:
                        if station["phone"].endswith(current_number[-9:]):
                            log_status(station["station"], current_number, msg)
                            break
                # Yeni SMS üçün setup
                num_match = re.search(r'"\+?(\d+)"', line_str)
                if num_match:
                    current_number = "+" + num_match.group(1)
                    print(f"📥 Yeni SMS nömrədən: {current_number}")
                    capturing_sms = True
                    sms_lines = []
                continue

            # SMS mətni toplanır
            if capturing_sms:
                sms_lines.append(line_str)
                # SMS bitmə şərti: yeni +CMT: gəlir və ya line boş olur
                if line_str:
                    if sms_lines and current_number:
                        msg = " ".join(sms_lines).strip()
                        root.after(0, lambda m=msg, n=current_number: show_status(m, n))
                        stations = load_stations()
                        for station in stations:
                            if station["phone"].endswith(current_number[-9:]):
                                # log_status(station["station"], current_number, msg)
                                break
                    # reset
                    sms_lines = []
                    capturing_sms = line_str.startswith("+CMT:")
                    if capturing_sms:
                        num_match = re.search(r'"\+?(\d+)"', line_str)
                        if num_match:
                            current_number = "+" + num_match.group(1)
                            print(f"📥 Yeni SMS nömrədən: {current_number}")
                    else:
                        current_number = None
                    continue

                
                

        except Exception as e:
            print("Oxuma xətası:", e)
            time.sleep(1)


# --- SMS və cavab funksiyaları --- 
def send_sms(number, message):
    global last_sent_number
    last_sent_number = number
    if ser and ser.is_open:
        try:
            ser.write(b"AT+CMGF=1\r\n")
            time.sleep(0.5)
            ser.write(f'AT+CMGS="{number}"\r\n'.encode())
            time.sleep(0.5)
            ser.write((message + chr(26)).encode())
            time.sleep(1)
            print(f"📤 SMS göndərildi: {number} -> {message}")

            # --- cavab gözləməyə başla ---
            threading.Thread(target=wait_for_response, args=(number, message), daemon=True).start()

        except Exception as e:
            messagebox.showerror("Xəta", f"SMS göndərmək olmadı:\n{e}")
    else:
        messagebox.showwarning("Diqqət", "Serial port qoşulu deyil!")


active_alerts = set()  # xəbərdarlığı aktiv olan nömrələr

def wait_for_response(number, message):
    # Əgər bu nömrə üçün artıq gözləmə varsa — təzə thread açma
    if number in events and not events[number].is_set():
        print(f"ℹ️ {number} üçün artıq gözləmə aktivdir, təzə thread açılmır.")
        return

    event = threading.Event()
    events[number] = event
    print(f"⏳ {number} üçün cavab gözlənilir...")

    def monitor():
        # Birinci gözləmə
        if not event.wait(timeout=60):
            if number in active_alerts:
                print(f"ℹ️ {number} üçün xəbərdarlıq artıq aktivdir, əlavə SMS göndərilmir.")
                return

            print(f"⚠️ {number} üçün cavab gəlmədi — ikinci SMS göndərilir.")
            send_sms(number, message)

            # İkinci gözləmə
            if not event.wait(timeout=60):
                # Cavab yenə gəlməyibsə, amma xəbərdarlıq yoxdursa — aktiv et
                if number not in active_alerts:
                    print(f"🚨 {number} 2 dəfədən sonra cavab vermədi — xəbərdarlıq aktivləşir.")
                    active_alerts.add(number)
                    root.after(0, lambda: send_sms_status(number))
            else:
                print(f"✅ {number} ikinci SMS-dən sonra cavab verdi, xəbərdarlıq ləğv olundu.")
                active_alerts.discard(number)
        else:
            print(f"✅ {number} cavab verdi, gözləmə dayandırıldı.")
            active_alerts.discard(number)

    threading.Thread(target=monitor, daemon=True).start()



def send_sms_status(number):
    if number not in active_alerts:
        active_alerts.add(number)

    stop_alert_event.clear()
    t = threading.Thread(target=alert_sound_thread, daemon=True)
    t.start()

    messagebox.showwarning(
        f"Stansiya işləmir: {number}",
        f"{number} stansiyası 2 dəqiqə ərzində cavab vermədi!\n"
        "OK düyməsini basın səsi dayandırmaq üçün."
    )

    stop_alert_event.set()
    t.join()

    # xəbərdarlıq bitdikdən sonra həmin nömrəni aktiv siyahıdan çıxar
    active_alerts.discard(number)


def alert_sound_thread():
    while not stop_alert_event.is_set():
        winsound.Beep(1000, 500)
        time.sleep(0.5)


def show_status(msg, number):
    print(f"Cavab alındı: {msg}")
    print(f"Cavab alındı nömrə: {number}")
    status_label.config(text="Cavab alındı", fg="green")

    # cavab gələndə event-i set et və xəbərdarlığı sil
    if number in events:
        events[number].set()
    active_alerts.discard(number)

    for phone, widgets in station_widgets.items():
        if phone.endswith(number[-9:]):
            widgets["response_label"].config(text=msg)
            balance_match = re.search(r"Balance[-:]?\s*([\d\.]+)\s*Azn", msg, re.IGNORECASE)
            if balance_match:
                widgets["balance_label"].config(text=f"Balans: {balance_match.group(1)} Azn")
            else:
                widgets["balance_label"].config(text="")
            stations = load_stations()
            for station in stations:
                if station["phone"] == phone:
                    log_status(station["station"], phone, msg)
                    break
            break


# --- Tkinter UI funksiyaları ---
def draw_station_cards(stations):
    global station_widgets
    station_widgets = {}
    for widget in stations_frame.winfo_children():
        widget.destroy()
    columns = 5
    for i, station in enumerate(stations):
        card = tk.Frame(stations_frame, bg="white", bd=2, relief="solid", padx=10, pady=10)
        row = i // columns
        col = i % columns
        card.grid(row=row, column=col, padx=10, pady=10, sticky="n")

        tk.Label(card, text=f"Stansiya: {station['station']}", font=("Arial", 12, "bold"), bg="white", fg="#000").pack(anchor="w")
        tk.Label(card, text=f"Yer: {station['location']}", font=("Arial", 11), fg="#000", bg="white").pack(anchor="w")
        tk.Label(card, text=f"Nömrə: {station['phone']}", font=("Arial", 11), fg="#000", bg="white").pack(anchor="w")

        # 🔗 Link hissəsi
        link_label = tk.Label(
            card,
            text="Link",
            font=("Arial", 12, "bold", ),
            fg="blue",
            bg="white",
            cursor="hand2"
        )
        link_label.pack(anchor="w", pady=(5, 0))
        link_label.bind("<Button-1>", lambda e, url=station["link"]: webbrowser.open(url))

        balance_label = tk.Label(card, text="", font=("Arial", 10, "bold"), fg="green", bg="white", justify="left")
        balance_label.pack(anchor="w", pady=(5, 0))
        response_label = tk.Label(card, text="", font=("Arial", 10), fg="blue", bg="white", justify="left", wraplength=150)
        response_label.pack(anchor="w", pady=(10, 0))

        station_widgets[station["phone"]] = {
            "card": card,
            "response_label": response_label,
            "balance_label": balance_label,
            
        }

        button_frame = tk.Frame(card, bg="white")
        button_frame.pack(anchor="e", pady=(10, 0))

        status_btn = tk.Button(button_frame, text="Status", bg="#007bff", fg="#000", width=10,
                               command=lambda number=station["phone"]: (
                                   station_widgets[number]["response_label"].config(text=""),
                                   send_sms(number, "Status")
                               ))
        status_btn.grid(row=0, column=0, padx=5)

        del_btn = tk.Button(button_frame, text="Sil", bg="#d9534f", fg="#000", width=10,
                            command=lambda s=station: delete_station(s))
        del_btn.grid(row=0, column=1, padx=5)

        history_btn = tk.Button(button_frame, text="Tarixçə", bg="#28a745", fg="#000", width=10,
                                command=lambda s=station: show_history(s))
        history_btn.grid(row=1, column=0, padx=5, pady=5)


def show_history(station):
    history_win = tk.Toplevel(root)
    history_win.title(f"{station['station']} - Tarixçə")
    history_win.geometry("500x400")

    tk.Label(history_win, text=f"Stansiya: {station['station']}", font=("Arial", 12, "bold")).pack(pady=5)
    tk.Label(history_win, text=f"Telefon: {station['phone']}", font=("Arial", 11)).pack(pady=5)

    history_text = tk.Text(history_win, wrap="word")
    history_text.pack(expand=True, fill="both", padx=10, pady=10)

    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', station["station"])
    station_log_file = os.path.join(exe_dir, f"{safe_name}.txt")
    if os.path.exists(station_log_file):
        with open(station_log_file, "r", encoding="utf-8") as f:
            history_text.insert("end", f.read())
    else:
        history_text.insert("end", "Hələlik tarixçə yoxdur.\n")

    history_text.config(state="disabled")


def delete_station(station):
    if messagebox.askyesno("Təsdiq", f"'{station['station']}' stansiyasını silmək istəyirsiniz?"):
        all_stations = load_stations()
        all_stations = [s for s in all_stations if s != station]
        save_stations(all_stations)
        draw_station_cards(all_stations)


def open_add_modal():
    modal = tk.Toplevel(root)
    modal.title("Yeni Stansiya Əlavə Et")
    modal.geometry("300x300")
    modal.grab_set()

    tk.Label(modal, text="Stansiya Adı:").pack(pady=(10, 0))
    name_entry = tk.Entry(modal, width=30)
    name_entry.pack()
    tk.Label(modal, text="Yer:").pack(pady=(10, 0))
    location_entry = tk.Entry(modal, width=30)
    location_entry.pack()
    tk.Label(modal, text="Link:").pack(pady=(10, 0))
    link_entry = tk.Entry(modal, width=30)
    link_entry.pack()
    tk.Label(modal, text="Nömrə:").pack(pady=(10, 0))
    phone_entry = tk.Entry(modal, width=30)
    phone_entry.pack()

    def submit():
        name = name_entry.get().strip()
        location = location_entry.get().strip()
        phone = phone_entry.get().strip()
        link = link_entry.get().strip()
        if not name or not location or not phone or not link:
            messagebox.showwarning("Xəta", "Bütün sahələri doldurun!")
            return
        pattern = r"^\+994(51|50|55|70|77|99)\d{7}$"
        if not re.match(pattern, phone):
            messagebox.showwarning("Xəta", "Nömrə düzgün formatda deyil! Məsələn: +99477xxxxxxx")
            return
        new_station = {"station": name, "location": location, "phone": phone, "link": link}
        stations = load_stations()
        stations.append(new_station)
        save_stations(stations)
        draw_station_cards(stations)
        modal.destroy()

    tk.Button(modal, text="Əlavə Et", command=submit, bg="#28a745", fg="#000").pack(pady=20)


# --- Tkinter UI Başlanğıcı ---
root = tk.Tk()
root.title("COM Port Monitor")
root.state("zoomed")  # Tam ekran açılır
root.configure(bg="#f0f0f0")

# Yuxarı hissə üçün ayrıca frame
top_frame = tk.Frame(root, bg="#f0f0f0")
top_frame.pack(fill="x", pady=10, padx=10)

# Sol tərəfdə COM port seçimi
left_frame = tk.Frame(top_frame, bg="#f0f0f0")
left_frame.pack(side="left")

tk.Label(left_frame, text="COM port seç:", bg="#f0f0f0", fg="#000", font=("Courier New", 16, "bold")).grid(row=0, column=0, padx=5)
port_var = tk.StringVar()
port_dropdown = ttk.Combobox(left_frame, textvariable=port_var, font=("Arial", 11), width=30)
port_dropdown.grid(row=0, column=1, padx=5)

tk.Button(left_frame, text="Yenilə", command=refresh_ports, width=10, bg="#d12b2b").grid(row=0, column=2, padx=5)
tk.Button(left_frame, text="Qoşul", command=connect_serial, width=10, bg="#06a96d").grid(row=0, column=3, padx=5)
tk.Button(left_frame, text="Bağla", command=disconnect_serial, width=10, bg="#5c3538").grid(row=0, column=4, padx=5)

status_label = tk.Label(left_frame, text="Qoşulmayıb", fg="red", bg="#f0f0f0", font=("Arial", 16))
status_label.grid(row=1, column=0, columnspan=5, pady=5)

# Sağ yuxarıda Stansiya əlavə et düyməsi
right_frame = tk.Frame(top_frame, bg="#f0f0f0")
right_frame.pack(side="right", anchor="ne")

tk.Button(right_frame, text="Stansiya əlavə et", command=open_add_modal,
          bg="#2b7de9", fg="#000", width=15).pack(anchor="ne")

# --- Canvas hissəsi tam ekrana uyğun olsun ---
canvas_frame = tk.Frame(root, bg="#901414")
canvas_frame.pack(fill="both", expand=True, padx=20, pady=10)

canvas = tk.Canvas(canvas_frame, bg="#f0f0f0")
scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
stations_frame = tk.Frame(canvas, bg="#f0f0f0")
stations_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
canvas.create_window((0, 0), window=stations_frame, anchor="nw")
canvas.configure(yscrollcommand=scrollbar.set)

canvas.pack(side="left", fill="both", expand=True)
scrollbar.pack(side="right", fill="y")


def _on_mousewheel(event):
    canvas.yview_scroll(-1 * (event.delta // 120), "units")


canvas.bind_all("<MouseWheel>", _on_mousewheel)

# --- Başlanğıc ---
stations = load_stations()
draw_station_cards(stations)
refresh_ports()
root.mainloop()

