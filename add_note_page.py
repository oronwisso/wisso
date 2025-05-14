import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import home  # ייבוא המודול שמספק את הפונקציה getsocket()
import os
import json  # ייבוא מודול JSON לעבודה עם פורמט JSON
import base64  # ייבוא מודול Base64 לקידוד תמונות

# הגדרת משתנה לפילטר דגימה (resampling) – לתאימות עם גרסאות שונות של Pillow
try:
    RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE = Image.LANCZOS


# מחלקה המאפשרת הוספת פתק חדש
class AddNotePage:
    def __init__(self, master, on_note_saved=None):
        self.master = master
        self.on_note_saved = on_note_saved
        self.selected_image_path = None

        self.master.title("הוספת פתק חדש")
        self.master.geometry("600x500")
        self.master.configure(bg="#f9f9f9")

        # תווית וקלט לכותרת הפתק
        self.title_label = tk.Label(master, text="כותרת הפתק:", bg="#f9f9f9", font=("Arial", 14))
        self.title_label.pack(pady=10)
        self.title_input = tk.Entry(master, width=40, font=("Arial", 14))
        self.title_input.pack(pady=5)

        # תווית ותיבת טקסט לתוכן הפתק
        self.text_label = tk.Label(master, text="תוכן הפתק:", bg="#f9f9f9", font=("Arial", 14))
        self.text_label.pack(pady=10)
        self.text_input = tk.Text(master, height=10, width=50, font=("Arial", 12), wrap="word",
                                  relief="flat", highlightbackground="#dfc592", highlightthickness=2)
        self.text_input.pack(expand=True, padx=10, pady=10)

        # אזור עם כפתור לבחירת תמונה – כאשר נבחרת תמונה, מוצגת תצוגה מקדמית בתיבת הטקסט
        self.image_frame = tk.Frame(master, bg="#f9f9f9")
        self.image_frame.pack(pady=10)
        self.image_label = tk.Label(self.image_frame, text="לא נבחרה תמונה", bg="#f9f9f9", font=("Arial", 12))
        self.image_label.pack()
        self.upload_button = tk.Button(
            self.image_frame,
            text="בחר תמונה",
            command=self.upload_image,
            bg="#dfc592",
            fg="black",
            font=("Arial", 12)
        )
        self.upload_button.pack(pady=5)

        # כפתור שמירת הפתק
        self.save_button = tk.Button(
            master,
            text="שמור פתק",
            command=self.save_note,
            bg="#dfc592",
            fg="black",
            font=("Arial", 14),
            width=15
        )
        self.save_button.pack(pady=20)

    def upload_image(self):
        # פתיחת תיבת דו-שיח לבחירת תמונה
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp;*.gif")])
        if not file_path:
            messagebox.showinfo("מידע", "לא נבחרה תמונה")
            return
        self.selected_image_path = file_path
        self.image_label.config(text=f"תמונה נבחרה: {os.path.basename(file_path)}")
        try:
            # טעינת התמונה ובניית תצוגה מקדמית
            img = Image.open(file_path)
            img.thumbnail((200, 200), RESAMPLE)
            photo = ImageTk.PhotoImage(img)
            # הכנסת התמונה לתוך תיבת הטקסט במיקום הסמן ושמירת הפניה למניעת איסוף זבל
            if not hasattr(self.text_input, "image_refs"):
                self.text_input.image_refs = []
            self.text_input.image_refs.append(photo)
            self.text_input.insert("insert", "\n")
            self.text_input.image_create("insert", image=photo)
            self.text_input.insert("insert", "\n")
        except Exception as e:
            messagebox.showerror("שגיאה", f"טעינת התמונה נכשלה: {e}")

    def save_note(self):
        # בדיקת קלטים – אם אין כותרת או תוכן, לא ניתן לשמור
        title = self.title_input.get().strip()
        text = self.text_input.get("1.0", tk.END).strip()
        if not title:
            messagebox.showerror("שגיאה", "אנא הזן כותרת לפתק")
            return
        if not text:
            messagebox.showerror("שגיאה", "אנא הזן תוכן לפתק")
            return

        # הכנת מילון נתוני הפתק לשליחה
        note_dict = {"title": title, "text": text}
        if self.selected_image_path:
            try:
                with open(self.selected_image_path, "rb") as img_file:
                    image_data = img_file.read()
                # המרת הנתונים לבס64 כדי שניתן יהיה לשלוח אותם בתוך JSON
                image_base64 = base64.b64encode(image_data).decode('utf-8')
                note_dict["image"] = image_base64
                note_dict["image_path"] = self.selected_image_path
            except Exception as e:
                messagebox.showerror("שגיאה", f"שגיאה בטעינת התמונה: {e}")
                return

        # כאן אנו מסיימים את עיבוד הפתק ומעבירים אותו בחזרה למסך הבית
        if self.on_note_saved:
            self.on_note_saved(note_dict)
        # messagebox.showinfo("הצלחה", "הפתק נשמר בהצלחה!")
        self.master.destroy()


def main():
    root = tk.Tk()
    app = AddNotePage(root)
    root.mainloop()


if __name__ == '__main__':
    main()
