import base64
import re
import tkinter as tk
from PIL import Image, ImageTk
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
import os
import home


class FormHandler:
    """מחלקה שמטפלת בעיבוד והצגת ערכי הטופס."""

    def __init__(self, sock, form):
        self.sock = sock
        self.form = form  # אובייקט של RegistrationForm

    def send_to_server(self, field_values, chunk_size=214):
        values = list(field_values.values())
        errors = self.form.check_takin(*values)

        if errors:  # בדיקה אם יש שגיאות
            self.form.show_error(errors, "red")
            return

        try:
            public_key_pem = os.getenv('Public_Key')
            if not public_key_pem:
                raise ValueError("המפתח הציבורי לא נמצא במשתני הסביבה (Public_Key)")
            inp = ""
            inp += self.encrypt_message(values[0], public_key_pem) + "$$$"
            inp += self.encrypt_message(values[1], public_key_pem) + "$$$"
            inp += values[2] + "$$$"
            inp += self.encrypt_message(values[3], public_key_pem) + "$$$"
            inp += self.encrypt_message(values[4], public_key_pem)

            # פיצול המחרוזת לחלקים
            chunks = [inp[i:i + chunk_size] for i in range(0, len(inp), chunk_size)]
            for i, chunk in enumerate(chunks):
                message = chunk
                self.sock.sendall(message.encode('utf-8'))
                print(f"Sent chunk {i+1}: {message}")

            # הדפסה לפני שליחת הודעת הסיום
            print("משגר הודעת סיום: END")
            self.sock.sendall("END".encode('utf-8'))

            # קבלת תשובה מהשרת
            data = self.sock.recv(1024).decode()
            print("Received response:", data)
            if data == "User registered successfully":
                self.form.show_error(data, "green")
            else:
                self.form.show_error(data, "red")

        except ValueError as ve:
            print(f"Validation error: {ve}")
            self.form.show_error("Invalid input or public key. Please try again.", "red")
        except Exception as e:
            print(f"Error during communication: {e}")
            self.form.show_error("Error during communication with the server.", "red")

    def clear_fields(self, entries):
        """ניקוי כל השדות בטופס."""
        for entry in entries.values():
            entry.delete(0, tk.END)
        self.form.hide_error()

    def encrypt_message(self, message, public_key_pem):
        """מצפין הודעה עם המפתח הציבורי של השרת."""
        try:
            # בדיקת מבנה המפתח הציבורי
            if not public_key_pem.startswith("-----BEGIN PUBLIC KEY-----"):
                raise ValueError("Invalid public key format. Please ensure the key is in PEM format.")

            # טעינת המפתח הציבורי
            public_key = serialization.load_pem_public_key(public_key_pem.encode('utf-8'))

            # ביצוע הצפנה
            encrypted_message = public_key.encrypt(
                message.encode('utf-8'),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )

            # החזרת המידע המוצפן כ-Base64
            return base64.b64encode(encrypted_message).decode('utf-8')

        except ValueError as ve:
            print(f"Value error during encryption: {ve}")
            raise ValueError("Invalid input for encryption.")
        except Exception as e:
            print(f"Encryption error: {e}")
            raise ValueError("Error encrypting the message. Please try again.")


