# Análisis de Seguridad: Implementación Backend — Sistema de Ratings

## Alcance

Revisión de los cambios introducidos por la implementación del sistema de ratings (Fases B1-B7). Archivos cubiertos:

- `Backend/app/models/course_rating.py`
- `Backend/app/schemas/rating.py`
- `Backend/app/services/course_service.py` (métodos nuevos y modificados)
- `Backend/app/main.py` (endpoints nuevos)
- `Backend/app/alembic/versions/0e01d82900f1_add_course_ratings_table.py`
- `Backend/app/db/seed.py`

---

## Hallazgos

### HAL-01 — Suplantación de `user_id` sin autenticación *(Severidad: MEDIA)*

**Ubicación:** `POST /courses/{slug}/ratings` · `GET /courses/{slug}/ratings/me`

**Descripción:** Los endpoints aceptan cualquier `user_id` de 36 caracteres en el body o query param sin verificar que corresponda al usuario que realiza la solicitud. No existe ningún mecanismo de sesión, token, ni cabecera que vincule el request al `user_id` declarado. Cualquier cliente puede votar en nombre de cualquier otro usuario conociendo (o adivinando) su UUID.

**Código afectado:**
```python
# main.py — el user_id viene del cliente sin verificación
def upsert_rating(slug: str, body: RatingCreate, ...):
    return course_service.upsert_rating(slug, body.user_id, body.rating)
```

**Riesgo concreto:** Un atacante puede sobrescribir el voto de otro usuario enviando su UUID en el cuerpo del request.

**Mitigación en el alcance actual:** El diseño asume identidad vía UUID de `localStorage` sin autenticación real; este riesgo está aceptado por decisión de producto. Debe documentarse explícitamente.

**Mitigación futura:** Introducir autenticación (JWT, sesión firmada) y validar que el `user_id` del token coincide con el del body antes de persistir.

---

### HAL-02 — Ausencia de rate limiting (ataque Sybil / inflado de ratings) *(Severidad: MEDIA)*

**Ubicación:** `POST /courses/{slug}/ratings`

**Descripción:** No existe ningún límite de frecuencia por IP ni por sesión. Un atacante puede generar automáticamente miles de UUIDs únicos de 36 caracteres y crear ratings masivos, alterando artificialmente el promedio de cualquier curso.

**Vector de ataque:**
```bash
for i in $(seq 1 1000); do
  uuid=$(python -c "import uuid; print(uuid.uuid4())")
  curl -s -X POST http://api/courses/curso-de-react/ratings \
    -H "Content-Type: application/json" \
    -d "{\"user_id\": \"$uuid\", \"rating\": 5}"
done
```

**Riesgo concreto:** Manipulación del sistema de recomendación; degradación del servicio bajo carga sostenida.

**Mitigación posible:** Agregar `slowapi` (rate limiter para FastAPI) con límite por IP: `@limiter.limit("10/minute")` sobre el endpoint de POST.

---

### HAL-03 — `user_id` no validado como UUID real *(Severidad: BAJA)*

**Ubicación:** `Backend/app/schemas/rating.py`

