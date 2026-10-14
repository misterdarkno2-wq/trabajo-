# 2. Decisiones de arquitectura y su fundamento

Este documento defiende cada decisión. Para cada una indico **qué elegí**, **por qué** (con números cuando se puede) y **qué descarté y por qué**.

---

## 2.1 Entender el problema antes de elegir tecnología

Un lienzo colaborativo tipo *r/place* tiene un perfil de carga muy particular:

| Característica | Valor estimado | Consecuencia de diseño |
|---|---|---|
| Lienzo | 2000 × 2000 = 4 millones de pixeles | Con 1 byte por pixel (paleta de 256 colores) el lienzo completo pesa **4 MB**: cabe entero en memoria RAM. |
| Usuarios simultáneos | 100.000 (con margen hasta 1.000.000) | Hacen falta **conexiones persistentes** (WebSocket) y servidores que aguanten muchas a la vez. |
| Escrituras | 1 pixel cada 5 min por usuario → ~330 escrituras/s de media, picos de ~10.000/s | Las escrituras son **pocas y pequeñas**. |
| Lecturas / difusión | Cada pixel nuevo se envía a **todos** los conectados | El cuello de botella es la **difusión (fan-out)**, no la base de datos. |
| Conflictos | Dos personas pintan el mismo pixel | **Gana el último** (*last-writer-wins*): no hace falta consistencia fuerte global. |

**Conclusión clave:** el sistema es de *lectura masiva en tiempo real y escritura pequeña*. Por eso:

1. El estado "caliente" (el lienzo) vive en **memoria**, no en la base de datos.
2. La base de datos es para **durabilidad e historial**, no para servir cada lectura.
3. No necesitamos transacciones globales: podemos aceptar **consistencia eventual** entre regiones (un pixel tarda ~150 ms en verse al otro lado del mundo, algo imperceptible en un juego de dibujo). Esto, según el **teorema CAP**, nos permite priorizar **Disponibilidad + Tolerancia a particiones (AP)**, que es justo lo que piden los requisitos.

---

## 2.2 Estilo arquitectónico: multi-región **activo-activo**

**Elegido:** 4 regiones (São Paulo, Virginia, Irlanda, Tokio) atendiendo tráfico **al mismo tiempo**, cada una con el stack completo.

**Por qué:**

- **Disponibilidad 99,9%** = como máximo **8 h 45 min de caída al año** (43 min al mes). Una sola región de nube tiene incidentes de varias horas al año; con una sola región ya estaríamos rozando el límite.
- Con regiones independientes, si cada una tuviera solo 99,5% de disponibilidad, la probabilidad de que caigan **todas a la vez** es 0,005⁴ ≈ 0,0000000006 → la disponibilidad teórica del conjunto supera ampliamente el 99,9%. El límite real lo ponen los componentes globales compartidos (DNS/borde), por eso elegimos uno con SLA de 100%.
- **Baja latencia:** la luz en fibra tarda ~100 ms en ir de Santiago a Tokio. Ningún software arregla eso; la única solución es **tener servidores cerca del usuario**. Con 4 regiones la mayoría de los usuarios queda a < 50 ms de RTT.
- **Activo-activo vs activo-pasivo:** en activo-pasivo la región de respaldo está "fría", nadie sabe si funciona hasta el día del desastre, y el *failover* tarda minutos. En activo-activo **todas las regiones se prueban con tráfico real todos los días**, y una caída solo implica redirigir usuarios (< 30 s).

**Descartado:** monolito en una región con réplica de lectura → no cumple ni latencia mundial ni disponibilidad.

---

## 2.3 Borde global: **Cloudflare** (DNS Anycast, CDN, WAF, balanceo)

**Por qué:**

- **Anycast + 300 puntos de presencia:** el usuario termina TLS en el PoP más cercano (ahorra 1–2 viajes de ida y vuelta en el *handshake*) → menos latencia.
- **Load balancing con health checks:** si una región falla sus *health checks*, Cloudflare deja de enviarle tráfico automáticamente. Ese es nuestro mecanismo de **failover**.
- **CDN para el lienzo:** el 99% de las cargas de página solo necesitan "la imagen actual". Un PNG del lienzo se regenera cada 5 s y se sirve desde caché → el backend **no recibe** esas peticiones. Además, si TODO el backend cayera, el lienzo sigue visible (degradación elegante).
- **Protección DDoS y WAF:** un sitio público de este tipo es blanco de bots y ataques. Sin esto, la disponibilidad dependería de la buena voluntad de terceros.

