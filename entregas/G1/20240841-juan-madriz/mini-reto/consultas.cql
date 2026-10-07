-- Mini-reto G1 - Spotify · carne 20240841
-- Las cuatro consultas de consultas.sql, en CQL, con los mismos parametros.

-- C1. Perfil de un usuario.
SELECT usuario_id, nombre, pais, plan
FROM spotify_20240841.usuarios_por_id
WHERE usuario_id = 'u116';

-- C2. Las 10 canciones que el usuario escucho mas recientemente.
SELECT reproducida_en, titulo, artista
FROM spotify_20240841.reproducciones_por_usuario
WHERE usuario_id = 'u031'
LIMIT 10;

-- C3. Las canciones de una playlist, en su orden.
SELECT posicion, titulo, artista
FROM spotify_20240841.canciones_por_playlist
WHERE playlist_id = 'p15';

-- C4. Cuantas veces se reprodujo una cancion en un dia.
SELECT count(*) AS reproducciones
FROM spotify_20240841.reproducciones_por_cancion_dia
WHERE cancion_id = 'c017' AND dia = '2026-09-09';
