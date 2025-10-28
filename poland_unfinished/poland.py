import re
import sys
import hashlib
import sqlite3
from typing import List

import numpy as np
import matplotlib
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
)
from matplotlib.figure import Figure
import math

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QTextEdit,
    QGroupBox,
    QSplitter,
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap

matplotlib.use("Qt5Agg")


def main():
    app = QApplication(sys.argv)
    db = DatabaseManager()
    login = LoginWindow(db)
    login.show()
    sys.exit(app.exec_())


class PolishNotation:
    def __init__(self):
        self.operators = {
            "+": 1,
            "-": 1,
            "*": 2,
            "/": 2,
            "^": 3,
        }
        self.functions = {"sin", "cos", "tan", "log", "exp"}
        self.all_ops = set(self.operators.keys()) | self.functions

    def is_operator(self, token: str) -> bool:
        return token in self.operators

    def is_function(self, token: str) -> bool:
        return token in self.functions

    def is_variable(self, token: str) -> bool:
        return token.lower() == "x"

    def is_number(self, token: str) -> bool:
        try:
            float(token)
            return True
        except ValueError:
            return False

    def tokenize(self, expression: str) -> List[str]:
        expression = expression.replace(" ", "")
        pattern = r"""
            \d*\.?\d+
            |sin|cos|tan|log|exp
            |[a-zA-Z_][a-zA-Z0-9_]*
            |[+\-*/^()]
        """
        tokens = re.findall(pattern, expression, re.VERBOSE | re.IGNORECASE)
        return [token for token in tokens if token]

    def infix_to_prefix(self, expression: str) -> List[str]:
        tokens = self.tokenize(expression)
        if not tokens:
            raise ValueError("Пустое выражение")

        processed = []
        for i, token in enumerate(tokens):
            is_unary = (
                i == 0
                or tokens[i - 1] in "(["
                or tokens[i - 1] in self.all_ops
            )
            if token == "-" and is_unary:
                processed.append("0")
                processed.append("-")
            else:
                processed.append(token)
        tokens = processed

        output = []
        stack = []

        for token in reversed(tokens):
            if self.is_number(token) or self.is_variable(token):
                output.append(token)
            elif token == ")":
                stack.append(token)
            elif token == "(":
                while stack and stack[-1] != ")":
                    output.append(stack.pop())
                if stack and stack[-1] == ")":
                    stack.pop()
            elif self.is_function(token):
                stack.append(token)
            elif self.is_operator(token):
                while (
                    stack
                    and stack[-1] not in "()"
                    and stack[-1] not in self.functions
                    and (
                        self.operators.get(stack[-1], 0)
                        > self.operators[token]
                    )
                ):
                    output.append(stack.pop())
                stack.append(token)

        while stack:
            output.append(stack.pop())

        return list(reversed(output))

    def format_prefix(self, prefix_tokens: List[str]) -> str:
        return " ".join(prefix_tokens)

    def evaluate_prefix(self, prefix_tokens: List[str], x_value: float = 0) -> float:
        stack = []
        for token in reversed(prefix_tokens):
            if self.is_number(token):
                stack.append(float(token))
            elif self.is_variable(token):
                stack.append(x_value)
            elif self.is_function(token):
                if not stack:
                    msg = f"Недостаточно аргументов для функции {token}"
                    raise ValueError(msg)
                arg = stack.pop()
                try:
                    if token == "sin":
                        res = math.sin(arg)
                    elif token == "cos":
                        res = math.cos(arg)
                    elif token == "tan":
                        res = math.tan(arg)
                    elif token == "log":
                        if arg <= 0:
                            raise ValueError(
                                "log от неположительного числа"
                            )
                        res = math.log(arg)
                    elif token == "exp":
                        res = math.exp(arg)
                    else:
                        raise ValueError(f"Неизвестная функция: {token}")
                    stack.append(res)
                except (ValueError, OverflowError):
                    raise ValueError(f"Ошибка вычисления {token}({arg})")
            elif self.is_operator(token):
                if len(stack) < 2:
                    raise ValueError("Недостаточно операндов для оператора")
                a = stack.pop()
                b = stack.pop()
                if token == "+":
                    result = a + b
                elif token == "-":
                    result = a - b
                elif token == "*":
                    result = a * b
                elif token == "/":
                    if b == 0:
                        raise ValueError("Деление на ноль")
                    result = a / b
                elif token == "^":
                    try:
                        result = a ** b
                    except OverflowError:
                        msg = "Слишком большое значение при в степени"
                        raise ValueError(msg)
                else:
                    raise ValueError(f"Неизвестный оператор: {token}")
                stack.append(result)
            else:
                raise ValueError(f"Неизвестный токен: {token}")

        if len(stack) != 1:
            raise ValueError("Некорректное выражение")
        return stack[0]


