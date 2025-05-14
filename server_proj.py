import json  # ייבוא מודול JSON לעבודה עם הודעות בפורמט JSON
import select
import socket
import sqlite3
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
import os
import base64  # ייבוא מודול Base64 לעבודה עם תמונות מקודדות
import threading  # ייבוא מודול התהליכים


class Server:
    def __init__(self, host="0.0.0.0", port=1234):
        self.listening_socket = socket.socket()
        self.listening_socket.bind((host, port))
        self.listening_socket.listen(1)
        self.listening_socket.setblocking(False)  # הגדרה לא-חוסמת
        self.open_sockets = []
        self.users = {}  # מילון המשתמשים המחוברים (סוקט -> משתמש)
        self.db_loc = r"C:\Users\Pc2\PycharmProjects\pythonProject\db.sqlite"
        self.user_loc = r"C:\Users\Pc2\PycharmProjects\pythonProject\users"
        self.default_counter = 1  # מונה ברירת מחדל למקרים בהם אין משתמש מחובר

        # שינוי: מילון לשמירת הפתקים המשותפים.
        # המפתח הוא tuple (original_owner, original_note_id) והערך מכיל את הפתק וגם רשימת המשתמשים ששותפים לו.
        self.shared_notes = {}

        self.private_key, self.public_key = self.generate_server_keys_once()
        print("Server is open. Open sockets:", self.open_sockets)

    def run(self):
        full_data = ""
        try:
            while True:
                allSock = [self.listening_socket] + self.open_sockets
                rlist, wlist, xlist = select.select(allSock, allSock, [])
                for sock in rlist:
                    if sock is self.listening_socket:
                        client_socket, addr = self.listening_socket.accept()
                        client_socket.setblocking(False)
                        self.open_sockets.append(client_socket)
                        print("Client connected:", addr)
                        self.users[client_socket] = "default"
                        client_socket.send(self.get_public_key_pem().encode())
                    else:
                        try:
                            while True:
                                if sock in rlist:
                                    data = sock.recv(1024).decode('utf-8')
                                    print(f"Received: {data}")
                                    if not data:
                                        print("Client disconnected")
                                        if sock in self.open_sockets:
                                            self.open_sockets.remove(sock)
                                        if sock in self.users:
                                            del self.users[sock]
                                        sock.close()
                                        break
                                    if "END" in data:
                                        full_data += data.split("END")[0]
                                        print("All parts received.")
                                        break
                                    full_data += data

                            data_str = full_data.strip()
                            if data_str.startswith('{'):
                                try:
                                    command_data = json.loads(data_str)
                                    action = command_data.get("action")
                                    if action == "create":
                                        note_data = command_data.get("note")
                                        user = self.users.get(sock, "default")
                                        folder = os.path.join(self.user_loc, user)
                                        if not os.path.exists(folder):
                                            os.makedirs(folder, exist_ok=True)
                                        try:
                                            note_id = self.update_and_get_last(user)
                                        except Exception as e:
                                            print("User not found in DB, using default counter")
                                            note_id = self.default_counter
                                            self.default_counter += 1
                                        note_data["id"] = str(note_id)
                                        # שמירת הפתק - גם אם הפתק לא משותף, נשתמש בשיטה זו
                                        self.save_note_to_file(note_data, folder, str(note_id))
                                        response = json.dumps({"status": "success", "note_id": note_data["id"]})
                                        if sock in wlist:
                                            sock.send(response.encode())
                                        broadcast_data = json.dumps({"action": "broadcast_create", "note": note_data})
                                        threading.Thread(target=self.broadcast_to_user,
                                                         args=(user, broadcast_data, sock)).start()

                                    elif action == "load":
                                        user = self.users.get(sock, "default")
                                        folder = os.path.join(self.user_loc, user)
                                        notes = []
                                        if os.path.exists(folder):
                                            for filename in os.listdir(folder):
                                                if filename.endswith(".txt"):
                                                    with open(os.path.join(folder, filename), "r", encoding="utf-8") as file:
                                                        content = file.read()
                                                    note = {}
                                                    for line in content.splitlines():
                                                        if line.startswith("Title:"):
                                                            note["title"] = line.replace("Title:", "").strip()
                                                        elif line.startswith("Text:"):
                                                            note["text"] = line.replace("Text:", "").strip()
                                                        elif line.startswith("Image:"):
                                                            note["image"] = line.replace("Image:", "").strip()
                                                        elif line.startswith("Shared:"):
                                                            shared_str = line.replace("Shared:", "").strip()
                                                            note["shared"] = True if shared_str.lower() == "true" else False
                                                        elif line.startswith("SharedFrom:"):
                                                            note["shared_from"] = line.replace("SharedFrom:", "").strip()
                                                        elif line.startswith("OriginalOwner:"):
                                                            note["original_owner"] = line.replace("OriginalOwner:", "").strip()
                                                    note["id"] = os.path.splitext(filename)[0]
                                                    notes.append(note)
                                        # שינוי: הוספת פתקים שהמשתמש קיבל בשיתוף
                                        current_user = self.users.get(sock, "default")
                                        for key, data in self.shared_notes.items():
                                            if current_user in data["shared_with"]:
                                                note = data["note"]
                                                notes.append(note)
                                        response = json.dumps({"action": "load_notes", "notes": notes})
                                        if sock in wlist:
                                            sock.send(response.encode())

                                    elif action == "delete":
                                        note_id = command_data.get("note_id")
                                        user = self.users.get(sock, "default")
                                        # שינוי: טיפול במחיקת פתקים משותפים
                                        for key, data in list(self.shared_notes.items()):
                                            note = data["note"]
                                            if note.get("id") == note_id:
                                                # אם המשתמש הוא הבעלים המקורי - מוחקים את הפתק בכללותו
                                                if note.get("original_owner") == user:
                                                    del self.shared_notes[key]
                                                else:
                                                    # אם המשתמש אינו הבעלים, נסיר אותו מרשימת השותפים
                                                    if user in data["shared_with"]:
                                                        data["shared_with"].remove(user)
                                                break
                                        folder = os.path.join(self.user_loc, user)
                                        self.delete_note_file(folder, note_id)
                                        response = json.dumps({"status": "success", "message": "Note deleted"})
                                        if sock in wlist:
                                            sock.send(response.encode())
                                        broadcast_data = json.dumps({"action": "broadcast_delete", "note_id": note_id})
                                        threading.Thread(target=self.broadcast_to_user,
                                                         args=(user, broadcast_data, sock)).start()

                                    elif action == "edit":
                                        note_data = command_data.get("note")
                                        # שינוי: אם הפתק משותף (יש לו shared_from ו-original_owner),
                                        # נטפל בו בתיקיית הבעלים המקורי ונעדכן את המידע במבנה המשותף.
                                        if note_data.get("shared_from") and note_data.get("original_owner"):
                                            folder = os.path.join(self.user_loc, note_data["original_owner"])
                                            key = (note_data["original_owner"], note_data["shared_from"])
                                            if key in self.shared_notes:
                                                self.shared_notes[key]["note"] = note_data
                                        else:
                                            user = self.users.get(sock, "default")
                                            folder = os.path.join(self.user_loc, user)
                                        note_id = note_data.get("id")
                                        self.edit_note_file(note_data, folder, note_id)
                                        response = json.dumps({"status": "success", "message": "Note edited"})
                                        if sock in wlist:
                                            sock.send(response.encode())
                                        # שינוי: שידור עדכון לכל המשתמשים שיש להם את הפתק המשותף
                                        if note_data.get("shared_from") and note_data.get("original_owner"):
                                            key = (note_data["original_owner"], note_data["shared_from"])
                                            shared_users = self.shared_notes.get(key, {}).get("shared_with", [])
                                            # כולל גם את הבעלים המקורי
                                            if note_data["original_owner"] not in shared_users:
                                                shared_users.append(note_data["original_owner"])
                                            shared_users = list(set(shared_users))
                                            for user in shared_users:
                                                if user != self.users.get(sock, "default"):
                                                    broadcast_data = json.dumps({"action": "broadcast_edit", "note": note_data})
                                                    threading.Thread(target=self.broadcast_to_user,
                                                                     args=(user, broadcast_data, sock)).start()
                                        else:
                                            user = self.users.get(sock, "default")
                                            broadcast_data = json.dumps({"action": "broadcast_edit", "note": note_data})
                                            threading.Thread(target=self.broadcast_to_user,
                                                             args=(user, broadcast_data, sock)).start()

                                    elif action == "get_users":
                                        current_user = self.users.get(sock, "default")
                                        users_list = list(set(self.users.values()) - {current_user})
                                        response = json.dumps({"action": "users_list", "users": users_list})
                                        if sock in wlist:
                                            sock.send(response.encode())

                                    elif action == "share":
                                        note_data = command_data.get("note")
                                        target_user = command_data.get("target_user")
                                        current_user = self.users.get(sock, "default")
                                        # שינוי: אם הפתק עדיין לא משותף, נגדיר shared_from ו-original_owner
                                        if not note_data.get("shared_from"):
                                            note_data["shared_from"] = note_data.get("id")
                                            note_data["original_owner"] = current_user
                                        note_data["shared"] = True
                                        key = (note_data["original_owner"], note_data["shared_from"])
                                        if key not in self.shared_notes:
                                            self.shared_notes[key] = {"note": note_data, "shared_with": []}
                                        if target_user in self.shared_notes[key]["shared_with"]:
                                            response = json.dumps({"status": "error", "message": "הפתק כבר שותף למשתמש זה."})
                                            if sock in wlist:
                                                sock.send(response.encode())
                                        else:
                                            self.shared_notes[key]["shared_with"].append(target_user)
                                            response = json.dumps({"status": "success"})
                                            if sock in wlist:
                                                sock.send(response.encode())
                                            broadcast_data = json.dumps({"action": "broadcast_create", "note": note_data})
                                            threading.Thread(target=self.broadcast_to_user,
                                                             args=(target_user, broadcast_data, sock)).start()
                                    else:
                                        response = json.dumps({"status": "error", "message": "Unknown action"})
                                        if sock in wlist:
                                            sock.send(response.encode())
                                except Exception as e:
                                    print("Error processing JSON command:", e)
                            else:
                                data_en = full_data.split('$$$')
                                print(data_en)
                                if not data_en or data_en == ['']:
                                    print("Client disconnected")
                                    if sock in self.users:
                                        del self.users[sock]
                                    if sock in self.open_sockets:
                                        self.open_sockets.remove(sock)
                                    sock.close()
                                    continue
                                if "TITLE:" in data_en[0]:
                                    user = self.users.get(sock, "default")
                                    folder = os.path.join(self.user_loc, user)
                                    note_num = self.update_and_get_last(user)
                                    note_dict = {}
                                    lines = data_en[0].strip().split("\\n")
                                    for line in lines:
                                        if ":" in line:
                                            key, value = line.split(":", 1)
                                            note_dict[key.strip().lower()] = value.strip()
                                    note_data1 = note_dict
                                    self.save_note_to_file(note_data1, folder, str(note_num))
                                elif len(data_en) < 5:
                                    exists, message = self.is_user_exists(data_en[0], data_en[1])
                                    if sock in wlist:
                                        sock.send(message.encode())
                                    self.users[sock] = data_en[0]
                                else:
                                    error_message = self.insert_row(data_en[0], data_en[1], data_en[2], data_en[3],
                                                                    data_en[4])
                                    if error_message:
                                        if sock in wlist:
                                            sock.send(error_message.encode())
                                    else:
                                        if sock in wlist:
                                            sock.send("User registered successfully".encode())
                                        self.create_folder(data_en[2])
                            full_data = ""
                        except BlockingIOError:
                            continue
                        except Exception as e:
                            print("Error:", e)
                            if sock in self.open_sockets:
                                self.open_sockets.remove(sock)
                            if sock in self.users:
                                del self.users[sock]
                            sock.close()
                    full_data = ""
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.listening_socket.close()
            for sock in self.open_sockets:
                sock.close()

    def broadcast_to_user(self, user, message, sender_sock):
        for sock, usr in list(self.users.items()):
            if usr == user and sock != sender_sock:
                try:
                    sock.send(message.encode())
                except Exception as e:
                    print("Broadcast error:", e)

    def generate_server_keys_once(self):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        public_key = private_key.public_key()
        return private_key, public_key

    def get_public_key_pem(self):
        public_pem = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return public_pem.decode('utf-8')

    def insert_row(self, fullname, ID, email, username, password):
        conn = sqlite3.connect(self.db_loc)
        c = conn.cursor()
        error_message = ""
        sql_str = "INSERT INTO users (email, ID, fullname, username, password) VALUES (?, ?, ?, ?, ?)"
        try:
            c.execute(sql_str, (email, ID, fullname, username, password))
        except sqlite3.IntegrityError:
            error_message = f"ERROR: email {email} already exists."
            print(error_message)
        conn.commit()
        conn.close()
        return error_message

    def is_user_exists(self, email, psw):
        conn = sqlite3.connect(self.db_loc)
        c = conn.cursor()
        sql_str = "SELECT password FROM users WHERE email = ?"
        c.execute(sql_str, (email,))
        user = c.fetchone()
        conn.close()
        stored_password = user[0]
        if self.decrypt_message(stored_password) == self.decrypt_message(psw):
            return True, "Login successful"
        else:
            return False, "Invalid email or password"

    def update_and_get_last(self, email):
        conn = sqlite3.connect(self.db_loc)
        cursor = conn.cursor()
        cursor.execute("SELECT last FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"User with email {email} not found.")
        last_value = row[0]
        new_value = last_value + 1
        cursor.execute("UPDATE users SET last = ? WHERE email = ?", (new_value, email))
        conn.commit()
        conn.close()
        return last_value

    def decrypt_message(self, encrypted_message):
        try:
            if len(encrypted_message) % 4 != 0:
                encrypted_message += "=" * (4 - len(encrypted_message) % 4)
            encrypted_message_bytes = base64.b64decode(encrypted_message)
            key_size_bytes = self.private_key.key_size // 8
            if len(encrypted_message_bytes) != key_size_bytes:
                raise ValueError(f"Invalid ciphertext length: {len(encrypted_message_bytes)} != {key_size_bytes}")
            decrypted_message = self.private_key.decrypt(
                encrypted_message_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            return decrypted_message.decode('utf-8')
        except Exception as e:
            print(f"Decryption error: {e}")
            raise

    def create_folder(self, folder_name):
        try:
            folder_path = os.path.join(self.user_loc, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            print(f"folder '{folder_name}' was created successfully.")
            return folder_path
        except Exception as e:
            print(f"שגיאה ביצירת התיקייה: {e}")
            return None

    def save_note_to_file(self, note_data, folder_path, name):
        try:
            if not os.path.exists(folder_path):
                raise FileNotFoundError(f"התיקייה {folder_path} לא קיימת")
            if isinstance(note_data, str):
                note_data = json.loads(note_data)
            title = note_data.get("title", "").strip()
            text = note_data.get("text", "").strip()
            image_data = note_data.get("image")
            filename = os.path.join(folder_path, f"{name}.txt")
            with open(filename, "w", encoding="utf-8") as file:
                file.write(f"Title: {title}\n")
                file.write(f"Text: {text}\n")
                if image_data:
                    if isinstance(image_data, str):
                        try:
                            image_bytes = base64.b64decode(image_data)
                        except Exception as e:
                            print(f"שגיאה בפענוח Base64 של תמונה: {e}")
                            image_bytes = None
                    else:
                        image_bytes = image_data
                    if image_bytes:
                        image_filename = os.path.join(folder_path, f"{title}_image.jpg")
                        with open(image_filename, "wb") as img_file:
                            img_file.write(image_bytes)
                        file.write(f"Image: {image_filename}\n")
                if note_data.get("shared"):
                    file.write("Shared: True\n")
                if note_data.get("shared_from"):
                    file.write(f"SharedFrom: {note_data['shared_from']}\n")
                if note_data.get("original_owner"):
                    file.write(f"OriginalOwner: {note_data['original_owner']}\n")
                file.write("\n")
            print(f"Note saved successfully in folder: {folder_path}")
        except Exception as e:
            print(f"Error saving note: {e}")

    def delete_note_file(self, folder_path, note_id):
        try:
            note_filename = os.path.join(folder_path, f"{note_id}.txt")
            if os.path.exists(note_filename):
                os.remove(note_filename)
                print(f"Note {note_id} deleted successfully.")
            else:
                print(f"Note file {note_filename} not found.")
        except Exception as e:
            print(f"Error deleting note {note_id}: {e}")

    def edit_note_file(self, note_data, folder_path, note_id):
        try:
            note_filename = os.path.join(folder_path, f"{note_id}.txt")
            if not os.path.exists(note_filename):
                print(f"Note file {note_filename} not found.")
                return
            title = note_data.get("title", "").strip()
            text = note_data.get("text", "").strip()
            image_data = note_data.get("image")
            with open(note_filename, "w", encoding="utf-8") as file:
                file.write(f"Title: {title}\n")
                file.write(f"Text: {text}\n")
                if image_data:
                    if isinstance(image_data, str):
                        try:
                            image_bytes = base64.b64decode(image_data)
                        except Exception as e:
                            print(f"שגיאה בפענוח Base64 של תמונה: {e}")
                            image_bytes = None
                    else:
                        image_bytes = image_data
                    if image_bytes:
                        image_filename = os.path.join(folder_path, f"{title}_image.jpg")
                        with open(image_filename, "wb") as img_file:
                            img_file.write(image_bytes)
                        file.write(f"Image: {image_filename}\n")
                if note_data.get("shared"):
                    file.write("Shared: True\n")
                if note_data.get("shared_from"):
                    file.write(f"SharedFrom: {note_data['shared_from']}\n")
                if note_data.get("original_owner"):
                    file.write(f"OriginalOwner: {note_data['original_owner']}\n")
                file.write("\n")
            print(f"Note {note_id} edited successfully.")
        except Exception as e:
            print(f"Error editing note {note_id}: {e}")


if __name__ == '__main__':
    server = Server()
    server.run()
