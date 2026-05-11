# Análisis Técnico: Sistema de Ratings de Cursos

## Problema

PlatziFlix necesita permitir que los usuarios califiquen cursos con 1 a 5 estrellas. El sistema debe mostrar el rating promedio y el total de votos en la card de cada curso y en la página de detalle, además de permitir que el usuario cambie su voto en cualquier momento.

No existe un sistema de autenticación en el proyecto; la identidad del usuario se maneja con un UUID generado y persistido en `localStorage`.

## Impacto Arquitectural

- **Backend**: nuevo modelo `CourseRating`, nueva migración Alembic, 3 métodos nuevos en `CourseService`, 2 endpoints nuevos, 2 endpoints existentes modificados para incluir stats de rating.
- **Frontend**: nuevo componente `StarRating`, nuevo servicio `ratingsApi.ts`, utilidad `getOrCreateUserId`, actualización de tipos TypeScript, integración en `Course.tsx` y extracción de `RatingWidget` (Client Component) desde `CourseDetail.tsx`.
- **Base de datos**: nueva tabla `course_ratings` con constraint UNIQUE `(course_id, user_id)` para garantizar upsert atómico, CHECK constraint para rango 1-5, índices filtrados por `deleted_at IS NULL`.

## Contratos de API

### Endpoints nuevos

**POST /courses/{slug}/ratings**

Registra o actualiza el voto de un usuario. Implementa upsert: si el usuario ya votó, actualiza el valor.

Request body:
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "rating": 4
}
```

Response 200:
```json
{
  "course_id": 1,
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "rating": 4,
  "average_rating": 4.3,
  "total_ratings": 127
}
```

Response 422 (validación fallida):
```json
{
  "detail": [
    {
      "loc": ["body", "rating"],
      "msg": "ensure this value is greater than or equal to 1",
      "type": "value_error.number.not_ge"
    }
  ]
}
```

Response 404: `{ "detail": "Course not found" }`

---

**GET /courses/{slug}/ratings/me**

Devuelve el voto previo de un usuario. Usado al cargar la página de detalle para pre-seleccionar estrellas.

Query parameter: `user_id=550e8400-e29b-41d4-a716-446655440000`

Response 200:
```json
{
  "course_id": 1,
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "rating": 4
}
```

Response 404: `{ "detail": "Rating not found" }` (el usuario aún no ha votado)

### Cambios en endpoints existentes

**GET /courses** — agrega `average_rating` y `total_ratings` en cada item:
```json
[
  {
    "id": 1,
    "name": "Curso de React",
    "description": "...",
    "thumbnail": "https://...",
    "slug": "curso-de-react",
    "average_rating": 4.3,
    "total_ratings": 127
  }
]
```

**GET /courses/{slug}** — mismo cambio en la respuesta de detalle:
```json
{
  "id": 1,
  "name": "Curso de React",
  "description": "...",
  "thumbnail": "https://...",
  "slug": "curso-de-react",
  "teacher_id": [1, 2],
  "classes": [...],
  "average_rating": 4.3,
  "total_ratings": 127
}
```

## Propuesta de Solución

### Base de datos

```sql
CREATE TABLE course_ratings (
    id          SERIAL PRIMARY KEY,
    course_id   INTEGER NOT NULL
                    REFERENCES courses(id) ON DELETE CASCADE,
    user_id     VARCHAR(36) NOT NULL,
    rating      SMALLINT NOT NULL
                    CONSTRAINT chk_rating_range CHECK (rating >= 1 AND rating <= 5),
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMP WITH TIME ZONE,

    CONSTRAINT uq_course_ratings_course_user
        UNIQUE (course_id, user_id)
);

CREATE INDEX ix_course_ratings_course_id
    ON course_ratings (course_id)
    WHERE deleted_at IS NULL;

CREATE INDEX ix_course_ratings_user_id
    ON course_ratings (user_id)
    WHERE deleted_at IS NULL;
```

Decisiones de diseño:
- `user_id` es `VARCHAR(36)` para UUID en formato string. No se crea tabla de usuarios porque la identidad es local via localStorage.
- `UNIQUE (course_id, user_id)` hace que el upsert sea atómico — la base de datos garantiza un voto por usuario por curso.
- `ON DELETE CASCADE` en `course_id` protege ante limpiezas manuales de cursos.
- El `CHECK` constraint duplica la validación de Pydantic como última línea de defensa.
- Los índices filtrados (`WHERE deleted_at IS NULL`) aceleran queries de agregación que siempre excluyen soft-deleted rows.

### Modelo SQLAlchemy

`Backend/app/models/course_rating.py`:
```python
from sqlalchemy import Column, Integer, SmallInteger, String, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class CourseRating(BaseModel):
    __tablename__ = "course_ratings"

    __table_args__ = (
        UniqueConstraint("course_id", "user_id", name="uq_course_ratings_course_user"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="chk_rating_range"),
    )

    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    user_id   = Column(String(36), nullable=False, index=True)
    rating    = Column(SmallInteger, nullable=False)

    course = relationship("Course", back_populates="ratings")