**Descartado:** solo el DNS de un proveedor de nube (Route 53 / Cloud DNS) → funciona, pero no tiene CDN + anti-DDoS + anti-bots integrados y nos ata a un solo proveedor en la pieza más crítica.

---

## 2.4 Comunicación en tiempo real: **WebSocket**

**Por qué:** el usuario debe ver los pixeles de otros **al instante**. Opciones:

| Opción | Problema |
|---|---|
| *Polling* HTTP cada segundo | 100.000 usuarios × 1 req/s = 100.000 req/s casi siempre vacías. Caro y con hasta 1 s de retraso. |
| Server-Sent Events | Solo servidor→cliente; el pixel del usuario iría por otro canal. Válido, pero menos simétrico. |
| **WebSocket** | Una sola conexión persistente bidireccional, mensajes de pocos bytes, latencia mínima. ✅ |

Los cambios se envían **agrupados cada 100 ms** (un solo mensaje con todos los pixeles de ese intervalo) para no saturar la red ni el navegador.

---

## 2.5 Backend: **Go (Golang)** sobre **Kubernetes**

**Por qué Go:**

1. **Concurrencia barata:** cada conexión WebSocket es una *goroutine* de ~4 KB. Un servidor de 8 GB maneja ~50.000 conexiones con holgura. En Java o Node tradicionales cada conexión es más costosa (hilos de ~1 MB o un solo hilo para todo).
2. **Latencia predecible:** el recolector de basura de Go tiene pausas por debajo de 1 ms; en un sistema de tiempo real las pausas largas se ven como "tirones".
3. **Binario único y pequeño:** imágenes de contenedor de ~20 MB que arrancan en < 1 s → el **autoescalado** responde rápido ante un pico (por ejemplo, cuando un streamer famoso invita a su comunidad).
4. **Ecosistema maduro** para exactamente lo que usamos: clientes oficiales de Redis, NATS (escrito en Go), ScyllaDB/Cassandra (gocql), OpenTelemetry, Kubernetes.
5. **Fácil de aprender y mantener:** lenguaje pequeño, ideal para que un equipo nuevo sea productivo.

**Microservicios (pocos y con propósito claro):**

| Servicio | Responsabilidad | Por qué separado |
|---|---|---|
| `ws-gateway` | Mantener conexiones, validar JWT, difundir cambios | Escala por **nº de conexiones**; es lo que más crece. |
| `pixel-service` | Validar pixel y *cooldown*, publicar evento | Escala por **escrituras**; lógica de negocio aislada. |
| `canvas-applier` | Aplicar eventos de todas las regiones al Redis local | Consistencia entre regiones. |
| `persister` | Guardar eventos en ScyllaDB en lotes | Si la DB está lenta, **no frena** a los usuarios. |
| `snapshotter` | Generar PNG para CDN y backups | Trabajo pesado fuera del camino crítico. |

Todos son **sin estado (stateless)**: cualquier pod puede morir y otro lo reemplaza sin pérdida.

**Por qué Kubernetes:** reinicio automático de pods caídos, distribución en **3 zonas de disponibilidad** por región, autoescalado horizontal (HPA), despliegues progresivos sin caída (*rolling / canary*) y el **mismo manifiesto** en las 4 regiones (GitOps con ArgoCD).

**Alternativas consideradas:**

- **Elixir/Phoenix:** excelente para conexiones masivas y tolerancia a fallos (máquina virtual BEAM). Lo descarté por la menor disponibilidad de desarrolladores y librerías; Go logra la resiliencia **a nivel de arquitectura** (réplicas, regiones) en vez de a nivel de lenguaje.
- **Node.js:** productivo, pero un solo hilo por proceso y GC menos predecible bajo cientos de miles de conexiones.
- **Serverless (Lambda/Cloud Functions):** no está pensado para conexiones persistentes largas y el costo por conexión-minuto se dispara con miles de usuarios conectados durante horas.

---

## 2.6 Base de datos: **dos niveles** (Redis/Valkey + ScyllaDB)

Una sola base de datos no puede ser a la vez la más rápida y la más durable. Separo responsabilidades:

### Nivel caliente: **Redis / Valkey Cluster** (por región)

