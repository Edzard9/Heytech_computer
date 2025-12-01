import sys
import os
import mysql.connector
from mysql.connector import Error
from datetime import datetime, date

# --- PERUBAHAN 1: Menambahkan import untuk pengaturan ukuran kertas custom ---
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QStackedWidget, QFrame, QTableWidget, 
    QTableWidgetItem, QHeaderView, QFormLayout, QLineEdit, QComboBox, 
    QMessageBox, QButtonGroup, QSpinBox, QDateEdit, QTextEdit,
    QDialog, QGroupBox, QGridLayout, QFileDialog, QCheckBox,
    QDialogButtonBox, QTextBrowser, QListWidget, QListWidgetItem, QSplitter
)
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog
from PyQt5.QtCore import Qt, QDate, pyqtSignal, QSizeF, QMarginsF
from PyQt5.QtGui import QFont, QPixmap, QPainter, QImage, QPageSize, QPageLayout
# ---------------------------------------------------------------------------

import qrcode
from PIL import Image
import cv2
import numpy as np
from pyzbar.pyzbar import decode
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from win10toast import ToastNotifier

# Buat folder untuk QR codes dan bukti pembayaran
os.makedirs("qr_codes", exist_ok=True)
os.makedirs("bukti_pembayaran", exist_ok=True)

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.connect()
    
    def connect(self):
        try:
            self.connection = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='toko_komputer'
            )
            if self.connection.is_connected():
                print("Berhasil terhubung ke database MySQL")
        except Error as e:
            print(f"Error: {e}")
            QMessageBox.critical(None, "Database Error", 
                               f"Tidak dapat terhubung ke database:\n{str(e)}")
    
    def execute_query(self, query, params=None):
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, params or ())
            
            if query.strip().upper().startswith('SELECT'):
                result = cursor.fetchall()
            else:
                self.connection.commit()
                result = cursor.lastrowid
            
            cursor.close()
            return result
        except Error as e:
            print(f"Database error: {e}")
            return None
    
    def close(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()

class PaymentDialog(QDialog):
    def __init__(self, total_amount, parent=None):
        super().__init__(parent)
        self.total_amount = total_amount
        self.bukti_path = None
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Pembayaran")
        self.setFixedSize(500, 600)
        
        layout = QVBoxLayout(self)
        
        # Info Total
        total_frame = QFrame()
        total_frame.setStyleSheet("background-color: #f8f9fa; border: 2px solid #dee2e6; border-radius: 8px; padding: 15px;")
        total_layout = QVBoxLayout(total_frame)
        total_layout.addWidget(QLabel("TOTAL PEMBAYARAN"))
        total_label = QLabel(f"Rp {self.total_amount:,}")
        total_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #28a745;")
        total_layout.addWidget(total_label)
        layout.addWidget(total_frame)
        
        # Form Pembayaran
        form_frame = QFrame()
        form_layout = QFormLayout(form_frame)
        
        # Metode Pembayaran
        self.combo_metode = QComboBox()
        self.combo_metode.addItems(["Cash", "Transfer Bank", "QRIS"])
        self.combo_metode.currentTextChanged.connect(self.on_metode_changed)
        
        # Admin
        self.input_admin = QLineEdit("Tony")  # Default admin
        self.input_admin.setPlaceholderText("Nama admin yang melayani")
        
        # Bukti Pembayaran
        self.btn_upload_bukti = QPushButton("📎 Upload Bukti Pembayaran")
        self.btn_upload_bukti.setStyleSheet("background-color: #17a2b8; color: white; padding: 8px;")
        self.btn_upload_bukti.clicked.connect(self.upload_bukti)
        
        self.label_bukti = QLabel("Belum ada bukti diupload")
        self.label_bukti.setStyleSheet("color: #6c757d; font-style: italic;")
        
        # Info tambahan untuk transfer/QRIS
        self.info_frame = QFrame()
        self.info_frame.setVisible(False)
        self.info_layout = QVBoxLayout(self.info_frame)
        self.info_layout.addWidget(QLabel("💡 Informasi:"))
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #856404; background-color: #fff3cd; padding: 10px; border-radius: 4px;")
        self.info_layout.addWidget(self.info_label)
        
        form_layout.addRow("Metode Pembayaran:", self.combo_metode)
        form_layout.addRow("Admin:", self.input_admin)
        form_layout.addRow("Bukti:", self.btn_upload_bukti)
        form_layout.addRow("", self.label_bukti)
        
        layout.addWidget(form_frame)
        layout.addWidget(self.info_frame)
        
        # Tombol
        button_layout = QHBoxLayout()
        btn_proses = QPushButton("✅ Proses Pembayaran")
        btn_proses.setStyleSheet("background-color: #28a745; color: white; padding: 10px; font-weight: bold;")
        btn_proses.clicked.connect(self.accept)
        
        btn_batal = QPushButton("❌ Batal")
        btn_batal.setStyleSheet("background-color: #dc3545; color: white; padding: 10px;")
        btn_batal.clicked.connect(self.reject)
        
        button_layout.addWidget(btn_batal)
        button_layout.addWidget(btn_proses)
        layout.addLayout(button_layout)
        
    def on_metode_changed(self, metode):
        if metode == "Transfer Bank":
            self.info_label.setText("Transfer ke: BCA 123-456-7890 a.n Haytech Store\nUpload bukti transfer setelah pembayaran.")
            self.info_frame.setVisible(True)
        elif metode == "QRIS":
            self.info_label.setText("Scan QRIS yang tersedia di kasir.\nUpload screenshot bukti pembayaran.")
            self.info_frame.setVisible(True)
        else:
            self.info_frame.setVisible(False)
            
    def upload_bukti(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Pilih Bukti Pembayaran", "",
            "Image Files (*.png *.jpg *.jpeg *.pdf)"
        )
        if file_path:
            self.bukti_path = file_path
            self.label_bukti.setText(f"File: {os.path.basename(file_path)}")
            self.label_bukti.setStyleSheet("color: #28a745; font-weight: bold;")
    
    def get_payment_data(self):
        return {
            'metode': self.combo_metode.currentText(),
            'admin': self.input_admin.text().strip(),
            'bukti_path': self.bukti_path
        }

class PrintReceiptDialog(QDialog):
    def __init__(self, transaksi_data, parent=None):
        super().__init__(parent)
        self.transaksi_data = transaksi_data
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Cetak Struk")
        self.setFixedSize(400, 700)
        
        layout = QVBoxLayout(self)
        
        # Preview Struk
        self.preview = QTextBrowser()
        self.preview.setStyleSheet("""
            font-family: 'Courier New', monospace; 
            font-size: 9px;
            background-color: white;
            border: 1px solid #ccc;
            padding: 5px;
        """)
        self.preview.setFixedWidth(320)
        self.generate_receipt_preview()
        
        # Tombol
        button_layout = QHBoxLayout()
        btn_print = QPushButton("🖨️ Print")
        btn_print.setStyleSheet("background-color: #007bff; color: white; padding: 8px;")
        btn_print.clicked.connect(self.print_receipt)
        
        btn_save = QPushButton("💾 Simpan PDF")
        btn_save.setStyleSheet("background-color: #28a745; color: white; padding: 8px;")
        btn_save.clicked.connect(self.save_as_pdf)
        
        btn_close = QPushButton("Tutup")
        btn_close.setStyleSheet("background-color: #6c757d; color: white; padding: 8px;")
        btn_close.clicked.connect(self.close)
        
        button_layout.addWidget(btn_print)
        button_layout.addWidget(btn_save)
        button_layout.addWidget(btn_close)
        
        layout.addWidget(self.preview, alignment=Qt.AlignCenter)
        layout.addLayout(button_layout)
        
    def generate_receipt_preview(self):
        """Generate struk dengan format 80mm (32 karakter per baris)"""
        receipt = []
        
        # Header
        receipt.append("=" * 32)
        receipt.append("      HAYTECH STORE".center(32))
        receipt.append("  Toko Komputer Terpercaya".center(32))
        receipt.append("=" * 32)
        
        # Info Transaksi
        receipt.append(f"ID Trans : {self.transaksi_data['id']}")
        receipt.append(f"Tanggal  : {self.transaksi_data['tanggal']}")
        receipt.append(f"Admin    : {self.transaksi_data['admin'][:12]}")
        receipt.append(f"Customer : {self.transaksi_data['pembeli'][:12]}")
        receipt.append(f"Bayar    : {self.transaksi_data['metode_bayar']}")
        receipt.append("-" * 32)
        
        # Header Item
        receipt.append("ITEM              QTY   SUBTOTAL")
        receipt.append("-" * 32)
        
        # Items
        for item in self.transaksi_data['items']:
            # Format nama barang (maks 15 karakter)
            nama = item['nama']
            if len(nama) > 15:
                nama = nama[:12] + "..."
            
            # Format baris item
            qty_str = f"{item['qty']:>2}"
            subtotal_str = f"Rp{item['subtotal']:,}"
            
            item_line = f"{nama:<15} {qty_str:>3} {subtotal_str:>11}"
            receipt.append(item_line)
        
        receipt.append("-" * 32)
        
        # Total
        total_str = f"Rp{self.transaksi_data['total']:,}"
        receipt.append(f"TOTAL      : {total_str:>16}")
        receipt.append(f"BAYAR      : {total_str:>16}")
        receipt.append(f"KEMBALI    : {'Rp0':>16}")
        receipt.append("=" * 32)
        
        # Footer
        receipt.append("   TERIMA KASIH ATAS".center(32))
        receipt.append("   KUNJUNGAN ANDA".center(32))
        receipt.append("=" * 32)
        receipt.append("*Barang yg sudah dibeli")
        receipt.append(" tdk dpt ditukar/dikembalikan")
        receipt.append("*Struk sbg bukti pembayaran")
        receipt.append(" yang sah")
        
        receipt_text = "\n".join(receipt)
        self.preview.setPlainText(receipt_text)
    
    def print_receipt(self):
        """Print struk dengan ukuran 80mm"""
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, self)
        
        if dialog.exec_() == QPrintDialog.Accepted:
            try:
                painter = QPainter()
                painter.begin(printer)
                
                # Font untuk struk thermal
                font = QFont("Courier New", 8)
                painter.setFont(font)
                
                # Render teks struk
                lines = self.preview.toPlainText().split('\n')
                y_pos = 100
                
                for line in lines:
                    painter.drawText(50, y_pos, line)
                    y_pos += 20
                    
                painter.end()
                
                QMessageBox.information(self, "Sukses", "Struk berhasil dicetak!")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Gagal mencetak: {str(e)}")
    
    def save_as_pdf(self):
        """Simpan struk sebagai PDF menggunakan reportlab dengan ukuran A4"""
        default_filename = f"struk_{self.transaksi_data['id']}.pdf"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Simpan Struk sebagai PDF", 
            default_filename,
            "PDF Files (*.pdf)"
        )
        
        if file_path:
            try:
                # Buat canvas dengan ukuran A4
                c = canvas.Canvas(file_path, pagesize=A4)
                
                # Set font - gunakan Courier untuk struk (monospace)
                c.setFont("Courier", 9)
                
                # Hitung dimensi A4
                width, height = A4
                
                # Mulai dari posisi atas
                y = height - 30  # Margin atas
                x = 50  # Margin kiri
                
                # Header
                c.drawString(x, y, "=" * 50)
                y -= 15
                c.drawString(x, y, "HAYTECH STORE - Toko Komputer Terpercaya")
                y -= 15
                c.drawString(x, y, "=" * 50)
                y -= 20
                
                # Info Transaksi
                c.drawString(x, y, f"Dicetak pada: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                y -= 15
                c.drawString(x, y, f"ID Transaksi : {self.transaksi_data['id']}")
                y -= 12
                c.drawString(x, y, f"Tanggal      : {self.transaksi_data['tanggal']}")
                y -= 12
                c.drawString(x, y, f"Admin        : {self.transaksi_data['admin']}")
                y -= 12
                c.drawString(x, y, f"Customer     : {self.transaksi_data['pembeli']}")
                y -= 12
                c.drawString(x, y, f"Metode Bayar : {self.transaksi_data['metode_bayar']}")
                y -= 20
                
                # Garis pemisah
                c.drawString(x, y, "-" * 50)
                y -= 15
                
                # Header items
                c.drawString(x, y, "ITEM                           QTY   SUBTOTAL")
                y -= 12
                c.drawString(x, y, "-" * 50)
                y -= 15
                
                # Items
                for item in self.transaksi_data['items']:
                    nama = item['nama']
                    if len(nama) > 25:
                        nama = nama[:22] + "..."
                    
                    # Format baris item dengan alignment yang tepat
                    item_line = f"{nama:<25} {item['qty']:>3}   Rp{item['subtotal']:>10,}"
                    c.drawString(x, y, item_line)
                    y -= 12
                    
                    # Cek jika perlu halaman baru
                    if y < 50:
                        c.showPage()
                        c.setFont("Courier", 9)
                        y = height - 30
                        c.drawString(x, y, "=== LANJUTAN STRUK PEMBELIAN ===")
                        y -= 20
                
                # Garis pemisah setelah items
                y -= 10
                c.drawString(x, y, "-" * 50)
                y -= 15
                
                # Total
                total_str = f"Rp{self.transaksi_data['total']:,}"
                c.drawString(x, y, f"TOTAL BELANJA : {total_str:>20}")
                y -= 12
                c.drawString(x, y, f"BAYAR         : {total_str:>20}")
                y -= 12
                c.drawString(x, y, f"KEMBALI       : {'Rp0':>20}")
                y -= 20
                
                # Footer
                c.drawString(x, y, "=" * 50)
                y -= 15
                c.drawString(x, y, "TERIMA KASIH ATAS KUNJUNGAN ANDA")
                y -= 15
                c.drawString(x, y, "=" * 50)
                y -= 20
                
                # Informasi tambahan
                c.drawString(x, y, "* Barang yang sudah dibeli tidak dapat ditukar")
                y -= 12
                c.drawString(x, y, "  atau dikembalikan")
                y -= 12
                c.drawString(x, y, "* Struk ini sebagai bukti pembayaran yang sah")
                y -= 12
                
                # Simpan PDF
                c.save()
                
                QMessageBox.information(self, "Sukses", 
                                      f"Struk PDF berhasil disimpan!\n{file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Gagal menyimpan PDF: {str(e)}")

class ModernDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.keranjang = []
        self.current_admin = "Tony"  # Default admin
        
        # Variabel untuk logika drag window
        self.oldPos = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # 1. Hapus bingkai native OS
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.setWindowTitle("Haytech Store")
        self.setGeometry(100, 100, 1200, 720)

        # Main Container
        self.central_widget = QWidget()
        self.central_widget.setObjectName("MainWidget")
        self.setCentralWidget(self.central_widget)
        
        # Layout Utama (Vertical)
        self.root_layout = QVBoxLayout(self.central_widget)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # 2. Tambahkan Custom Title Bar
        self.setup_custom_title_bar()

        # 3. Container untuk Konten (Sidebar + Halaman)
        self.content_widget = QWidget()
        self.main_layout = QHBoxLayout(self.content_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.root_layout.addWidget(self.content_widget)

        # Sidebar
        self.setup_sidebar()
        
        # Main content pages
        self.pages = QStackedWidget()
        self.main_layout.addWidget(self.pages)

        # Initialize pages
        self.setup_pages()
        
        # Connect signals
        self.connect_signals()

        # Styling
        self.apply_styles()
        
        self.central_widget.setStyleSheet("""
            QWidget#MainWidget {
                background-color: #f1f5f9;
                border-radius: 10px;
                border: 1px solid #334155;
            }
        """)

    def setup_custom_title_bar(self):
        """Membuat Title Bar ala MacOS"""
        self.title_bar = QFrame()
        self.title_bar.setFixedHeight(40)
        self.title_bar.setStyleSheet("""
            background-color: #0f172a; 
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
            border-bottom: 1px solid #1e293b;
        """)
        
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(15, 0, 0, 0)
        title_layout.setSpacing(10)

        # Tombol MacOS (Merah, Kuning, Hijau)
        btn_close = QPushButton()
        btn_close.setFixedSize(14, 14)
        btn_close.setStyleSheet("""
            QPushButton { background-color: #ff5f56; border-radius: 7px; border: none; }
            QPushButton:hover { background-color: #ff3b30; }
        """)
        btn_close.clicked.connect(self.close)

        btn_minimize = QPushButton()
        btn_minimize.setFixedSize(14, 14)
        btn_minimize.setStyleSheet("""
            QPushButton { background-color: #ffbd2e; border-radius: 7px; border: none; }
            QPushButton:hover { background-color: #ffaa00; }
        """)
        btn_minimize.clicked.connect(self.showMinimized)

        btn_maximize = QPushButton()
        btn_maximize.setFixedSize(14, 14)
        btn_maximize.setStyleSheet("""
            QPushButton { background-color: #27c93f; border-radius: 7px; border: none; }
            QPushButton:hover { background-color: #20a030; }
        """)
        btn_maximize.clicked.connect(self.toggle_maximize)

        lbl_header = QLabel("Haytech Store")
        lbl_header.setStyleSheet("color: #94a3b8; font-weight: bold; font-family: 'Segoe UI'; border: none;")
        lbl_header.setAlignment(Qt.AlignCenter)

        title_layout.addWidget(btn_close)
        title_layout.addWidget(btn_minimize)
        title_layout.addWidget(btn_maximize)
        title_layout.addStretch() 
        title_layout.addWidget(lbl_header)
        title_layout.addStretch() 

        self.root_layout.addWidget(self.title_bar)

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # === LOGIKA DRAG WINDOW ===
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            if event.y() < 50:
                self.oldPos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.oldPos:
            delta = event.globalPos() - self.oldPos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.oldPos = None

    def setup_sidebar(self):
        self.sidebar_frame = QFrame()
        self.sidebar_frame.setObjectName("Sidebar")
        self.sidebar_frame.setStyleSheet("border-bottom-left-radius: 10px;")
        self.sidebar_layout = QVBoxLayout(self.sidebar_frame)
        self.sidebar_layout.setContentsMargins(0, 20, 0, 20)
        self.sidebar_layout.setSpacing(15)
        
        lbl_title = QLabel("Haytech\nStore")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("""
            background-color: #0f172a;
            color: white; 
            font-size: 20px; 
            font-weight: bold; 
            padding-top: 30px;
            padding-bottom: 30px;
            margin-bottom: 20px;
        """)
        self.sidebar_layout.addWidget(lbl_title)
        
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        
        self.btn_dashboard = self.create_nav_button("Dashboard")
        self.btn_input = self.create_nav_button("Input Barang")
        self.btn_transaksi = self.create_nav_button("Transaksi")
        self.btn_laporan = self.create_nav_button("Laporan")
        self.btn_qr = self.create_nav_button("Generator QR")
        
        self.nav_group.addButton(self.btn_dashboard)
        self.nav_group.addButton(self.btn_input)
        self.nav_group.addButton(self.btn_transaksi)
        self.nav_group.addButton(self.btn_laporan)
        self.nav_group.addButton(self.btn_qr)
        
        self.btn_dashboard.setChecked(True)
        
        self.sidebar_layout.addWidget(self.btn_dashboard)
        self.sidebar_layout.addWidget(self.btn_input)
        self.sidebar_layout.addWidget(self.btn_transaksi)
        self.sidebar_layout.addWidget(self.btn_laporan)
        self.sidebar_layout.addWidget(self.btn_qr)
        
        self.sidebar_layout.addStretch()
        
        lbl_footer = QLabel("Copyright © 2025. \n Created by Tony & Satya")
        lbl_footer.setStyleSheet("color: #6c757d; font-size: 10px; padding-left: 20px;")
        self.sidebar_layout.addWidget(lbl_footer)
        
        self.main_layout.addWidget(self.sidebar_frame)

    def setup_pages(self):
        self.page_dashboard = self.create_page_dashboard()
        self.page_input = self.create_page_input()
        self.page_transaksi = self.create_page_transaksi()
        self.page_laporan = self.create_page_laporan()
        self.page_qr = self.create_page_qr_generator()

        self.pages.addWidget(self.page_dashboard)
        self.pages.addWidget(self.page_input)
        self.pages.addWidget(self.page_transaksi)
        self.pages.addWidget(self.page_laporan)
        self.pages.addWidget(self.page_qr)

    def connect_signals(self):
        self.btn_dashboard.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        self.btn_input.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        self.btn_transaksi.clicked.connect(lambda: self.pages.setCurrentIndex(2))
        self.btn_laporan.clicked.connect(lambda: self.pages.setCurrentIndex(3))
        self.btn_qr.clicked.connect(lambda: self.pages.setCurrentIndex(4))

    def create_nav_button(self, text):
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setCheckable(True)
        return btn

    def apply_styles(self):
        self.setStyleSheet("""
            QFrame#Sidebar {
                background-color: #0f172a; 
                min-width: 200px;
                max-width: 200px;
            }
            
            QFrame#Sidebar QPushButton {
                background-color: transparent;
                color: #94a3b8;
                border: none;
                text-align: left;
                padding: 15px 20px;
                font-size: 14px;
                font-family: 'Segoe UI', sans-serif;
            }
            
            QFrame#Sidebar QPushButton:hover {
                background-color: #1e293b;
                color: white;
                border-left: 4px solid #3b82f6;
            }
            
            QFrame#Sidebar QPushButton:checked {
                background-color: #1e293b;
                color: white;
                font-weight: bold;
                border-left: 4px solid #3b82f6;
            }

            QWidget {
                background-color: #f1f5f9; 
                font-family: 'Segoe UI', sans-serif;
            }
            
            QPushButton {
                background-color: #e2e8f0;
                border: 1px solid #cbd5e1;
                padding: 6px 12px;
                border-radius: 4px;
            }

            QLabel#PageTitle {
                font-size: 24px;
                font-weight: bold;
                color: #1e293b;
                margin-bottom: 10px;
                background-color: transparent;
            }

            QFrame#Card {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #e2e8f0;
            }
            
            QFrame#Card QLabel {
                background-color: white;
            }
            
            QTableWidget {
                background-color: white;
                gridline-color: #e2e8f0;
                border: 1px solid #e2e8f0;
                border-radius: 4px;
            }
            
            QLineEdit, QComboBox, QSpinBox, QDateEdit {
                padding: 8px;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                background-color: white;
            }
        """)

    # === HALAMAN DASHBOARD ===
    def create_page_dashboard(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        layout.addWidget(QLabel("Dashboard Operasional", objectName="PageTitle"))
        layout.addWidget(QLabel("Ringkasan kinerja toko hari ini."))
        layout.addSpacing(20)
        cards_layout = QHBoxLayout()
        
        total_barang = self.get_total_barang()
        penjualan_hari_ini = self.get_penjualan_hari_ini()
        stok_kritis = self.get_stok_kritis_count()
        
        for title, val, color in [
            ("Total Barang", str(total_barang), "#3b82f6"), 
            ("Penjualan Hari Ini", f"Rp {penjualan_hari_ini:,}", "#10b981"), 
            ("Stok Kritis", str(stok_kritis), "#ef4444")
        ]:
            card = QFrame(objectName="Card")
            card.setFixedHeight(100)
            card.setStyleSheet(f"QFrame#Card {{ border-left: 5px solid {color}; }}")
            v_layout = QVBoxLayout(card)
            
            title_label = QLabel(title)
            title_label.setStyleSheet("color: #64748b; font-size: 14px;")
            v_layout.addWidget(title_label)
            
            val_label = QLabel(str(val))
            val_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #1e293b;")
            v_layout.addWidget(val_label)
            cards_layout.addWidget(card)
        
        layout.addLayout(cards_layout)
        
        if stok_kritis > 0:
            stok_frame = QFrame(objectName="Card")
            stok_layout = QVBoxLayout(stok_frame)
            stok_layout.addWidget(QLabel("⚠️ Barang Stok Kritis"))
            
            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["Nama Barang", "Kategori", "Stok", "Harga"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            
            stok_kritis_items = self.get_barang_stok_kritis()
            table.setRowCount(len(stok_kritis_items))
            
            for row, barang in enumerate(stok_kritis_items):
                table.setItem(row, 0, QTableWidgetItem(barang["nama_barang"]))
                table.setItem(row, 1, QTableWidgetItem(barang["nama_kategori"]))
                table.setItem(row, 2, QTableWidgetItem(str(barang["stok"])))
                table.setItem(row, 3, QTableWidgetItem(f"Rp {barang['harga']:,}"))
            
            stok_layout.addWidget(table)
            layout.addWidget(stok_frame)
        
        layout.addStretch()
        return page

    # === HALAMAN INPUT BARANG ===
    def create_page_input(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Master Data Barang", objectName="PageTitle"))
        
        scan_frame = QFrame(objectName="Card")
        scan_layout = QHBoxLayout(scan_frame)
        
        btn_scan_qr = QPushButton("📷 Scan QR Code Barang")
        btn_scan_qr.setStyleSheet("background-color: #8b5cf6; color: white; padding: 10px;")
        btn_scan_qr.clicked.connect(self.scan_qr_code)
        
        self.label_scan_result = QLabel("Hasil scan akan muncul di sini")
        self.label_scan_result.setStyleSheet("color: #64748b; font-style: italic;")
        
        scan_layout.addWidget(btn_scan_qr)
        scan_layout.addWidget(self.label_scan_result)
        scan_layout.addStretch()
        
        layout.addWidget(scan_frame)
        
        form_frame = QFrame(objectName="Card")
        form_layout = QFormLayout(form_frame)
        form_layout.setContentsMargins(20, 20, 20, 20)
        
        self.input_nama = QLineEdit()
        self.input_kategori = QComboBox()
        self.load_kategori_combo()
        self.input_harga = QLineEdit()
        self.input_harga.setPlaceholderText("Contoh: 1500000")
        self.input_stok = QSpinBox()
        self.input_stok.setRange(0, 9999)
        self.input_deskripsi = QTextEdit()
        self.input_deskripsi.setMaximumHeight(100)
        
        form_layout.addRow("Nama Barang:", self.input_nama)
        form_layout.addRow("Kategori:", self.input_kategori)
        form_layout.addRow("Harga (Rp):", self.input_harga)
        form_layout.addRow("Stok:", self.input_stok)
        form_layout.addRow("Deskripsi:", self.input_deskripsi)
        
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Simpan Data")
        btn_save.setStyleSheet("background-color: #3b82f6; color: white; padding: 8px; border-radius: 4px;")
        btn_save.clicked.connect(self.simpan_barang)
        
        btn_reset = QPushButton("Reset")
        btn_reset.setStyleSheet("background-color: #6c757d; color: white; padding: 8px; border-radius: 4px;")
        btn_reset.clicked.connect(self.reset_form_barang)
        
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_reset)
        form_layout.addRow(btn_layout)
        
        layout.addWidget(form_frame)
        
        list_frame = QFrame(objectName="Card")
        list_layout = QVBoxLayout(list_frame)
        list_layout.addWidget(QLabel("Daftar Barang"))
        
        self.table_barang = QTableWidget()
        self.table_barang.setColumnCount(6)
        self.table_barang.setHorizontalHeaderLabels(["ID", "Nama", "Kategori", "Harga", "Stok", "Aksi"])
        self.table_barang.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        list_layout.addWidget(self.table_barang)
        layout.addWidget(list_frame)
        
        self.load_data_barang()
        return page

    def simpan_barang(self):
        try:
            nama = self.input_nama.text().strip()
            harga = int(self.input_harga.text().replace(',', '').replace('.', ''))
            stok = self.input_stok.value()
            deskripsi = self.input_deskripsi.toPlainText().strip()
            id_kategori = self.input_kategori.currentData()
            
            if not nama:
                QMessageBox.warning(self, "Peringatan", "Nama barang harus diisi!")
                return
            
            query = """
                INSERT INTO barang (nama_barang, id_kategori, harga, stok, deskripsi) 
                VALUES (%s, %s, %s, %s, %s)
            """
            params = (nama, id_kategori, harga, stok, deskripsi)
            
            result = self.db.execute_query(query, params)
            if result:
                QMessageBox.information(self, "Sukses", "Data barang berhasil disimpan!")
                self.reset_form_barang()
                self.load_data_barang()
            else:
                QMessageBox.warning(self, "Error", "Gagal menyimpan data barang!")
                
        except ValueError:
            QMessageBox.warning(self, "Error", "Format harga tidak valid!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Terjadi kesalahan: {str(e)}")

    def reset_form_barang(self):
        self.input_nama.clear()
        self.input_harga.clear()
        self.input_stok.setValue(0)
        self.input_deskripsi.clear()

    def load_kategori_combo(self):
        query = "SELECT id, nama_kategori FROM kategori ORDER BY nama_kategori"
        categories = self.db.execute_query(query)
        
        self.input_kategori.clear()
        for category in categories:
            self.input_kategori.addItem(category['nama_kategori'], category['id'])

    def load_data_barang(self):
        query = """
            SELECT b.id, b.nama_barang, k.nama_kategori, b.harga, b.stok 
            FROM barang b 
            LEFT JOIN kategori k ON b.id_kategori = k.id 
            ORDER BY b.id
        """
        barang_list = self.db.execute_query(query)
        
        self.table_barang.setRowCount(len(barang_list))
        
        for row, barang in enumerate(barang_list):
            self.table_barang.setItem(row, 0, QTableWidgetItem(str(barang["id"])))
            self.table_barang.setItem(row, 1, QTableWidgetItem(barang["nama_barang"]))
            self.table_barang.setItem(row, 2, QTableWidgetItem(barang["nama_kategori"]))
            self.table_barang.setItem(row, 3, QTableWidgetItem(f"Rp {barang['harga']:,}"))
            self.table_barang.setItem(row, 4, QTableWidgetItem(str(barang["stok"])))
            
            btn_hapus = QPushButton("Hapus")
            btn_hapus.setStyleSheet("background-color: #ef4444; color: white;")
            btn_hapus.clicked.connect(lambda checked, id_barang=barang["id"]: self.hapus_barang(id_barang))
            self.table_barang.setCellWidget(row, 5, btn_hapus)

    def hapus_barang(self, id_barang):
        reply = QMessageBox.question(self, "Konfirmasi", 
                                   f"Apakah Anda yakin ingin menghapus barang ini?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            query = "DELETE FROM barang WHERE id = %s"
            result = self.db.execute_query(query, (id_barang,))
            
            if result is not None:
                QMessageBox.information(self, "Sukses", "Barang berhasil dihapus!")
                self.load_data_barang()
            else:
                QMessageBox.warning(self, "Error", "Gagal menghapus barang!")

    # === HALAMAN TRANSAKSI ===
    def create_page_transaksi(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Kasir / Point of Sales", objectName="PageTitle"))

        filter_frame = QFrame(objectName="Card")
        filter_layout = QHBoxLayout(filter_frame)
        
        filter_layout.addWidget(QLabel("Filter Kategori:"))
        self.combo_kategori_filter = QComboBox()
        self.combo_kategori_filter.addItem("Semua Kategori", 0)
        self.load_kategori_filter()
        self.combo_kategori_filter.currentIndexChanged.connect(self.filter_barang_by_kategori)
        
        btn_scan_transaksi = QPushButton("📷 Scan QR Barang")
        btn_scan_transaksi.setStyleSheet("background-color: #8b5cf6; color: white;")
        btn_scan_transaksi.clicked.connect(self.scan_qr_transaksi)
        
        filter_layout.addWidget(self.combo_kategori_filter)
        filter_layout.addStretch()
        filter_layout.addWidget(btn_scan_transaksi)
        
        layout.addWidget(filter_frame)

        select_frame = QFrame(objectName="Card")
        select_layout = QHBoxLayout(select_frame)
        
        self.combo_barang = QComboBox()
        self.load_combo_barang()
        
        self.spin_qty = QSpinBox()
        self.spin_qty.setRange(1, 100)
        self.spin_qty.setValue(1)
        
        btn_tambah = QPushButton("Tambah ke Keranjang")
        btn_tambah.setStyleSheet("background-color: #10b981; color: white;")
        btn_tambah.clicked.connect(self.tambah_ke_keranjang)
        
        select_layout.addWidget(QLabel("Pilih Barang:"))
        select_layout.addWidget(self.combo_barang)
        select_layout.addWidget(QLabel("Qty:"))
        select_layout.addWidget(self.spin_qty)
        select_layout.addWidget(btn_tambah)
        
        layout.addWidget(select_frame)
        
        cart_frame = QFrame(objectName="Card")
        cart_layout = QVBoxLayout(cart_frame)
        cart_layout.addWidget(QLabel("Keranjang Belanja"))
        
        self.table_keranjang = QTableWidget()
        self.table_keranjang.setColumnCount(5)
        self.table_keranjang.setHorizontalHeaderLabels(["Barang", "Harga", "Qty", "Subtotal", "Aksi"])
        self.table_keranjang.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        cart_layout.addWidget(self.table_keranjang)
        
        buyer_frame = QFrame(objectName="Card")
        buyer_layout = QHBoxLayout(buyer_frame)
        buyer_layout.addWidget(QLabel("Nama Pembeli:"))
        self.input_pembeli = QLineEdit()
        self.input_pembeli.setPlaceholderText("Nama customer")
        buyer_layout.addWidget(self.input_pembeli)
        buyer_layout.addStretch()
        
        cart_layout.addWidget(buyer_frame)
        
        total_layout = QHBoxLayout()
        self.label_total = QLabel("Total: Rp 0")
        self.label_total.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e293b;")
        
        btn_bayar = QPushButton("💳 Proses Pembayaran")
        btn_bayar.setStyleSheet("background-color: #3b82f6; color: white; padding: 10px; font-weight: bold;")
        btn_bayar.clicked.connect(self.proses_pembayaran)
        
        btn_reset_cart = QPushButton("Kosongkan Keranjang")
        btn_reset_cart.setStyleSheet("background-color: #ef4444; color: white;")
        btn_reset_cart.clicked.connect(self.kosongkan_keranjang)
        
        total_layout.addWidget(self.label_total)
        total_layout.addStretch()
        total_layout.addWidget(btn_reset_cart)
        total_layout.addWidget(btn_bayar)
        
        cart_layout.addLayout(total_layout)
        layout.addWidget(cart_frame)
        
        return page

    def load_combo_barang(self):
        self.combo_barang.clear()
        query = """
            SELECT b.id, b.nama_barang, b.harga, b.stok, k.nama_kategori 
            FROM barang b 
            LEFT JOIN kategori k ON b.id_kategori = k.id 
            WHERE b.stok > 0 
            ORDER BY b.nama_barang
        """
        barang_list = self.db.execute_query(query)
        
        for barang in barang_list:
            self.combo_barang.addItem(
                f"{barang['nama_barang']} - Rp {barang['harga']:,} (Stok: {barang['stok']})", 
                barang["id"]
            )

    def tambah_ke_keranjang(self):
        if self.combo_barang.currentData() is None:
            QMessageBox.warning(self, "Peringatan", "Tidak ada barang yang dipilih!")
            return
        
        id_barang = self.combo_barang.currentData()
        qty = self.spin_qty.value()
        
        query = "SELECT id, nama_barang, harga, stok FROM barang WHERE id = %s"
        barang = self.db.execute_query(query, (id_barang,))
        
        if not barang:
            return
        
        barang = barang[0]
        
        if qty > barang["stok"]:
            QMessageBox.warning(self, "Peringatan", f"Stok tidak mencukupi! Stok tersedia: {barang['stok']}")
            return
        
        for item in self.keranjang:
            if item["id_barang"] == id_barang:
                new_qty = item["qty"] + qty
                if new_qty > barang["stok"]:
                    QMessageBox.warning(self, "Peringatan", f"Stok tidak mencukupi! Stok tersedia: {barang['stok']}")
                    return
                item["qty"] = new_qty
                break
        else:
            self.keranjang.append({
                "id_barang": id_barang,
                "nama": barang["nama_barang"],
                "harga": barang["harga"],
                "qty": qty
            })
        
        self.update_tampilan_keranjang()
        self.spin_qty.setValue(1)

    def update_tampilan_keranjang(self):
        self.table_keranjang.setRowCount(len(self.keranjang))
        total_semua = 0
        
        for row, item in enumerate(self.keranjang):
            subtotal = item["harga"] * item["qty"]
            total_semua += subtotal
            
            self.table_keranjang.setItem(row, 0, QTableWidgetItem(item["nama"]))
            self.table_keranjang.setItem(row, 1, QTableWidgetItem(f"Rp {item['harga']:,}"))
            self.table_keranjang.setItem(row, 2, QTableWidgetItem(str(item["qty"])))
            self.table_keranjang.setItem(row, 3, QTableWidgetItem(f"Rp {subtotal:,}"))
            
            btn_hapus = QPushButton("Hapus")
            btn_hapus.setStyleSheet("background-color: #ef4444; color: white;")
            btn_hapus.clicked.connect(lambda checked, r=row: self.hapus_dari_keranjang(r))
            self.table_keranjang.setCellWidget(row, 4, btn_hapus)
        
        self.label_total.setText(f"Total: Rp {total_semua:,}")

    def hapus_dari_keranjang(self, row):
        if 0 <= row < len(self.keranjang):
            self.keranjang.pop(row)
            self.update_tampilan_keranjang()

    def kosongkan_keranjang(self):
        self.keranjang.clear()
        self.update_tampilan_keranjang()

    def proses_pembayaran(self):
        if not self.keranjang:
            QMessageBox.warning(self, "Peringatan", "Keranjang belanja kosong!")
            return
        
        if not self.input_pembeli.text().strip():
            QMessageBox.warning(self, "Peringatan", "Nama pembeli harus diisi!")
            return
        
        total = sum(item["harga"] * item["qty"] for item in self.keranjang)
        
        payment_dialog = PaymentDialog(total, self)
        if payment_dialog.exec_() == QDialog.Accepted:
            payment_data = payment_dialog.get_payment_data()
            
            if not payment_data['admin']:
                QMessageBox.warning(self, "Peringatan", "Nama admin harus diisi!")
                return
            
            if payment_data['metode'] in ['Transfer Bank', 'QRIS'] and not payment_data['bukti_path']:
                QMessageBox.warning(self, "Peringatan", "Bukti pembayaran wajib diupload untuk metode ini!")
                return
            
            try:
                try:
                    if self.db.connection.in_transaction:
                        self.db.connection.rollback()
                except:
                    pass
                
                bukti_filename = None
                if payment_data['bukti_path']:
                    nama_pembeli = self.input_pembeli.text().strip()
                    folder_name = f"{nama_pembeli}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    pembeli_folder = os.path.join("bukti_pembayaran", folder_name)
                    os.makedirs(pembeli_folder, exist_ok=True)
                    
                    file_ext = os.path.splitext(payment_data['bukti_path'])[1]
                    bukti_filename = f"bukti_{folder_name}{file_ext}"
                    bukti_dest = os.path.join(pembeli_folder, bukti_filename)
                    
                    import shutil
                    shutil.copy2(payment_data['bukti_path'], bukti_dest)
                
                query_transaksi = """
                    INSERT INTO transaksi (nama_pembeli, total, metode_bayar, admin, bukti_pembayaran) 
                    VALUES (%s, %s, %s, %s, %s)
                """
                id_transaksi = self.db.execute_query(query_transaksi, (
                    self.input_pembeli.text().strip(), 
                    total, 
                    payment_data['metode'],
                    payment_data['admin'],
                    bukti_filename
                ))
                
                if not id_transaksi:
                    raise Exception("Gagal menyimpan transaksi")
                
                for item in self.keranjang:
                    subtotal = item["harga"] * item["qty"]
                    
                    query_detail = """
                        INSERT INTO detail_transaksi (id_transaksi, id_barang, qty, harga, subtotal)
                        VALUES (%s, %s, %s, %s, %s)
                    """
                    result_detail = self.db.execute_query(query_detail, (id_transaksi, item["id_barang"], item["qty"], item["harga"], subtotal))
                    
                    if result_detail is None:
                        raise Exception("Gagal menyimpan detail transaksi")
                    
                    query_update_stok = "UPDATE barang SET stok = stok - %s WHERE id = %s"
                    result_stok = self.db.execute_query(query_update_stok, (item["qty"], item["id_barang"]))
                    
                    if result_stok is None:
                        raise Exception("Gagal update stok barang")
                
                transaksi_data = {
                    'id': id_transaksi,
                    'tanggal': datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                    'admin': payment_data['admin'],
                    'pembeli': self.input_pembeli.text().strip(),
                    'metode_bayar': payment_data['metode'],
                    'total': total,
                    'items': [{
                        'nama': item['nama'],
                        'qty': item['qty'],
                        'subtotal': item['harga'] * item['qty']
                    } for item in self.keranjang]
                }
                
                receipt_dialog = PrintReceiptDialog(transaksi_data, self)
                receipt_dialog.exec_()
                
                QMessageBox.information(self, "Sukses", 
                                      f"Transaksi berhasil!\nID Transaksi: {id_transaksi}\nTotal: Rp {total:,}")
                
                self.kosongkan_keranjang()
                self.input_pembeli.clear()
                self.load_combo_barang() 
                
            except Exception as e:
                try:
                    self.db.connection.rollback()
                except:
                    pass
                QMessageBox.critical(self, "Error", f"Terjadi kesalahan: {str(e)}")

    # === HALAMAN LAPORAN ===
    def create_page_laporan(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Laporan Penjualan", objectName="PageTitle"))
        
        filter_frame = QFrame(objectName="Card")
        filter_layout = QHBoxLayout(filter_frame)
        
        filter_layout.addWidget(QLabel("Dari:"))
        self.date_from = QDateEdit()
        self.date_from.setDate(QDate.currentDate().addDays(-7))
        self.date_from.setCalendarPopup(True)
        
        filter_layout.addWidget(QLabel("Sampai:"))
        self.date_to = QDateEdit()
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        
        btn_filter = QPushButton("Filter")
        btn_filter.setStyleSheet("background-color: #3b82f6; color: white;")
        btn_filter.clicked.connect(self.filter_laporan)
        
        btn_export = QPushButton("🖨️ Print Laporan")
        btn_export.setStyleSheet("background-color: #10b981; color: white;")
        btn_export.clicked.connect(self.print_laporan)
        
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(btn_filter)
        filter_layout.addWidget(btn_export)
        filter_layout.addStretch()
        
        layout.addWidget(filter_frame)
        
        self.table_laporan = QTableWidget()
        self.table_laporan.setColumnCount(7)
        self.table_laporan.setHorizontalHeaderLabels(["ID", "Tanggal", "Pembeli", "Metode", "Admin", "Total", "Aksi"])
        self.table_laporan.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(self.table_laporan)
        
        self.filter_laporan()
        
        return page

    def filter_laporan(self):
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        
        query = """
            SELECT t.id, t.tanggal_transaksi, t.nama_pembeli, t.metode_bayar, 
                   t.admin, t.total, t.bukti_pembayaran
            FROM transaksi t
            WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            ORDER BY t.tanggal_transaksi DESC
        """
        transaksi_list = self.db.execute_query(query, (date_from, date_to))
        
        self.table_laporan.setRowCount(len(transaksi_list))
        
        for row, transaksi in enumerate(transaksi_list):
            self.table_laporan.setItem(row, 0, QTableWidgetItem(str(transaksi["id"])))
            self.table_laporan.setItem(row, 1, QTableWidgetItem(str(transaksi["tanggal_transaksi"])))
            self.table_laporan.setItem(row, 2, QTableWidgetItem(transaksi["nama_pembeli"]))
            self.table_laporan.setItem(row, 3, QTableWidgetItem(transaksi.get("metode_bayar", "Cash")))
            self.table_laporan.setItem(row, 4, QTableWidgetItem(transaksi.get("admin", "-")))
            self.table_laporan.setItem(row, 5, QTableWidgetItem(f"Rp {transaksi['total']:,}"))
            
            action_layout = QHBoxLayout()
            action_widget = QWidget()
            
            btn_detail = QPushButton("Detail")
            btn_detail.setStyleSheet("background-color: #3b82f6; color: white;")
            btn_detail.clicked.connect(lambda checked, id_transaksi=transaksi["id"]: self.lihat_detail_transaksi(id_transaksi))
            
            btn_struk = QPushButton("Struk")
            btn_struk.setStyleSheet("background-color: #f59e0b; color: white;")
            btn_struk.clicked.connect(lambda checked, id_transaksi=transaksi["id"]: self.cetak_struk(id_transaksi))
            
            action_layout.addWidget(btn_detail)
            action_layout.addWidget(btn_struk)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_widget.setLayout(action_layout)
            
            self.table_laporan.setCellWidget(row, 6, action_widget)

    def lihat_detail_transaksi(self, id_transaksi):
        query = """
            SELECT dt.id_barang, b.nama_barang, dt.qty, dt.harga, dt.subtotal
            FROM detail_transaksi dt
            JOIN barang b ON dt.id_barang = b.id
            WHERE dt.id_transaksi = %s
        """
        detail_items = self.db.execute_query(query, (id_transaksi,))
        
        detail_text = f"Detail Transaksi #{id_transaksi}\n\n"
        for item in detail_items:
            detail_text += f"{item['nama_barang']} - {item['qty']} x Rp {item['harga']:,} = Rp {item['subtotal']:,}\n"
        
        QMessageBox.information(self, "Detail Transaksi", detail_text)

    def cetak_struk(self, id_transaksi):
        query = """
            SELECT t.id, t.tanggal_transaksi, t.nama_pembeli, t.metode_bayar, 
                   t.admin, t.total
            FROM transaksi t
            WHERE t.id = %s
        """
        transaksi = self.db.execute_query(query, (id_transaksi,))
        
        if not transaksi:
            return
            
        transaksi = transaksi[0]
        
        query_items = """
            SELECT dt.id_barang, b.nama_barang, dt.qty, dt.harga, dt.subtotal
            FROM detail_transaksi dt
            JOIN barang b ON dt.id_barang = b.id
            WHERE dt.id_transaksi = %s
        """
        items = self.db.execute_query(query_items, (id_transaksi,))
        
        transaksi_data = {
            'id': transaksi['id'],
            'tanggal': transaksi['tanggal_transaksi'].strftime("%d/%m/%Y %H:%M:%S"),
            'admin': transaksi.get('admin', '-'),
            'pembeli': transaksi['nama_pembeli'],
            'metode_bayar': transaksi.get('metode_bayar', 'Cash'),
            'total': transaksi['total'],
            'items': [{
                'nama': item['nama_barang'],
                'qty': item['qty'],
                'subtotal': item['subtotal']
            } for item in items]
        }
        
        receipt_dialog = PrintReceiptDialog(transaksi_data, self)
        receipt_dialog.exec_()

    def print_laporan(self):
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        
        query = """
            SELECT t.id, t.tanggal_transaksi, t.nama_pembeli, t.metode_bayar, 
                   t.admin, t.total
            FROM transaksi t
            WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            ORDER BY t.tanggal_transaksi DESC
        """
        transaksi_list = self.db.execute_query(query, (date_from, date_to))
        
        report_text = f"""
LAPORAN PENJUALAN
Periode: {date_from} s/d {date_to}
Dicetak: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
==============================================
ID | Tanggal | Pembeli | Metode | Admin | Total
----------------------------------------------
"""
        total_penjualan = 0
        for transaksi in transaksi_list:
            report_text += f"{transaksi['id']} | {transaksi['tanggal_transaksi']} | {transaksi['nama_pembeli']} | {transaksi.get('metode_bayar', 'Cash')} | {transaksi.get('admin', '-')} | Rp {transaksi['total']:,}\n"
            total_penjualan += transaksi['total']
            
        report_text += f"""
----------------------------------------------
TOTAL PENJUALAN: Rp {total_penjualan:,}
==============================================
"""
        
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, self)
        
        if dialog.exec_() == QPrintDialog.Accepted:
            painter = QPainter()
            painter.begin(printer)
            
            font = painter.font()
            font.setPointSize(9)
            font.setFamily("Courier New")
            painter.setFont(font)
            
            lines = report_text.split('\n')
            y_pos = 100
            for line in lines:
                painter.drawText(100, y_pos, line)
                y_pos += 20
                
            painter.end()
            
            QMessageBox.information(self, "Sukses", "Laporan berhasil dicetak!")

    # === METHOD UNTUK DASHBOARD ===
    def get_total_barang(self):
        query = "SELECT COUNT(*) as total FROM barang"
        result = self.db.execute_query(query)
        return result[0]['total'] if result else 0

    def get_penjualan_hari_ini(self):
        today = date.today().strftime("%Y-%m-%d")
        query = "SELECT COALESCE(SUM(total), 0) as total FROM transaksi WHERE DATE(tanggal_transaksi) = %s"
        result = self.db.execute_query(query, (today,))
        return result[0]['total'] if result else 0

    def get_stok_kritis_count(self):
        query = "SELECT COUNT(*) as total FROM barang WHERE stok < 5"
        result = self.db.execute_query(query)
        return result[0]['total'] if result else 0

    def get_barang_stok_kritis(self):
        query = """
            SELECT b.nama_barang, k.nama_kategori, b.stok, b.harga 
            FROM barang b 
            LEFT JOIN kategori k ON b.id_kategori = k.id 
            WHERE b.stok < 5 
            ORDER BY b.stok ASC
        """
        return self.db.execute_query(query) or []

    # === METHOD UNTUK KATEGORI ===
    def load_kategori_filter(self):
        query = "SELECT id, nama_kategori FROM kategori ORDER BY nama_kategori"
        categories = self.db.execute_query(query)
        
        self.combo_kategori_filter.clear()
        self.combo_kategori_filter.addItem("Semua Kategori", 0)
        for category in categories:
            self.combo_kategori_filter.addItem(category['nama_kategori'], category['id'])

    def filter_barang_by_kategori(self):
        kategori_id = self.combo_kategori_filter.currentData()
        
        if kategori_id == 0:
            self.load_combo_barang()
        else:
            query = """
                SELECT b.id, b.nama_barang, b.harga, b.stok, k.nama_kategori 
                FROM barang b 
                LEFT JOIN kategori k ON b.id_kategori = k.id 
                WHERE b.stok > 0 AND b.id_kategori = %s
                ORDER BY b.nama_barang
            """
            barang_list = self.db.execute_query(query, (kategori_id,))
            
            self.combo_barang.clear()
            for barang in barang_list:
                self.combo_barang.addItem(
                    f"{barang['nama_barang']} - Rp {barang['harga']:,} (Stok: {barang['stok']})", 
                    barang["id"]
                )

    # === METHOD UNTUK SCAN QR ===
    def scan_qr_code(self):
        try:
            cap = cv2.VideoCapture(0)
            
            if not cap.isOpened():
                QMessageBox.warning(self, "Error", "Tidak dapat mengakses kamera!")
                return
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                decoded_objects = decode(frame)
                
                for obj in decoded_objects:
                    qr_data = obj.data.decode('utf-8')
                    self.label_scan_result.setText(f"Data terdeteksi: {qr_data}")
                    
                    self.process_qr_data(qr_data)
                    
                    cap.release()
                    cv2.destroyAllWindows()
                    return
                
                cv2.imshow('QR Scanner - Tekan ESC untuk keluar', frame)
                
                if cv2.waitKey(1) & 0xFF == 27:
                    break
            
            cap.release()
            cv2.destroyAllWindows()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error saat scan QR: {str(e)}")

    def scan_qr_transaksi(self):
        try:
            cap = cv2.VideoCapture(0)
            
            if not cap.isOpened():
                QMessageBox.warning(self, "Error", "Tidak dapat mengakses kamera!")
                return
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                decoded_objects = decode(frame)
                
                for obj in decoded_objects:
                    qr_data = obj.data.decode('utf-8')
                    
                    if self.process_qr_transaksi(qr_data):
                        cap.release()
                        cv2.destroyAllWindows()
                        return
                
                cv2.imshow('QR Scanner Transaksi - Tekan ESC untuk keluar', frame)
                
                if cv2.waitKey(1) & 0xFF == 27:
                    break
            
            cap.release()
            cv2.destroyAllWindows()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error saat scan QR: {str(e)}")

    def process_qr_data(self, qr_data):
        try:
            if qr_data.startswith("BARANG|"):
                parts = qr_data.split("|")
                if len(parts) >= 5:
                    self.input_nama.setText(parts[2])
                    self.input_harga.setText(parts[3])
                    
                    kategori_id = int(parts[4])
                    index = self.input_kategori.findData(kategori_id)
                    if index >= 0:
                        self.input_kategori.setCurrentIndex(index)
                    
                    QMessageBox.information(self, "Sukses", "Data barang berhasil diisi dari QR code!")
                    return True
            
            self.input_nama.setText(qr_data)
            QMessageBox.information(self, "Info", f"Data QR: {qr_data}")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error processing QR data: {str(e)}")

    def process_qr_transaksi(self, qr_data):
        try:
            if qr_data.startswith("BARANG|"):
                parts = qr_data.split("|")
                if len(parts) >= 2:
                    barang_id = int(parts[1])
                    
                    for i in range(self.combo_barang.count()):
                        if self.combo_barang.itemData(i) == barang_id:
                            self.combo_barang.setCurrentIndex(i)
                            self.tambah_ke_keranjang()
                            QMessageBox.information(self, "Sukses", "Barang berhasil ditambahkan dari QR code!")
                            return True
            
            QMessageBox.warning(self, "Peringatan", "QR code tidak valid untuk transaksi")
            return False
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error processing QR transaksi: {str(e)}")
            return False

    # === HALAMAN GENERATOR QR ===
    def create_page_qr_generator(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Generator QR Code", objectName="PageTitle"))
        
        form_frame = QFrame(objectName="Card")
        form_layout = QFormLayout(form_frame)
        
        self.qr_data_input = QLineEdit()
        self.qr_data_input.setPlaceholderText("Masukkan data untuk QR code...")
        
        self.qr_barang_combo = QComboBox()
        self.load_barang_for_qr()
        
        btn_generate_from_text = QPushButton("Generate dari Teks")
        btn_generate_from_text.setStyleSheet("background-color: #3b82f6; color: white;")
        btn_generate_from_text.clicked.connect(self.generate_qr_from_text)
        
        btn_generate_from_barang = QPushButton("Generate dari Barang")
        btn_generate_from_barang.setStyleSheet("background-color: #10b981; color: white;")
        btn_generate_from_barang.clicked.connect(self.generate_qr_from_barang)
        
        form_layout.addRow("Data QR:", self.qr_data_input)
        form_layout.addRow("Pilih Barang:", self.qr_barang_combo)
        form_layout.addRow(btn_generate_from_text)
        form_layout.addRow(btn_generate_from_barang)
        
        layout.addWidget(form_frame)
        
        preview_frame = QFrame(objectName="Card")
        preview_layout = QVBoxLayout(preview_frame)
        
        preview_layout.addWidget(QLabel("Preview QR Code:"))
        self.qr_preview_label = QLabel()
        self.qr_preview_label.setAlignment(Qt.AlignCenter)
        self.qr_preview_label.setMinimumSize(300, 300)
        self.qr_preview_label.setStyleSheet("border: 2px dashed #cbd5e1; background-color: white;")
        self.qr_preview_label.setText("QR Code akan muncul di sini")
        
        btn_save_qr = QPushButton("💾 Simpan QR Code")
        btn_save_qr.setStyleSheet("background-color: #f59e0b; color: white;")
        btn_save_qr.clicked.connect(self.save_qr_code)
        
        preview_layout.addWidget(self.qr_preview_label)
        preview_layout.addWidget(btn_save_qr)
        layout.addWidget(preview_frame)
        
        return page

    def load_barang_for_qr(self):
        query = """
            SELECT b.id, b.nama_barang, k.nama_kategori, b.harga 
            FROM barang b 
            LEFT JOIN kategori k ON b.id_kategori = k.id 
            ORDER BY b.nama_barang
        """
        barang_list = self.db.execute_query(query)
        
        self.qr_barang_combo.clear()
        for barang in barang_list:
            self.qr_barang_combo.addItem(
                f"{barang['nama_barang']} - {barang['nama_kategori']} - Rp {barang['harga']:,}",
                barang["id"]
            )

    def generate_qr_from_text(self):
        data = self.qr_data_input.text().strip()
        if not data:
            QMessageBox.warning(self, "Peringatan", "Masukkan data terlebih dahulu!")
            return
        
        self.generate_and_display_qr(data)

    def generate_qr_from_barang(self):
        if self.qr_barang_combo.currentData() is None:
            QMessageBox.warning(self, "Peringatan", "Pilih barang terlebih dahulu!")
            return
        
        barang_id = self.qr_barang_combo.currentData()
        
        query = """
            SELECT b.id, b.nama_barang, b.harga, k.id as kategori_id, k.nama_kategori
            FROM barang b 
            LEFT JOIN kategori k ON b.id_kategori = k.id 
            WHERE b.id = %s
        """
        barang = self.db.execute_query(query, (barang_id,))
        
        if barang:
            barang = barang[0]
            qr_data = f"BARANG|{barang['id']}|{barang['nama_barang']}|{barang['harga']}|{barang['kategori_id']}"
            self.generate_and_display_qr(qr_data)

    def generate_and_display_qr(self, data):
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            import io
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            
            qimg = QPixmap()
            qimg.loadFromData(buffer.getvalue())
            
            scaled_pixmap = qimg.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.qr_preview_label.setPixmap(scaled_pixmap)
            
            self.current_qr_data = data
            self.current_qr_image = img
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal generate QR: {str(e)}")

    def save_qr_code(self):
        if not hasattr(self, 'current_qr_image'):
            QMessageBox.warning(self, "Peringatan", "Generate QR code terlebih dahulu!")
            return
        
        try:
            filename = f"qr_code_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            file_path = os.path.join("qr_codes", filename)
            self.current_qr_image.save(file_path)
            
            QMessageBox.information(self, "Sukses", f"QR code berhasil disimpan di:\n{file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Gagal menyimpan QR: {str(e)}")

    def closeEvent(self, event):
        self.db.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernDashboard()
    window.show()
    sys.exit(app.exec_())