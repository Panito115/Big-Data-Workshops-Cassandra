#!/usr/bin/env python3
"""Carga los CSV de G1-spotify en el keyspace spotify_20240841.

Lee los cinco CSV, resuelve en memoria los JOIN que Cassandra no tiene y carga
las cuatro tablas de modelo.cql con COPY FROM de cqlsh.

Se puede correr dos veces sin duplicar nada: el INSERT de Cassandra es upsert y
todas las llaves salen de los CSV.

    python3 entregas/G1/20240841-juan-madriz/mini-reto/carga.py
"""
import csv
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NODO = "cassandra1"
KEYSPACE = "spotify_20240841"
REINTENTOS = 3
ORIGEN = Path(__file__).resolve().parents[4] / "data" / "mini-reto" / "G1-spotify"
DESTINO = "/tmp/carga_20240841"

# Los CSV traen la hora en UTC sin zona; le pego el +0000 para que cqlsh no la
# interprete en otra. Es la opcion DATETIMEFORMAT de COPY FROM.
FORMATO_FECHA = "%Y-%m-%d %H:%M:%S%z"


def leer(nombre):
    # newline='' para que los \r\n del archivo no se cuelen en el ultimo campo
    with open(ORIGEN / f"{nombre}.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def escribir(carpeta, nombre, columnas, filas):
    with open(carpeta / f"{nombre}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(columnas)
        w.writerows(filas)


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True)


def cqlsh(comando):
    return docker("exec", "-i", NODO, "cqlsh", "--request-timeout=120", "-e", comando)


def copy_from(tabla, columnas):
    """COPY FROM con reintentos: el enlace entre laptops anda en 200-500 ms."""
    comando = (
        f"COPY {KEYSPACE}.{tabla} ({', '.join(columnas)}) "
        f"FROM '{DESTINO}/{tabla}.csv' "
        f"WITH HEADER = true AND ENCODING = 'utf8' "
        f"AND DATETIMEFORMAT = '{FORMATO_FECHA}' AND MAXATTEMPTS = 5;"
    )
    for intento in range(1, REINTENTOS + 1):
        r = cqlsh(comando)
        salida = (r.stdout + r.stderr).strip()
        if r.returncode == 0 and "rows imported" in salida and "Failed to import" not in salida:
            for linea in salida.splitlines():
                if "rows imported" in linea:
                    print(f"  {tabla}: {linea.strip()}")
            return True
        print(f"  {tabla}: intento {intento} de {REINTENTOS} fallo", file=sys.stderr)
        for linea in salida.splitlines()[-4:]:
            print(f"    {linea}", file=sys.stderr)
    return False


def contar(tabla):
    r = cqlsh(f"SELECT count(*) FROM {KEYSPACE}.{tabla};")
    for linea in r.stdout.splitlines():
        if linea.strip().isdigit():
            return int(linea.strip())
    return -1


def main():
    usuarios = leer("usuarios")
    canciones = leer("canciones")
    playlist_canciones = leer("playlist_canciones")
    reproducciones = leer("reproducciones")
    print(f"CSV leidos: usuarios={len(usuarios)} canciones={len(canciones)} "
          f"playlist_canciones={len(playlist_canciones)} reproducciones={len(reproducciones)}")

    # El JOIN: canciones indexada por su llave para pegarle titulo y artista a
    # las filas de reproducciones y de playlist_canciones.
    cancion = {c["cancion_id"]: c for c in canciones}
    utc = lambda t: t.strip() + "+0000"

    tablas = {
        "usuarios_por_id": (
            ["usuario_id", "nombre", "pais", "plan"],
            [[u["usuario_id"], u["nombre"], u["pais"], u["plan"]] for u in usuarios],
        ),
        "reproducciones_por_usuario": (
            ["usuario_id", "reproducida_en", "reproduccion_id", "cancion_id", "titulo", "artista"],
            [[r["usuario_id"], utc(r["reproducida_en"]), r["reproduccion_id"], r["cancion_id"],
              cancion[r["cancion_id"]]["titulo"], cancion[r["cancion_id"]]["artista"]]
             for r in reproducciones],
        ),
        "canciones_por_playlist": (
            ["playlist_id", "posicion", "cancion_id", "titulo", "artista"],
            [[p["playlist_id"], p["posicion"], p["cancion_id"],
              cancion[p["cancion_id"]]["titulo"], cancion[p["cancion_id"]]["artista"]]
             for p in playlist_canciones],
        ),
        # Las mismas reproducciones, pero particionadas por (cancion, dia).
        "reproducciones_por_cancion_dia": (
            ["cancion_id", "dia", "reproducida_en", "reproduccion_id", "usuario_id"],
            [[r["cancion_id"], r["reproducida_en"][:10], utc(r["reproducida_en"]),
              r["reproduccion_id"], r["usuario_id"]]
             for r in reproducciones],
        ),
    }

    carpeta = Path(tempfile.mkdtemp(prefix="carga_20240841_"))
    try:
        docker("exec", NODO, "mkdir", "-p", DESTINO)
        for tabla, (columnas, filas) in tablas.items():
            escribir(carpeta, tabla, columnas, filas)
            r = docker("cp", str(carpeta / f"{tabla}.csv"), f"{NODO}:{DESTINO}/{tabla}.csv")
            if r.returncode != 0:
                print(f"No pude copiar {tabla}.csv: {r.stderr}", file=sys.stderr)
                return 1

        print("Cargando con COPY FROM")
        for tabla, (columnas, _) in tablas.items():
            if not copy_from(tabla, columnas):
                print(f"La carga de {tabla} fallo despues de {REINTENTOS} intentos", file=sys.stderr)
                return 1

        print("Verificando")
        malas = 0
        for tabla, (_, filas) in tablas.items():
            n = contar(tabla)
            print(f"  {tabla}: {n} filas en Cassandra, {len(filas)} en los CSV "
                  f"-> {'OK' if n == len(filas) else 'NO COINCIDE'}")
            malas += n != len(filas)
        if malas:
            return 1
    finally:
        docker("exec", NODO, "rm", "-rf", DESTINO)
        shutil.rmtree(carpeta, ignore_errors=True)

    print("Carga terminada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
