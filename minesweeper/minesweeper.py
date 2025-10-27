import sys
import hashlib
import sqlite3
import os
import random
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QGridLayout,
)
from PyQt5.QtCore import Qt, QTimer, QRectF, QPoint, pyqtSignal
from PyQt5.QtGui import QPainter, QColor, QFont, QKeyEvent, QPixmap


def main():
    app = QApplication(sys.argv)
    db_manager = DatabaseManager()
    login_window = LoginWindow(db_manager)
    login_window.show()
    sys.exit(app.exec_())


class DatabaseManager:
    def __init__(self, db_name='users.db'):
        self.db_name = db_name
        self.create_database()

    def create_database(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
        self.add_default_users()

    def add_default_users(self):
        users = [
            ("admin", "admin123"),
            ("user", "user123"),
            ("superuser", "super123")
        ]
        for username, password in users:
            self.add_user(username, password)

    def hash_password(self, password):
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def add_user(self, username, password):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        password_hash = self.hash_password(password)
        try:
            cursor.execute('''
                INSERT INTO users (username, password_hash)
                VALUES (?, ?)
            ''', (username, password_hash))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()

    def verify_user(self, username, password):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT password_hash FROM users WHERE username = ?
        ''', (username,))
        result = cursor.fetchone()
        conn.close()
        if not result:
            return False
        stored_hash = result[0]
        return self.hash_password(password) == stored_hash


class CaptchaConfig:
    TARGET_POS = {
        "Label 1": (100, 100),
        "Label 2": (200, 100),
        "Label 3": (100, 200),
        "Label 4": (200, 200)
    }

    CORRECT_ORDER = [
        "Label 1",
        "Label 2",
        "Label 3",
        "Label 4"
    ]

    TOLERANCE = 15


class DraggableLabel(QLabel):
    def __init__(self, image_path, text, parent=None):
        super().__init__(parent)
        self.setFixedSize(100, 100)
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            scaled_pixmap = pixmap.scaled(
                100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.setPixmap(scaled_pixmap)
        else:
            self.setText(text)
            self.setAlignment(Qt.AlignCenter)
            self.setStyleSheet("""
                QLabel {
                    background-color: #FF5722;
                    color: white;
                    border-radius: 5px;
                    font-weight: bold;
                    text-align: center;
                    border: 2px solid #D84315;
                }
            """)
            print(f"Предупреждение: файл {image_path} не найден")

        self.setStyleSheet("""
            QLabel {
                background-color: #4CAF50;
                border-radius: 5px;
                border: 2px solid #2E7D32;
            }
            QLabel:hover {
                background-color: #66BB6A;
                border: 2px solid #388E3C;
            }
        """)

        self.old_pos = None
        self.correct_position = False
        self.text = text

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()
            self.raise_()

    def mouseMoveEvent(self, event):
        if not self.old_pos:
            return
        delta = QPoint(event.globalPos() - self.old_pos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.old_pos = None


class CaptchaWindow(QWidget):
    captcha_passed = pyqtSignal()
    captcha_failed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.config = CaptchaConfig()
        self.setWindowTitle("Проверка безопасности")
        self.setGeometry(300, 300, 600, 400)
        self.setStyleSheet("background-color: #f0f0f0;")
        self.labels = {}
        positions = [
            (50, 50),
            (50, 160),
            (160, 50),
            (160, 160)
        ]
        image_files = {
            "Label 1": "1.png",
            "Label 2": "2.png",
            "Label 3": "3.png",
            "Label 4": "4.png"
        }

        for i, (x, y) in enumerate(positions, 1):
            label_name = f"Label {i}"
            image_path = image_files[label_name]
            label = DraggableLabel(image_path, label_name, self)
            label.move(x, y)
            self.labels[label_name] = label

        self.create_target_hints()
        self.check_button = QPushButton("Проверить", self)
        self.check_button.setGeometry(250, 350, 100, 40)
        self.check_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.check_button.clicked.connect(self.check_all_positions)

        self.instruction = QLabel(
            "Соберите квадрат в правильном порядке!\n"
            "Перетащите картинки на соответствующие позиции.",
            self
        )
        self.instruction.setGeometry(100, 10, 400, 40)
        self.instruction.setAlignment(Qt.AlignCenter)
        self.instruction.setStyleSheet("font-weight: bold;")

    def create_target_hints(self):
        for name, (x, y) in self.config.TARGET_POS.items():
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
            target_x, target_y = self.config.TARGET_POS[name]
            x, y = label.x(), label.y()
            if (abs(x - target_x) <= self.config.TOLERANCE
                    and abs(y - target_y) <= self.config.TOLERANCE):
                if not label.correct_position:
                    label.correct_position = True
                    label.setStyleSheet("""
                        QLabel {
                            background-color: #2E7D32;
                            border-radius: 5px;
                            border: 2px solid #1B5E20;
                        }
                    """)
            else:
                label.correct_position = False
                label.setStyleSheet("""
                    QLabel {
                        background-color: #4CAF50;
                        border-radius: 5px;
                        border: 2px solid #2E7D32;
                    }
                    QLabel:hover {
                        background-color: #66BB6A;
                        border: 2px solid #388E3C;
                    }
                """)
                all_correct_position = False

        if all_correct_position:
            self.check_order()
        else:
            QMessageBox.warning(
                self, "Ошибка",
                "❌ Не все метки находятся на своих местах!"
            )

    def check_order(self):
        correct_order = True

        for i, correct_name in enumerate(self.config.CORRECT_ORDER):
            target_x, target_y = self.config.TARGET_POS[correct_name]
            for name, label in self.labels.items():
                x, y = label.x(), label.y()
                if (abs(x - target_x) <= self.config.TOLERANCE
                        and abs(y - target_y) <= self.config.TOLERANCE):
                    if name != correct_name:
                        correct_order = False
                        break
            if not correct_order:
                break

        if correct_order:
            QMessageBox.information(
                self, "Успех",
                "🎉 Капча пройдена успешно! 🎉"
            )
            self.captcha_passed.emit()
            self.close()
        else:
            QMessageBox.critical(
                self, "Ошибка",
                "❌ Картинки не в правильном порядке!"
            )
            self.captcha_failed.emit()
            self.close()


# ========================
# 🧨 САПЁР
# ========================

class MinesweeperCell(QPushButton):
    reveal = pyqtSignal(int, int)
    flag = pyqtSignal(int, int)

    def __init__(self, row, col):
        super().__init__()
        self.row = row
        self.col = col
        self.setFixedSize(40, 40)
        self.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.setCheckable(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.reveal.emit(self.row, self.col)
        elif event.button() == Qt.RightButton:
            self.flag.emit(self.row, self.col)


class MinesweeperGame(QMainWindow):
    def __init__(self, player_name):
        super().__init__()
        self.player_name = player_name
        self.size = 9
        self.mines_count = 10
        self.board = [[0 for _ in range(self.size)] for _ in range(self.size)]
        self.revealed = [[False for _ in range(self.size)] for _ in range(self.size)]
        self.flagged = [[False for _ in range(self.size)] for _ in range(self.size)]
        self.game_over = False
        self.first_click = True
        self.initUI()
        self.init_game()

    def initUI(self):
        self.setWindowTitle(f'Сапёр — {self.player_name}')
        self.setFixedSize(400, 450)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()

        self.status_label = QLabel("Нажмите на любую клетку, чтобы начать")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(2)
        self.cells = []

        for r in range(self.size):
            row = []
            for c in range(self.size):
                cell = MinesweeperCell(r, c)
                cell.reveal.connect(self.on_reveal)
                cell.flag.connect(self.on_flag)
                self.grid_layout.addWidget(cell, r, c)
                row.append(cell)
            self.cells.append(row)

        self.grid_widget.setLayout(self.grid_layout)
        layout.addWidget(self.status_label)
        layout.addWidget(self.grid_widget)

        button_layout = QHBoxLayout()
        self.restart_button = QPushButton("Новая игра")
        self.menu_button = QPushButton("В меню")
        self.restart_button.clicked.connect(self.restart_game)
        self.menu_button.clicked.connect(self.return_to_menu)
        button_layout.addWidget(self.restart_button)
        button_layout.addWidget(self.menu_button)
        layout.addLayout(button_layout)

        central_widget.setLayout(layout)

    def init_game(self):
        self.board = [[0 for _ in range(self.size)] for _ in range(self.size)]
        self.revealed = [[False for _ in range(self.size)] for _ in range(self.size)]
        self.flagged = [[False for _ in range(self.size)] for _ in range(self.size)]
        self.game_over = False
        self.first_click = True
        self.update_display()

    def place_mines(self, exclude_row, exclude_col):
        mines_placed = 0
        while mines_placed < self.mines_count:
            r = random.randint(0, self.size - 1)
            c = random.randint(0, self.size - 1)
            if (r == exclude_row and c == exclude_col) or self.board[r][c] == -1:
                continue
            self.board[r][c] = -1
            mines_placed += 1

            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < self.size and 0 <= nc < self.size and self.board[nr][nc] != -1:
                        self.board[nr][nc] += 1

    def on_reveal(self, row, col):
        if self.game_over or self.flagged[row][col]:
            return
        if self.first_click:
            self.place_mines(row, col)
            self.first_click = False
            self.status_label.setText("Игра началась! Удачи!")

        if self.board[row][col] == -1:
            self.reveal_all_mines()
            self.status_label.setText("💥 Вы проиграли! Нажмите 'Новая игра'")
            self.game_over = True
            return

        self.flood_fill(row, col)
        self.update_display()
        if self.check_win():
            self.status_label.setText("🏆 Победа! Все мины обезврежены!")
            self.game_over = True

    def on_flag(self, row, col):
        if self.game_over or self.revealed[row][col]:
            return
        self.flagged[row][col] = not self.flagged[row][col]
        self.update_display()

    def flood_fill(self, row, col):
        if not (0 <= row < self.size and 0 <= col < self.size):
            return
        if self.revealed[row][col] or self.flagged[row][col]:
            return
        self.revealed[row][col] = True
        if self.board[row][col] == 0:
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    self.flood_fill(row + dr, col + dc)

    def reveal_all_mines(self):
        for r in range(self.size):
            for c in range(self.size):
                if self.board[r][c] == -1:
                    self.revealed[r][c] = True
        self.update_display()

    def check_win(self):
        for r in range(self.size):
            for c in range(self.size):
                if not self.revealed[r][c] and self.board[r][c] != -1:
                    return False
        return True

    def update_display(self):
        for r in range(self.size):
            for c in range(self.size):
                btn = self.cells[r][c]
                if self.revealed[r][c]:
                    if self.board[r][c] == -1:
                        btn.setText("💣")
                        btn.setStyleSheet("background-color: red; color: black;")
                    elif self.board[r][c] == 0:
                        btn.setText("")
                        btn.setStyleSheet("background-color: #d3d3d3;")
                    else:
                        colors = {1: "blue", 2: "green", 3: "red", 4: "purple", 5: "maroon", 6: "turquoise", 7: "black", 8: "gray"}
                        btn.setText(str(self.board[r][c]))
                        btn.setStyleSheet(f"color: {colors.get(self.board[r][c], 'black')}; background-color: #d3d3d3;")
                else:
                    if self.flagged[r][c]:
                        btn.setText("🚩")
                        btn.setStyleSheet("color: red;")
                    else:
                        btn.setText("")
                        btn.setStyleSheet("")

    def restart_game(self):
        self.init_game()
        self.status_label.setText("Нажмите на любую клетку, чтобы начать")

    def return_to_menu(self):
        self.names_window = NamesWindow()
        self.names_window.show()
        self.close()


# ========================
# PING-PONG (оставлен без изменений)
# ========================

class PingPongGame(QMainWindow):
    def __init__(self, name1, name2):
        super().__init__()
        self.name1 = name1
        self.name2 = name2
        self.score1 = 0
        self.score2 = 0
        self.initUI()
        self.initGame()

    def initUI(self):
        self.setWindowTitle('Ping Pong Game')
        self.setFixedSize(800, 600)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()

        score_layout = QHBoxLayout()
        self.score_label1 = QLabel(f'{self.name1}: 0')
        self.score_label2 = QLabel(f'{self.name2}: 0')
        self.score_label1.setAlignment(Qt.AlignCenter)
        self.score_label2.setAlignment(Qt.AlignCenter)
        self.score_label1.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: blue;"
        )
        self.score_label2.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: red;"
        )
        score_layout.addWidget(self.score_label1)
        label_vs = QLabel('VS')
        label_vs.setAlignment(Qt.AlignCenter)
        score_layout.addWidget(label_vs)
        score_layout.addWidget(self.score_label2)

        self.game_canvas = PingPongCanvas(self.name1, self.name2)
        self.game_canvas.score_updated.connect(self.update_score)
        self.game_canvas.game_over.connect(self.handle_game_over)

        controls_label = QLabel(
            'Управление: W/S - левый игрок, ↑/↓ - правый игрок, '
            'Space - пауза, R - рестарт'
        )
        controls_label.setAlignment(Qt.AlignCenter)
        controls_label.setStyleSheet("font-size: 12px; color: gray;")

        buttons_layout = QHBoxLayout()
        self.pause_button = QPushButton('Пауза')
        self.restart_button = QPushButton('Рестарт')
        self.menu_button = QPushButton('В меню')
        self.pause_button.clicked.connect(self.game_canvas.toggle_pause)
        self.restart_button.clicked.connect(self.restart_game)
        self.menu_button.clicked.connect(self.return_to_menu)
        buttons_layout.addWidget(self.pause_button)
        buttons_layout.addWidget(self.restart_button)
        buttons_layout.addWidget(self.menu_button)

        layout.addLayout(score_layout)
        layout.addWidget(self.game_canvas)
        layout.addWidget(controls_label)
        layout.addLayout(buttons_layout)
        central_widget.setLayout(layout)

    def initGame(self):
        self.updateDisplay()

    def update_score(self, player1_score, player2_score):
        self.score1 = player1_score
        self.score2 = player2_score
        self.updateDisplay()

    def updateDisplay(self):
        self.score_label1.setText(f'{self.name1}: {self.score1}')
        self.score_label2.setText(f'{self.name2}: {self.score2}')

    def handle_game_over(self, winner_name):
        QMessageBox.information(
            self, 'Конец игры', f'Победил: {winner_name}'
        )
        self.pause_button.setEnabled(False)
        self.restart_button.setEnabled(True)

    def restart_game(self):
        self.score1 = 0
        self.score2 = 0
        self.updateDisplay()
        self.game_canvas.restart_game()
        self.pause_button.setEnabled(True)

    def return_to_menu(self):
        self.names_window = NamesWindow()
        self.names_window.show()
        self.close()


class PingPongCanvas(QWidget):
    score_updated = pyqtSignal(int, int)
    game_over = pyqtSignal(str)

    def __init__(self, name1, name2):
        super().__init__()
        self.name1 = name1
        self.name2 = name2
        self.setFixedSize(800, 400)
        self.setFocusPolicy(Qt.StrongFocus)

        self.paddle_width = 15
        self.paddle_height = 100
        self.ball_size = 15
        self.paddle_speed = 8
        self.ball_speed_x = 6
        self.ball_speed_y = 6

        self.initGame()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_game)
        self.timer.start(16)
        self.paused = False
        self.keys_pressed = set()
        self.game_active = True

    def initGame(self):
        self.player1_y = 150
        self.player2_y = 150
        self.ball_x = 400
        self.ball_y = 200
        self.ball_dx = self.ball_speed_x
        self.ball_dy = self.ball_speed_y
        self.player1_score = 0
        self.player2_score = 0
        self.game_active = True

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(0, 0, self.width(), self.height(), QColor(0, 0, 0))
        painter.setPen(QColor(255, 255, 255))

        for i in range(0, self.height(), 20):
            painter.drawRect(self.width() // 2 - 1, i, 2, 10)

        painter.fillRect(
            20,
            int(self.player1_y),
            self.paddle_width,
            self.paddle_height,
            QColor(0, 100, 255)
        )
        painter.fillRect(
            self.width() - 20 - self.paddle_width,
            int(self.player2_y),
            self.paddle_width,
            self.paddle_height,
            QColor(255, 100, 100)
        )

        ball_rect = QRectF(
            int(self.ball_x - self.ball_size // 2),
            int(self.ball_y - self.ball_size // 2),
            self.ball_size,
            self.ball_size
        )
        painter.fillRect(ball_rect, QColor(255, 255, 255))

        if self.paused:
            painter.setFont(QFont('Arial', 40))
            painter.drawText(
                self.width() // 2 - 100,
                self.height() // 2,
                "ПАУЗА"
            )

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        self.keys_pressed.add(key)
        if key == Qt.Key_Space:
            self.toggle_pause()
        elif key == Qt.Key_R:
            self.restart_game()
        self.update()

    def keyReleaseEvent(self, event: QKeyEvent):
        key = event.key()
        if key in self.keys_pressed:
            self.keys_pressed.remove(key)

    def update_game(self):
        if self.paused or not self.game_active:
            return

        if Qt.Key_W in self.keys_pressed:
            self.player1_y = max(0, self.player1_y - self.paddle_speed)
        if Qt.Key_S in self.keys_pressed:
            self.player1_y = min(
                self.height() - self.paddle_height,
                self.player1_y + self.paddle_speed
            )
        if Qt.Key_Up in self.keys_pressed:
            self.player2_y = max(0, self.player2_y - self.paddle_speed)
        if Qt.Key_Down in self.keys_pressed:
            self.player2_y = min(
                self.height() - self.paddle_height,
                self.player2_y + self.paddle_speed
            )

        self.ball_x += self.ball_dx
        self.ball_y += self.ball_dy

        if self.ball_y <= 0 or self.ball_y >= self.height():
            self.ball_dy = -self.ball_dy

        if (self.ball_x <= 20 + self.paddle_width
                and self.ball_y >= self.player1_y
                and self.ball_y <= self.player1_y + self.paddle_height):
            self.ball_dx = abs(self.ball_dx)
            hit_pos = (self.ball_y - self.player1_y) / self.paddle_height
            self.ball_dy = 6 * (hit_pos - 0.5)

        if (self.ball_x >= (self.width() - 20 - self.paddle_width
                            - self.ball_size)
                and self.ball_y >= self.player2_y
                and self.ball_y <= self.player2_y + self.paddle_height):
            self.ball_dx = -abs(self.ball_dx)
            hit_pos = (self.ball_y - self.player2_y) / self.paddle_height
            self.ball_dy = 6 * (hit_pos - 0.5)

        if self.ball_x < 0:
            self.player2_score += 1
            self.score_updated.emit(self.player1_score, self.player2_score)
            self.reset_ball()
            if self.player2_score >= 5:
                self.game_active = False
                self.game_over.emit(self.name2)
        elif self.ball_x > self.width():
            self.player1_score += 1
            self.score_updated.emit(self.player1_score, self.player2_score)
            self.reset_ball()
            if self.player1_score >= 5:
                self.game_active = False
                self.game_over.emit(self.name1)

        self.update()

    def reset_ball(self):
        self.ball_x = self.width() // 2
        self.ball_y = self.height() // 2
        self.ball_dx = (-self.ball_speed_x
                        if self.ball_dx > 0 else self.ball_speed_x)
        self.ball_dy = self.ball_speed_y * (1 if self.ball_dy > 0 else -1)

    def toggle_pause(self):
        if self.game_active:
            self.paused = not self.paused
            self.update()

    def restart_game(self):
        self.initGame()
        self.score_updated.emit(self.player1_score, self.player2_score)
        self.paused = False
        self.keys_pressed.clear()
        self.update()


# ========================
# NAMES WINDOW (обновлён)
# ========================

class NamesWindow(QMainWindow):
    def __init__(self, login_window=None):
        super().__init__()
        self.login_window = login_window
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Выбор игры')
        self.setFixedSize(400, 300)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        layout.setSpacing(15)

        help_label = QLabel('Не забудьте поменять раскладку на английскую!')
        layout.addWidget(help_label)

        title_label = QLabel('Введите имя:')
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('Ваше имя')
        self.name_input.setMinimumHeight(35)
        self.name_input.setText('Игрок')

        self.minesweeper_button = QPushButton('Играть в Сапёр')
        self.minesweeper_button.setMinimumHeight(40)
        self.minesweeper_button.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.minesweeper_button.clicked.connect(self.start_minesweeper)

        self.ping_pong_button = QPushButton('Играть в Пинг-Понг')
        self.ping_pong_button.setMinimumHeight(40)
        self.ping_pong_button.setStyleSheet("font-size: 14px; font-weight: bold;")
        self.ping_pong_button.clicked.connect(self.start_ping_pong)

        self.logout_button = QPushButton('Выйти')
        self.logout_button.setMinimumHeight(35)
        self.logout_button.setStyleSheet(
            "font-size: 12px; background-color: #FF5722; color: white;"
        )
        self.logout_button.clicked.connect(self.logout)

        layout.addWidget(title_label)
        layout.addWidget(self.name_input)
        layout.addWidget(self.minesweeper_button)
        layout.addWidget(self.ping_pong_button)
        layout.addWidget(self.logout_button)

        central_widget.setLayout(layout)
        self.name_input.setFocus()

    def start_minesweeper(self):
        name = self.name_input.text().strip()
        if not name:
            name = "Игрок"
        self.minesweeper_window = MinesweeperGame(name)
        self.minesweeper_window.show()
        self.close()

    def start_ping_pong(self):
        name1 = self.name_input.text().strip()
        if not name1:
            name1 = "Игрок 1"
        name2 = "Компьютер"  # или можно запросить второе имя, но для упрощения — так
        self.ping_pong_window = PingPongGame(name1, name2)
        self.ping_pong_window.show()
        self.close()

    def logout(self):
        reply = QMessageBox.question(
            self, 'Подтверждение выхода',
            'Вы уверены, что хотите выйти?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self.login_window:
                self.login_window.show()
            else:
                db_manager = DatabaseManager()
                login_window = LoginWindow(db_manager)
                login_window.show()
            self.close()


# ========================
# LOGIN WINDOW (без изменений)
# ========================

class LoginWindow(QMainWindow):
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
        self.failed_attempts = 0
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Авторизация')
        self.setFixedSize(400, 200)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        layout.setSpacing(15)

        login_label = QLabel('Логин:')
        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText('Введите логин')
        self.login_input.setMinimumHeight(35)

        password_label = QLabel('Пароль:')
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText('Введите пароль')
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setMinimumHeight(35)

        self.login_button = QPushButton('Войти')
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
            QMessageBox.warning(self, 'Ошибка', 'Заполните все поля!')
            return

        if self.db_manager.verify_user(username, password):
            QMessageBox.information(self, 'Успех', 'Вход выполнен!')
            self.failed_attempts = 0
            self.open_names_window()
            return

        self.failed_attempts += 1
        if self.failed_attempts >= 3:
            QMessageBox.warning(
                self, 'Ошибка',
                'Слишком много неудачных попыток! '
                'Пройдите капчу.'
            )
            self.show_captcha()
        else:
            QMessageBox.warning(
                self, 'Ошибка',
                f'Неверный логин или пароль! '
                f'Осталось попыток: {3 - self.failed_attempts}'
            )

    def show_captcha(self):
        self.captcha_window = CaptchaWindow()
        self.captcha_window.captcha_passed.connect(self.on_captcha_passed)
        self.captcha_window.captcha_failed.connect(self.on_captcha_failed)
        self.captcha_window.show()

    def on_captcha_passed(self):
        QMessageBox.information(
            self, 'Успех',
            'Проверка пройдена! Попробуйте войти снова.'
        )
        self.failed_attempts = 0

    def on_captcha_failed(self):
        QMessageBox.critical(
            self, 'Ошибка',
            'Проверка не пройдена! Программа будет закрыта.'
        )
        QApplication.quit()

    def open_names_window(self):
        self.names_window = NamesWindow(login_window=self)
        self.names_window.show()
        self.close()


if __name__ == '__main__':
    main()
