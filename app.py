import tkinter as tk
from tkinter import ttk, messagebox
import serial
import threading
from serial.tools import list_ports
import time
import os
import re
import json

ser = None
reading = False
log_file = open("serial_log.txt", "a", encoding="utf-8")

response_event = threading.Event()
last_sms_buffer = []


station_status = {}  # Yeni: stansiya cavab statusu


def list_serial_ports():
    ports = list_ports.comports()
    return [port.device for port in ports]


def refresh_ports():
    ports = list_serial_ports()
    port_dropdown["values"] = ports
    if ports:
        port_var.set(ports[0])


# connect_serial funksiyasına avtomatik status başlatmaq əlavə olunur
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
        threading.Thread(target=read_serial, daemon=True).start()
        send_status_to_all()
    except Exception as e:
        messagebox.showerror("Xəta", f"Qoşulmaq mümkün olmadı:\n{e}")


def disconnect_serial():
    global ser, reading
    reading = False
    if ser and ser.is_open:
        ser.close()
        status_label.config(text="Bağlandı", fg="red")


def log_message(msg):
    log_file.write(msg + "\n")
    log_file.flush()


def send_command(cmd):
    global ser
    if ser and ser.is_open:
        try:
            ser.write((cmd + "\r\n").encode())
            log_message(f"Sent: {cmd}")

            # Cavab gözləmə funksiyasını ayrı thread-də işə salırıq
            threading.Thread(target=wait_for_response, daemon=True).start()

        except Exception as e:
            messagebox.showerror("Xəta", f"Komanda göndərmək mümkün olmadı:\n{e}")
    else:
        messagebox.showwarning("Diqqət", "Serial port qoşulu deyil!")


def read_serial():
    global reading
    capturing_cmgr = False
    cmgr_message = ""

    while reading:
        try:
            if ser is None or not ser.is_open:
                print("Port bağlı deyil və ya mövcud deyil.")
                time.sleep(1)
                continue  # dövrü davam etdir, oxumağa çalışma

            line = ser.readline()
            if line:
                line_str = line.decode("utf-8", errors="replace").strip()
                log_message(f"Received: {line_str}")

                # output_text.config(state=tk.NORMAL)
                # output_text.insert(tk.END, line_str + "\n")
                # output_text.see(tk.END)
                # output_text.config(state=tk.DISABLED)

                if line_str.startswith("+CMTI:"):
                    match = re.search(r'\+CMTI: ".*?",(\d+)', line_str)
                    if match:
                        index = match.group(1)
                        send_command(f"AT+CMGR={index}")

                if line_str.startswith("+CMGR:"):
                    capturing_cmgr = True
                    cmgr_message = ""
                elif capturing_cmgr:
                    if line_str == "OK" or line_str == "ERROR":
                        capturing_cmgr = False
                        if cmgr_message.strip():
                            last_sms_buffer.append(cmgr_message.strip())
                            response_event.set()
                    else:
                        cmgr_message += line_str + "\n"

        except Exception as e:
            print("Oxuma xətası:", e)
            time.sleep(1)  # xətadan sonra qısa gözləmə, çoxlu error axını olmaması üçün


def wait_for_response(timeout=120):
    print("Cavab gözlənir...")
    response_event.clear()
    is_received = response_event.wait(timeout=timeout)

    if is_received and last_sms_buffer:
        message = last_sms_buffer.pop(0)
        root.after(0, show_status, message)
    else:
        root.after(0, show_warning)


# def show_status(msg):
#     global station_widgets
#     status_label.config(text="Cavab alındı", fg="green")

#     if last_sent_number and last_sent_number in station_widgets:
#         label = station_widgets[last_sent_number]["response_label"]
#         label.config(text=msg)
#     else:
#         print("Cavab hansı stansiyaya aiddir, təyin edilə bilmədi.")


def draw_status_cards(sms_text):
    for widget in stations_frame.winfo_children():
        widget.destroy()

    try:
        voltage = re.search(r"voltage-(\d+(\.\d+)?)", sms_text).group(1) + " V"
        balance = re.search(r"Balance-(\d+(\.\d+)?)", sms_text).group(1) + " AZN"
        water = re.search(r"Water used-([^\s]+)", sms_text).group(1) + " L"
        temp = re.search(r"Temp:\s*(\d+(\.\d+)?)", sms_text).group(1) + " °C"
        status = re.search(r"\b(OK|ERROR)\b", sms_text).group(1)
    except:
        tk.Label(stations_frame, text="Format uyğun deyil!", fg="red").pack()
        return

    data = {
        "Status": status,
        "Balance": balance,
        "Voltage": voltage,
        "Water Used": water,
        "Temperature": temp,
    }

    card = tk.Frame(stations_frame, bg="white", bd=2, relief="solid", padx=15, pady=15)
    card.pack(pady=10, padx=10)

    for key, val in data.items():
        line = f"{key}: {val}"
        tk.Label(
            card,
            text=line,
            font=("Arial", 11),
            anchor="w",
            bg="white",
            fg="black",
        ).pack(anchor="w", pady=2)


