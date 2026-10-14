# 4. Validación del esquema final con ChatGPT

> **Aclaración honesta:** el esquema de [03-esquema-final.md](03-esquema-final.md) se generó con un asistente de IA (Claude), no con ChatGPT. Si la pauta exige que el esquema final esté hecho **con ChatGPT**, usa el prompt de abajo, pega la respuesta en este archivo y compárala con nuestra propuesta en la sección de comparación.

## Prompt sugerido

```text
Actúa como arquitecto de software senior. Necesito diseñar una aplicación web tipo r/place:
miles de usuarios simultáneos pintan pixeles en un lienzo compartido de 2000x2000 en tiempo real.

Requisitos no funcionales obligatorios:
- Disponibilidad del 99,9%
- Baja latencia para usuarios de todo el mundo
- Réplicas a nivel mundial
- Copias de seguridad
- Resiliencia ante fallas

Entrégame:
1. Un diagrama de la arquitectura en formato Mermaid (flowchart).
2. Qué tecnología usar para el BACKEND y por qué (compara al menos 3 opciones).
3. Qué tecnología usar para la BASE DE DATOS y por qué (compara al menos 4 opciones,
   considerando el teorema CAP y la replicación multi-región).
4. Estrategia de copias de seguridad (frecuencias, retención, RPO y RTO).
5. Qué pasa ante la caída de un servidor, una zona, una región completa y la base de datos.

Mi propuesta actual es: Cloudflare (CDN + DNS Anycast + WAF) → Kubernetes en 4 regiones activo-activo
→ microservicios en Go con WebSocket → Redis/Valkey (lienzo en BITFIELD) + NATS JetStream entre regiones
+ ScyllaDB multi-datacenter, con backups en S3 inmutable. Critica esta propuesta y dime qué cambiarías.
```

## Respuesta de ChatGPT

_(pegar aquí)_

## Comparación

| Aspecto | Nuestra propuesta | ChatGPT | ¿Coinciden? / Comentario |
|---|---|---|---|
| Backend | Go + WebSocket en Kubernetes | | |
| DB caliente | Redis / Valkey | | |
| DB durable | ScyllaDB multi-DC | | |
| Mensajería | NATS JetStream | | |
| Borde / CDN | Cloudflare | | |
| Backups | S3 inmutable + Scylla Manager + snapshots 5 min | | |
