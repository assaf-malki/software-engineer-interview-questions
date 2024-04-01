import configparser
import sqlite3
import sys

from PyQt5.QtCore import Qt, QUrl, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QDesktopServices, QCursor
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea, \
    QMainWindow, QFrame, \
    QCheckBox, QComboBox, QDialog, QProgressBar

from utils import fetch_and_save_questions, DATABASE_NAME


class DataFetcher(QThread):
    finished = pyqtSignal()  # Signal to emit when data fetching is done

    def __init__(self):
        super().__init__()

    def run(self):
        # Your data fetching logic here
        fetch_and_save_questions()
        self.finished.emit()


class LoadingDialog(QDialog):
    def __init__(self, parent=None):
        super(LoadingDialog, self).__init__(parent)

        # Set window flags to disable the close button and hide the question mark
        self.setWindowFlags(self.windowFlags() & ~(Qt.WindowCloseButtonHint | Qt.WindowContextHelpButtonHint))

        self.setModal(True)
        self.setWindowTitle("Loading Questions")
        layout = QVBoxLayout(self)

        self.spinner = QProgressBar(self)
        self.spinner.setRange(0, 0)  # Indeterminate mode
        self.spinner.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.spinner)


class QuestionCard(QFrame):
    def __init__(self, question, parent=None, main_window=None):
        super().__init__(parent)
        self.question = question
        self.main_window = main_window
        self.is_solved = question.get('solved', False)  # Assuming 'solved' is part of the question dictionary
        self.titleSlug = question['titleSlug']  # Make sure titleSlug is stored in the instance
        self.setObjectName("questionCard")
        self.setStyleSheet("#questionCard {"
                           "border: 1px solid lightgrey;"
                           "border-radius: 5px;"
                           "padding: 10px;"
                           "}")

        layout = QVBoxLayout(self)
        titleLayout = QHBoxLayout()

        # Title label with larger font and bold
        self.titleLabel = QLabel(question['title'], self)
        titleFont = QFont()
        titleFont.setBold(True)
        titleFont.setPointSize(12)  # You can adjust the size as needed
        self.titleLabel.setFont(titleFont)

        # Difficulty label with larger font
        self.difficultyLabel = QLabel(question['difficulty'], self)
        difficultyFont = QFont()
        difficultyFont.setPointSize(10)  # Adjust the size as needed
        self.difficultyLabel.setFont(difficultyFont)

        # Tags label with larger font
        self.tagsLabel = QLabel(', '.join(question['topicTags']), self)
        tagsFont = QFont()
        tagsFont.setPointSize(10)  # Adjust the size as needed
        self.tagsLabel.setFont(tagsFont)

        button_style = """
        QPushButton {
            background-color: #339DFF;
            color: white;
            border: none;
            padding: 5px 10px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 4px 2px;
            transition-duration: 0.4s;
            cursor: pointer;
            border-radius: 5px;
        }

        QPushButton:hover {
            background-color: #138cfb;
        }
        """

        self.solvedButton = QPushButton('Solved', self)
        self.solvedButton.clicked.connect(self.mark_as_solved)
        self.solvedButton.setStyleSheet(button_style)
        self.solvedButton.setCursor(QCursor(Qt.PointingHandCursor))

        self.viewButton = QPushButton('View in Browser', self)
        self.viewButton.setMinimumWidth(100)  # Adjust width as needed
        self.viewButton.clicked.connect(lambda: self.view_question(question['titleSlug']))
        self.viewButton.setStyleSheet(button_style)
        self.viewButton.setCursor(QCursor(Qt.PointingHandCursor))

        titleLayout.addWidget(self.titleLabel)
        titleLayout.addStretch()
        titleLayout.addWidget(self.solvedButton)
        titleLayout.addWidget(self.viewButton)

        layout.addLayout(titleLayout)
        layout.addWidget(self.difficultyLabel)
        layout.addWidget(self.tagsLabel)

        self.setLayout(layout)

        self.update_solved_button()

    def update_solved_button(self):
        if self.is_solved:
            self.solvedButton.setText('Unsolved')
            self.setStyleSheet("#questionCard {border: 1px solid green; border-radius: 5px; padding: 10px;}")
        else:
            self.solvedButton.setText('Solved')
            self.setStyleSheet("#questionCard {border: 1px solid lightgrey; border-radius: 5px; padding: 10px;}")

    def mark_as_solved(self):
        self.is_solved = not self.is_solved  # Toggle the solved state
        conn = sqlite3.connect(DATABASE_NAME)
        cur = conn.cursor()
        cur.execute('UPDATE questions SET solved = ? WHERE titleSlug = ?', (self.is_solved, self.titleSlug))
        conn.commit()
        conn.close()

        self.update_solved_button()

        if self.main_window:
            self.main_window.refresh_display()

    def view_question(self, titleSlug):
        url = f'https://leetcode.com/problems/{titleSlug}'
        QDesktopServices.openUrl(QUrl(url))