**Descripción:** El campo `user_id` solo valida que tenga exactamente 36 caracteres. No verifica el formato UUID (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`). Strings como `"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"` o `"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"`  pasan la validación y se persisten en la DB.

**Código afectado:**
```python
class RatingCreate(BaseModel):
    user_id: str = Field(min_length=36, max_length=36)  # no valida formato UUID
    rating: int = Field(ge=1, le=5)
```

**Riesgo concreto:** Datos de baja calidad en la tabla `course_ratings`; el `UNIQUE (course_id, user_id)` sigue funcionando, pero el identificador pierde semántica de UUID.

**Mitigación posible:** Usar `pydantic.UUID4` como tipo de campo (Pydantic lo valida y convierte a `uuid.UUID`):
```python
from uuid import UUID
class RatingCreate(BaseModel):
    user_id: UUID
    rating: int = Field(ge=1, le=5)
```
Requiere ajustar el almacenamiento en DB a `String(36)` con `.hex` o usar `UUID` nativo de PostgreSQL.

---

### HAL-04 — `user_id` expuesto en URL (query param) *(Severidad: BAJA)*

**Ubicación:** `GET /courses/{slug}/ratings/me?user_id=...`

**Descripción:** El identificador de usuario viaja en la URL, quedando registrado en:
- Access logs del servidor Nginx/Uvicorn
- Historial del navegador
- Cabecera `Referer` al navegar hacia otra página
- Caches intermedios (proxies, CDNs)

**Código afectado:**
```python
@app.get("/courses/{slug}/ratings/me", response_model=UserRatingResponse)
def get_user_rating(slug: str, user_id: str, ...):  # user_id en query param
```

**Riesgo concreto:** Aunque el UUID no está vinculado a PII real, su exposición en logs permite trazar la actividad de un usuario a través del tiempo si los logs son comprometidos.

**Mitigación posible:** Recibir `user_id` en una cabecera HTTP personalizada (`X-User-Id`) en lugar de query param, o como parte del body en un POST.

---

### HAL-05 — Sin CORS configurado *(Severidad: BAJA)*

**Ubicación:** `Backend/app/main.py`

**Descripción:** No hay `CORSMiddleware` configurado en la aplicación FastAPI. Por defecto, los navegadores bloquean requests cross-origin, lo que impediría al Frontend (puerto 3000) llamar al Backend (puerto 8000) desde el cliente.

**Riesgo en producción:** Si se agrega CORS más adelante con `allow_origins=["*"]` para solucionar el problema rápidamente, se estaría permitiendo requests desde cualquier origen, incluyendo páginas maliciosas.

**Mitigación:** Configurar CORS explícitamente con la lista de orígenes permitidos:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # ajustar a dominio de producción
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
```

---

### HAL-06 — `/health` expone detalles internos de error de DB *(Severidad: BAJA)*

**Ubicación:** `Backend/app/main.py` — endpoint `/health`

**Descripción:** Cuando la base de datos no está disponible, la respuesta incluye el mensaje de excepción de psycopg2/SQLAlchemy en texto plano, que puede contener el host, puerto, nombre de la base de datos o credenciales truncadas.

**Código afectado:**
```python
except Exception as e:
    health_status["database_error"] = str(e)  # expone detalles internos
```

**Riesgo concreto:** Un atacante que induce un fallo de conexión (o que monitorea el endpoint) obtiene información sobre la topología de la infraestructura.

**Mitigación posible:** Loguear el error completo en el servidor y retornar solo un mensaje genérico al cliente:
```python
except Exception as e:
    logger.error(f"DB health check failed: {e}")
    health_status["status"] = "degraded"
    health_status["database_error"] = "connection failed"
```

---

### HAL-07 — Reactivación silenciosa de ratings soft-deleted *(Severidad: INFORMATIVA)*

**Ubicación:** `Backend/app/services/course_service.py` — `upsert_rating`

**Descripción:** El `ON CONFLICT DO UPDATE` incluye `"deleted_at": None`, lo que reactiva automáticamente cualquier rating que haya sido previamente soft-deleted. Este comportamiento es correcto para el flujo de "el usuario volvió a votar", pero no está documentado y podría confundir a quien extienda el código.

**Código afectado:**
```python
.on_conflict_do_update(
    constraint="uq_course_ratings_course_user",
    set_={"rating": rating, "updated_at": now, "deleted_at": None},  # reactiva sin aviso
)
```

**Riesgo concreto:** Si en el futuro se agrega lógica de "suspender usuario", un rating soft-deleted podría reactivarse sin que el sistema de administración lo detecte.

---

## Riesgos Aceptados

| ID | Descripción | Justificación |
|----|-------------|---------------|
| HAL-01 | Suplantación de `user_id` | Diseño sin autenticación real; UUID de localStorage es la identidad de facto. Decisión de alcance del proyecto. |
| HAL-02 | Sybil attack / inflado de ratings | Aceptado para MVP; el proyecto no tiene monetización ni consecuencias críticas por manipulación de ratings. |

---

## Hallazgos No Encontrados (por diseño)

| Categoría | Estado |
|-----------|--------|
| SQL Injection | **No aplica** — todo el código usa SQLAlchemy ORM con parámetros vinculados y `pg_insert` parametrizado. Sin SQL raw. |
| Duplicación de votos (race condition) | **No aplica** — el `ON CONFLICT DO UPDATE` es atómico a nivel de PostgreSQL; no hay ventana de race condition. |
| Bypass del CHECK constraint | **No aplica** — la validación de Pydantic (`ge=1, le=5`) y el CHECK de PostgreSQL son capas independientes y redundantes. |
| Información de cursos privados | **No aplica** — todos los cursos son públicos; no existe concepto de visibilidad privada. |

---

## Recomendaciones Prioritarias

Ordenadas por impacto / esfuerzo de implementación:

| Prioridad | Hallazgo | Acción | Esfuerzo |
|-----------|----------|--------|----------|
| 1 | HAL-05 — CORS | Agregar `CORSMiddleware` con `allow_origins` explícitos antes de la integración Frontend | Bajo |
| 2 | HAL-03 — UUID validation | Cambiar `user_id: str` por `user_id: UUID` en `RatingCreate` | Bajo |
| 3 | HAL-06 — Health endpoint | Reemplazar `str(e)` por mensaje genérico; loguear error internamente | Bajo |
| 4 | HAL-02 — Rate limiting | Agregar `slowapi` con límite `10/minute` en `POST /ratings` | Medio |
| 5 | HAL-04 — user_id en URL | Mover `user_id` a cabecera `X-User-Id` en el GET | Medio |
| 6 | HAL-07 — Soft-delete reactivo | Agregar comentario explicativo en el `set_` del upsert | Bajo |
