import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk
import os
import json  # ייבוא מודול JSON לעבודה עם הודעות בפורמט JSON
import home  # ייבוא המודול שמספק את הפונקציה getsocket() ואת הפונקציה הראשית
import threading  # ייבוא מודול התהליכים
import queue     # ייבוא מודול התורים לשמירת תגובות מהשרת
import socket

# הגדרת משתנה לפילטר דגימה (resampling) – לתאימות עם גרסאות שונות של Pillow
try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = Image.LANCZOS

# מחלקת כפתור מותאם אישית עם אפקט ריחוף
class ButtonWithHover(tk.Button):
    def __init__(self, master=None, stay_red=False, **kwargs):
        super().__init__(master, **kwargs)
        self.default_bg = kwargs.get("bg", "white")
        self.hover_bg = kwargs.get("hover_bg", "#b8903b")
        self.stay_red = stay_red
        self.bind("<Enter>", self.on_hover)
        self.bind("<Leave>", self.on_leave)

    def on_hover(self, event):
        if self.stay_red:
            return
        self.config(bg=self.hover_bg)

    def on_leave(self, event):
        if self.stay_red:
            return
        self.config(bg=self.default_bg)

# מחלקת מסך הבית המציגה את הפתקים ומאפשרת הוספה, צפייה, עריכה, מחיקה ושיתוף
class HomeScreen:
    def __init__(self, root):
        self.root = root
        self.root.title("מסך הבית")
        self.width = self.root.winfo_screenwidth()
        self.height = self.root.winfo_screenheight()
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.attributes("-fullscreen", True)

        # ניסיון להציג תמונת רקע
        self.background_color = "#f6f6f6"
        bg_image_path = r"C:\Users\Pc2\PycharmProjects\pythonProject\images\main_page.jpg"
        if os.path.exists(bg_image_path):
            try:
                bg_image = Image.open(bg_image_path)
                bg_image = bg_image.resize((self.width, self.height), RESAMPLE)
                self.bg_image = ImageTk.PhotoImage(bg_image)
                background_label = tk.Label(self.root, image=self.bg_image)
                background_label.place(x=0, y=0, relwidth=1, relheight=1)
                background_label.lower()
            except Exception as e:
                messagebox.showerror("שגיאה", f"טעינת תמונת הרקע נכשלה: {e}")
                self.root.configure(bg=self.background_color)
        else:
            self.root.configure(bg=self.background_color)

        self.button_bg_color = "#dfc592"
        self.text_color = "white"

        self.notes_frame = tk.Frame(self.root, bg=self.background_color)
        self.notes_frame.place(x=self.width - 1600, y=self.height - 700)

        self.notes = []  # רשימת הפתקים
        self.note_thumbnail_size = (111, 111)
        self.delete_mode = False
        self.share_mode = False  # מצב שיתוף

        # רשימת חלונות פתוחים לעריכת פתקים, key = note_id
        self.open_note_windows = {}

        # השגת הסוקט המחובר לשרת
        self.sock = home.getsocket()

        # *** שליחת הודעת טעינה לשרת כדי לקבל את כל הפתקים הקודמים ***
        try:
            load_command = json.dumps({"action": "load"})
            self.sock.send(load_command.encode())
            self.sock.send("END".encode())
        except Exception as e:
            print("שגיאה בשליחת הודעת טעינה:", e)

        # יצירת תור לקבלת תגובות מהשרת
        self.response_queue = queue.Queue()

        # השקת תהליך מאזין להודעות מהשרת (ללא חסימת הממשק)
        threading.Thread(target=self.listen_to_server, daemon=True).start()

        self.create_buttons()

    def create_buttons(self):
        button_frame = tk.Frame(self.root, bg=self.background_color)
        button_frame.pack(pady=30)
        button_frame.place(x=200, y=self.height - 160)
        back_frame = tk.Frame(self.root)
        back_frame.pack(pady=30)
        back_frame.place(x=self.width - 250, y=10)

        add_button = ButtonWithHover(
            button_frame,
            text="+",
            font=("Arial", 25, "bold"),
            bg=self.button_bg_color,
            fg=self.text_color,
            width=8,
            command=self.open_add_note_window
        )
        add_button.grid(row=0, column=0, padx=20, pady=10)

        self.delete_button = ButtonWithHover(
            button_frame,
            text="X",
            font=("Arial", 25, "bold"),
            bg=self.button_bg_color,
            fg=self.text_color,
            width=8,
            stay_red=False,
            command=self.toggle_delete_mode
        )
        self.delete_button.grid(row=0, column=1, padx=20, pady=10)

        # כפתור שיתוף – עובר למצב שיתוף וקובע את צבעו הכחול ללא שינוי hover
        self.share_button = ButtonWithHover(
            button_frame,
            text="Share",
            font=("Arial", 25, "bold"),
            bg=self.button_bg_color,
            fg=self.text_color,
            width=8,
            stay_red=False,
            command=self.toggle_share_mode
        )
        self.share_button.grid(row=0, column=2, padx=20, pady=10)

        back_button = ButtonWithHover(
            back_frame,
            text="SignOut",
            font=("Arial", 15, "bold"),
            bg=self.button_bg_color,
            fg=self.text_color,
            width=8,
            command=self.sign_out
        )
        back_button.grid(row=0, column=2, padx=20, pady=10)

    def toggle_share_mode(self):
        # מעבר בין מצב רגיל למצב שיתוף – כפתור נותר כחול וקבוע במצב שיתוף
        self.share_mode = not self.share_mode
        if self.share_mode:
            self.share_button.config(bg="#4da6ff")
            self.share_button.stay_red = True
            for note in self.notes:
                note["button"].config(command=lambda n=note: self.share_note(n))
        else:
            self.share_button.config(bg=self.button_bg_color)
            self.share_button.stay_red = False
            for note in self.notes:
                note["button"].config(command=lambda nid=note["data"].get("id"): self.view_note_by_id(nid))

    def listen_to_server(self):
        while True:
            try:
                data = self.sock.recv(1024).decode('utf-8')
                if not data:
                    break
                message = json.loads(data)
                action = message.get("action")
                if action == "load_notes":
                    self.root.after(0, self.load_notes, message)
                elif action in ["broadcast_create", "broadcast_edit", "broadcast_delete"]:
                    self.root.after(0, self.handle_broadcast, message)
                else:
                    self.response_queue.put(message)
            except Exception as e:
                print("Listener error:", e)
                break

    def load_notes(self, message):
        notes = message.get("notes", [])
        for note in notes:
            self.add_note_from_broadcast(note)

    def handle_broadcast(self, message):
        action = message.get("action")
        if action == "broadcast_create":
            note_data = message.get("note")
            self.add_note_from_broadcast(note_data)
        elif action == "broadcast_edit":
            note_data = message.get("note")
            self.edit_note_from_broadcast(note_data)
        elif action == "broadcast_delete":
            note_id = message.get("note_id")
            self.delete_note_from_broadcast(note_id)

    def add_note_from_broadcast(self, note_data):
        exists = False
        for note in self.notes:
            if note["data"].get("id") == note_data.get("id"):
                exists = True
                break
        if exists:
            return
        # אם הפתק מסומן כשותף, משתמשים בתמונה מיוחדת
        if note_data.get("shared"):
            default_icon_path = r"C:\Users\Pc2\PycharmProjects\pythonProject\images\shared-note.png"
        else:
            default_icon_path = r"C:\Users\Pc2\PycharmProjects\pythonProject\images\note.png"
        if os.path.exists(default_icon_path):
            try:
                img = Image.open(default_icon_path)
                img = img.resize(self.note_thumbnail_size, RESAMPLE)
                thumbnail = ImageTk.PhotoImage(img)
            except Exception as e:
                messagebox.showerror("שגיאה", f"טעינת האייקון נכשלה: {e}")
                thumbnail = None
        else:
            thumbnail = None
        note_button = tk.Button(
            self.notes_frame,
            image=thumbnail,
            relief="flat",
            bd=0,
            bg="#f6f6f6",
            activebackground="#f6f6f6",
            command=lambda nid=note_data.get("id"): self.view_note_by_id(nid)
        )
        note_button.image = thumbnail
        note_label = tk.Label(
            self.notes_frame,
            text=note_data.get("title", "Untitled"),
            bg="white",
            font=("Arial", 12)
        )
        self.notes.append({"button": note_button, "label": note_label, "data": note_data})
        self.refresh_notes()

    def edit_note_from_broadcast(self, note_data):
        for note in self.notes:
            if note["data"].get("id") == note_data.get("id"):
                note["data"] = note_data
                note["label"].config(text=note_data.get("title", "Untitled"))
                break
        note_id = note_data.get("id")
        if note_id in self.open_note_windows:
            win_data = self.open_note_windows[note_id]
            win_data["title_entry"].delete(0, tk.END)
            win_data["title_entry"].insert(0, note_data.get("title", ""))
            win_data["text_entry"].delete("1.0", tk.END)
            win_data["text_entry"].insert("1.0", note_data.get("text", ""))

    def delete_note_from_broadcast(self, note_id):
        note_to_delete = None
        for note in self.notes:
            if note["data"].get("id") == note_id:
                note_to_delete = note
                break
        if note_to_delete:
            note_to_delete["button"].destroy()
            note_to_delete["label"].destroy()
            self.notes.remove(note_to_delete)
            self.refresh_notes()
        if note_id in self.open_note_windows:
            win_data = self.open_note_windows.pop(note_id)
            win_data["window"].destroy()

    def open_add_note_window(self):
        add_window = tk.Toplevel(self.root)
        from add_note_page import AddNotePage  # ייבוא דינמי של דף הוספת הפתק
        AddNotePage(add_window, on_note_saved=self.add_note_callback)

    def add_note_callback(self, note_data):
        try:
            create_msg = json.dumps({"action": "create", "note": note_data})
            self.sock.send(create_msg.encode())
            self.sock.send("END".encode())
            response = self.response_queue.get()
            resp_dict = response
            if resp_dict.get("status") == "success":
                note_data["id"] = resp_dict.get("note_id")
            else:
                messagebox.showerror("שגיאה", "תקלה ביצירת הפתק בשרת")
                return
        except Exception as e:
            messagebox.showerror("שגיאה", f"לא ניתן לשלוח הודעת יצירה לשרת: {e}")
            return

        default_icon_path = r"C:\Users\Pc2\PycharmProjects\pythonProject\images\note.png"
        if os.path.exists(default_icon_path):
            try:
                img = Image.open(default_icon_path)
                img = img.resize(self.note_thumbnail_size, RESAMPLE)
                thumbnail = ImageTk.PhotoImage(img)
            except Exception as e:
                messagebox.showerror("שגיאה", f"טעינת האייקון נכשלה: {e}")
                thumbnail = None
        else:
            thumbnail = None

        note_button = tk.Button(
            self.notes_frame,
            image=thumbnail,
            relief="flat",
            bd=0,
            bg="#f6f6f6",
            activebackground="#f6f6f6",
            command=lambda nid=note_data.get("id"): self.view_note_by_id(nid)
        )
        note_button.image = thumbnail
        note_label = tk.Label(
            self.notes_frame,
            text=note_data.get("title", "Untitled"),
            bg="white",
            font=("Arial", 12)
        )
        self.notes.append({"button": note_button, "label": note_label, "data": note_data})
        self.refresh_notes()

    def refresh_notes(self):
        for i, note in enumerate(self.notes):
            row, col = divmod(i, 9)
            note["button"].grid(row=row * 2, column=col, padx=10, pady=10)
            note["label"].grid(row=row * 2 + 1, column=col, pady=(0, 10))

    def toggle_delete_mode(self):
        self.delete_mode = not self.delete_mode
        if self.delete_mode:
            self.delete_button.config(bg="#ff4d4d")
            self.delete_button.stay_red = True
            for note in self.notes:
                note["button"].config(command=lambda n=note: self.delete_note(n))
        else:
            self.delete_button.config(bg=self.button_bg_color)
            self.delete_button.stay_red = False
            for note in self.notes:
                note["button"].config(command=lambda nid=note["data"].get("id"): self.view_note_by_id(nid))

    def delete_note(self, note):
        note_id = note["data"].get("id")
        note["button"].destroy()
        note["label"].destroy()
        if note in self.notes:
            self.notes.remove(note)
        self.refresh_notes()
        try:
            delete_msg = json.dumps({"action": "delete", "note_id": note_id})
            self.sock.send(delete_msg.encode())
            self.sock.send("END".encode('utf-8'))
            self.response_queue.get()
        except Exception as e:
            messagebox.showerror("שגיאה", f"לא ניתן לשלוח הודעת מחיקה לשרת: {e}")

    def view_note_by_id(self, note_id):
        for note in self.notes:
            if note["data"].get("id") == note_id:
                self.view_note(note["data"])
                break

    def view_note(self, note_data):
        note_id = note_data.get("id")
        if note_id in self.open_note_windows:
            win_data = self.open_note_windows[note_id]
            win_data["window"].lift()
            return

        view_window = tk.Toplevel(self.root)
        view_window.title(note_data.get("title", "Untitled"))
        view_window.geometry("600x500")

        title_label = tk.Label(view_window, text="Title:", font=("Arial", 14))
        title_label.pack(pady=5)
        title_entry = tk.Entry(view_window, font=("Arial", 14))
        title_entry.insert(0, note_data.get("title", ""))
        title_entry.pack(pady=5, fill="x", padx=10)

        text_label = tk.Label(view_window, text="Text:", font=("Arial", 14))
        text_label.pack(pady=5)
        text_entry = tk.Text(view_window, wrap="word", font=("Arial", 14), height=15)
        text_entry.insert("1.0", note_data.get("text", ""))
        text_entry.pack(pady=5, fill="both", expand=True, padx=10)

        # אין כפתור שמירה - השינויים נשמרים אוטומטית
        # הגדרת פונקציית Auto-save שתופעל בכל KeyRelease
        def on_key_release(event):
            if "auto_save_job" in self.open_note_windows[note_id]:
                self.root.after_cancel(self.open_note_windows[note_id]["auto_save_job"])
            # קביעת עיכוב של 2 שניות לפני ביצוע שמירה
            job = self.root.after(2000, lambda: self.auto_save_note(note_data, title_entry, text_entry, view_window))
            self.open_note_windows[note_id]["auto_save_job"] = job

        title_entry.bind("<KeyRelease>", on_key_release)
        text_entry.bind("<KeyRelease>", on_key_release)

        # טיפול בסגירת החלון - אם הכותרת ריקה, לא ניתן לסגור
        def on_close():
            if title_entry.get().strip() == "":
                messagebox.showerror("שגיאה", "לא ניתן לסגור פתק ללא כותרת. אנא הוסף כותרת.")
                return
            # שמירה סופית לפני הסגירה
            self.auto_save_note(note_data, title_entry, text_entry, view_window)
            if note_id in self.open_note_windows:
                del self.open_note_windows[note_id]
            view_window.destroy()
        view_window.protocol("WM_DELETE_WINDOW", on_close)

        self.open_note_windows[note_id] = {
            "window": view_window,
            "title_entry": title_entry,
            "text_entry": text_entry
        }

    def auto_save_note(self, note_data, title_entry, text_entry, view_window):
        updated_title = title_entry.get()
        updated_text = text_entry.get("1.0", "end-1c")
        # אם הכותרת ריקה, לא מתבצעת שמירה
        if not updated_title.strip():
            return
        note_data["title"] = updated_title
        note_data["text"] = updated_text
        try:
            edit_msg = json.dumps({"action": "edit", "note": note_data})
            self.sock.send(edit_msg.encode())
            self.sock.send("END".encode('utf-8'))
            self.response_queue.get()
        except Exception as e:
            messagebox.showerror("שגיאה", f"לא ניתן לשלוח הודעת עדכון לשרת: {e}")
        for note in self.notes:
            if note["data"].get("id") == note_data.get("id"):
                note["label"].config(text=updated_title)
                note["data"] = note_data
                break

    def share_note(self, note):
        try:
            get_users_msg = json.dumps({"action": "get_users"})
            self.sock.send(get_users_msg.encode())
            self.sock.send("END".encode())
            response = self.response_queue.get()
            if response.get("action") == "users_list":
                users = response.get("users", [])
                # סינון: להציג רק משתמשים שאינם "default"
                users = [u for u in users if u.lower() != "default"]
                if not users:
                    messagebox.showinfo("מידע", "אין משתמשים מחוברים לשיתוף")
                    return
                self.open_share_window(note, users)
            else:
                messagebox.showerror("שגיאה", "לא התקבלה רשימת משתמשים")
        except Exception as e:
            messagebox.showerror("שגיאה", f"תקלה בבקשת משתמשים: {e}")

    def open_share_window(self, note, users):
        share_win = tk.Toplevel(self.root)
        share_win.title("בחר משתמש לשיתוף הפתק")
        share_win.geometry("300x200")
        label = tk.Label(share_win, text="בחר משתמש:")
        label.pack(pady=10)
        for user in users:
            btn = tk.Button(share_win, text=user, command=lambda u=user: self.share_note_confirm(note, u, share_win))
            btn.pack(pady=5)

    def share_note_confirm(self, note, target_user, window):
        window.destroy()
        try:
            share_msg = json.dumps({"action": "share", "note": note["data"], "target_user": target_user})
            self.sock.send(share_msg.encode())
            self.sock.send("END".encode())
            response = self.response_queue.get()
            if response.get("status") == "success":
                messagebox.showinfo("הצלחה", f"הפתק שותף ל-{target_user} בהצלחה")
            else:
                messagebox.showerror("שגיאה", response.get("message", "לא ניתן לשתף את הפתק"))
        except Exception as e:
            messagebox.showerror("שגיאה", f"תקלה בשליחת פתק משותף: {e}")
        self.share_mode = False
        self.share_button.config(bg=self.button_bg_color)
        self.share_button.stay_red = False
        for note in self.notes:
            note["button"].config(command=lambda nid=note["data"].get("id"): self.view_note_by_id(nid))

    def sign_out(self):
        try:
            logout_msg = json.dumps({"action": "logout"})
            self.sock.send(logout_msg.encode())
            self.sock.send("END".encode())
        except Exception as e:
            print("Logout send error:", e)
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
            self.sock.close()
        except Exception as e:
            print("שגיאה בסגירת הסוקט:", e)
        self.root.destroy()
        try:
            home.reset_socket()  # יש לממש פונקציה זו במודול home לאתחול סוקט חדש
        except Exception as e:
            print("Reset socket error:", e)
        home.main()

def main():
    root = tk.Tk()
    app = HomeScreen(root)
    root.mainloop()

if __name__ == '__main__':
    main()
