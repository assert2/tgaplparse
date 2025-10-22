import asyncio
import tkinter as tk
from tkinter import ttk, messagebox
from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from datetime import datetime
import json
import os
import subprocess
from pathlib import Path
import threading
from tkcalendar import DateEntry
from datetime import date

# Конфигурационный файл для хранения учетных данных
CONFIG_FILE = os.path.expanduser('~/.telegram_parser_config.json')
OUTPUT_DIR = os.path.expanduser('~/Documents/TelegramParserData')

# Коды стран с флагами
# Коды стран с флагами
COUNTRY_CODES = [
    ('+7', '🇷🇺'),
    ('+1', '🇺🇸'),
    ('+44', '🇬🇧'),
    ('+49', '🇩🇪'),
    ('+33', '🇫🇷'),
    ('+39', '🇮🇹'),
    ('+34', '🇪🇸'),
    ('+380', '🇺🇦'),
    ('+375', '🇧🇾'),
    ('+374', '🇦🇲'),
    ('+994', '🇦🇿'),
    ('+995', '🇬🇪'),
    ('+998', '🇺🇿'),
    ('+996', '🇰🇬'),
    ('+992', '🇹🇯'),
    ('+993', '🇹🇲'),
    ('+86', '🇨🇳'),
    ('+81', '🇯🇵'),
    ('+82', '🇰🇷'),
    ('+91', '🇮🇳'),
    ('+48', '🇵🇱'),
    ('+90', '🇹🇷'),
    ('+62', '🇮🇩'),
    ('+66', '🇹🇭'),
    ('+84', '🇻🇳'),
]



