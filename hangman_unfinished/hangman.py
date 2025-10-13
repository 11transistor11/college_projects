import sys
import random
import sqlite3
import hashlib
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox
)
from PyQt5.QtGui import QPainter, QPen, QPixmap
from PyQt5.QtCore import Qt, pyqtSignal


class DatabaseManager:
    def __init__(self, db_name="users.db"):
        self.db_name = db_name
        self.create_database()

    def create_database(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()
        self.add_default_users()

    def add_default_users(self):
        users = [
            ("admin", "admin123"),
            ("user", "user123"),
            ("superuser", "super123"),
        ]
        for username, password in users:
            self.add_user(username, password)

    def hash_password(self, password):
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def add_user(self, username, password):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        password_hash = self.hash_password(password)
        try:
            cursor.execute(
                """
                INSERT INTO users (username, password_hash)
                VALUES (?, ?)
                """,
                (username, password_hash),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()

    def verify_user(self, username, password):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT password_hash FROM users WHERE username = ?
            """,
            (username,),
        )
        result = cursor.fetchone()
        conn.close()
        if result:
            stored_hash = result[0]
            return self.hash_password(password) == stored_hash
        return False


class DraggableLabel(QLabel):
    def __init__(self, image_path, name, parent=None):
        super().__init__(parent)
        self.name = name
        self.setFixedSize(100, 100)
        self.setStyleSheet(
            """
            QLabel {
                background-color: #4CAF50;
                border-radius: 5px;
                border: 2px solid #2E7D32;
            }
            QLabel:hover {
                background-color: #66BB6A;
                border: 2px solid #388E3C;
            }
            """
        )
        self.can_move = True
        self.correct_position = False
        pixmap = QPixmap(image_path)
        self.setPixmap(pixmap.scaled(self.size()))
        self.setAlignment(Qt.AlignCenter)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.can_move:
            self.offset = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.can_move:
            x = (event.globalX() - self.parent().x() - self.offset.x())
            y = (event.globalY() - self.parent().y() - self.offset.y())
            self.move(x, y)


class CaptchaWindow(QWidget):
    captcha_passed = pyqtSignal()
    captcha_failed = pyqtSignal()
    WIDTH = 600
    HEIGHT = 400
    TARGET_POS = {
        "Label 1": (130, 130), "Label 2": (230, 130),
        "Label 3": (130, 230), "Label 4": (230, 230),
    }
    TOLERANCE = 20
    CORRECT_ORDER = ["Label 1", "Label 2", "Label 3", "Label 4"]
    IMAGE_FILES = {
        "Label 1": "1.png", "Label 2": "2.png",
        "Label 3": "3.png", "Label 4": "4.png",
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Проверка безопасности")
        self.setGeometry(300, 300, self.WIDTH, self.HEIGHT)
        self.setStyleSheet("background-color: #f0f0f0;")
        self.labels = {}
        positions = [(50, 50), (50, 160), (160, 50), (160, 160)]
        for i, (x, y) in enumerate(positions, 1):
            label_name = f"Label {i}"
            image_path = self.IMAGE_FILES[label_name]
            label = DraggableLabel(image_path, label_name, self)
            label.move(x, y)
            self.labels[label_name] = label
        self.create_target_hints()
        self.check_button = QPushButton("Проверить", self)
        self.check_button.setGeometry(250, 350, 100, 40)
        self.check_button.setStyleSheet(
            """
            QPushButton {
                background-color: #2196F3; color: white;
                border-radius: 5px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
            """
        )
        self.check_button.clicked.connect(self.check_all_positions)
        self.instruction = QLabel(
            "Соберите квадрат в правильном порядке!\n"
            "Перетащите картинки на соответствующие позиции.", self
        )
        self.instruction.setGeometry(100, 10, 400, 40)
        self.instruction.setAlignment(Qt.AlignCenter)
        self.instruction.setStyleSheet("font-weight: bold;")

    def create_target_hints(self):
        for name, (x, y) in self.TARGET_POS.items():
            hint = QLabel(self)
            hint.setFixedSize(100, 100)
            hint.move(x, y)
            hint.setStyleSheet(
                "background-color: rgba(76, 175, 80, 0.2); "
                "border: 2px dashed rgba(46, 125, 50, 0.5);"
            )
            hint.lower()
        order_labels = [
            ("1", 140, 140), ("2", 240, 140),
            ("3", 140, 240), ("4", 240, 240)
        ]
        for text, x, y in order_labels:
            order_label = QLabel(text, self)
            order_label.setFixedSize(20, 20)
            order_label.move(x, y)
            order_label.setAlignment(Qt.AlignCenter)
            order_label.setStyleSheet(
                "background-color: rgba(255, 255, 255, 0.7); "
                "border-radius: 10px; font-weight: bold;"
            )
            order_label.lower()

    def check_all_positions(self):
        all_correct_position = True
        for name, label in self.labels.items():
            target_x, target_y = self.TARGET_POS[name]
            x, y = label.x(), label.y()
            if (abs(x - target_x) <= self.TOLERANCE and
                    abs(y - target_y) <= self.TOLERANCE):
                if not label.correct_position:
                    label.correct_position = True
                    label.setStyleSheet(
                        """
                        QLabel {
                            background-color: #2E7D32;
                            border-radius: 5px;
                            border: 2px solid #1B5E20;
                        }
                        """
                    )
            else:
                label.correct_position = False
                label.setStyleSheet(
                    """
                    QLabel {
                        background-color: #4CAF50; border-radius: 5px;
                        border: 2px solid #2E7D32;
                    }
                    QLabel:hover {
                        background-color: #66BB6A;
                        border: 2px solid #388E3C;
                    }
                    """
                )
                all_correct_position = False
        if all_correct_position:
            self.check_order()
        else:
            QMessageBox.warning(
                self, "Ошибка", "❌ Не все метки находятся на своих местах!"
            )

    def check_order(self):
        correct_order = True
        for i, correct_name in enumerate(self.CORRECT_ORDER):
            target_x, target_y = self.TARGET_POS[correct_name]
            found = False
            for name, label in self.labels.items():
                x, y = label.x(), label.y()
                if (abs(x - target_x) <= self.TOLERANCE and
                        abs(y - target_y) <= self.TOLERANCE):
                    if name != correct_name:
                        correct_order = False
                    found = True
                    break
            if not found or not correct_order:
                break
        if correct_order:
            QMessageBox.information(
                self, "Успех", "🎉 Капча пройдена успешно! 🎉"
            )
            self.captcha_passed.emit()
            self.close()
        else:
            QMessageBox.critical(
                self, "Ошибка", "❌ Картинки не в правильном порядке!"
            )
            self.captcha_failed.emit()
            self.close()


class LoginWindow(QMainWindow):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.failed_attempts = 0
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Авторизация")
        self.setFixedSize(400, 200)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        layout.setSpacing(15)
        login_label = QLabel("Логин:")
        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("Введите логин")
        self.login_input.setMinimumHeight(35)
        password_label = QLabel("Пароль:")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Введите пароль")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(35)
        self.login_button = QPushButton("Войти")
        self.login_button.setMinimumHeight(35)
        self.login_button.clicked.connect(self.login)
        layout.addWidget(login_label)
        layout.addWidget(self.login_input)
        layout.addWidget(password_label)
        layout.addWidget(self.password_input)
        layout.addWidget(self.login_button)
        central_widget.setLayout(layout)
        self.login_input.setFocus()

    def login(self):
        username = self.login_input.text().strip()
        password = self.password_input.text()
        if not username or not password:
            QMessageBox.warning(self, "Ошибка", "Заполните все поля!")
            return
        if self.db_manager.verify_user(username, password):
            QMessageBox.information(self, "Успех", "Вход выполнен!")
            self.failed_attempts = 0
            self.open_hangman_game()
        else:
            self.failed_attempts += 1
            if self.failed_attempts >= 3:
                message = (
                    "Слишком много неудачных попыток! "
                    "Пройдите проверку безопасности."
                )
                QMessageBox.warning(self, "Ошибка", message)
                self.show_captcha()
            else:
                message = (
                    f"Неверный логин или пароль! "
                    f"Осталось попыток: {3 - self.failed_attempts}"
                )
                QMessageBox.warning(self, "Ошибка", message)

    def show_captcha(self):
        self.captcha_window = CaptchaWindow()
        self.captcha_window.captcha_passed.connect(self.on_captcha_passed)
        self.captcha_window.captcha_failed.connect(self.on_captcha_failed)
        self.captcha_window.show()

    def on_captcha_passed(self):
        QMessageBox.information(
            self, "Успех", "Проверка пройдена! Попробуйте войти снова."
        )
        self.failed_attempts = 0

    def on_captcha_failed(self):
        QMessageBox.critical(
            self, "Ошибка", "Проверка не пройдена! Программа будет закрыта."
        )
        QApplication.quit()

    def open_hangman_game(self):
        self.hangman_window = HangmanGame()
        self.hangman_window.show()
        self.close()


class HangmanGame(QWidget):
    WORDS = [
        "ПИТОН", "ЯРОСЛАВ", "ЯБЛОКО", "ИСИП",
        "СОБАКА", "КОШКА", "ЧЕЛЯБИНСК", "КОПЕЙСК"
    ]
    MAX_WRONG_GUESSES = 6

    def __init__(self):
        super().__init__()
        self.secret_word = ""
        self.guessed_letters = set()
        self.wrong_guesses = 0
        self.display_word = []
        self.init_ui()
        self.new_game()

    def init_ui(self):
        self.setWindowTitle('Виселица')
        self.setFixedSize(400, 500)
        main_layout = QVBoxLayout()
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.word_label = QLabel()
        self.word_label.setAlignment(Qt.AlignCenter)
        self.word_label.setStyleSheet("font-size: 24px; letter-spacing: 4px;")
        self.guessed_label = QLabel("Уже названные буквы: ")
        self.guessed_label.setAlignment(Qt.AlignCenter)
        self.guessed_label.setWordWrap(True)
        input_layout = QHBoxLayout()
        self.input_letter = QLineEdit()
        self.input_letter.setMaxLength(1)
        self.guess_button = QPushButton("Угадать")
        input_layout.addWidget(self.input_letter)
        input_layout.addWidget(self.guess_button)
        self.new_game_button = QPushButton("Новая игра")
        main_layout.addWidget(self.image_label, 1)
        main_layout.addWidget(self.word_label)
        main_layout.addWidget(self.guessed_label)
        main_layout.addLayout(input_layout)
        main_layout.addWidget(self.new_game_button)
        self.setLayout(main_layout)
        self.guess_button.clicked.connect(self.guess_letter)
        self.new_game_button.clicked.connect(self.new_game)
        self.input_letter.returnPressed.connect(self.guess_button.click)

    def new_game(self):
        self.secret_word = random.choice(self.WORDS)
        self.guessed_letters = set()
        self.wrong_guesses = 0
        self.display_word = ['_'] * len(self.secret_word)
        self.input_letter.clear()
        self.input_letter.setEnabled(True)
        self.guess_button.setEnabled(True)
        self.update_display()

    def update_display(self):
        self.word_label.setText(' '.join(self.display_word))
        guessed_str = ", ".join(sorted(self.guessed_letters))
        self.guessed_label.setText(
            f"Уже названные буквы: {guessed_str}"
        )
        self.update_drawing()

    def guess_letter(self):
        letter = self.input_letter.text().upper()
        self.input_letter.clear()
        if not letter.isalpha() or len(letter) != 1:
            QMessageBox.warning(self, "Ошибка", "Введите одну букву.")
            return
        if letter in self.guessed_letters:
            QMessageBox.information(
                self, "Внимание", "Эта буква уже была названа."
            )
            return
        self.guessed_letters.add(letter)
        if letter in self.secret_word:
            for i, char in enumerate(self.secret_word):
                if char == letter:
                    self.display_word[i] = letter
        else:
            self.wrong_guesses += 1
        self.update_display()
        self.check_game_over()

    def check_game_over(self):
        if '_' not in self.display_word:
            self.end_game(True)
        elif self.wrong_guesses >= self.MAX_WRONG_GUESSES:
            self.end_game(False)

    def end_game(self, won):
        self.input_letter.setEnabled(False)
        self.guess_button.setEnabled(False)
        if won:
            QMessageBox.information(
                self, "Победа!", f"Слово: {self.secret_word}"
            )
        else:
            QMessageBox.information(
                self, "Поражение", f"Слово: {self.secret_word}"
            )

    def update_drawing(self):
        pixmap = QPixmap(300, 300)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        pen = QPen(Qt.black, 3, Qt.SolidLine)
        painter.setPen(pen)
        if self.wrong_guesses >= 0:
            painter.drawLine(50, 280, 250, 280)
            painter.drawLine(100, 280, 100, 50)
            painter.drawLine(100, 50, 200, 50)
            painter.drawLine(200, 50, 200, 80)
        if self.wrong_guesses >= 1:
            painter.drawEllipse(180, 80, 40, 40)
        if self.wrong_guesses >= 2:
            painter.drawLine(200, 120, 200, 200)
        if self.wrong_guesses >= 3:
            painter.drawLine(200, 140, 160, 180)
        if self.wrong_guesses >= 4:
            painter.drawLine(200, 140, 240, 180)
        if self.wrong_guesses >= 5:
            painter.drawLine(200, 200, 160, 240)
        if self.wrong_guesses >= 6:
            painter.drawLine(200, 200, 240, 240)
        painter.end()
        self.image_label.setPixmap(pixmap)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    db_manager = DatabaseManager()
    login_window = LoginWindow(db_manager)
    login_window.show()
    sys.exit(app.exec_())
