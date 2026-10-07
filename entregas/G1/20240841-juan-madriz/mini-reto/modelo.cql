-- Mini-reto G1 - Spotify · carne 20240841
-- Una tabla por consulta de consultas.sql. titulo y artista van duplicados
-- porque en SQL salen del JOIN con canciones y Cassandra no tiene JOIN.

CREATE KEYSPACE IF NOT EXISTS spotify_20240841
  WITH replication = {'class': 'NetworkTopologyStrategy', 'dc-g1': 3};

-- C1
CREATE TABLE IF NOT EXISTS spotify_20240841.usuarios_por_id (
  usuario_id text,
  nombre     text,
  pais       text,
  plan       text,
  PRIMARY KEY ((usuario_id))
);

-- C2. reproducida_en DESC para que el LIMIT 10 solo lea las 10 primeras filas
-- de la particion. reproduccion_id desempata si dos caen en el mismo segundo.
CREATE TABLE IF NOT EXISTS spotify_20240841.reproducciones_por_usuario (
  usuario_id      text,
  reproducida_en  timestamp,
  reproduccion_id int,
  cancion_id      text,
  titulo          text,
  artista         text,
  PRIMARY KEY ((usuario_id), reproducida_en, reproduccion_id)
) WITH CLUSTERING ORDER BY (reproducida_en DESC, reproduccion_id ASC);

-- C3. posicion ASC es el ORDER BY del SQL. cancion_id cierra la llave porque
-- en schema.sql la PK es (playlist_id, cancion_id) y posicion no es unica.
CREATE TABLE IF NOT EXISTS spotify_20240841.canciones_por_playlist (
  playlist_id text,
  posicion    int,
  cancion_id  text,
  titulo      text,
  artista     text,
  PRIMARY KEY ((playlist_id), posicion, cancion_id)
) WITH CLUSTERING ORDER BY (posicion ASC, cancion_id ASC);

-- C4. El rango del SQL es un dia exacto, asi que el dia va en la partition key
-- y el COUNT lee una sola particion. dia sale de reproducida_en en UTC.
CREATE TABLE IF NOT EXISTS spotify_20240841.reproducciones_por_cancion_dia (
  cancion_id      text,
  dia             date,
  reproducida_en  timestamp,
  reproduccion_id int,
  usuario_id      text,
  PRIMARY KEY ((cancion_id, dia), reproducida_en, reproduccion_id)
) WITH CLUSTERING ORDER BY (reproducida_en ASC, reproduccion_id ASC);
