# 1. Boceto inicial (a mano alzada)

![Boceto a mano](../diagramas/boceto-a-mano.svg)

> **Nota:** este boceto es una versión digital con estilo de dibujo a mano. Si la pauta exige que el boceto esté hecho físicamente a mano, cópialo en papel tal cual (son 4 capas: usuarios → nube Cloudflare → 3 regiones → datos y backups), sácale una foto y guárdala como `diagramas/boceto-a-mano.jpg`.

## Cómo leer el boceto (de arriba hacia abajo)

1. **Usuarios:** miles de personas abren la web en el navegador. Ven el lienzo y pintan 1 pixel cada 5 minutos.
2. **Cloudflare (la nube):** es la "puerta de entrada" mundial.
   - Entrega la página y una **imagen PNG del lienzo** desde su caché (CDN), así el backend no recibe esas peticiones.
   - Filtra ataques (DDoS) y bots.
   - Envía a cada usuario a la **región más cercana**.
3. **Tres regiones (América, Europa, Asia), todas activas al mismo tiempo.** Cada una tiene:
   - **WS Gateway (Go):** mantiene abierta la conexión WebSocket de cada usuario para enviarle los pixeles nuevos al instante.
   - **Pixel service (Go):** revisa que el pixel sea válido y que el usuario respete su tiempo de espera.
   - **Redis:** guarda el lienzo completo **en memoria** (pesa solo 4 MB), por eso responde en menos de 1 ms.
4. **NATS JetStream (línea azul punteada):** cada pixel se publica como un "evento" y llega a **todas** las regiones en ~150 ms. Así todas tienen el mismo dibujo.
5. **ScyllaDB multi-región:** guarda el **historial** de todos los pixeles y los usuarios. No tiene un servidor "jefe": se puede escribir en cualquier región, así que si una cae las demás siguen.
6. **S3 / R2 (backups):** foto del lienzo cada 5 minutos, respaldo diario de la base de datos, copias que **no se pueden borrar** (inmutables) y copiadas a otra región.

## Ideas principales anotadas en rojo

- **"Todas activas a la vez":** no hay un servidor de respaldo esperando sin uso; si se cae una región, el DNS manda a sus usuarios a la siguiente.
- **"Si se cae la DB, igual se ve el lienzo":** el lienzo vive en Redis y en el CDN; la base de datos solo guarda el historial. El sistema **se degrada** en vez de caerse.
- **"La imagen sale del CDN":** la operación más frecuente (cargar la página) no toca nuestros servidores.

Las justificaciones detalladas están en [02-decisiones-tecnologicas.md](02-decisiones-tecnologicas.md).