class MainWindow(QMainWindow):
    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path
        self.setWindowTitle('Software Engineer Interview Questions')

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.layout = QVBoxLayout()
        central_widget.setLayout(self.layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.layout.addWidget(self.scroll_area)

        self.cards_widget = QWidget()
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(10)
        self.cards_layout.setAlignment(Qt.AlignTop)
        self.cards_widget.setLayout(self.cards_layout)

        self.scroll_area.setWidget(self.cards_widget)

        filter_layout = QHBoxLayout()
        checkbox_layout = QHBoxLayout()  # Create a new layout for checkboxes
        checkbox_layout.setSpacing(10)  # Set the spacing to 0 or any value you prefer

        self.show_unsolved_checkbox = QCheckBox("Show only unsolved questions", self)
        checkbox_layout.addWidget(self.show_unsolved_checkbox, alignment=Qt.AlignLeft)

        self.load_on_start_checkbox = QCheckBox("Load questions at startup", self)
        self.load_on_start_checkbox.stateChanged.connect(self.save_settings)
        checkbox_layout.addWidget(self.load_on_start_checkbox, alignment=Qt.AlignLeft)

        # Create a container for your new checkbox layout
        checkbox_container = QWidget()
        checkbox_container.setLayout(checkbox_layout)

        # Add the checkbox container to the filter layout
        filter_layout.addWidget(checkbox_container, alignment=Qt.AlignLeft)

        # Number of questions label
        self.num_questions_label = QLabel("0 Questions")
        filter_layout.addWidget(self.num_questions_label, alignment=Qt.AlignCenter)
        num_questions_label_font = QFont()
        num_questions_label_font.setPointSize(12)
        self.num_questions_label.setFont(num_questions_label_font)

        # Dropdown for difficulty filter
        self.difficulty_filter = QComboBox(self)
        self.difficulty_filter.addItems(['All Questions', 'Hard', 'Medium'])
        self.difficulty_filter.setFixedWidth(100)  # Fix the width of the filter
        filter_layout.addWidget(self.difficulty_filter, alignment=Qt.AlignRight)

        # Adding margins to the filter layout
        filter_container = QWidget()
        filter_container_layout = QVBoxLayout()
        filter_container_layout.setContentsMargins(0, 5, 0, 5)  # Add top and bottom margins here
        filter_container_layout.addLayout(filter_layout)
        filter_container.setLayout(filter_container_layout)

        self.layout.addWidget(filter_container)

        self.show_unsolved_checkbox.stateChanged.connect(self.refresh_display)
        self.difficulty_filter.currentTextChanged.connect(self.refresh_display)

        navigation_layout = QHBoxLayout()

        # Style for buttons
        button_style = """
        QPushButton {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 5px 10px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            margin: 4px 2px;
            transition-duration: 0.4s;
            cursor: pointer;
            border-radius: 5px;
        }

        QPushButton:hover {
            background-color: #45a049;
        }
        """

        # Fixed width for buttons
        button_width = 100
        self.prev_button = QPushButton('Previous')
        self.prev_button.setStyleSheet(button_style)
        self.prev_button.setFixedWidth(button_width)
        self.prev_button.setCursor(QCursor(Qt.PointingHandCursor))

        self.next_button = QPushButton('Next')
        self.next_button.setStyleSheet(button_style)
        self.next_button.setFixedWidth(button_width)
        self.next_button.setCursor(QCursor(Qt.PointingHandCursor))

        self.page_label = QLabel('Page: <b>1</b>')
        page_label_font = QFont()
        page_label_font.setPointSize(14)
        self.page_label.setFont(page_label_font)

        navigation_layout.addWidget(self.prev_button, alignment=Qt.AlignLeft)
        navigation_layout.addWidget(self.page_label, alignment=Qt.AlignCenter)
        navigation_layout.addWidget(self.next_button, alignment=Qt.AlignRight)

        self.layout.addLayout(navigation_layout)

        self.prev_button.clicked.connect(self.load_previous_page)
        self.next_button.clicked.connect(self.load_next_page)

        config = configparser.ConfigParser()
        config.read('settings.ini')
        load_on_start = config.getboolean('Settings', 'load_on_start', fallback=True)
        self.load_on_start_checkbox.setChecked(load_on_start)

        if load_on_start:
            self.data_fetcher = DataFetcher()
            self.data_fetcher.finished.connect(self.on_data_fetched)
            self.data_fetcher.start()

            self.loading_dialog = LoadingDialog(self)
            self.loading_dialog.show()
        else:
            self.on_data_fetched()

    def calculate_total_pages(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM questions')
        total_questions = cur.fetchone()[0]
        conn.close()
        return (total_questions + self.questions_per_page - 1) // self.questions_per_page

    def display_questions(self, page_number):
        show_unsolved = self.show_unsolved_checkbox.isChecked()
        selected_difficulty = self.difficulty_filter.currentText()

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        offset = (page_number - 1) * self.questions_per_page

        base_query = 'SELECT title, difficulty, topicTags, titleSlug, solved FROM questions WHERE 1=1'
        count_query = 'SELECT COUNT(*) FROM questions WHERE 1=1'
        params = []

        if show_unsolved:
            base_query += ' AND solved = 0'
            count_query += ' AND solved = 0'

        if selected_difficulty != 'All Questions':
            base_query += ' AND difficulty = ?'
            count_query += ' AND difficulty = ?'
            params.append(selected_difficulty)

        # Execute count query to find the total number of questions based on the filters
        cur.execute(count_query, params)
        total_questions = cur.fetchone()[0]
        self.num_questions_label.setText(f"{total_questions} Questions")

        base_query += ' LIMIT ? OFFSET ?'
        params.extend([self.questions_per_page, offset])

        cur.execute(base_query, params)
        questions = [{'title': row[0], 'difficulty': row[1], 'topicTags': row[2].split(', '), 'titleSlug': row[3],
                      'solved': row[4]} for row in cur.fetchall()]
        conn.close()

        for i in reversed(range(self.cards_layout.count())):
            self.cards_layout.itemAt(i).widget().deleteLater()

        for question in questions:
            card = QuestionCard(question, parent=self, main_window=self)
            self.cards_layout.addWidget(card)

        self.page_label.setText(f"Page: <b>{page_number}</b>")
        self.scroll_area.verticalScrollBar().setValue(0)

    def refresh_display(self):
        self.current_page = 1
        self.total_pages = self.calculate_total_pages()
        self.display_questions(self.current_page)

    def load_previous_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.display_questions(self.current_page)

    def load_next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.display_questions(self.current_page)

    def on_data_fetched(self):

        self.current_page = 1
        self.questions_per_page = 20
        self.total_pages = self.calculate_total_pages()

        self.display_questions(self.current_page)
        if self.load_on_start_checkbox.isChecked():
            self.loading_dialog.accept()

    def save_settings(self):
        config = configparser.ConfigParser()
        config['Settings'] = {
            'load_on_start': self.load_on_start_checkbox.isChecked()
        }
        with open('settings.ini', 'w') as configfile:
            config.write(configfile)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    mainWindow = MainWindow(DATABASE_NAME)  # Replace with your actual database path
    mainWindow.showMaximized()
    sys.exit(app.exec_())
