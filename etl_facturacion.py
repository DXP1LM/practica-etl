import csv
import mysql.connector
from mysql.connector import Error


DB_CONFIG = {
    "host": "localhost",
    "user": "root",      
    "password": "MySQL",
    "database": "saludMedica"
}

CSV_FILE = "citas_dia.csv"


def obtener_conexion():
    """Establece y retorna la conexión a la base de datos saludMedica."""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print(f"[ERROR CRÍTICO] No se pudo conectar a MySQL: {e}")
        return None


def crear_tabla_si_no_existe(cursor):
    """Crea la tabla facturacion_citas con las columnas especificadas si no existe."""
    query = """
    CREATE TABLE IF NOT EXISTS facturacion_citas (
        id INT AUTO_INCREMENT PRIMARY KEY,
        paciente VARCHAR(150) NOT NULL,
        especialidad VARCHAR(100) NOT NULL,
        costo_base DECIMAL(10, 2) NOT NULL,
        descuento DECIMAL(10, 2) NOT NULL,
        igv DECIMAL(10, 2) NOT NULL,
        total DECIMAL(10, 2) NOT NULL
    );
    """
    cursor.execute(query)


def ejecutar_etl():
    conn = obtener_conexion()
    if not conn:
        return

    cursor = conn.cursor()
    crear_tabla_si_no_existe(cursor)

    registros_validos = []
    exitosos = 0
    descartados = 0

    print("=" * 65)
    print(" INICIANDO PROCESO ETL: FACTURACIÓN MÉDICA")
    print("=" * 65)

    try:
        with open(CSV_FILE, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)

            for fila_num, row in enumerate(reader, start=2):  # Fila 2 = primer registro tras header
                paciente = row.get("paciente", "").strip()
                especialidad = row.get("especialidad", "").strip()
                costo_raw = row.get("costo_base", "").strip()

                try:
                    # 1. Validación de conversión numérica
                    costo_base = float(costo_raw)

                    # 2. Validación de reglas de negocio: especialidad vacía o costo <= 0
                    if not especialidad:
                        print(f"[-] Fila {fila_num} descartada: Especialidad vacía para el paciente '{paciente}'.")
                        descartados += 1
                        continue

                    if costo_base <= 0:
                        print(f"[-] Fila {fila_num} descartada: Costo base no válido ({costo_base}) para '{paciente}'.")
                        descartados += 1
                        continue

                    # 3. Aplicación de descuentos
                    # Consideramos coincidencia estándar para "Pediatria" (con o sin tilde)
                    if especialidad.lower() in ["pediatria", "pediatría"]:
                        descuento = round(costo_base * 0.10, 2)
                    else:
                        descuento = 0.0

                    # 4. Cálculo de Impuestos (IGV 18% sobre el monto con descuento)
                    subtotal = costo_base - descuento
                    igv = round(subtotal * 0.18, 2)

                    # 5. Cálculo del Total a Pagar
                    total = round(subtotal + igv, 2)

                    registros_validos.append((
                        paciente,
                        especialidad,
                        costo_base,
                        descuento,
                        igv,
                        total
                    ))
                    exitosos += 1

                except (ValueError, TypeError):
                    print(f"[-] Fila {fila_num} descartada: Error de conversión de datos en costo_base ('{costo_raw}').")
                    descartados += 1

    except FileNotFoundError:
        print(f"[ERROR] No se encontró el archivo '{CSV_FILE}' en la raíz del proyecto.")
        cursor.close()
        conn.close()
        return

    # Inserción en la base de datos (Load)
    if registros_validos:
        insert_query = """
        INSERT INTO facturacion_citas (paciente, especialidad, costo_base, descuento, igv, total)
        VALUES (%s, %s, %s, %s, %s, %s);
        """
        cursor.executemany(insert_query, registros_validos)
        conn.commit()

    cursor.close()
    conn.close()

    # Reporte consolidado de ejecución
    print("\n" + "=" * 65)
    print(" RESUMEN DE EJECUCIÓN")
    print("=" * 65)
    print(f" Total de registros procesados con éxito : {exitosos}")
    print(f" Total de registros descartados por errores : {descartados}")
    print("=" * 65)


if __name__ == "__main__":
    ejecutar_etl()