class RegistrationForm:
    """מחלקה ליצירת ממשק משתמש עבור טופס הרשמה."""

    def __init__(self, root, sock):
        self.sock = sock
        self.root = root
        self.root.title("טופס הרשמה")
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        self.root.geometry(f"{width}x{height}")
        self.root.configure(bg="#f6f6f6")
        self.handler = FormHandler(sock, self)
        self.entries = {}
        self.root.attributes("-fullscreen", True)

        # Set background image
        bg_image = Image.open(r"C:\Users\Pc2\PycharmProjects\pythonProject\images\sign_up.jpg")
        bg_image = bg_image.resize((width, height))
        self.bg_image = ImageTk.PhotoImage(bg_image)
        background_label = tk.Label(self.root, image=self.bg_image)
        background_label.place(x=0, y=0, relwidth=1, relheight=1)

        # מסגרת לשדות הקלט
        frame = tk.Frame(root, bg="#f6f6f6")
        frame.pack(pady=10)
        frame.place(y=height // 2, x=width // 2 - 210)

        # יצירת שדות טופס
        self.create_entry(frame, "שם מלא:", "fullname", 0)
        self.create_entry(frame, "תעודת זהות:", "id", 1)
        self.create_entry(frame, "אימייל:", "email", 2)
        self.create_entry(frame, "שם משתמש:", "username", 3)
        self.create_entry(frame, "סיסמא:", "password", 4, show="*")

        # מסגרת לכפתורים והודעה
        button_frame = tk.Frame(root, bg="#f6f6f6")
        button_frame.pack(pady=10)
        button_frame.place(y=height // 2 + 225, x=width // 2 - 145)
        msg_frame = tk.Frame(root, bg="#f6f6f6")
        msg_frame.place(y=height // 2 + 270, x=width // 2 - 170)

        # כפתור הרשמה
        register_button = tk.Button(button_frame, text="submit", font=("Arial", 15, "bold"), bg="#dfc592", fg="white",
                                    width=10, command=self.submit)
        register_button.grid(row=0, column=0, padx=5)
        register_button.bind("<Enter>", lambda e: self.on_hover(register_button))
        register_button.bind("<Leave>", lambda e: self.on_leave(register_button))

        # כפתור נקה
        clear_button = tk.Button(button_frame, text="clear", font=("Arial", 15, "bold"), bg="#dfc592", fg="white",
                                 width=10, command=self.clear)
        clear_button.grid(row=0, column=1, padx=5)
        clear_button.bind("<Enter>", lambda e: self.on_hover(clear_button))
        clear_button.bind("<Leave>", lambda e: self.on_leave(clear_button))

        # כפתור אחורה
        back_button = tk.Button(root, text=">>>", font=("Arial", 15, "bold"), bg="#dfc592", fg="white",
                                width=5, command=self.open_home)
        back_button.place(x=width - 85, y=10)
        back_button.bind("<Enter>", lambda e: self.on_hover(back_button))
        back_button.bind("<Leave>", lambda e: self.on_leave(back_button))

        # מקום להודעת שגיאה (תחילה מוסתר)
        self.error_label = tk.Label(msg_frame, text="", font=("Arial", 12), fg="red", bg="#f6f6f6")
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
        button.config(bg="#dfc592")

    def open_home(self):
        self.root.destroy()
        home.main()

    def show_error(self, message, color="red"):
        """פונקציה להצגת הודעה - אם יש שגיאה, הצבע יהיה אדום, ואם הצלחה, ירוק."""
        self.error_label.config(text=message, fg=color)
        self.error_label.pack()  # להבטיח שהלייבל יוצג

    def hide_error(self):
        """פונקציה להסתיר את הודעת השגיאה"""
        self.error_label.config(text="")
        self.error_label.pack_forget()  # להסתיר את הלייבל

    def check_takin(self, fullname, id, email, username, password):
        emsg = ""
        if not re.fullmatch(r"[A-Za-zא-ת\s]{2,}", fullname):
            emsg += "שם מלא חייב להיות לפחות 2 תווים ולכלול אותיות בלבד.\n"
        if not re.fullmatch(r"\d{9}", id):
            emsg += "תעודת זהות חייבת להיות בדיוק 9 ספרות.\n"
        if not re.fullmatch(r"[^@]+@[^@]+\.[^@]+", email):
            emsg += "כתובת האימייל אינה תקינה.\n"
        if not re.fullmatch(r"\w{5,}", username):
            emsg += "שם המשתמש חייב להיות לפחות 5 תווים ולכלול אותיות או ספרות בלבד.\n"
        if not (len(password) >= 8 and re.search(r"\d", password) and re.search(r"[A-Za-z]", password)):
            emsg += "הסיסמא חייבת להיות לפחות 8 תווים, עם לפחות אות וספרה אחת.\n"
        return emsg


def main():
    root = tk.Tk()
    sock = home.getsocket()
    app = RegistrationForm(root, sock)
    root.mainloop()


if __name__ == '__main__':
    main()
