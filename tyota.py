import tkinter as tk
import home
import socket
import re
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import base64



class FormHandler:
    """מחלקה שמטפלת בעיבוד והצגת ערכי הטופס."""

    def __init__(self, sock, form):
        self.sock = sock
        self.form = form  # אובייקט של RegistrationForm

    def send_to_server(self, field_values, chunk_size=1024):
        values = list(field_values.values())
        erors = self.form.check_takin(values[0], values[1], values[2], values[3], values[4])

        if erors is not "":   # בדיקת האם יש שגיה באחת משדות ההרשמה
            self.form.show_error(erors)
        else:

            public_key_pem = self.sock.recv(1024).decode()
            inp = ""
            inp += self.encrypt_message(values[0], public_key_pem) + "$$$"
            inp += self.encrypt_message(values[1], public_key_pem) + "$$$"
            inp += values[2] + "$$$"
            inp += self.encrypt_message(values[3], public_key_pem) + "$$$"
            inp += self.encrypt_message(values[4], public_key_pem)

            try:

                # שליחת הנתונים לשרת
                chunks = [inp[i:i+chunk_size] for i in range(0, len(inp), chunk_size)]
                for i, chunk in enumerate(chunks):
                    # שליחת כל חלק
                    self.sock.sendall(f"PART:{i}:{chunk}".encode('utf-8'))

                # שליחת הודעת סיום
                self.sock.sendall("END".encode('utf-8'))
                # קבלת תגובה מהשרת
                data = self.sock.recv(1024).decode()
                print("Response from server:", data)
                # קריאה לפונקציה show_error מתוך אובייקט form של RegistrationForm
                self.form.show_error(data)

            except Exception as e:
                print(f"Error while sending to server: {e}")

    def clear_fields(self, entries):
        """ניקוי כל השדות בטופס."""
        for entry in entries.values():
            entry.delete(0, tk.END)
            self.form.hide_error()

    def encrypt_message(self, message, public_key_pem):
        """מצפין הודעה עם המפתח הציבורי של השרת"""
        public_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))

        encrypted_message = public_key.encrypt(
            message.encode('utf-8'),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return base64.b64encode(encrypted_message).decode('utf-8')

class RegistrationForm:
    """מחלקה ליצירת ממשק משתמש עבור טופס הרשמה."""

    def __init__(self, root, sock):
        self.sock = sock
        self.root = root
        self.root.title("טופס הרשמה")
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        self.root.geometry(f"{width}x{height}")
        self.root.configure(bg="#ecb653")
        self.handler = FormHandler(sock, self)
        self.entries = {}

        # כותרת לטופס
        title_label = tk.Label(root, text="טופס הרשמה", font=("Arial", 30, "bold"), bg="#ecb653")
        title_label.pack(pady=10)

        # מסגרת לשדות הקלט
        frame = tk.Frame(root, bg="#ecb653")
        frame.pack(pady=10)

        # יצירת שדות טופס
        self.create_entry(frame, "שם מלא:", "fullname", 0)
        self.create_entry(frame, "תעודת זהות:", "id", 1)
        self.create_entry(frame, "אימייל:", "email", 2)
        self.create_entry(frame, "שם משתמש:", "username", 3)
        self.create_entry(frame, "סיסמא:", "password", 4, show="*")

        # מסגרת לכפתורים
        button_frame = tk.Frame(root, bg="#ecb653")
        button_frame.pack(pady=10)

        # כפתור הרשמה
        register_button = tk.Button(button_frame, text="הרשמה", font=("Arial", 15, "bold"), bg="#d4a549", fg="white",
                                    width=10, command=self.submit)
        register_button.grid(row=0, column=0, padx=5)
        register_button.bind("<Enter>", lambda e: self.on_hover(register_button))
        register_button.bind("<Leave>", lambda e: self.on_leave(register_button))

        # כפתור נקה
        clear_button = tk.Button(button_frame, text="נקה", font=("Arial", 15, "bold"), bg="#d4a549", fg="white",
                                 width=10, command=self.clear)
        clear_button.grid(row=0, column=1, padx=5)
        clear_button.bind("<Enter>", lambda e: self.on_hover(clear_button))
        clear_button.bind("<Leave>", lambda e: self.on_leave(clear_button))

        # כפתור אחורה
        back_button = tk.Button(root, text=">>>", font=("Arial", 15, "bold"), bg="#d4a549", fg="white",
                                width=5, command=self.open_home)
        back_button.place(x=width - 85, y=10)
        back_button.bind("<Enter>", lambda e: self.on_hover(back_button))
        back_button.bind("<Leave>", lambda e: self.on_leave(back_button))

        # מקום להודעת שגיאה (תחילה מוסתר)
        self.error_label = tk.Label(root, text="", font=("Arial", 12), fg="red", bg="#ecb653")
        self.error_label.pack(pady=10)

    def create_entry(self, frame, label_text, field_name, row, show=None):
        """פונקציה ליצירת שדה קלט ומוסיפה אותו למילון הקלטים."""
        label = tk.Label(frame, text=label_text, font=("Arial", 15, "bold"), bg="#ecb653")
        label.grid(row=row, column=0, padx=5, pady=5, sticky="e")
        entry = tk.Entry(frame, font=("Arial", 15), show=show)
        entry.grid(row=row, column=1, padx=5, pady=5)
        self.entries[field_name] = entry

    def submit(self):
        """פונקציה לקריאת הערכים מהשדות והעברתם לטיפול."""
        field_values = {name: entry.get() for name, entry in self.entries.items()}
        self.handler.send_to_server(field_values)

    def clear(self):
        """פונקציה לניקוי כל השדות בטופס."""
        self.handler.clear_fields(self.entries)

    def on_hover(self, button):
        button.config(bg="#b8903b")

    def on_leave(self, button):
        button.config(bg="#d4a549")

    def open_home(self):
        self.root.destroy()
        home.main()

    def show_error(self, message):
        """פונקציה להצגת הודעת שגיאה"""
        self.error_label.config(text=message)
        self.error_label.pack()  # להבטיח שהלייבל יוצג

    def hide_error(self):
        """פונקציה להסתיר את הודעת השגיאה"""
        self.error_label.config(text="")
        self.error_label.pack_forget()  # להסתיר את הלייבל

    def check_takin(self, fullname, id, email, username, password):
        emsg = """"""
        if not re.fullmatch(r"[A-Za-zא-ת\s]{2,}", fullname):
            emsg += "שם מלא חייב להיות לפחות 2 תווים ולכלול אותיות בלבד." + "\n"
        if not re.fullmatch(r"\d{9}", id):
            emsg += "תעודת זהות חייבת להיות בדיוק 9 ספרות." + "\n"
        if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email):
            emsg += "כתובת האימייל אינה תקינה." + "\n"
        if not re.fullmatch(r"\w{5,}", username):
            emsg += "שם המשתמש חייב להיות לפחות 5 תווים ולכלול אותיות או ספרות בלבד." + "\n"
        if not (len(password) >= 8 and re.search(r"\d", password) and re.search(r"[A-Za-z]", password)):
            emsg += "הסיסמא חייבת להיות לפחות 8 תווים, עם לפחות אות וספרה אחת." + "\n"
        return emsg


def main():
    root = tk.Tk()
    sock = home.getsocket()
    app = RegistrationForm(root, sock)
    root.mainloop()


if __name__ == '__main__':
    main()