```

Agregar en `Backend/app/models/course.py` la relación inversa:
```python
ratings = relationship(
    "CourseRating",
    back_populates="course",
    primaryjoin="and_(Course.id == CourseRating.course_id, CourseRating.deleted_at.is_(None))"
)
```

### Schemas Pydantic

En `main.py` o en un archivo `schemas.py` dedicado:
```python
from pydantic import BaseModel, Field

class RatingCreate(BaseModel):
    user_id: str = Field(..., min_length=36, max_length=36)
    rating: int  = Field(..., ge=1, le=5)

class RatingResponse(BaseModel):
    course_id:      int
    user_id:        str
    rating:         int
    average_rating: float
    total_ratings:  int

class UserRatingResponse(BaseModel):
    course_id: int
    user_id:   str
    rating:    int
```

### Métodos nuevos en CourseService

```python
def upsert_rating(self, db: Session, slug: str, user_id: str, rating: int) -> dict:
    """Crea o actualiza el rating de un usuario. Reactiva soft-deleted ratings."""
    course = db.query(Course).filter(
        Course.slug == slug,
        Course.deleted_at.is_(None)
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    stmt = (
        pg_insert(CourseRating)
        .values(course_id=course.id, user_id=user_id, rating=rating)
        .on_conflict_do_update(
            constraint="uq_course_ratings_course_user",
            set_={"rating": rating, "updated_at": func.now(), "deleted_at": None},
        )
        .returning(CourseRating.rating)
    )
    db.execute(stmt)
    db.commit()

    stats = self._compute_rating_stats(db, course.id)
    return {"course_id": course.id, "user_id": user_id, "rating": rating, **stats}


def get_user_rating(self, db: Session, slug: str, user_id: str) -> CourseRating | None:
    """Devuelve el rating activo del usuario para el curso, o None."""
    course = db.query(Course).filter(
        Course.slug == slug,
        Course.deleted_at.is_(None)
    ).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    return db.query(CourseRating).filter(
        CourseRating.course_id == course.id,
        CourseRating.user_id == user_id,
        CourseRating.deleted_at.is_(None),
    ).first()


def _compute_rating_stats(self, db: Session, course_id: int) -> dict:
    """Calcula average_rating y total_ratings en una sola query SQL."""
    result = (
        db.query(
            func.avg(CourseRating.rating).label("average_rating"),
            func.count(CourseRating.id).label("total_ratings"),
        )
        .filter(
            CourseRating.course_id == course_id,
            CourseRating.deleted_at.is_(None),
        )
        .one()
    )
    return {
        "average_rating": round(float(result.average_rating or 0), 1),
        "total_ratings":  result.total_ratings or 0,
    }
```

`get_all_courses` y `get_course_by_slug` se modifican para llamar a `_compute_rating_stats` por curso. Para evitar N+1, usar un LEFT JOIN con subquery al listar todos los cursos.

### Servicio Frontend

`Frontend/src/services/ratingsApi.ts`:
```typescript
const API_BASE = "http://localhost:8000";

export async function submitRating(
  slug: string,
  userId: string,
  rating: number
): Promise<{ average_rating: number; total_ratings: number }> {
  const res = await fetch(`${API_BASE}/courses/${slug}/ratings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, rating }),
  });
  if (!res.ok) throw new Error("Failed to submit rating");
  return res.json();
}

export async function getUserRating(
  slug: string,
  userId: string
): Promise<number | null> {
  const res = await fetch(
    `${API_BASE}/courses/${slug}/ratings/me?user_id=${userId}`,
    { cache: "no-store" }
  );
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch user rating");
  const data = await res.json();
  return data.rating;
}
```

`Frontend/src/utils/userId.ts`:
```typescript
export function getOrCreateUserId(): string {
  if (typeof window === "undefined") return "";
  let userId = localStorage.getItem("platziflix_user_id");
  if (!userId) {
    userId = crypto.randomUUID();
    localStorage.setItem("platziflix_user_id", userId);
  }
  return userId;
}
```

### Componente StarRating

`Frontend/src/components/StarRating/StarRating.tsx` — Client Component (`"use client"`):

Props:
- `averageRating: number` — valor para display readonly
- `totalRatings: number` — contador de votos
- `userRating?: number` — estrella pre-seleccionada (undefined = no ha votado)
- `onRate?: (rating: number) => void` — undefined significa modo readonly
- `courseId: number`

Internamente maneja hover state con `useState` para preview de estrellas. Las medias estrellas en display se implementan con CSS clip-path o dos capas superpuestas (outlined + filled con width en porcentaje).

### Integración en CourseDetail

`CourseDetail.tsx` permanece como Server Component. Se extrae `RatingWidget.tsx` como Client Component separado que:
1. Lee `userId` de `localStorage` via `getOrCreateUserId()`
2. Fetch del voto previo via `getUserRating` al montar
3. Submit via `submitRating` con optimistic UI (actualiza el estado local antes de que la API responda)
4. Recibe `slug`, `initialAverageRating` e `initialTotalRatings` como props desde el Server Component padre

## Plan de Implementación

### Paso 1 — Modelo y migración

1. Crear `Backend/app/models/course_rating.py` con el modelo `CourseRating`.
2. Agregar `ratings = relationship(...)` en `Backend/app/models/course.py`.
3. Importar `CourseRating` en `Backend/app/models/__init__.py`.
4. Generar migración: `alembic revision --autogenerate -m "add_course_ratings_table"`.
5. Revisar el archivo generado y confirmar tabla, UNIQUE constraint y CHECK.
6. Aplicar: `make migrate`.

Estado al finalizar: backend arranca, endpoints existentes funcionan, tabla `course_ratings` existe vacía.

### Paso 2 — Métodos de service

1. Agregar `_compute_rating_stats`, `upsert_rating` y `get_user_rating` en `CourseService`.
2. Agregar imports necesarios (`func`, `pg_insert`, `CourseRating`, `HTTPException`).
3. Ejecutar `make test` — los tests existentes deben seguir pasando.

Estado al finalizar: métodos disponibles, no expuestos en API todavía.

### Paso 3 — Endpoints nuevos

1. Agregar schemas Pydantic `RatingCreate`, `RatingResponse`, `UserRatingResponse` en `main.py`.
2. Agregar `POST /courses/{slug}/ratings`.
3. Agregar `GET /courses/{slug}/ratings/me`.
4. Verificar con Swagger UI en `http://localhost:8000/docs`.

Estado al finalizar: endpoints nuevos responden, endpoints existentes sin cambios.

### Paso 4 — Modificar endpoints existentes

1. Actualizar `get_all_courses` para incluir stats con LEFT JOIN (evitar N+1).
2. Actualizar `get_course_by_slug` de manera análoga.
3. Verificar que `GET /courses` y `GET /courses/{slug}` devuelven `average_rating: 0.0` y `total_ratings: 0` con la DB sin votos.

Estado al finalizar: API completa. Ejecutar `make test`.

### Paso 5 — Seed data

1. Agregar `CourseRating` records en `Backend/app/db/seed.py` con UUIDs ficticios.
2. Ejecutar `make seed` y verificar que `GET /courses` devuelve valores de rating no-cero.

### Paso 6 — Tipos TypeScript

1. Agregar `average_rating: number` y `total_ratings: number` a las interfaces `Course` y `CourseDetail` en `Frontend/src/types/index.ts`.
2. Verificar que `yarn build` no lanza errores de TypeScript.

### Paso 7 — Componente StarRating

1. Crear `Frontend/src/components/StarRating/StarRating.tsx`.
2. Crear `Frontend/src/components/StarRating/StarRating.module.scss`.
3. Implementar modos readonly e interactivo con hover state.
4. Implementar medias estrellas con CSS.

### Paso 8 — Servicio de ratings

1. Crear `Frontend/src/services/ratingsApi.ts` con `submitRating` y `getUserRating`.
2. Crear `Frontend/src/utils/userId.ts` con `getOrCreateUserId`.

### Paso 9 — Integración en componentes

1. Modificar `Course.tsx` para mostrar `StarRating` en modo readonly.
2. Extraer `CourseDetail/RatingWidget.tsx` como Client Component con optimistic UI.
3. Modificar `CourseDetail.tsx` para pasar datos de rating a `RatingWidget`.

### Paso 10 — Verificación final

1. Levantar Backend (`docker-compose up`) y Frontend (`yarn dev`).
2. Navegar a `/` y verificar que las cards muestran estrellas.
3. Abrir un curso, votar, verificar que el promedio se actualiza visualmente de inmediato (optimistic UI).
4. Recargar la página y verificar que el voto previo se mantiene pre-seleccionado.
5. Ejecutar `make test` y `yarn test`.

## Dependencias entre pasos

```
Paso 1 (modelo + migración)
    └── Paso 2 (métodos service)
            └── Paso 3 (endpoints nuevos)
            └── Paso 4 (modificar endpoints existentes)
                    └── Paso 5 (seed data)
                            └── [Backend completo]

Paso 6 (tipos TS)          ← puede empezar en paralelo con Paso 1
    └── Paso 7 (StarRating)
        └── Paso 8 (ratingsApi + userId)
            └── Paso 9 (integración en Course + CourseDetail)
                └── Paso 10 (verificación final)
```

Los pasos 1-5 (Backend) y los pasos 6-8 (Frontend base) son independientes entre sí y pueden ejecutarse en paralelo.

## Consideraciones de Seguridad

| Riesgo | Mitigación |
|--------|-----------|
| Rating fuera de rango | Validación en Pydantic (`ge=1, le=5`) + CHECK constraint en PostgreSQL |
| Múltiples votos del mismo usuario | UNIQUE `(course_id, user_id)` + upsert atómico |
| SQL injection | SQLAlchemy ORM + parámetros vinculados en `pg_insert` |
| Concurrencia (dos requests simultáneos) | `ON CONFLICT DO UPDATE` serializado por PostgreSQL |
| Inflado de ratings (múltiples UUIDs) | Aceptado para el alcance del proyecto; mitigable con rate limiting (`slowapi`) |
| PII | El UUID de localStorage no identifica personas reales |
