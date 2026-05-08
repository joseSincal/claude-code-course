# PlatziFlix — CLAUDE.md

Plataforma de cursos online (estilo Netflix para aprendizaje). Repositorio monorepo con tres proyectos independientes que comparten el mismo Backend REST.

## Estructura del repositorio

```
/
├── Backend/     # FastAPI + PostgreSQL (Python)
├── Frontend/    # Next.js 15 (TypeScript)
└── Mobile/
    ├── PlatziFlixiOS/      # SwiftUI (Swift)
    └── PlatziFlixAndroid/  # Jetpack Compose (Kotlin)
```

---

## Backend

**Stack:** Python 3.11 · FastAPI · SQLAlchemy 2.0 · Alembic · PostgreSQL 15 · Docker · uv

### Levantar el entorno

```bash
cd Backend
docker-compose up --build        # levanta api (8000) + db (5432)
```

Comandos adicionales (ver `Makefile`):
```bash
make migrate      # aplica migraciones con Alembic
make seed         # carga datos de prueba
make test         # ejecuta pytest
```

### Estructura clave

```
Backend/app/
├── main.py               # Rutas FastAPI (entry point)
├── core/config.py        # Settings via pydantic-settings
├── db/
│   ├── base.py           # Engine SQLAlchemy + get_db()
│   └── seed.py           # Datos de prueba
├── models/
│   ├── base.py           # BaseModel (id, created_at, updated_at, deleted_at)
│   ├── course.py         # Course
│   ├── lesson.py         # Lesson (clases de un curso)
│   ├── teacher.py        # Teacher
│   └── course_teacher.py # Tabla asociativa M:N
├── services/
│   └── course_service.py # Lógica de negocio (CourseService)
└── alembic/              # Migraciones de base de datos
```

### Modelo de datos

```
Teacher (id, name, email)
   └── M:N via course_teachers
Course (id, name, description, thumbnail, slug)
   └── 1:N
Lesson (id, course_id, name, description, slug, video_url)
```

Todos los modelos heredan de `BaseModel` que incluye soft-delete via `deleted_at`. Las queries siempre filtran `deleted_at.is_(None)`.

### API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Bienvenida |
| GET | `/health` | Estado del servicio + conectividad DB |
| GET | `/courses` | Lista de cursos (id, name, description, thumbnail, slug) |
| GET | `/courses/{slug}` | Detalle: curso + teacher_ids + clases |

**Respuesta GET /courses:**
```json
[{ "id": 1, "name": "Curso de React", "description": "...", "thumbnail": "https://...", "slug": "curso-de-react" }]
```

**Respuesta GET /courses/{slug}:**
```json
{
  "id": 1, "name": "Curso de React", "description": "...", "thumbnail": "https://...", "slug": "curso-de-react",
  "teacher_id": [1, 2],
  "classes": [{ "id": 1, "name": "Introducción", "description": "...", "slug": "introduccion" }]
}
```

### Convenciones Backend

- Arquitectura en capas: Routes → Service → ORM → DB. No poner lógica de negocio en las rutas.
- Agregar nuevas rutas en `main.py`; lógica en `services/`.
- Al agregar modelos, crear migración con `alembic revision --autogenerate -m "descripcion"`.
- Variable de entorno principal: `DATABASE_URL`.

---

## Frontend

**Stack:** Next.js 15 (App Router) · TypeScript · SCSS Modules · Vitest · React 19

### Levantar el entorno

```bash
cd Frontend
yarn install
yarn dev          # servidor en http://localhost:3000
yarn test         # ejecuta Vitest
yarn build        # build de producción
```

### Estructura clave

```
Frontend/src/
├── app/
│   ├── page.tsx                        # Home: lista de cursos
│   ├── course/[slug]/page.tsx          # Detalle del curso
│   └── classes/[class_id]/page.tsx     # Reproductor de video
├── components/
│   ├── Course/Course.tsx               # Card de curso
│   ├── CourseDetail/CourseDetail.tsx   # Detalle completo con lista de clases
│   └── VideoPlayer/VideoPlayer.tsx     # Reproductor HTML5
├── types/index.ts                      # Interfaces TypeScript
└── styles/
    ├── vars.scss                       # Design tokens (colores, etc.)
    └── reset.scss                      # CSS reset global
```

### Rutas

| Ruta | Página | Descripción |
|------|--------|-------------|
| `/` | `page.tsx` | Lista todos los cursos |
| `/course/[slug]` | `course/[slug]/page.tsx` | Detalle + lista de clases |
| `/classes/[class_id]` | `classes/[class_id]/page.tsx` | Reproductor de video |

### Data fetching

Los `page.tsx` son Server Components que hacen `fetch()` directo al backend. La URL base es `http://localhost:8000`. No hay capa de servicio centralizada — el fetch vive dentro de cada página con `cache: "no-store"`.