- El lienzo completo se guarda como un **BITFIELD** de 4 MB: pintar un pixel es `BITFIELD canvas SET u8 #offset color`, operación **O(1) en < 1 ms**. Leer el lienzo entero es un solo `GET`.
- El *cooldown* (1 pixel cada 5 min) se resuelve con `SET user:{id}:cd 1 NX EX 300` dentro de un **script Lua atómico**: imposible saltarse el límite con peticiones simultáneas.
- Pub/Sub local para avisar a los gateways.
- 3 primarios + 3 réplicas repartidos en 3 zonas → si cae un nodo, su réplica asciende automáticamente.
- *Valkey* es el fork open-source (licencia BSD) de Redis, compatible al 100%; cualquiera de los dos sirve.

### Nivel durable: **ScyllaDB** (multi-región)

**Por qué ScyllaDB:**

1. **Sin maestro (masterless):** todos los nodos aceptan lecturas y escrituras. No existe "el primario" que pueda caerse → **no hay failover de base de datos**, simplemente se sigue escribiendo en los nodos vivos. Esto es exactamente **resiliencia**.
2. **Multi-región nativo:** con `NetworkTopologyStrategy` cada región es un *datacenter* con 3 copias de cada dato; escribimos con `LOCAL_QUORUM` (2 de 3 nodos **locales**) → la latencia de escritura es local (~2 ms) y la replicación a otros continentes es asíncrona.
3. **Optimizada para escrituras:** su motor (LSM-tree) es ideal para un registro de eventos que solo crece (*append-only*), justo nuestro caso.
4. **Last-Writer-Wins incorporado:** cada celda tiene un timestamp; el conflicto "dos personas pintan el mismo pixel" se resuelve solo.
5. Compatible con Cassandra (mismo protocolo y CQL) pero escrito en C++: menor latencia de cola (p99) y menos nodos para la misma carga.

**Modelo de datos (resumen):**

```sql
-- Historial inmutable (event sourcing): permite reconstruir el lienzo en cualquier instante
CREATE TABLE pixel_events (
  bucket      int,          -- hora del evento (particiona por tiempo)
  ts          timeuuid,
  x int, y int, color tinyint, user_id uuid, region text,
  PRIMARY KEY ((bucket), ts)
);

-- Último estado de cada pixel (para auditoría y "¿quién pintó esto?")
CREATE TABLE pixel_state (
  chunk int, x int, y int,
  color tinyint, user_id uuid, updated_at timestamp,
  PRIMARY KEY ((chunk), x, y)
);

CREATE TABLE users (user_id uuid PRIMARY KEY, name text, provider text, banned boolean, created_at timestamp);
```

**Alternativas consideradas:**

| Base de datos | Por qué NO como principal |
|---|---|
| PostgreSQL / MySQL | Un solo primario por clúster; multi-región activo-activo requiere herramientas extra y el failover del primario implica segundos/minutos de escrituras caídas. |
| CockroachDB / Google Spanner | Excelentes, pero dan **consistencia fuerte global**: cada escritura espera confirmación entre regiones (+100–200 ms). Pagamos latencia por una garantía que un pixel no necesita. |
| DynamoDB Global Tables | Muy buena opción equivalente (AP, multi-región, LWW). La descarté para no quedar atado a AWS; si el equipo ya usa AWS, es un reemplazo directo de ScyllaDB. |
| MongoDB | Réplica con un solo primario por *shard*; mismo problema de failover que PostgreSQL. |

---

## 2.7 Mensajería entre regiones: **NATS JetStream**

**Problema:** un pixel pintado en Tokio debe aparecer en Santiago. ¿Cómo viaja?

**Por qué NATS JetStream:**

- **Super-clúster con *gateways*:** los clústeres de cada región se conectan entre sí y los mensajes se propagan entre continentes en ~100–200 ms.
- **Latencia de microsegundos** dentro de la región; mucho más liviano que Kafka (un binario de ~20 MB, sin ZooKeeper).
- **JetStream** guarda los mensajes en disco con replicación RAFT (3 nodos): si el `persister` o la base de datos se caen, los eventos **esperan en la cola** y se procesan al volver. Nada se pierde.
- **Retención 7 días → *replay*:** podemos reconstruir cualquier componente re-leyendo los eventos.
- Desacopla: el usuario recibe "pixel aceptado" sin esperar a la base de datos.

**Descartado:** Kafka (más pesado de operar, replicación entre regiones con MirrorMaker añade complejidad); replicación "a mano" vía la base de datos (lenta y acoplada).

---

## 2.8 Copias de seguridad: regla **3-2-1** + *event sourcing*

