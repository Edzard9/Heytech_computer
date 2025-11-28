import mysql.connector
from mysql.connector import Error

def create_connection(db_name=None):
    """Membuat koneksi ke database MySQL."""
    try:
        config = {
            'host': 'localhost',
            'user': 'root',
            'password': '', 
        }
        
        if db_name:
            config['database'] = db_name

        connection = mysql.connector.connect(**config)
        return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

def init_db():
    conn = create_connection()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("CREATE DATABASE IF NOT EXISTS toko_komputer")
            print("Database 'toko_komputer' berhasil dibuat atau sudah ada.")
        except Error as e:
            print(f"Error creating database: {e}")
        finally:
            cursor.close()
            conn.close()

    conn = create_connection("toko_komputer")
    if conn:
        cursor = conn.cursor()
        try:
            tables = {}
            
            tables['kategori'] = """
            CREATE TABLE IF NOT EXISTS kategori (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nama_kategori VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """

            tables['barang'] = """
            CREATE TABLE IF NOT EXISTS barang (
                id INT AUTO_INCREMENT PRIMARY KEY,
                nama_barang VARCHAR(255) NOT NULL,
                id_kategori INT,
                harga DECIMAL(15,2) NOT NULL,
                stok INT NOT NULL DEFAULT 0,
                deskripsi TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (id_kategori) REFERENCES kategori(id)
            )
            """

            tables['transaksi'] = """
            CREATE TABLE IF NOT EXISTS transaksi (
                id INT AUTO_INCREMENT PRIMARY KEY,
                tanggal_transaksi DATETIME DEFAULT CURRENT_TIMESTAMP,
                nama_pembeli VARCHAR(255) NOT NULL,
                total DECIMAL(15,2) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """

            tables['detail_transaksi'] = """
            CREATE TABLE IF NOT EXISTS detail_transaksi (
                id INT AUTO_INCREMENT PRIMARY KEY,
                id_transaksi INT,
                id_barang INT,
                qty INT NOT NULL,
                harga DECIMAL(15,2) NOT NULL,
                subtotal DECIMAL(15,2) NOT NULL,
                FOREIGN KEY (id_transaksi) REFERENCES transaksi(id) ON DELETE CASCADE,
                FOREIGN KEY (id_barang) REFERENCES barang(id)
            )
            """

            for name, ddl in tables.items():
                cursor.execute(ddl)
                print(f"Tabel '{name}' siap.")

            cursor.execute("SELECT COUNT(*) FROM kategori")
            if cursor.fetchone()[0] == 0:
                sql_kategori = "INSERT INTO kategori (nama_kategori) VALUES (%s)"
                val_kategori = [
                    ('Processor',), ('Motherboard',), ('RAM'), ('SSD/HDD'),
                    ('VGA'), ('Power Supply'), ('Casing'), ('Monitor'),
                    ('Keyboard'), ('Mouse')
                ]
                cursor.executemany(sql_kategori, val_kategori)
                print(f"{cursor.rowcount} kategori berhasil ditambahkan.")
                conn.commit() 
                sql_barang = """
                INSERT INTO barang (nama_barang, id_kategori, harga, stok, deskripsi) 
                VALUES (%s, %s, %s, %s, %s)
                """
                val_barang = [
                    ('Intel Core i5-12400F', 1, 2450000, 10, 'Processor Intel Gen 12'),
                    ('AMD Ryzen 5 5600X', 1, 2850000, 8, 'Processor AMD Ryzen 5'),
                    ('ASUS Prime B660M-A', 2, 1850000, 5, 'Motherboard Intel LGA 1700'),
                    ('Gigabyte B550 AORUS ELITE', 2, 2200000, 6, 'Motherboard AMD AM4'),
                    ('Corsair Vengeance LPX 16GB DDR4', 3, 850000, 15, 'RAM DDR4 3200MHz'),
                    ('Team T-Force Delta RGB 32GB DDR4', 3, 1450000, 12, 'RAM RGB DDR4 3200MHz'),
                    ('Samsung 970 EVO Plus 1TB NVMe', 4, 1850000, 7, 'SSD NVMe PCIe 3.0'),
                    ('WD Blue SN570 1TB NVMe', 4, 1650000, 9, 'SSD NVMe PCIe 3.0'),
                    ('NVIDIA RTX 4060 8GB', 5, 6250000, 4, 'VGA Card NVIDIA RTX 4060'),
                    ('AMD Radeon RX 7600 8GB', 5, 4850000, 5, 'VGA Card AMD Radeon')
                ]
                cursor.executemany(sql_barang, val_barang)
                print(f"{cursor.rowcount} barang berhasil ditambahkan.")
                
                conn.commit()
            else:
                print("Data awal sudah ada, melewati proses seeding.")

        except Error as e:
            print(f"Error saat setup tabel/data: {e}")
            conn.rollback() 
        finally:
            cursor.close()
            conn.close()
            print("Koneksi ditutup.")

if __name__ == "__main__":
    init_db()