class TelegramParser:
    def __init__(self, api_id, api_hash, phone):
        session_path = os.path.expanduser('~/Documents/TelegramParserData/session')
        os.makedirs(os.path.dirname(session_path), exist_ok=True)
        
        self.client = TelegramClient(
            session_path, 
            api_id, 
            api_hash, 
            device_model="iPhone 55 Pro",
            system_version="IOS 100.1"
        )
        self.phone = phone
        
    async def start_client(self):
        """Подключение клиента без авторизации"""
        await self.client.connect()
        return await self.client.is_user_authorized()
        
    async def send_code_request(self):
        """Отправка запроса на код"""
        return await self.client.send_code_request(self.phone)
    
    async def sign_in(self, code):
        """Вход с кодом"""
        try:
            await self.client.sign_in(self.phone, code)
            return True
        except SessionPasswordNeededError:
            return 'password_needed'
        except PhoneCodeInvalidError:
            raise Exception("Неверный код")
        except Exception as e:
            raise Exception(f"Ошибка входа: {str(e)}")
    
    async def sign_in_password(self, password):
        """Вход с паролем 2FA"""
        await self.client.sign_in(password=password)
        return True
    
    async def check_authorization(self):
        """Проверка авторизации"""
        return await self.client.is_user_authorized()
    
    async def get_channel_by_id(self, channel_id):
        """Получение канала по ID"""
        try:
            entity = await self.client.get_entity(channel_id)
            return entity
        except Exception as e:
            raise Exception(f"Не удалось получить канал по ID: {str(e)}")
    
    async def get_channel_by_invite_link(self, invite_link):
        """Получение канала по пригласительной ссылке"""
        try:
            entity = await self.client.get_entity(invite_link)
            return entity
        except Exception as e:
            raise Exception(f"Не удалось получить канал по ссылке: {str(e)}")
    
    async def get_channel_by_username(self, username):
        """Получение канала по юзернейму"""
        try:
            entity = await self.client.get_entity(username)
            return entity
        except Exception as e:
            raise Exception(f"Не удалось получить канал по юзернейму: {str(e)}")
    
    async def list_joined_channels(self):
        """Список всех каналов, на которые подписан пользователь"""
        channels = []
        try:
            async for dialog in self.client.iter_dialogs():
                if dialog.is_channel:
                    channels.append({
                        'id': dialog.entity.id,
                        'title': dialog.title,
                        'username': dialog.entity.username if hasattr(dialog.entity, 'username') else 'N/A',
                        'entity': dialog.entity
                    })
            return channels
        except Exception as e:
            raise Exception(f"Ошибка при получении списка каналов: {str(e)}")
    
    async def get_post_data(self, channel, post_id):
        """Получение данных одного поста"""
        try:
            message = await self.client.get_messages(channel, ids=post_id)
            
            if not message:
                return None
            
            text = message.message or ""
            
            reactions = await self.get_reactions(message)
            comments = await self.get_comments(message)
            
            post_data = {
                'post_id': message.id,
                'date': message.date.strftime('%Y-%m-%d %H:%M:%S'),
                'text': text,
                'views': message.views or 0,
                'forwards': message.forwards or 0,
                'reactions': reactions,
                'comments': comments,
                'comments_count': message.replies.replies if message.replies else 0,
                'media_type': self.get_media_type(message)
            }
            
            return post_data
            
        except Exception as e:
            print(f"Ошибка при получении поста {post_id}: {e}")
            return None
    
    async def get_reactions(self, message):
        """Получение реакций на пост"""
        reactions_data = []
        
        try:
            if message.reactions:
                for reaction in message.reactions.results:
                    reactions_data.append({
                        'emoji': reaction.reaction.emoticon if hasattr(reaction.reaction, 'emoticon') else str(reaction.reaction),
                        'count': reaction.count
                    })
        except Exception as e:
            print(f"Ошибка при получении реакций: {e}")
            
        return reactions_data
    
    async def get_comments(self, message):
        """Получение комментариев под постом"""
        comments_data = []
        
        try:
            if message.replies and message.replies.replies > 0:
                if hasattr(message.replies, 'channel_id') and message.replies.channel_id:
                    discussion_chat_id = message.replies.channel_id
                    
                    async for comment in self.client.iter_messages(
                        discussion_chat_id,
                        reply_to=message.replies.read_max_id or message.id,
                        limit=100
                    ):
                        comment_data = {
                            'comment_id': comment.id,
                            'date': comment.date.strftime('%Y-%m-%d %H:%M:%S'),
                            'text': comment.message or "",
                            'author_id': comment.sender_id,
                        }
                        comments_data.append(comment_data)
                        
        except Exception as e:
            print(f"Ошибка при получении комментариев для поста {message.id}: {e}")
            
        return comments_data
    
    def get_media_type(self, message):
        """Определение типа медиа в посте"""
        if message.photo:
            return 'photo'
        elif message.video:
            return 'video'
        elif message.document:
            return 'document'
        elif message.voice:
            return 'voice'
        else:
            return 'text'
    
    async def parse_channel(self, channel, start_date=None, progress_callback=None):
        """Парсинг канала с указанной даты"""
        all_posts = []

        try:
            async for message in self.client.iter_messages(channel):
                # --- безопасное сравнение aware/naive ---
                if start_date:
                    # message.date — часто offset-aware; приводим его к naive для сравнения
                    msg_dt = message.date
                    if msg_dt is None:
                        continue

                    # делаем временные naive-версии (только для сравнения)
                    if hasattr(msg_dt, 'tzinfo') and msg_dt.tzinfo is not None:
                        msg_compare = msg_dt.replace(tzinfo=None)
                    else:
                        msg_compare = msg_dt

                    # start_date может быть date или datetime; приводим к datetime (00:00:00)
                    if isinstance(start_date, datetime):
                        sd = start_date
                    else:
                        sd = datetime.combine(start_date, datetime.min.time())

                    # уверяемся, что sd тоже naive
                    if hasattr(sd, 'tzinfo') and sd.tzinfo is not None:
                        sd = sd.replace(tzinfo=None)

                    if msg_compare < sd:
                        # пост старее чем требуемая дата — пропускаем / останавливаем (как у тебя)
                        break

                if progress_callback:
                    progress_callback(f"Обработка поста {message.id}...")

                post_data = await self.get_post_data(channel, message.id)

                if post_data:
                    all_posts.append(post_data)

            return all_posts

        except Exception as e:
            raise Exception(f"Ошибка при парсинге канала: {str(e)}")

    
    async def save_to_json(self, data, filename='telegram_data.json'):
        """Сохранение данных в JSON файл"""
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    async def close(self):
        """Закрытие соединения"""
        await self.client.disconnect()


class TelegramParserApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Telegram Parser")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        
        self.parser = None
        self.selected_channel = None
        self.channels_list = []
        self.loop = None
        self.authenticated = False
        
        # Сохраненные значения для полей
        self.saved_api_id = ""
        self.saved_api_hash = ""
        self.saved_phone = ""
        self.saved_country_code = "+7"
        
        # Проверяем наличие сохраненных учетных данных
        if self.load_credentials():
            self.try_auto_login()
        else:
            self.show_login_screen()
    
    def load_credentials(self):
        """Загрузка сохраненных учетных данных"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self.api_id = config.get('api_id')
                    self.api_hash = config.get('api_hash')
                    self.phone = config.get('phone')
                    
                    # Сохраняем для полей
                    self.saved_api_id = self.api_id
                    self.saved_api_hash = self.api_hash
                    
                    # Извлекаем код страны и номер
                    if self.phone:
                        for code, flag in COUNTRY_CODES:
                            if self.phone.startswith(code):
                                self.saved_country_code = code
                                self.saved_phone = self.phone[len(code):]
                                break
                    
                    if self.api_id and self.api_hash and self.phone:
                        return True
            except Exception as e:
                print(f"Ошибка загрузки конфигурации: {e}")
        return False
    
    def try_auto_login(self):
        """Попытка автоматического входа"""
        self.show_progress("Подключение к Telegram...")
        
        def auto_login():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop = loop
            
            try:
                self.parser = TelegramParser(self.api_id, self.api_hash, self.phone)
                is_authorized = loop.run_until_complete(self.parser.start_client())
                
                if is_authorized:
                    self.authenticated = True
                    self.root.after(0, self.show_main_screen)
                else:
                    # Не авторизован - возвращаемся к входу
                    self.root.after(0, self.show_login_screen)
                    
            except Exception as e:
                print(f"Ошибка автоматического входа: {e}")
                self.root.after(0, self.show_login_screen)
        
        threading.Thread(target=auto_login, daemon=True).start()
    
    def save_credentials(self, api_id, api_hash, phone):
        """Сохранение учетных данных"""
        config = {
            'api_id': api_id,
            'api_hash': api_hash,
            'phone': phone
        }
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    
    def clear_window(self):
        """Очистка окна"""
        for widget in self.root.winfo_children():
            widget.destroy()
    
    def show_login_screen(self):
        """Экран входа"""
        self.clear_window()
        
        frame = ttk.Frame(self.root, padding="40")
        frame.pack(expand=True)
        
        ttk.Label(frame, text="Telegram Parser", font=('Arial', 24, 'bold')).grid(row=0, column=0, columnspan=3, pady=20)
        ttk.Label(frame, text="Вход в аккаунт", font=('Arial', 12)).grid(row=1, column=0, columnspan=3, pady=10)
        
        ttk.Label(frame, text="API ID:").grid(row=2, column=0, sticky='e', padx=5, pady=10)
        self.api_id_entry = ttk.Entry(frame, width=30)
        self.api_id_entry.grid(row=2, column=1, columnspan=2, pady=10)
        self.api_id_entry.insert(0, self.saved_api_id)
        
        ttk.Label(frame, text="API Hash:").grid(row=3, column=0, sticky='e', padx=5, pady=10)
        self.api_hash_entry = ttk.Entry(frame, width=30)
        self.api_hash_entry.grid(row=3, column=1, columnspan=2, pady=10)
        self.api_hash_entry.insert(0, self.saved_api_hash)
        
        ttk.Label(frame, text="Телефон:").grid(row=4, column=0, sticky='e', padx=5, pady=10)
        
        # Комбобокс только с флагами и кодами
        self.country_code_var = tk.StringVar(value=self.saved_country_code)
        country_combo = ttk.Combobox(frame, textvariable=self.country_code_var, width=8, state='readonly')
        country_combo['values'] = [f"{code} {flag}" for code, flag in COUNTRY_CODES]
        
        for code, flag in COUNTRY_CODES:
            if code == self.saved_country_code:
                country_combo.set(f"{code} {flag}")
                break
        
        country_combo.grid(row=4, column=1, sticky='w', pady=10, padx=(0, 5))
        
        # Поле для телефона
        self.phone_entry = ttk.Entry(frame, width=18)
        self.phone_entry.grid(row=4, column=2, sticky='w', pady=10)
        self.phone_entry.insert(0, self.saved_phone)
        
        def validate_phone(text):
            return text.isdigit() or text == ""
        
        vcmd = (self.root.register(validate_phone), '%P')
        self.phone_entry.config(validate='key', validatecommand=vcmd)
        
        ttk.Label(frame, text="(только цифры, без +)", font=('Arial', 8)).grid(row=5, column=1, columnspan=2, sticky='w')
        
        ttk.Button(frame, text="Войти", command=self.login).grid(row=6, column=0, columnspan=3, pady=20)
        
        # Новая кнопка для изменения аккаунта
        ttk.Button(frame, text="Поменять данные аккаунта", command=self.reset_to_login).grid(row=7, column=0, columnspan=3, pady=10)

    def reset_to_login(self):
        """Возврат к логину без удаления файлов"""
        self.authenticated = False
        self.saved_api_id = ""
        self.saved_api_hash = ""
        self.saved_phone = ""
        self.saved_country_code = "+7"
        self.show_login_screen()


    def login(self):
        """Обработка входа"""
        api_id = self.api_id_entry.get().strip()
        api_hash = self.api_hash_entry.get().strip()
        
        # Получаем код страны из комбобокса
        country_code_full = self.country_code_var.get()
        country_code = country_code_full.split()[0]  # Берем только код (+7, +1 и т.д.)
        
        phone_number = self.phone_entry.get().strip()
        
        if not api_id or not api_hash or not phone_number:
            messagebox.showerror("Ошибка", "Все поля должны быть заполнены!")
            return
        
        # Сохраняем значения для восстановления при ошибке
        self.saved_api_id = api_id
        self.saved_api_hash = api_hash
        self.saved_phone = phone_number
        self.saved_country_code = country_code
        
        # Формируем полный номер телефона
        phone = f"{country_code}{phone_number}"
        
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        
        # Сохраняем учетные данные
        self.save_credentials(api_id, api_hash, phone)
        
        # Пытаемся авторизоваться
        self.authenticate()
    
    def authenticate(self):
        """Аутентификация в Telegram"""
        self.show_progress("Подключение к Telegram...")
        
        def auth():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop = loop
            
            try:
                self.parser = TelegramParser(self.api_id, self.api_hash, self.phone)
                is_authorized = loop.run_until_complete(self.parser.start_client())
                
                if is_authorized:
                    # Уже авторизован — сразу на главный экран
                    self.authenticated = True
                    self.root.after(0, self.show_main_screen)
                    return
                
                # Если Telegram требует код
                self.root.after(0, lambda: self.update_progress_text("Отправка кода..."))
                loop.run_until_complete(self.parser.send_code_request())
                self.root.after(0, self.ask_code)
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка подключения:\n{str(e)}"))
                self.root.after(0, self.show_login_screen)
        
        threading.Thread(target=auth, daemon=True).start()

    
    def ask_code(self):
        """Запрос кода подтверждения"""
        self.clear_window()
        
        frame = ttk.Frame(self.root, padding="40")
        frame.pack(expand=True)
        
        ttk.Label(frame, text="Введите код из Telegram", font=('Arial', 16, 'bold')).pack(pady=20)
        ttk.Label(frame, text=f"Код отправлен на номер: {self.phone}", font=('Arial', 11)).pack(pady=10)
        
        code_entry = ttk.Entry(frame, width=20, font=('Arial', 14))
        code_entry.pack(pady=20)
        code_entry.focus()
        
        def submit_code():
            code = code_entry.get().strip()
            if not code:
                messagebox.showerror("Ошибка", "Введите код!")
                return
            
            self.show_progress("Проверка кода...")
            
            def verify_code():
                try:
                    result = self.loop.run_until_complete(self.parser.sign_in(code))
                    
                    if result == 'password_needed':
                        # Требуется пароль 2FA
                        self.root.after(0, self.ask_password)
                    elif result:
                        # Успешный вход
                        self.authenticated = True
                        self.root.after(0, self.show_main_screen)
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("Ошибка", error_msg))
                    self.root.after(0, self.ask_code)
            
            threading.Thread(target=verify_code, daemon=True).start()
        
        ttk.Button(frame, text="Подтвердить", command=submit_code).pack(pady=10)
        code_entry.bind('<Return>', lambda e: submit_code())
    
    def ask_password(self):
        """Запрос пароля двухфакторной аутентификации"""
        self.clear_window()
        
        frame = ttk.Frame(self.root, padding="40")
        frame.pack(expand=True)
        
        ttk.Label(frame, text="Двухфакторная аутентификация", font=('Arial', 16, 'bold')).pack(pady=20)
        ttk.Label(frame, text="Введите пароль облачного хранилища:", font=('Arial', 11)).pack(pady=10)
        
        password_entry = ttk.Entry(frame, width=30, font=('Arial', 12), show='*')
        password_entry.pack(pady=20)
        password_entry.focus()
        
        def submit_password():
            password = password_entry.get().strip()
            if not password:
                messagebox.showerror("Ошибка", "Введите пароль!")
                return
            
            self.show_progress("Проверка пароля...")
            
            def verify_password():
                try:
                    self.loop.run_until_complete(self.parser.sign_in_password(password))
                    self.authenticated = True
                    self.root.after(0, self.show_main_screen)
                except Exception as e:
                    error_msg = str(e)
                    self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Неверный пароль:\n{error_msg}"))
                    self.root.after(0, self.ask_password)
            
            threading.Thread(target=verify_password, daemon=True).start()
        
        ttk.Button(frame, text="Подтвердить", command=submit_password).pack(pady=10)
        password_entry.bind('<Return>', lambda e: submit_password())
    
    def show_main_screen(self):
        """Главный экран с выбором канала"""
        self.clear_window()
        
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(expand=True, fill='both')
        
        ttk.Label(frame, text="Выберите способ получения канала", font=('Arial', 16, 'bold')).pack(pady=20)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(expand=True)
        
        ttk.Button(btn_frame, text="По ID канала", width=40, command=lambda: self.select_channel_method('id')).pack(pady=10)
        ttk.Button(btn_frame, text="По пригласительной ссылке", width=40, command=lambda: self.select_channel_method('invite')).pack(pady=10)
        ttk.Button(btn_frame, text="По юзернейму", width=40, command=lambda: self.select_channel_method('username')).pack(pady=10)
        ttk.Button(btn_frame, text="Из списка подписок", width=40, command=lambda: self.select_channel_method('list')).pack(pady=10)
        
        ttk.Button(frame, text="Сбросить учетные данные", command=self.reset_credentials).pack(pady=20)
    
    def reset_credentials(self):
        """Сброс учетных данных"""
        if messagebox.askyesno("Подтверждение", "Вы уверены, что хотите сбросить учетные данные?"):
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
            session_path = os.path.expanduser('~/Documents/TelegramParserData/session.session')
            if os.path.exists(session_path):
                os.remove(session_path)
            self.authenticated = False
            self.saved_api_id = ""
            self.saved_api_hash = ""
            self.saved_phone = ""
            self.saved_country_code = "+7"
            self.show_login_screen()
    
    def select_channel_method(self, method):
        """Выбор метода получения канала"""
        self.channel_method = method
        
        if method == 'id':
            self.ask_channel_id()
        elif method == 'invite':
            self.ask_invite_link()
        elif method == 'username':
            self.ask_username()
        elif method == 'list':
            self.show_channels_list()
    
    def ask_channel_id(self):
        """Запрос ID канала"""
        dialog = tk.Toplevel(self.root)
        dialog.title("ID канала")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Введите ID канала:", font=('Arial', 12)).pack(pady=20)
        entry = ttk.Entry(dialog, width=30)
        entry.pack(pady=10)
        entry.focus()
        
        def submit():
            channel_id = entry.get().strip()
            if channel_id:
                try:
                    channel_id = int(channel_id)
                    dialog.destroy()
                    self.get_channel_by_id(channel_id)
                except ValueError:
                    messagebox.showerror("Ошибка", "ID должен быть числом!")
        
        ttk.Button(dialog, text="OK", command=submit).pack(pady=10)
        entry.bind('<Return>', lambda e: submit())
    
    def ask_invite_link(self):
        """Запрос пригласительной ссылки"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Пригласительная ссылка")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Введите ссылку (https://t.me/+...):", font=('Arial', 12)).pack(pady=20)
        entry = ttk.Entry(dialog, width=40)
        entry.pack(pady=10)
        entry.focus()
        
        def submit():
            invite_link = entry.get().strip()
            if invite_link:
                dialog.destroy()
                self.get_channel_by_invite_link(invite_link)
        
        ttk.Button(dialog, text="OK", command=submit).pack(pady=10)
        entry.bind('<Return>', lambda e: submit())
    
    def ask_username(self):
        """Запрос юзернейма"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Юзернейм канала")
        dialog.geometry("400x150")
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text="Введите юзернейм (@channel_name):", font=('Arial', 12)).pack(pady=20)
        entry = ttk.Entry(dialog, width=30)
        entry.pack(pady=10)
        entry.focus()
        
        def submit():
            username = entry.get().strip()
            if username:
                dialog.destroy()
                self.get_channel_by_username(username)
        
        ttk.Button(dialog, text="OK", command=submit).pack(pady=10)
        entry.bind('<Return>', lambda e: submit())
    
    def show_channels_list(self):
        """Показ списка каналов"""
        self.show_progress("Загрузка списка каналов...")
        
        def load_channels():
            try:
                self.channels_list = self.loop.run_until_complete(self.parser.list_joined_channels())
                self.root.after(0, self.display_channels_list)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Не удалось загрузить каналы:\n{str(e)}"))
                self.root.after(0, self.show_main_screen)
        
        threading.Thread(target=load_channels, daemon=True).start()
    
    def display_channels_list(self):
        """Отображение списка каналов"""
        self.clear_window()
        
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(expand=True, fill='both')
        
        ttk.Label(frame, text="Выберите канал", font=('Arial', 16, 'bold')).pack(pady=10)
        
        # Создаем список с прокруткой
        list_frame = ttk.Frame(frame)
        list_frame.pack(expand=True, fill='both', pady=10)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side='right', fill='y')
        
        self.channels_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=('Arial', 11))
        self.channels_listbox.pack(side='left', expand=True, fill='both')
        scrollbar.config(command=self.channels_listbox.yview)
        
        for channel in self.channels_list:
            self.channels_listbox.insert('end', f"{channel['title']} (ID: {channel['id']})")
        
        ttk.Button(frame, text="Выбрать", command=self.select_from_list).pack(pady=10)
        ttk.Button(frame, text="Назад", command=self.show_main_screen).pack()
    
    def select_from_list(self):
        """Выбор канала из списка"""
        selection = self.channels_listbox.curselection()
        if selection:
            index = selection[0]
            self.selected_channel = self.channels_list[index]['entity']
            self.ask_start_date()
        else:
            messagebox.showwarning("Предупреждение", "Выберите канал из списка!")
    
    def get_channel_by_id(self, channel_id):
        """Получение канала по ID"""
        self.show_progress("Подключение к каналу...")
        
        def get_channel():
            try:
                channel = self.loop.run_until_complete(self.parser.get_channel_by_id(channel_id))
                
                if channel:
                    self.selected_channel = channel
                    self.root.after(0, self.ask_start_date)
                else:
                    self.root.after(0, lambda: messagebox.showerror("Ошибка", "Канал не найден!"))
                    self.root.after(0, self.show_main_screen)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка подключения:\n{str(e)}"))
                self.root.after(0, self.show_main_screen)
        
        threading.Thread(target=get_channel, daemon=True).start()
    
    def get_channel_by_invite_link(self, invite_link):
        """Получение канала по ссылке"""
        self.show_progress("Подключение к каналу...")
        
        def get_channel():
            try:
                channel = self.loop.run_until_complete(self.parser.get_channel_by_invite_link(invite_link))
                
                if channel:
                    self.selected_channel = channel
                    self.root.after(0, self.ask_start_date)
                else:
                    self.root.after(0, lambda: messagebox.showerror("Ошибка", "Канал не найден!"))
                    self.root.after(0, self.show_main_screen)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка подключения:\n{str(e)}"))
                self.root.after(0, self.show_main_screen)
        
        threading.Thread(target=get_channel, daemon=True).start()
    
    def get_channel_by_username(self, username):
        """Получение канала по юзернейму"""
        self.show_progress("Подключение к каналу...")
        
        def get_channel():
            try:
                channel = self.loop.run_until_complete(self.parser.get_channel_by_username(username))
                
                if channel:
                    self.selected_channel = channel
                    self.root.after(0, self.ask_start_date)
                else:
                    self.root.after(0, lambda: messagebox.showerror("Ошибка", "Канал не найден!"))
                    self.root.after(0, self.show_main_screen)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка подключения:\n{str(e)}"))
                self.root.after(0, self.show_main_screen)
        
        threading.Thread(target=get_channel, daemon=True).start()


    def ask_start_date(self):
        """Запрос даты начала парсинга (с календарём вместо текста)"""
        self.clear_window()
        frame = ttk.Frame(self.root, padding="40")
        frame.pack(expand=True)

        channel_name = self.selected_channel.title if hasattr(self.selected_channel, 'title') else 'Канал'
        ttk.Label(frame, text=f"Канал: {channel_name}", font=('Arial', 14, 'bold')).pack(pady=20)
        ttk.Label(frame, text="С какой даты парсить канал?", font=('Arial', 12)).pack(pady=10)

        # DateEntry с ISO-форматом (YYYY-MM-DD) — удобно парсить
        self.date_entry = DateEntry(
            frame,
            width=18,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            date_pattern='yyyy-MM-dd',  # вернёт строку вида "2025-10-22"
            locale='ru_RU',
            maxdate=date.today()
        )
        self.date_entry.pack(pady=20)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text="Начать парсинг", command=self.start_parsing).pack(side='left', padx=10)
        ttk.Button(btn_frame, text="Парсить все посты", command=lambda: self.start_parsing(all_posts=True)).pack(side='left', padx=10)
        ttk.Button(btn_frame, text="Назад", command=self.show_main_screen).pack(side='left', padx=10)
        
    def start_parsing(self, all_posts=False):
        """Начало парсинга"""
        start_date = None

        if not all_posts:
            # DateEntry возвращает строку в формате yyyy-MM-dd (как выше), либо пустую
            date_str = self.date_entry.get().strip() if hasattr(self, 'date_entry') else ""
            if date_str:
                try:
                    # преобразуем в datetime (00:00:00), naive (без tzinfo)
                    start_date = datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    messagebox.showerror("Ошибка", "Неверный формат даты! Используйте ГГГГ-ММ-ДД")
                    return

        self.show_progress("Начинаем парсинг канала...")

        def parse():
            try:
                def update_progress(message):
                    self.root.after(0, lambda: self.update_progress_text(message))

                posts = self.loop.run_until_complete(
                    self.parser.parse_channel(self.selected_channel, start_date, update_progress)
                )

                channel_name = self.selected_channel.title if hasattr(self.selected_channel, 'title') else 'channel'
                safe_name = "".join(c for c in channel_name if c.isalnum() or c in (' ', '-', '_')).strip()
                filename = f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

                filepath = self.loop.run_until_complete(self.parser.save_to_json(posts, filename))

                self.root.after(0, lambda: self.show_results(len(posts), filepath))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Ошибка", f"Ошибка при парсинге:\n{str(e)}"))
                self.root.after(0, self.show_main_screen)

        threading.Thread(target=parse, daemon=True).start()
    
    def show_progress(self, message):
        """Показ экрана прогресса"""
        self.clear_window()
        
        frame = ttk.Frame(self.root, padding="40")
        frame.pack(expand=True)
        
        self.progress_label = ttk.Label(frame, text=message, font=('Arial', 12))
        self.progress_label.pack(pady=20)
        
        self.progress_bar = ttk.Progressbar(frame, mode='indeterminate', length=400)
        self.progress_bar.pack(pady=20)
        self.progress_bar.start(10)
    
    def update_progress_text(self, message):
        """Обновление текста прогресса"""
        if hasattr(self, 'progress_label'):
            self.progress_label.config(text=message)
    
    def show_results(self, posts_count, filepath):
        """Показ результатов парсинга"""
        self.clear_window()
        
        frame = ttk.Frame(self.root, padding="40")
        frame.pack(expand=True)
        
        ttk.Label(frame, text="✓ Парсинг завершен!", font=('Arial', 18, 'bold'), foreground='green').pack(pady=20)
        ttk.Label(frame, text=f"Собрано постов: {posts_count}", font=('Arial', 14)).pack(pady=10)
        ttk.Label(frame, text=f"Файл сохранен:", font=('Arial', 11)).pack(pady=5)
        ttk.Label(frame, text=filepath, font=('Arial', 9), foreground='blue').pack(pady=5)
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=30)
        
        ttk.Button(btn_frame, text="Открыть папку с файлом", width=25, command=lambda: self.open_folder(filepath)).pack(pady=10)
        ttk.Button(btn_frame, text="Спарсить другой канал", width=25, command=self.show_main_screen).pack(pady=10)
    
    def open_folder(self, filepath):
        """Открытие папки с файлом"""
        folder = os.path.dirname(filepath)
        
        try:
            # Для Windows
            if os.name == 'nt':
                os.startfile(folder)
            # Для macOS
            elif os.name == 'posix':
                subprocess.run(['open', folder])
            # Для Linux
            else:
                subprocess.run(['xdg-open', folder])
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть папку:\n{str(e)}")


def main():
    root = tk.Tk()
    app = TelegramParserApp(root)
    root.mainloop()


if __name__ == '__main__':

    main()
