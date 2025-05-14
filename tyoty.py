import tkinter as tk
import home
import socket, select, msvcrt, sys
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import base64

class LoginHandler:
    """מחלקה שמטפלת באימות פרטי ההתחברות."""

    def __init__(self, sock, form):
        self.username = ""
        self.password = ""
        self.sock = sock
        self.form = form  # אובייקט של RegistrationForm

    def process_login(self, email, password, chunk_size=1024):
        public_key_pem = self.sock.recv(1024).decode()
        inp = email + "$$$" + self.encrypt_message(password, public_key_pem)
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
            self.form.show_error(data)
        except Exception as e:
            print(f"Error while sending to server: {e}")

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


class LoginApp:
    """מחלקה עבור התחברות."""

    def __init__(self, root, socket):
        self.root = root
        self.root.title("חלון התחברות")
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        self.root.geometry(f"{width}x{height}")
        self.root.configure(bg="#ecb653")
        self.handler = LoginHandler(socket, self)  # יצירת מופע של LoginHandler

        # כותרת לעמוד
        title_label = tk.Label(root, text="התחברות", font=("Arial", 30, "bold"), bg="#ecb653")
        title_label.pack(pady=20)

        # מסגרת לשדות הקלט
        frame = tk.Frame(root, bg="#ecb653")
        frame.pack(pady=10)

        # אימייל
        tk.Label(frame, text="אימייל:", font=("Arial", 20, "bold"), bg="#ecb653").grid(row=0, column=0, padx=5,
                                                                                       pady=5, sticky="e")
        self.username_entry = tk.Entry(frame, font=("Arial", 20, "bold"))
        self.username_entry.grid(row=0, column=1, padx=5, pady=5)

        # סיסמה
        tk.Label(frame, text="סיסמה:", font=("Arial", 20, "bold"), bg="#ecb653").grid(row=1, column=0, padx=5, pady=5,
                                                                                      sticky="e")
        self.password_entry = tk.Entry(frame, show="*", font=("Arial", 20, "bold"))
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)

        # מסגרת לכפתורים
        button_frame = tk.Frame(root, bg="#ecb653")
        button_frame.pack(pady=10)

        # כפתור התחברות
        login_button = tk.Button(button_frame, text="התחבר", font=("Arial", 15, "bold"), bg="#d4a549", fg="white",
                                 width=10, command=self.login)
        login_button.grid(row=0, column=0, padx=5)
        login_button.bind("<Enter>", lambda e: self.on_hover(login_button))
        login_button.bind("<Leave>", lambda e: self.on_leave(login_button))

        # כפתור נקה
        clear_button = tk.Button(button_frame, text="נקה", font=("Arial", 15, "bold"), bg="#d4a549", fg="white",
                                 width=10, command=self.clear_fields)
        clear_button.grid(row=0, column=1, padx=5)
        clear_button.bind("<Enter>", lambda e: self.on_hover(clear_button))
        clear_button.bind("<Leave>", lambda e: self.on_leave(clear_button))

        # כפתור אחורה
        back_button = tk.Button(root, text=">>>", font=("Arial", 15, "bold"), bg="#d4a549", fg="white",
                                width=5, command=self.open_home)
        back_button.place(x=width - 85, y=10)  # מיקום הכפתור (מימין למעלה)
        back_button.bind("<Enter>", lambda e: self.on_hover(back_button))
        back_button.bind("<Leave>", lambda e: self.on_leave(back_button))

        # מקום להודעת שגיאה (תחילה מוסתר)
        self.error_label = tk.Label(root, text="", font=("Arial", 12), fg="red", bg="#ecb653")
        self.error_label.pack(pady=10)

    def login(self):
        """פונקציה שמטפלת בלחיצה על כפתור התחברות, לוקחת את הערכים מהשדות ומדפיסה אותם."""
        username = self.username_entry.get()
        password = self.password_entry.get()
        self.handler.process_login(username, password)

    def clear_fields(self):
        """פונקציה לניקוי שדות שם המשתמש והסיסמה."""
        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)
        self.hide_error()

    def on_hover(self, button):
        """שינוי צבע הכפתור בעת מעבר עכבר עליו."""
        button.config(bg="#b8903b")  # צבע כהה יותר

    def on_leave(self, button):
        """החזרת צבע הכפתור לקדמותו בעת יציאת העכבר."""
        button.config(bg="#d4a549")  # צבע מקורי

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

def main():
    # יצירת חלון והפעלת האפליקציה
    root = tk.Tk()
    socket = home.getsocket()
    app = LoginApp(root, socket)
    root.mainloop()


if __name__ == '__main__':
    main()