def show_warning():
    status_label.config(text="Cavab yoxdur ❌", fg="red")
    messagebox.showwarning("Xəbərdarlıq", "2 dəqiqə ərzində cavab gəlmədi!")
    try:
        os.system('say "not, response"')
    except:
        pass


last_sent_number = None


def send_sms(number, message):
    global last_sent_number
    last_sent_number = number  # sonuncu göndərilən nömrəni yadda saxla

    if ser and ser.is_open:
        ser.write(b"AT+CMGF=1\r\n")
        time.sleep(0.5)
        ser.write(f'AT+CMGS="{number}"\r\n'.encode())
        time.sleep(0.5)
        ser.write((message + chr(26)).encode())
        time.sleep(1)
    else:
        print("Serial port açıq deyil")


def open_sms_window():
    sms_win = tk.Toplevel(root)
    sms_win.title("SMS Göndər")
    sms_win.geometry("350x200")
    sms_win.grab_set()

    tk.Label(sms_win, text="Nömrə:").pack(pady=(10, 0))
    number_entry = tk.Entry(sms_win, width=30)
    number_entry.pack(pady=5)
    number_entry.insert(0, "+994")

    tk.Label(sms_win, text="Mesaj:").pack(pady=(10, 0))
    message_entry = tk.Text(sms_win, height=5, width=30)
    message_entry.pack(pady=5)

    def on_send():
        number = number_entry.get().strip()
        message = message_entry.get("1.0", tk.END).strip()
        if not number or not message:
            messagebox.showwarning(
                "Diqqət", "Zəhmət olmasa həm nömrə, həm də mesaj daxil edin."
            )
            return
        send_sms(number, message)
        sms_win.destroy()

    send_btn = tk.Button(sms_win, text="Göndər", command=on_send)
    send_btn.pack(pady=10)


def load_stations():
    with open("stations.txt", "r", encoding="utf-8") as f:
        return json.load(f)


