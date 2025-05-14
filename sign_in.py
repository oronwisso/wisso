import base64
import tkinter as tk
import main_page
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
import os
import home
from PIL import Image, ImageTk

class LoginHandler:
    """מחלקה שמטפלת באימות פרטי ההתחברות."""

    def __init__(self, sock, form):
        self.username = ""
        self.password = ""
        self.sock = sock
        self.form = form  # אובייקט של RegistrationForm

    def process_login(self, email, password, chunk_size=214):
        try:

            # הצפנת הנתונים
            encrypted_password = self.encrypt_message(password, os.getenv('Public_Key'))
            inp = f"{email}$$${encrypted_password}"

            # שליחת הנתונים ב-chunks
            chunks = [inp[i:i + chunk_size] for i in range(0, len(inp), chunk_size)]
            for i, chunk in enumerate(chunks):
                message = chunk
                self.sock.sendall(message.encode('utf-8'))
                print(f"Sent: {message}")

            # סימון סיום שליחה
            self.sock.sendall("END".encode('utf-8'))

            # קבלת תגובה מהשרת
            data = self.sock.recv(1024).decode()
            print(data)
            self.form.show_error(data)
            if data == "Login successful":
                self.form.open_main_page()

        except ValueError as ve:
            print(f"Validation error: {ve}")
            self.form.show_error("Invalid input or public key. Please try again.")
        except Exception as e:
            print(f"Error during communication: {e}")
            self.form.show_error("Error during communication with the server.")

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
            return base64.b64encode(encrypted_message).decode('utf-8')

        except ValueError as ve:
            print(f"Value error during encryption: {ve}")
            raise ValueError("Invalid input for encryption.")
        except Exception as e:
            print(f"Encryption error: {e}")
            raise ValueError("Error encrypting the message. Please try again.")


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
        self.root.attributes("-fullscreen", True)

        # Set background image
        bg_image = Image.open(r"C:\\Users\\Pc2\\PycharmProjects\\pythonProject\\images\\sign_in.jpg")
        bg_image = bg_image.resize((width, height))
        self.bg_image = ImageTk.PhotoImage(bg_image)
        background_label = tk.Label(self.root, image=self.bg_image)
        background_label.place(x=0, y=0, relwidth=1, relheight=1)

        # מסגרת לשדות הקלט
        frame = tk.Frame(root, bg="#f6f6f6")
        frame.pack(pady=10)
        frame.place(y=height // 2 + 50, x=width // 2 - 225)
        msg_frame = tk.Frame(root, bg="#f6f6f6")
        msg_frame.place(y=height // 2 + 270, x=width // 2 - 140)

        # אימייל
        tk.Label(frame, text="אימייל:", font=("Arial", 20, "bold"), bg="#f6f6f6").grid(row=0, column=0, padx=5,
                                                                                           pady=5, sticky="e")
        self.username_entry = tk.Entry(frame, font=("Arial", 20, "bold"))
        self.username_entry.grid(row=0, column=1, padx=5, pady=5)

        # סיסמה
        tk.Label(frame, text="סיסמה:", font=("Arial", 20, "bold"), bg="#f6f6f6").grid(row=1, column=0, padx=5, pady=5,
                                                                                          sticky="e")
        self.password_entry = tk.Entry(frame, show="*", font=("Arial", 20, "bold"))
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)

        # מסגרת לכפתורים
        vertical_offset = 200  # ערך ניתן לשינוי לקביעת המרחק מלמעלה
        button_frame = tk.Frame(root, bg="#f6f6f6")
        button_frame.place(y=height // 2 + vertical_offset, x=width // 2 - 110)

        # כפתור התחברות
        login_button = tk.Button(button_frame, text="log in", font=("Arial", 15, "bold"), bg="#dfc592", fg="white",
                                 width=10, command=self.login)
        login_button.grid(row=0, column=0, padx=5)
        login_button.bind("<Enter>", lambda e: self.on_hover(login_button))
        login_button.bind("<Leave>", lambda e: self.on_leave(login_button))

        # כפתור נקה
        clear_button = tk.Button(button_frame, text="clear", font=("Arial", 15, "bold"), bg="#dfc592", fg="white",
                                 width=10, command=self.clear_fields)
        clear_button.grid(row=0, column=1, padx=5)
        clear_button.bind("<Enter>", lambda e: self.on_hover(clear_button))
        clear_button.bind("<Leave>", lambda e: self.on_leave(clear_button))

        # כפתור אחורה
        back_button = tk.Button(root, text=">>>", font=("Arial", 15, "bold"), bg="#dfc592", fg="white",
                                width=5, command=self.open_home)
        back_button.place(x=width - 85, y=10)  # מיקום הכפתור (מימין למעלה)
        back_button.bind("<Enter>", lambda e: self.on_hover(back_button))
        back_button.bind("<Leave>", lambda e: self.on_leave(back_button))

        # מקום להודעת שגיאה (תחילה מוסתר)
        self.error_label = tk.Label(msg_frame, text="", font=("Arial", 12), fg="red", bg="#f6f6f6")
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
        button.config(bg="#dfc592")  # צבע מקורי

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

    def open_main_page(self):
        self.root.destroy()
        main_page.main()


def main():
    # יצירת חלון והפעלת האפליקציה
    root = tk.Tk()
    socket = home.getsocket()
    app = LoginApp(root, socket)
    root.mainloop()


if __name__ == '__main__':
    main()
