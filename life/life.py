import sys
import pygame
import numpy as np
import time
import random
import hashlib
import sqlite3

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap


def main():
    app = QApplication(sys.argv)
    db_manager = DatabaseManager()
    login_window = LoginWindow(db_manager)
    login_window.show()
    sys.exit(app.exec_())


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
        "Label 1": (130, 130),
        "Label 2": (230, 130),
        "Label 3": (130, 230),
        "Label 4": (230, 230),
    }
    TOLERANCE = 20
    CORRECT_ORDER = ["Label 1", "Label 2", "Label 3", "Label 4"]
    IMAGE_FILES = {
        "Label 1": "1.png",
        "Label 2": "2.png",
        "Label 3": "3.png",
        "Label 4": "4.png",
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
                background-color: #2196F3;
                color: white;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """
        )
        self.check_button.clicked.connect(self.check_all_positions)

        self.instruction = QLabel(
            "Соберите квадрат в правильном порядке!\n"
            "Перетащите картинки на соответствующие позиции.",
            self,
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
            ("1", 140, 140),
            ("2", 240, 140),
            ("3", 140, 240),
            ("4", 240, 240)
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
                all_correct_position = False

        if all_correct_position:
            self.check_order()
        else:
            QMessageBox.warning(
                self,
                "Ошибка",
                "❌ Не все метки находятся на своих местах!"
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
                self,
                "Успех",
                "🎉 Капча пройдена успешно! 🎉"
            )
            self.captcha_passed.emit()
            self.close()
        else:
            QMessageBox.critical(
                self,
                "Ошибка",
                "❌ Картинки не в правильном порядке!"
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
            self.open_game()
        else:
            self.failed_attempts += 1
            if self.failed_attempts >= 3:
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    "Слишком много неудачных попыток! "
                    "Пройдите проверку безопасности.",
                )
                self.show_captcha()
            else:
                QMessageBox.warning(
                    self,
                    "Ошибка",
                    f"Неверный логин или пароль! "
                    f"Осталось попыток: {3 - self.failed_attempts}",
                )

    def show_captcha(self):
        self.captcha_window = CaptchaWindow()
        self.captcha_window.captcha_passed.connect(self.on_captcha_passed)
        self.captcha_window.captcha_failed.connect(self.on_captcha_failed)
        self.captcha_window.show()

    def on_captcha_passed(self):
        QMessageBox.information(
            self,
            "Успех",
            "Проверка пройдена! Попробуйте войти снова."
        )
        self.failed_attempts = 0

    def on_captcha_failed(self):
        QMessageBox.critical(
            self,
            "Ошибка",
            "Проверка не пройдена! Программа будет закрыта."
        )
        QApplication.quit()

    def open_game(self):
        self.game_window = GameWindow()
        self.game_window.show()
        self.close()


class GameOfLife:
    WIDTH = 800
    HEIGHT = 600
    CELL_SIZE = 10
    COLS = WIDTH // CELL_SIZE
    ROWS = HEIGHT // CELL_SIZE
    BLACK = (0, 0, 0)
    WHITE = (255, 255, 255)
    GRAY = (128, 128, 128)
    YELLOW = (255, 255, 0)

    def __init__(self):
        self.grid = np.zeros((self.ROWS, self.COLS))
        self.paused = False
        self.start_time = time.time()
        self.figure_spawned = False
        self.figure_spawn_interval = 15
        self.next_figure_time = self.figure_spawn_interval
        self.figure_appearing = False
        self.figure_appear_start = 0
        self.figure_appear_duration = 5
        self.figure_grid = None
        self.speed = 10
        self.show_grid = True

    def create_smiley(self):
        smiley_grid = np.zeros((self.ROWS, self.COLS))
        center_x, center_y = self.COLS // 2, self.ROWS // 2
        radius = min(self.COLS, self.ROWS) // 3
        for i in range(self.ROWS):
            for j in range(self.COLS):
                distance = np.sqrt((i - center_y) ** 2 + (j - center_x) ** 2)
                if distance <= radius:
                    smiley_grid[i, j] = 1
        inner_radius = radius * 0.8
        for i in range(self.ROWS):
            for j in range(self.COLS):
                distance = np.sqrt((i - center_y) ** 2 + (j - center_x) ** 2)
                if distance <= inner_radius:
                    smiley_grid[i, j] = 0
        eye_radius = radius // 5
        left_eye_x = center_x - radius // 3
        right_eye_x = center_x + radius // 3
        eyes_y = center_y - radius // 3
        for i in range(self.ROWS):
            for j in range(self.COLS):
                distance_left = np.sqrt(
                    (i - eyes_y) ** 2 + (j - left_eye_x) ** 2
                )
                if distance_left <= eye_radius:
                    smiley_grid[i, j] = 1
                distance_right = np.sqrt(
                    (i - eyes_y) ** 2 + (j - right_eye_x) ** 2
                )
                if distance_right <= eye_radius:
                    smiley_grid[i, j] = 1
        smile_radius = radius * 0.6
        smile_width = radius * 0.4
        for i in range(self.ROWS):
            for j in range(self.COLS):
                distance = np.sqrt(
                    (i - (center_y + radius // 4)) ** 2 + (j - center_x) ** 2
                )
                if (smile_radius - smile_width <= distance <= smile_radius
                        and i > center_y):
                    smiley_grid[i, j] = 1
        return smiley_grid

    def initialize_grid(self, pattern="random"):
        if pattern == "random":
            self.grid = np.random.choice(
                [0, 1],
                size=(self.ROWS, self.COLS),
                p=[0.9, 0.1]
            )

    def count_neighbors(self, grid, x, y):
        total = 0
        for i in range(-1, 2):
            for j in range(-1, 2):
                if i == 0 and j == 0:
                    continue
                x_edge = (x + i) % self.ROWS
                y_edge = (y + j) % self.COLS
                total += grid[x_edge, y_edge]
        return total

    def update(self):
        if self.paused:
            return
        current_time = time.time() - self.start_time
        if (not self.figure_appearing and
                not self.figure_spawned and
                current_time >= self.next_figure_time):
            self.figure_appearing = True
            self.figure_appear_start = time.time()
            self.figure_grid = self.create_smiley()
            self.next_figure_time = current_time + self.figure_spawn_interval
        if self.figure_appearing and not self.figure_spawned:
            elapsed = time.time() - self.figure_appear_start
            progress = min(elapsed / self.figure_appear_duration, 1.0)
            for i in range(self.ROWS):
                for j in range(self.COLS):
                    if (self.figure_grid[i, j] == 1 and
                            random.random() < progress):
                        self.grid[i, j] = 1
            if progress >= 1.0:
                self.figure_spawned = True
                self.figure_appearing = False
            return
        if (self.figure_spawned and
                current_time >= self.next_figure_time):
            self.figure_spawned = False
            self.figure_appearing = True
            self.figure_appear_start = time.time()
            self.figure_grid = self.create_smiley()
            self.next_figure_time = current_time + self.figure_spawn_interval
            return
        if not self.figure_appearing:
            new_grid = self.grid.copy()
            for i in range(self.ROWS):
                for j in range(self.COLS):
                    neighbors = self.count_neighbors(self.grid, i, j)
                    if self.grid[i, j] == 1:
                        if neighbors < 2 or neighbors > 3:
                            new_grid[i, j] = 0
                    else:
                        if neighbors == 3:
                            new_grid[i, j] = 1
            self.grid = new_grid

    def toggle_cell(self, x, y):
        grid_x, grid_y = y // self.CELL_SIZE, x // self.CELL_SIZE
        if 0 <= grid_x < self.ROWS and 0 <= grid_y < self.COLS:
            self.grid[grid_x, grid_y] = 1 - self.grid[grid_x, grid_y]

    def clear_grid(self):
        self.grid = np.zeros((self.ROWS, self.COLS))
        self.figure_spawned = False
        self.figure_appearing = False
        self.start_time = time.time()
        self.next_figure_time = self.figure_spawn_interval

    def change_speed(self, delta):
        self.speed = max(1, min(30, self.speed + delta))

    def toggle_grid(self):
        self.show_grid = not self.show_grid


class GameWindow(QWidget):
    def __init__(self):
        super().__init__()
        pygame.init()
        self.screen = pygame.display.set_mode(
            (GameOfLife.WIDTH, GameOfLife.HEIGHT)
        )
        pygame.display.set_caption("Game of Life")
        self.clock = pygame.time.Clock()
        self.game = GameOfLife()
        self.game.initialize_grid("random")
        self.font = pygame.font.SysFont("Arial", 16)
        self.small_font = pygame.font.SysFont("Arial", 12)
        self.running = True
        self.run_pygame_loop()

    def run_pygame_loop(self):
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        self.game.paused = not self.game.paused
                    elif event.key == pygame.K_r:
                        self.game.initialize_grid("random")
                        self.game.figure_spawned = False
                        self.game.figure_appearing = False
                        self.game.start_time = time.time()
                        self.game.next_figure_time = (
                            self.game.figure_spawn_interval
                        )
                    elif event.key == pygame.K_c:
                        self.game.clear_grid()
                    elif event.key == pygame.K_m:
                        self.game.figure_appearing = True
                        self.game.figure_appear_start = time.time()
                        self.game.figure_grid = self.game.create_smiley()
                        current_time = time.time() - self.game.start_time
                        self.game.next_figure_time = (
                            current_time + self.game.figure_spawn_interval
                        )
                    elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):
                        self.game.change_speed(2)
                    elif event.key == pygame.K_MINUS:
                        self.game.change_speed(-2)
                    elif event.key == pygame.K_h:
                        self.game.toggle_grid()
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        x, y = pygame.mouse.get_pos()
                        self.game.toggle_cell(x, y)
                    elif event.button == 4:
                        self.game.change_speed(1)
                    elif event.button == 5:
                        self.game.change_speed(-1)

            self.game.update()
            self.screen.fill(GameOfLife.BLACK)

            for i in range(self.game.ROWS):
                for j in range(self.game.COLS):
                    if self.game.grid[i, j] == 1:
                        if (self.game.figure_grid is not None and
                                i < self.game.figure_grid.shape[0] and
                                j < self.game.figure_grid.shape[1] and
                                self.game.figure_grid[i, j] == 1 and
                                (self.game.figure_appearing or
                                 self.game.figure_spawned)):
                            color = GameOfLife.YELLOW
                        else:
                            color = GameOfLife.WHITE
                        pygame.draw.rect(
                            self.screen,
                            color,
                            (j * self.game.CELL_SIZE,
                             i * self.game.CELL_SIZE,
                             self.game.CELL_SIZE,
                             self.game.CELL_SIZE),
                        )
                    if self.game.show_grid:
                        pygame.draw.rect(
                            self.screen,
                            GameOfLife.GRAY,
                            (j * self.game.CELL_SIZE,
                             i * self.game.CELL_SIZE,
                             self.game.CELL_SIZE,
                             self.game.CELL_SIZE),
                            1,
                        )

            status_lines = []
            if self.game.paused:
                status_lines.append("ПАУЗА")
            else:
                if self.game.figure_spawned:
                    status_lines.append("СМАЙЛИК ПОЯВИЛСЯ!")
                elif self.game.figure_appearing:
                    elapsed = time.time() - self.game.figure_appear_start
                    progress = min(elapsed / self.game.figure_appear_duration,
                                   1.0)
                    status_lines.append(
                        f"Появление смайлика: {int(progress * 100)}%"
                    )
                else:
                    current_time = time.time() - self.game.start_time
                    time_left = max(
                        0,
                        self.game.next_figure_time - current_time
                    )
                    status_lines.append(f"До смайлика: {int(time_left)}с")
            status_lines.append(f"Скорость: {self.game.speed} FPS")
            grid_status = "ВКЛ" if self.game.show_grid else "ВЫКЛ"
            status_lines.append(f"Сетка: {grid_status}")

            for i, line in enumerate(status_lines):
                text_surface = self.small_font.render(
                    line, True, GameOfLife.WHITE
                )
                self.screen.blit(text_surface, (10, 10 + i * 20))

            controls = [
                "Space: Пауза | R: Перезапуск | C: Очистить | M: Смайлик",
                "+/-: Скорость | H: Сетка | Колесо: Скорость",
            ]
            for i, line in enumerate(controls):
                text_surface = self.small_font.render(
                    line, True, GameOfLife.WHITE
                )
                self.screen.blit(
                    text_surface,
                    (10, GameOfLife.HEIGHT - 40 + i * 20)
                )

            pygame.display.flip()
            self.clock.tick(self.game.speed)

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    main()