### Tipos definidos en `src/types/index.ts`

`Course`, `Class`, `CourseDetail`, `Progress`, `Quiz`, `QuizOption`, `FavoriteToggle` — estos tipos anticipan features futuras (progreso, quiz, favoritos) que aún no están implementadas en el backend.

### Convenciones Frontend

- Usar Server Components por defecto; `"use client"` solo cuando sea estrictamente necesario.
- Estilos con SCSS Modules (`.module.scss`) por componente.
- El alias `@/` apunta a `src/`.
- Tests en `__tests__/` o con sufijo `.test.tsx` junto al componente.

---

## Mobile iOS

**Stack:** Swift · SwiftUI · URLSession · async/await · Clean Architecture

### Estructura (Clean Architecture)

```
PlatziFlixiOS/
├── Data/
│   ├── Entities/         # DTOs (CourseDTO, ClassDetailDTO, TeacherDTO)
│   ├── Mapper/           # DTO → Domain (CourseMapper, etc.)
│   └── Repositories/     # RemoteCourseRepository
├── Domain/
│   ├── Models/           # Course, Class, Teacher (modelos de dominio)
│   └── Repositories/     # CourseRepositoryProtocol (interfaz)
├── Presentation/
│   ├── ViewModels/       # CourseListViewModel (@Published)
│   └── Views/            # CourseListView, CourseCardView, DesignSystem
└── Services/             # NetworkManager, NetworkError, APIEndpoint
```

**API base URL:** `http://localhost:8000`  
**Endpoints consumidos:** `GET /courses`, `GET /courses/{slug}`  
**Pantallas implementadas:** Lista de cursos

### Convenciones iOS

- Flujo de datos: API → DTO → Mapper → Domain Model → ViewModel → View.
- No usar URLSession directamente en ViewModels; pasar por el Repository.
- `@MainActor` en ViewModels para seguridad de hilo en actualizaciones de UI.

---

## Mobile Android

**Stack:** Kotlin · Jetpack Compose · Retrofit 2 · OkHttp3 · Coil · Coroutines · Clean Architecture + MVI

### Estructura (Clean Architecture + MVI)

```
PlatziFlixAndroid/app/src/main/java/.../
├── data/
│   ├── entities/         # CourseDTO
│   ├── mappers/          # CourseMapper (DTO → Domain)
│   ├── network/          # ApiService (Retrofit), NetworkModule
│   └── repositories/     # RemoteCourseRepository, MockCourseRepository
├── domain/
│   ├── models/           # Course (modelo de dominio)
│   └── repositories/     # CourseRepository (interfaz)
├── presentation/courses/
│   ├── components/       # CourseCard, LoadingIndicator, ErrorMessage
│   ├── screen/           # CourseListScreen
│   ├── state/            # CourseListUiState (estados MVI)
│   └── viewmodel/        # CourseListViewModel (StateFlow)
├── ui/theme/             # Color, Spacing, Theme, Type
└── di/AppModule.kt       # Inyección de dependencias manual
```

**API base URL:** `http://10.0.2.2:8000` (emulador) · IP dinámica (dispositivo físico)  
**Endpoints consumidos:** `GET /courses`  
**Pantallas implementadas:** Lista de cursos

### Convenciones Android

- Flujo de datos: API → DTO → Mapper → Domain Model → Repository → ViewModel → Compose UI.
- Estado de UI manejado con `StateFlow` y sealed classes (`CourseListUiState`).
- `MockCourseRepository` disponible para tests sin red.
- Inyección de dependencias manual en `AppModule`.

---

## Gaps conocidos y trabajo pendiente

### Desajuste entre Backend y Frontend

El backend devuelve `name` pero el frontend espera `title` en sus tipos TypeScript. Hay campos que el frontend define pero el backend aún no expone: `duration`, `video` (URL del video en clases), `teacher` (nombre en string). Cuando se trabaje en la integración completa, se debe alinear el contrato de la API.

### Feature de Ratings (revertida)

El git log muestra que existió una implementación de sistema de ratings (`course_rating`, `StarRating`, `ratingsApi`) que fue eliminada o está pendiente de reimplementación. Si se retoma, los archivos de referencia serían: `Backend/app/models/course_rating.py`, `Frontend/src/components/StarRating/`, `Frontend/src/services/ratingsApi.ts`.

### Features anticipadas en tipos (Frontend)

Los tipos `Progress`, `Quiz`, `QuizOption` y `FavoriteToggle` están definidos en `src/types/index.ts` pero no tienen endpoints en el backend ni UI implementada. Son el roadmap implícito del producto.

---

## Contexto del proyecto

Este repositorio es el proyecto del **Curso de Claude Code de Platzi** (instructor: Eduardo Alvarez). El desarrollo sirve como ejemplo práctico para aprender a trabajar con Claude Code en un proyecto real full-stack.