- **3 copias** de cada dato: réplicas en ScyllaDB (RF=3 por región × 4 regiones), backups en S3 y réplica de S3 en otra región.
- **2 medios distintos:** disco de la base de datos y almacenamiento de objetos.
- **1 copia fuera de sitio e inmutable:** S3 con **Object Lock** (ni un administrador ni un ransomware pueden borrarla durante el periodo de retención).

| Qué | Frecuencia | Retención | Objetivo |
|---|---|---|---|
| Snapshot del lienzo (binario + PNG) | Cada 5 min | 90 días | RPO del lienzo ≤ 5 min; además da un "timelapse" del arte. |
| ScyllaDB (Scylla Manager) | Completo diario + incremental cada hora | 30 días | Recuperar ante borrado accidental o corrupción. |
| Log de eventos NATS | Continuo | 7 días | Re-aplicar eventos posteriores al último snapshot → **pérdida real ≈ 0**. |

**Importante:** una réplica **no es** un backup (si alguien borra una tabla, la réplica también la borra). Por eso tenemos ambos. Y un backup que nunca se restauró no es un backup: se hace un **simulacro de restauración mensual** automatizado.

---

## 2.9 Resiliencia: qué pasa cuando algo falla

| Falla | Qué ocurre | Impacto para el usuario |
|---|---|---|
| Muere un pod | Kubernetes lo reemplaza en segundos; el cliente se reconecta a otro pod. | Reconexión de ~1 s. |
| Cae una zona de disponibilidad | Las otras 2 zonas de la región siguen; Redis y Scylla tienen copias en ellas. | Ninguno visible. |
| **Cae una región completa** | Cloudflare detecta el *health check* fallido y redirige a la siguiente región más cercana (< 30 s). Las otras regiones ya tienen el lienzo completo. | Reconexión; algo más de latencia hasta que vuelva. |
| ScyllaDB lenta o caída | Los eventos se acumulan en NATS JetStream; se escriben al recuperarse. | **Ninguno**: se sigue pintando. |
| NATS caído en una región | El `pixel-service` rechaza escrituras (*circuit breaker*); la región queda en **modo solo lectura**. | Se ve el lienzo, no se puede pintar temporalmente. |
| Pico de tráfico (streamer famoso) | HPA agrega pods; *rate limiting* en el borde protege el origen. | Ninguno o mínimo. |
| Ataque DDoS / bots | Cloudflare WAF + Turnstile + límite por IP y por usuario. | Ninguno. |

**Patrones aplicados:** reintentos con *backoff* exponencial + *jitter*, *circuit breakers*, *bulkheads* (servicios separados), *timeouts* en toda llamada, idempotencia (cada pixel lleva un ID único, reintentarlo no lo duplica), *PodDisruptionBudgets*, despliegues *canary* y **chaos engineering** (apagar pods/regiones a propósito en pruebas para verificar que todo lo anterior funciona).

---

## 2.10 Observabilidad: no se puede garantizar 99,9% sin medirlo

- **OpenTelemetry** para trazas (seguir un pixel desde el clic hasta que aparece en otro continente).
- **Prometheus + Grafana** con **SLOs y *error budget***: si se gasta el presupuesto de errores del mes, se congelan despliegues de funcionalidades nuevas.
- **Loki** para logs; **Alertmanager → PagerDuty** para guardias.
- **Terraform** (infraestructura como código) + **ArgoCD** (GitOps): levantar una región nueva idéntica es ejecutar código, no seguir un manual.

---

## 2.11 Resumen de por qué esta arquitectura cumple cada requisito

| Requisito | Cómo se cumple |
|---|---|
| **Disponibilidad 99,9%** | 4 regiones activo-activo × 3 zonas cada una; base de datos sin maestro; failover automático por DNS; degradación a solo lectura desde CDN. |
| **Baja latencia** | Usuario conectado a la región más cercana; lienzo en memoria (< 1 ms); escritura con quórum local; WebSocket persistente; TLS en el borde. |
| **Réplicas mundiales** | Redis por región + NATS super-cluster + ScyllaDB multi-DC; todas las regiones tienen el lienzo completo. |
| **Copias de seguridad** | Regla 3-2-1, snapshots cada 5 min, backups diarios/horarios, S3 inmutable y replicado, *event sourcing*, restauraciones probadas. |
| **Resiliencia** | Servicios sin estado, colas persistentes, *circuit breakers*, reintentos idempotentes, chaos engineering. |
