# Análisis Técnico: Implementación Backend — Sistema de Ratings

## Problema

El backend de PlatziFlix no tiene soporte para ratings de cursos. Se necesita una nueva tabla `course_ratings`, métodos de negocio en `CourseService`, dos endpoints nuevos, y modificaciones a los endpoints existentes para exponer estadísticas de rating sin introducir N+1 queries.

## Impacto Arquitectural

- **Backend**: nuevo modelo `CourseRating`, 3 métodos nuevos en `CourseService` (`_compute_rating_stats`, `upsert_rating`, `get_user_rating`), 2 endpoints nuevos, 2 endpoints existentes modificados para incluir `average_rating` y `total_ratings`.
- **Base de datos**: nueva tabla `course_ratings` con UNIQUE `(course_id, user_id)`, CHECK constraint `rating 1-5`, índices parciales filtrados por `deleted_at IS NULL`.
- **Schemas**: 3 nuevos schemas Pydantic (`RatingCreate`, `RatingResponse`, `UserRatingResponse`).
- **Tests**: extensión de `test_main.py` con cobertura de los nuevos endpoints.

## Propuesta de Solución

Seguir el patrón de capas existente: Routes → Service → ORM → DB. La identidad del usuario se recibe como `VARCHAR(36)` (UUID de localStorage), sin tabla de usuarios. El upsert se implementa con `INSERT ... ON CONFLICT DO UPDATE` de PostgreSQL, garantizando atomicidad. Las estadísticas del listado de cursos se calculan con un LEFT JOIN y subquery para evitar N+1.

## Plan de Implementación

### ~~Fase B1 — Modelo ORM y migración~~ ✅ COMPLETADA

**Archivos:**
- `Backend/app/models/course_rating.py` — crear
- `Backend/app/models/course.py` — modificar (relación inversa)
- `Backend/app/models/__init__.py` — modificar (importar `CourseRating`)
- `Backend/app/alembic/versions/<hash>_add_course_ratings_table.py` — autogenerar

**Cambios:**
Crear `CourseRating` heredando de `BaseModel` con columnas `course_id` (FK a `courses.id` ON DELETE CASCADE), `user_id` (String 36), `rating` (SmallInteger). Agregar `UniqueConstraint("course_id", "user_id", name="uq_course_ratings_course_user")`, `CheckConstraint("rating >= 1 AND rating <= 5", name="ck_course_ratings_rating_range")`, e índices parciales filtrados por `deleted_at IS NULL` sobre `course_id` y `user_id`. Agregar relación inversa `ratings` en `Course`.

**Validación:** `alembic upgrade head` sin errores; insertar duplicado de `(course_id, user_id)` lanza unicidad; `rating=0` o `rating=6` lanza check constraint; eliminar un `Course` hace cascada en sus ratings.

**Dependencias:** Ninguna.

---

### ~~Fase B2 — Schemas Pydantic~~ ✅ COMPLETADA *(paralela con B1)*

**Archivos:**
- `Backend/app/schemas/rating.py` — crear

**Cambios:**
Definir `RatingCreate` (`user_id: str` len=36, `rating: int` ge=1 le=5), `RatingResponse` (`course_id`, `user_id`, `rating`, `average_rating`, `total_ratings`), `UserRatingResponse` (`course_id`, `user_id`, `rating`).

**Validación:** `RatingCreate` con `user_id` corto o `rating` fuera de rango lanza `ValidationError`; con valores válidos instancia correctamente.

**Dependencias:** Ninguna.

---

### ~~Fase B3 — Métodos en CourseService~~ ✅ COMPLETADA *(requiere B1)*

**Archivos:**
- `Backend/app/services/course_service.py` — modificar

**Cambios:**
Agregar `_compute_rating_stats(db, course_id)`: query única con `AVG(rating)` y `COUNT(id)` sobre ratings activos, normaliza `None` a `0.0` y `0`. Agregar `upsert_rating(db, slug, user_id, rating)`: resuelve `course_id` desde slug (404 si no existe), ejecuta `INSERT ... ON CONFLICT (constraint="uq_course_ratings_course_user") DO UPDATE SET rating, updated_at, deleted_at=None`, hace commit y retorna dict con stats. Agregar `get_user_rating(db, slug, user_id)`: resuelve curso (404 si no existe), consulta rating activo y retorna ORM o `None`.