class FunctionGraph(FigureCanvas):
    def __init__(self, parent=None, width=6, height=5, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)
        self.ax = self.fig.add_subplot(111)

    def plot_function(
        self,
        prefix_tokens,
        expression_str,
        x_range=(-10, 10),
        num_points=400,
    ):
        self.ax.clear()

        if not prefix_tokens:
            self.ax.text(
                0.5,
                0.5,
                "Введите функцию и нажмите Enter",
                ha="center",
                va="center",
                fontsize=12,
            )
            self.ax.set_title("График функции")
            self.ax.grid(True, alpha=0.3)
            self.draw()
            return

        try:
            x = np.linspace(x_range[0], x_range[1], num_points)
            y = []

            evaluator = PolishNotation()
            for x_val in x:
                try:
                    y_val = evaluator.evaluate_prefix(prefix_tokens, x_val)
                    y.append(y_val)
                except (ValueError, ZeroDivisionError, OverflowError):
                    y.append(np.nan)

            y = np.array(y)
            valid = ~np.isnan(y)

            if np.any(valid):
                self.ax.plot(
                    x[valid], y[valid], "b-", linewidth=2, label="f(x)"
                )

            self.ax.set_xlabel("x")
            self.ax.set_ylabel("f(x)")
            self.ax.set_title(f"График: f(x) = {expression_str}")
            self.ax.grid(True, alpha=0.3)
            self.ax.legend()
            self.fig.tight_layout()
            self.draw()

        except Exception as e:
            self.ax.text(
                0.5,
                0.5,
                f"Ошибка:\n{str(e)}",
                ha="center",
                va="center",
                fontsize=10,
                color="red",
            )
            self.ax.set_title("Ошибка построения графика")
            self.draw()


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
        users = [("admin", "admin123"), ("user", "user123")]
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
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
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
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        )
        result = cursor.fetchone()
        conn.close()
        if result:
            return self.hash_password(password) == result[0]
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
        self.setPixmap(pixmap.scaled(self.size(), Qt.KeepAspectRatio))
        self.setAlignment(Qt.AlignCenter)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.can_move:
            self.offset = event.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.can_move:
            x = event.globalX() - self.parent().x() - self.offset.x()
            y = event.globalY() - self.parent().y() - self.offset.y()
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
                background-color: #2196F3; color: white;
                border-radius: 5px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
        """
        )
        self.check_button.clicked.connect(self.check_all_positions)

        instruction_text = (
            "Соберите квадрат в правильном порядке!\n"
            "Перетащите картинки на соответствующие позиции."
        )
        self.instruction = QLabel(instruction_text, self)
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
            ("4", 240, 240),
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
        all_correct = True
        for name, label in self.labels.items():
            tx, ty = self.TARGET_POS[name]
            is_in_pos = (
                abs(label.x() - tx) <= self.TOLERANCE
                and abs(label.y() - ty) <= self.TOLERANCE
            )
            if is_in_pos:
                if not label.correct_position:
                    label.correct_position = True
                    label.setStyleSheet(
                        """
                        QLabel {
                            background-color: #2E7D32; border-radius: 5px;
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
                all_correct = False

        if all_correct:
            self.check_order()
        else:
            QMessageBox.warning(
                self, "Ошибка", "❌ Не все метки на своих местах!"
            )

    def check_order(self):
        correct = True
        for name in self.CORRECT_ORDER:
            tx, ty = self.TARGET_POS[name]
            placed = None
            for n, lbl in self.labels.items():
                is_in_pos = (
                    abs(lbl.x() - tx) <= self.TOLERANCE
                    and abs(lbl.y() - ty) <= self.TOLERANCE
                )
                if is_in_pos:
                    placed = n
                    break
            if placed != name:
                correct = False
                break

        if correct:
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
            self.open_calculator()
        else:
            self.failed_attempts += 1
            if self.failed_attempts >= 3:
                msg = (
                    "Слишком много неудачных попыток! "
                    "Пройдите проверку безопасности."
                )
                QMessageBox.warning(self, "Ошибка", msg)
                self.show_captcha()
            else:
                attempts_left = 3 - self.failed_attempts
                msg = (
                    f"Неверный логин или пароль! "
                    f"Осталось попыток: {attempts_left}"
                )
                QMessageBox.warning(self, "Ошибка", msg)

    def show_captcha(self):
        self.captcha_window = CaptchaWindow()
        self.captcha_window.captcha_passed.connect(self.on_captcha_passed)
        self.captcha_window.captcha_failed.connect(self.on_captcha_failed)
        self.captcha_window.show()

    def on_captcha_passed(self):
        msg = "Проверка пройдена! Попробуйте войти снова."
        QMessageBox.information(self, "Успех", msg)
        self.failed_attempts = 0

    def on_captcha_failed(self):
        msg = "Проверка не пройдена! Программа будет закрыта."
        QMessageBox.critical(self, "Ошибка", msg)
        QApplication.quit()

    def open_calculator(self):
        self.calc_window = PolishNotationCalculator()
        self.calc_window.show()
        self.close()


class PolishNotationCalculator(QMainWindow):
    def __init__(self):
        super().__init__()
        self.pn = PolishNotation()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Калькулятор с графиком функции")
        self.setGeometry(100, 100, 800, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)

        self.expression_input = QLineEdit()
        placeholder = (
            "Введите функцию, например: "
            "sin(x^2) и нажмите Enter"
        )
        self.expression_input.setPlaceholderText(placeholder)
        self.expression_input.setMinimumHeight(40)
        self.expression_input.returnPressed.connect(self.process_expression)

        input_layout.addWidget(QLabel("f(x) ="))
        input_layout.addWidget(self.expression_input)

        main_layout.addWidget(input_widget)

        splitter = QSplitter(Qt.Vertical)

        self.graph = FunctionGraph(self, width=7, height=5, dpi=100)
        splitter.addWidget(self.graph)

        prefix_group = QGroupBox("Польская нотация")
        prefix_layout = QVBoxLayout()
        self.prefix_output = QTextEdit()
        self.prefix_output.setReadOnly(True)
        self.prefix_output.setMaximumHeight(100)
        prefix_layout.addWidget(self.prefix_output)
        prefix_group.setLayout(prefix_layout)

        splitter.addWidget(prefix_group)
        splitter.setSizes([500, 100])
        main_layout.addWidget(splitter)

        self.clear_display()

    def process_expression(self):
        expr = self.expression_input.text().strip()
        if not expr:
            self.clear_display()
            return

        try:
            prefix_tokens = self.pn.infix_to_prefix(expr)
            prefix_str = self.pn.format_prefix(prefix_tokens)
            self.prefix_output.setText(prefix_str)
            self.graph.plot_function(prefix_tokens, expr, x_range=(-10, 10))
        except Exception as e:
            msg = f"Не удалось обработать выражение:\n{str(e)}"
            QMessageBox.critical(self, "Ошибка", msg)
            self.prefix_output.setText(f"Ошибка: {e}")
            self.graph.plot_function([], f"Ошибка в: {expr}")

    def clear_display(self):
        self.expression_input.clear()
        self.prefix_output.clear()
        self.graph.plot_function([], "")


if __name__ == "__main__":
    main()