def draw_station_cards(stations):
    global station_widgets
    station_widgets = {}

    for widget in stations_frame.winfo_children():
        widget.destroy()

    for i, station in enumerate(stations):
        card = tk.Frame(
            stations_frame, bg="white", bd=2, relief="solid", padx=10, pady=10
        )
        card.grid(row=i // 2, column=i % 2, padx=10, pady=10, sticky="n")

        tk.Label(
            card,
            text=f"Stansiya: {station['station']}",
            font=("Arial", 12, "bold"),
            bg="white",
            fg="#000",
        ).pack(anchor="w")
        tk.Label(
            card,
            text=f"Yer: {station['location']}",
            font=("Arial", 11),
            fg="#000",
            bg="white",
        ).pack(anchor="w")
        tk.Label(
            card,
            text=f"Nömrə: {station['phone']}",
            font=("Arial", 11),
            fg="#000",
            bg="white",
        ).pack(anchor="w")

        # Yeni: cavab üçün boş Label əlavə et
        response_label = tk.Label(
            card,
            text="",
            font=("Arial", 10),
            fg="blue",
            bg="white",
            justify="left",
            wraplength=250,
        )
        response_label.pack(anchor="w", pady=(10, 0))

        # Qutunu yadda saxla: nömrəyə uyğun
        station_widgets[station["phone"]] = {
            "card": card,
            "response_label": response_label,
        }

        def delete_station():
            if messagebox.askyesno(
                "Təsdiq", f"'{station['station']}' stansiyasını silmək istəyirsiniz?"
            ):
                try:
                    all_stations = load_stations()
                except:
                    all_stations = []
                all_stations = [s for s in all_stations if s != station]
                with open("stations.txt", "w", encoding="utf-8") as f:
                    json.dump(all_stations, f, indent=4, ensure_ascii=False)
                draw_station_cards(all_stations)

        button_frame = tk.Frame(card, bg="white")
        button_frame.pack(anchor="e", pady=(10, 0))

        status_btn = tk.Button(
            button_frame,
            text="Status",
            bg="#007bff",
            fg="#000",
            width=10,
            command=lambda number=station["phone"]: send_sms(number, "STATUS"),
        )
        status_btn.grid(row=0, column=0, padx=5)

        del_btn = tk.Button(
            button_frame,
            text="Sil",
            bg="#d9534f",
            fg="#000",
            command=delete_station,
            width=10,
        )
        del_btn.grid(row=0, column=1, padx=5)


def open_add_modal():
    modal = tk.Toplevel(root)
    modal.title("Yeni Stansiya Əlavə Et")
    modal.geometry("300x250")
    modal.grab_set()

    tk.Label(modal, text="Stansiya Adı:").pack(pady=(10, 0))
    name_entry = tk.Entry(modal, width=30)
    name_entry.pack()

    tk.Label(modal, text="Yer:").pack(pady=(10, 0))
    location_entry = tk.Entry(modal, width=30)
    location_entry.pack()

    tk.Label(modal, text="Nömrə:").pack(pady=(10, 0))
    phone_entry = tk.Entry(modal, width=30)
    phone_entry.pack()

    def submit():
        name = name_entry.get().strip()
        location = location_entry.get().strip()
        phone = phone_entry.get().strip()

        if not name or not location or not phone:
            messagebox.showwarning("Xəta", "Bütün sahələri doldurun!")
            return

        new_station = {"station": name, "location": location, "phone": phone}
        try:
            stations = load_stations()
        except:
            stations = []

        stations.append(new_station)

        with open("stations.txt", "w", encoding="utf-8") as f:
            json.dump(stations, f, indent=4, ensure_ascii=False)

        draw_station_cards(stations)
        modal.destroy()

    tk.Button(modal, text="Əlavə Et", command=submit, bg="#28a745", fg="#000").pack(
        pady=20
    )


def show_status(msg):
    global station_widgets, last_sent_number
    status_label.config(text="Cavab alındı", fg="green")

    if last_sent_number and last_sent_number in station_widgets:
        label = station_widgets[last_sent_number]["response_label"]
        label.config(text=msg)
        if last_sent_number in station_status:
            station_status[last_sent_number]["responded"] = True
            current_index = station_status[last_sent_number].get("index")
            if current_index is not None:
                next_index = current_index + 1
                if next_index < len(stations):
                    next_station = stations[next_index]
                    number = next_station["phone"]
                    station_status[number] = {
                        "attempts": 1,
                        "responded": False,
                        "last_sent": time.time(),
                        "index": next_index,
                    }
                    last_sent_number = number
                    send_sms(number, "STATUS")
                    root.after(60 * 1000, lambda n=number: retry_status(n))
    else:
        print("Cavab hansı stansiyaya aiddir, təyin edilə bilmədi.")


# Yeni: avtomatik STATUS göndərən funksiyalar
def send_status_to_all():
    global station_status, last_sent_number

    def send_to_station(index):
        if index >= len(stations):
            return

        station = stations[index]
        number = station["phone"]
        station_status[number] = {
            "attempts": 1,
            "responded": False,
            "last_sent": time.time(),
            "index": index,
        }
        last_sent_number = number
        send_sms(number, "STATUS")
        root.after(60 * 1000, lambda n=number: retry_status(n))

    send_to_station(0)


def retry_status(number):
    if station_status.get(number) and not station_status[number]["responded"]:
        attempts = station_status[number]["attempts"]
        if attempts == 1:
            station_status[number]["attempts"] += 1
            send_sms(number, "STATUS")
            root.after(60 * 1000, lambda n=number: retry_status(n))
            if number in station_widgets:
                station_widgets[number]["response_label"].config(
                    text="Stansiya cavab vermədi, yenidən yoxlanacaq", fg="orange"
                )
        elif attempts >= 2:
            if number in station_widgets:
                station_widgets[number]["response_label"].config(
                    text="❌ Stansiya cavab vermədi! XƏBƏRDARLIQ!", fg="red"
                )
            try:
                os.system('say "Warning, station did not respond"')
            except:
                pass


root = tk.Tk()
root.title("COM Port Monitor")
width, height = 1250, 600
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
x = (screen_width - width) // 2
y = (screen_height - height) // 2
root.geometry(f"{width}x{height}+{x}+{y}")
root.configure(bg="#f0f0f0")

port_var = tk.StringVar()
tk.Label(
    root,
    text="COM port seç:",
    bg="#f0f0f0",
    fg="#000",
    font=("Courier New", 16, "bold"),
).place(x=10, y=20)
port_dropdown = ttk.Combobox(root, textvariable=port_var, font=("Arial", 11), width=30)
port_dropdown.place(x=150, y=20)

status_label = tk.Label(
    root, text="Qoşulmayıb", fg="red", bg="#f0f0f0", font=("Arial", 16)
)
status_label.place(x=20, y=60)


tk.Button(root, text="Yenilə", command=refresh_ports, width=10, bg="#d12b2b").place(
    x=400, y=18
)
tk.Button(root, text="Qoşul", command=connect_serial, width=10, bg="#06a96d").place(
    x=540, y=18
)
tk.Button(root, text="Bağla", command=disconnect_serial, width=10, bg="#5c3538").place(
    x=680, y=18
)
tk.Button(
    root, text="Stansiya əlavə et", command=open_add_modal, bg="#2b7de9", fg="#000"
).place(x=1100, y=18)


stations_frame = tk.Frame(root, bg="#901414")
stations_frame.place(x=100, y=300)

stations = load_stations()
draw_station_cards(stations)


refresh_ports()
root.mainloop()