**Validación:** Doble upsert con mismo usuario actualiza en lugar de duplicar; slug inexistente lanza 404; stats sin ratings retorna `{average_rating: 0.0, total_ratings: 0}`.

> **Punto crítico:** el `ON CONFLICT` debe referenciar el constraint por nombre exacto `uq_course_ratings_course_user` definido en B1.

**Dependencias:** B1.

---

### ~~Fase B4 — Endpoints nuevos~~ ✅ COMPLETADA *(requiere B2 + B3)*

**Archivos:**
- `Backend/app/main.py` — modificar

**Cambios:**
Agregar `POST /courses/{slug}/ratings`: recibe `slug` y body `RatingCreate`, delega a `upsert_rating`, retorna `RatingResponse` 200. Agregar `GET /courses/{slug}/ratings/me`: recibe `slug` y query param `user_id`, delega a `get_user_rating`, retorna `UserRatingResponse` 200 o 404 si `None`. Ambos usan `Depends(get_db)`.

**Validación:** POST exitoso devuelve stats; POST con slug inexistente devuelve 404; POST con `rating=6` devuelve 422; GET sin rating previo devuelve 404; GET sin `user_id` devuelve 422.

**Dependencias:** B2, B3.

---

### ~~Fase B5 — Modificar endpoints existentes~~ ✅ COMPLETADA *(requiere B1 + B3)*

**Archivos:**
- `Backend/app/services/course_service.py` — modificar
- `Backend/app/test_main.py` — modificar

**Cambios:**
`get_all_courses`: reemplazar query actual por LEFT JOIN con subquery que agrupa `course_ratings` activos por `course_id` calculando AVG y COUNT, usando `coalesce` para normalizar NULLs. Resultado: una sola query SQL para todos los cursos. `get_course_by_slug`: tras resolver el curso, llamar `_compute_rating_stats(db, course.id)` e incluir las stats en el dict de retorno. Actualizar `test_main.py` para incluir `average_rating` y `total_ratings` en los mocks y en los conjuntos `expected_fields`.

**Validación:** `GET /courses` devuelve `average_rating` y `total_ratings` en cada item; la query es exactamente 1 SQL; `GET /courses/{slug}` incluye las mismas stats; `pytest -v` pasa.

**Dependencias:** B1, B3.

---

### ~~Fase B6 — Seed data~~ ✅ COMPLETADA *(requiere B1 + B5)*

**Archivos:**
- `Backend/app/db/seed.py` — modificar

**Cambios:**
Importar `CourseRating`. Después del commit de lessons, agregar mínimo 5 instancias de `CourseRating` con UUIDs ficticios en formato `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`, distribuidos entre los cursos existentes con valores de rating 1-5. Agregar `db.query(CourseRating).delete()` en `clear_all_data` antes de eliminar lessons.

**Validación:** `make seed` sin errores; `SELECT COUNT(*) FROM course_ratings` retorna ≥ 5; `GET /courses` muestra `average_rating` distinto de 0; ejecutar `make seed` dos veces no lanza errores de constraint.

**Dependencias:** B1, B5.

---

### ~~Fase B7 — Tests~~ ✅ COMPLETADA *(requiere B4 + B5)*

**Archivos:**
- `Backend/app/test_main.py` — modificar

**Cambios:**
Agregar clase `TestRatingEndpoints` con mocks sobre `upsert_rating` cubriendo: POST exitoso, POST 404, POST 422. Agregar clase `TestUserRatingEndpoint` cubriendo: GET con rating existente, GET 404, GET sin query param 422. Todos los tests siguen patrón AAA y usan mocks sin llamadas reales a PostgreSQL.

**Validación:** `pytest -v` al 100%; cobertura de los 6 casos de endpoint; sin llamadas reales a DB.

**Dependencias:** B4, B5.

---

## Dependencias entre fases

```
B1 ──────────────────── B3 ─── B4
B2 (paralela con B1) ──┘       │
                        B5 ─── B6
                        └───── B7
```
