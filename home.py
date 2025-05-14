import sqlite3
import tkinter as tk
import sign_in
import sign_up
import socket
import os
from PIL import Image, ImageTk


def init_socket():
    """
    יוצר סוקט חדש ומתחבר לשרת.
    לאחר החיבור, מקבל את המפתח הציבורי ושומר אותו במשתנה הסביבה.
    """
    s = socket.socket()
    s.connect(("192.168.1.11", 1234))
    #s.connect(("127.0.0.1", 1234))
    public_key_pem = s.recv(1024).decode()
    os.environ['Public_Key'] = public_key_pem
    return s


# אתחול חיבור ראשוני
my_socket = init_socket()


def getsocket():
    """
    פונקציה המחזירה את הסוקט הנוכחי.
    במידה ויש צורך להתחבר מחדש, יש לעדכן את המשתנה my_socket.
    """
    return my_socket


def reset_socket():
    global sock
    sock = None


class ButtonWithHover(tk.Button):
    """מחלקת כפתור מותאמת אישית עם אנימציה בריחוף."""

    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.default_bg = kwargs.get("bg", "white")
        self.hover_bg = "#b8903b"  # צבע כהה יותר בעת ריחוף
        self.bind("<Enter>", self.on_hover)
        self.bind("<Leave>", self.on_leave)

    def on_hover(self, event):
        self.config(bg="#906b52")

    def on_leave(self, event):
        self.config(bg="#dfc592")


class HomeScreen:
    """מחלקה שמנהלת את מסך הבית."""

    def __init__(self, root):
        self.root = root
        self.root.title("מסך בית")
        self.width = root.winfo_screenwidth()
        self.height = root.winfo_screenheight()
        self.root.geometry(f"{self.width}x{self.height}")
        self.root.attributes("-fullscreen", True)

        # הגדרות עיצוב
        self.background_color = "#f3f3f3"
        self.button_bg_color = "#f3f3f3"
        self.text_color = "#000000"

        # הגדרת תמונת רקע
        bg_image = Image.open(r"C:\Users\Pc2\PycharmProjects\pythonProject\images\homepage.jpg")
        bg_image = bg_image.resize((self.width, self.height))
        self.bg_image = ImageTk.PhotoImage(bg_image)
        background_label = tk.Label(self.root, image=self.bg_image)
        background_label.place(x=0, y=0, relwidth=1, relheight=1)

        # יצירת כפתורים
        self.create_buttons()

    def create_buttons(self):
        """יצירת כפתורי התחברות והרשמה עם אנימציה."""
        button_frame = tk.Frame(self.root, bg=self.background_color)
        button_frame.place(relx=0.5, rely=0.6, anchor=tk.CENTER)

        button_style = {
            "font": ("Arial", 18, "bold"),
            "bg": "#dfc592",
            "fg": "#f3f3f3",
            "width": 12,
            "height": 2,
            "relief": "flat",
            "bd": 2
        }

        register_button = ButtonWithHover(button_frame, text="sign up", command=self.open_sign_up, **button_style)
        register_button.pack(side=tk.LEFT, padx=20)

        login_button = ButtonWithHover(button_frame, text="sign in", command=self.open_sign_in, **button_style)
        login_button.pack(side=tk.LEFT, padx=20)

    def open_sign_in(self):
        """
        בעת המעבר למסך ההתחברות, סוגרים את הסוקט הקודם ופותחים חיבור חדש.
        לאחר מכן, מסירים את המסך הבית ומפעילים את המודול sign_in.
        """
        global my_socket
        try:
            my_socket.close()
        except Exception:
            pass
        my_socket = init_socket()
        self.root.destroy()
        sign_in.main()

    def open_sign_up(self):
        """                                                                                                                                         
        בעת המעבר למסך ההרשמה, סוגרים את הסוקט הקודם ופותחים חיבור חדש.
        לאחר מכן, מסירים את המסך הבית ומפעילים את המודול sign_up.
        """
        global my_socket
        try:
            my_socket.close()
        except Exception:
            pass
        my_socket = init_socket()
        self.root.destroy()
        sign_up.main()


def main():
    # אתחול המסך הבית
    root = tk.Tk()
    app = HomeScreen(root)
    root.mainloop()


if __name__ == '__main__':
    main()
