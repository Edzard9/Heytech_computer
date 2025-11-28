import sys
import mysql.connector
from mysql.connector import Error
from datetime import datetime, date
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QStackedWidget, QFrame, QTableWidget, 
    QTableWidgetItem, QHeaderView, QFormLayout, QLineEdit, QComboBox, 
    QMessageBox, QButtonGroup, QSpinBox, QDateEdit, QTextEdit
)
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QFont


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


class ModernDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.keranjang = []
        
        # Variabel untuk logika drag window
        self.oldPos = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # 1. Hapus bingkai native OS
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.setWindowTitle("Haytech Store")
        self.setGeometry(100, 100, 1200, 720)
        # self.showMaximized() # Hapus ini agar start tidak langsung full screen aneh di frameless

        # Main Container (Sekarang Vertical untuk menampung Title Bar + Konten)
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
        self.main_layout = QHBoxLayout(self.content_widget) # Tetap gunakan nama main_layout agar kompatibel
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # Masukkan content widget ke root layout (di bawah title bar)
        self.root_layout.addWidget(self.content_widget)

        # Sidebar (Logic tetap sama, dia akan masuk ke self.main_layout)
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
        
        # Style tambahan untuk border radius window utama agar terlihat rapi
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
        # Warna disamakan dengan sidebar agar menyatu
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
        # Close
        btn_close = QPushButton()
        btn_close.setFixedSize(14, 14)
        btn_close.setStyleSheet("""
            QPushButton { background-color: #ff5f56; border-radius: 7px; border: none; }
            QPushButton:hover { background-color: #ff3b30; }
        """)
        btn_close.clicked.connect(self.close)

        # Minimize
        btn_minimize = QPushButton()
        btn_minimize.setFixedSize(14, 14)
        btn_minimize.setStyleSheet("""
            QPushButton { background-color: #ffbd2e; border-radius: 7px; border: none; }
            QPushButton:hover { background-color: #ffaa00; }
        """)
        btn_minimize.clicked.connect(self.showMinimized)

        # Maximize
        btn_maximize = QPushButton()
        btn_maximize.setFixedSize(14, 14)
        btn_maximize.setStyleSheet("""
            QPushButton { background-color: #27c93f; border-radius: 7px; border: none; }
            QPushButton:hover { background-color: #20a030; }
        """)
        btn_maximize.clicked.connect(self.toggle_maximize)

        # Judul di tengah header (Opsional)
        lbl_header = QLabel("Haytech Store")
        lbl_header.setStyleSheet("color: #94a3b8; font-weight: bold; font-family: 'Segoe UI'; border: none;")
        lbl_header.setAlignment(Qt.AlignCenter)

        # Tambah ke layout
        title_layout.addWidget(btn_close)
        title_layout.addWidget(btn_minimize)
        title_layout.addWidget(btn_maximize)
        title_layout.addStretch() # Spacer agar judul ke tengah (atau tombol tetap di kiri)
        title_layout.addWidget(lbl_header)
        title_layout.addStretch() 

        # Tambahkan Title Bar ke Root Layout paling atas
        self.root_layout.addWidget(self.title_bar)

    def toggle_maximize(self):
        """Logika toggle maximize/restore"""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # === LOGIKA DRAG WINDOW (Karena frameless, window tidak bisa digeser tanpa ini) ===
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Hanya bisa drag jika klik di area Title Bar (Y < 50)
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

        # Judul Sidebar
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

        # Tombol Navigasi
        self.btn_dashboard = self.create_nav_button("Dashboard")
        self.btn_input = self.create_nav_button("Input Barang")
        self.btn_transaksi = self.create_nav_button("Transaksi")
        self.btn_laporan = self.create_nav_button("Laporan")

        # Grouping Tombol
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        
        self.nav_group.addButton(self.btn_dashboard)
        self.nav_group.addButton(self.btn_input)
        self.nav_group.addButton(self.btn_transaksi)
        self.nav_group.addButton(self.btn_laporan)

        self.btn_dashboard.setChecked(True)

        # Tambahkan ke layout
        self.sidebar_layout.addWidget(self.btn_dashboard)
        self.sidebar_layout.addWidget(self.btn_input)
        self.sidebar_layout.addWidget(self.btn_transaksi)
        self.sidebar_layout.addWidget(self.btn_laporan)
        self.sidebar_layout.addStretch()

        # Footer
        lbl_footer = QLabel("Copyright © 2025. \n Created by Tony & Satya")
        lbl_footer.setStyleSheet("color: #6c757d; font-size: 10px; padding-left: 20px;")
        self.sidebar_layout.addWidget(lbl_footer)

        self.main_layout.addWidget(self.sidebar_frame)

    def setup_pages(self):
        self.page_dashboard = self.create_page_dashboard()
        self.page_input = self.create_page_input()
        self.page_transaksi = self.create_page_transaksi()
        self.page_laporan = self.create_page_laporan()

        self.pages.addWidget(self.page_dashboard)
        self.pages.addWidget(self.page_input)
        self.pages.addWidget(self.page_transaksi)
        self.pages.addWidget(self.page_laporan)

    def connect_signals(self):
        self.btn_dashboard.clicked.connect(lambda: self.pages.setCurrentIndex(0))
        self.btn_input.clicked.connect(lambda: self.pages.setCurrentIndex(1))
        self.btn_transaksi.clicked.connect(lambda: self.pages.setCurrentIndex(2))
        self.btn_laporan.clicked.connect(lambda: self.pages.setCurrentIndex(3))

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
        
        # Header
        layout.addWidget(QLabel("Dashboard Operasional", objectName="PageTitle"))
        layout.addWidget(QLabel("Ringkasan kinerja toko hari ini."))
        layout.addSpacing(20)

        # Cards Statistik
        cards_layout = QHBoxLayout()
        
        # Ambil data dari database
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
        
        # Daftar Stok Kritis
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
        
        # Form Input Barang
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
        
        # Daftar Barang
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
        """Menyimpan data barang ke database"""
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
        """Reset form input barang"""
        self.input_nama.clear()
        self.input_harga.clear()
        self.input_stok.setValue(0)
        self.input_deskripsi.clear()

    def load_kategori_combo(self):
        """Memuat data kategori ke combobox"""
        query = "SELECT id, nama_kategori FROM kategori ORDER BY nama_kategori"
        categories = self.db.execute_query(query)
        
        self.input_kategori.clear()
        for category in categories:
            self.input_kategori.addItem(category['nama_kategori'], category['id'])

    def load_data_barang(self):
        """Memuat data barang dari database"""
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
            
            # Tombol Hapus
            btn_hapus = QPushButton("Hapus")
            btn_hapus.setStyleSheet("background-color: #ef4444; color: white;")
            btn_hapus.clicked.connect(lambda checked, id_barang=barang["id"]: self.hapus_barang(id_barang))
            self.table_barang.setCellWidget(row, 5, btn_hapus)

    def hapus_barang(self, id_barang):
        """Menghapus barang dari database"""
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
        
        # Area Pilih Barang
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
        
        # Area Keranjang
        cart_frame = QFrame(objectName="Card")
        cart_layout = QVBoxLayout(cart_frame)
        cart_layout.addWidget(QLabel("Keranjang Belanja"))
        
        self.table_keranjang = QTableWidget()
        self.table_keranjang.setColumnCount(5)
        self.table_keranjang.setHorizontalHeaderLabels(["Barang", "Harga", "Qty", "Subtotal", "Aksi"])
        self.table_keranjang.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        cart_layout.addWidget(self.table_keranjang)
        
        # Form Pembeli
        buyer_frame = QFrame(objectName="Card")
        buyer_layout = QHBoxLayout(buyer_frame)
        buyer_layout.addWidget(QLabel("Nama Pembeli:"))
        self.input_pembeli = QLineEdit()
        self.input_pembeli.setPlaceholderText("Nama customer")
        buyer_layout.addWidget(self.input_pembeli)
        buyer_layout.addStretch()
        
        cart_layout.addWidget(buyer_frame)
        
        # Total dan Tombol
        total_layout = QHBoxLayout()
        self.label_total = QLabel("Total: Rp 0")
        self.label_total.setStyleSheet("font-size: 18px; font-weight: bold; color: #1e293b;")
        
        btn_bayar = QPushButton("Proses Pembayaran")
        btn_bayar.setStyleSheet("background-color: #3b82f6; color: white; padding: 10px;")
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
        """Memuat data barang ke combobox"""
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
        """Menambah barang ke keranjang"""
        if self.combo_barang.currentData() is None:
            QMessageBox.warning(self, "Peringatan", "Tidak ada barang yang dipilih!")
            return
        
        id_barang = self.combo_barang.currentData()
        qty = self.spin_qty.value()
        
        # Ambil data barang dari database
        query = "SELECT id, nama_barang, harga, stok FROM barang WHERE id = %s"
        barang = self.db.execute_query(query, (id_barang,))
        
        if not barang:
            return
        
        barang = barang[0]
        
        # Cek stok
        if qty > barang["stok"]:
            QMessageBox.warning(self, "Peringatan", f"Stok tidak mencukupi! Stok tersedia: {barang['stok']}")
            return
        
        # Cek apakah barang sudah ada di keranjang
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
        """Update tampilan keranjang belanja"""
        self.table_keranjang.setRowCount(len(self.keranjang))
        total_semua = 0
        
        for row, item in enumerate(self.keranjang):
            subtotal = item["harga"] * item["qty"]
            total_semua += subtotal
            
            self.table_keranjang.setItem(row, 0, QTableWidgetItem(item["nama"]))
            self.table_keranjang.setItem(row, 1, QTableWidgetItem(f"Rp {item['harga']:,}"))
            self.table_keranjang.setItem(row, 2, QTableWidgetItem(str(item["qty"])))
            self.table_keranjang.setItem(row, 3, QTableWidgetItem(f"Rp {subtotal:,}"))
            
            # Tombol hapus
            btn_hapus = QPushButton("Hapus")
            btn_hapus.setStyleSheet("background-color: #ef4444; color: white;")
            btn_hapus.clicked.connect(lambda checked, r=row: self.hapus_dari_keranjang(r))
            self.table_keranjang.setCellWidget(row, 4, btn_hapus)
        
        self.label_total.setText(f"Total: Rp {total_semua:,}")

    def hapus_dari_keranjang(self, row):
        """Hapus item dari keranjang"""
        if 0 <= row < len(self.keranjang):
            self.keranjang.pop(row)
            self.update_tampilan_keranjang()

    def kosongkan_keranjang(self):
        """Kosongkan semua keranjang"""
        self.keranjang.clear()
        self.update_tampilan_keranjang()

    def proses_pembayaran(self):
        """Proses pembayaran transaksi"""
        if not self.keranjang:
            QMessageBox.warning(self, "Peringatan", "Keranjang belanja kosong!")
            return
        
        if not self.input_pembeli.text().strip():
            QMessageBox.warning(self, "Peringatan", "Nama pembeli harus diisi!")
            return
        
        total = sum(item["harga"] * item["qty"] for item in self.keranjang)
        nama_pembeli = self.input_pembeli.text().strip()
        
        try:
            # Mulai transaction
            self.db.connection.start_transaction()
            
            # 1. Insert ke tabel transaksi
            query_transaksi = """
                INSERT INTO transaksi (nama_pembeli, total) 
                VALUES (%s, %s)
            """
            id_transaksi = self.db.execute_query(query_transaksi, (nama_pembeli, total))
            
            if not id_transaksi:
                raise Exception("Gagal menyimpan transaksi")
            
            # 2. Insert ke detail_transaksi dan update stok
            for item in self.keranjang:
                subtotal = item["harga"] * item["qty"]
                
                # Insert detail transaksi
                query_detail = """
                    INSERT INTO detail_transaksi (id_transaksi, id_barang, qty, harga, subtotal)
                    VALUES (%s, %s, %s, %s, %s)
                """
                self.db.execute_query(query_detail, (id_transaksi, item["id_barang"], item["qty"], item["harga"], subtotal))
                
                # Update stok barang
                query_update_stok = "UPDATE barang SET stok = stok - %s WHERE id = %s"
                self.db.execute_query(query_update_stok, (item["qty"], item["id_barang"]))
            
            # Commit transaction
            self.db.connection.commit()
            
            QMessageBox.information(self, "Sukses", 
                                  f"Transaksi berhasil!\nID Transaksi: {id_transaksi}\nTotal: Rp {total:,}")
            
            self.kosongkan_keranjang()
            self.input_pembeli.clear()
            self.load_combo_barang()  # Refresh stok
            
        except Exception as e:
            self.db.connection.rollback()
            QMessageBox.critical(self, "Error", f"Terjadi kesalahan: {str(e)}")

    # === HALAMAN LAPORAN ===
    def create_page_laporan(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Laporan Penjualan", objectName="PageTitle"))
        
        # Filter
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
        
        btn_export = QPushButton("Export PDF")
        btn_export.setStyleSheet("background-color: #10b981; color: white;")
        btn_export.clicked.connect(self.export_pdf)
        
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(btn_filter)
        filter_layout.addWidget(btn_export)
        filter_layout.addStretch()
        
        layout.addWidget(filter_frame)
        
        # Tabel Laporan
        self.table_laporan = QTableWidget()
        self.table_laporan.setColumnCount(6)
        self.table_laporan.setHorizontalHeaderLabels(["ID", "Tanggal", "Pembeli", "Items", "Total", "Detail"])
        self.table_laporan.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(self.table_laporan)
        
        # Load data awal
        self.filter_laporan()
        
        return page

    def filter_laporan(self):
        date_from = self.date_from.date().toString("yyyy-MM-dd")
        date_to = self.date_to.date().toString("yyyy-MM-dd")
        
        query = """
            SELECT t.id, t.tanggal_transaksi, t.nama_pembeli, t.total,
                   COUNT(dt.id) as jumlah_item
            FROM transaksi t
            LEFT JOIN detail_transaksi dt ON t.id = dt.id_transaksi
            WHERE DATE(t.tanggal_transaksi) BETWEEN %s AND %s
            GROUP BY t.id
            ORDER BY t.tanggal_transaksi DESC
        """
        transaksi_list = self.db.execute_query(query, (date_from, date_to))
        
        self.table_laporan.setRowCount(len(transaksi_list))
        
        for row, transaksi in enumerate(transaksi_list):
            self.table_laporan.setItem(row, 0, QTableWidgetItem(str(transaksi["id"])))
            self.table_laporan.setItem(row, 1, QTableWidgetItem(str(transaksi["tanggal_transaksi"])))
            self.table_laporan.setItem(row, 2, QTableWidgetItem(transaksi["nama_pembeli"]))
            self.table_laporan.setItem(row, 3, QTableWidgetItem(str(transaksi["jumlah_item"])))
            self.table_laporan.setItem(row, 4, QTableWidgetItem(f"Rp {transaksi['total']:,}"))
            
            # Tombol Detail
            btn_detail = QPushButton("Lihat Detail")
            btn_detail.setStyleSheet("background-color: #3b82f6; color: white;")
            btn_detail.clicked.connect(lambda checked, id_transaksi=transaksi["id"]: self.lihat_detail_transaksi(id_transaksi))
            self.table_laporan.setCellWidget(row, 5, btn_detail)

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

    def export_pdf(self):
        QMessageBox.information(self, "Export PDF", "Fitur export PDF akan diimplementasikan kemudian")

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

    def closeEvent(self, event):
        """Menutup koneksi database saat aplikasi ditutup"""
        self.db.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernDashboard()
    window.show()
    sys.exit(app.exec_())