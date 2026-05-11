# Análisis Técnico: Implementación Frontend — Sistema de Ratings

## Problema

El frontend de PlatziFlix no tiene UI para mostrar ni enviar ratings de cursos. Se necesita un componente `StarRating` reutilizable, un servicio de API, una utilidad de identidad de usuario vía `localStorage`, y la integración en las cards de curso y en la página de detalle con optimistic UI.

## Impacto Arquitectural

- **Frontend**: nuevo componente `StarRating` (Client Component con modos readonly e interactivo), nuevo Client Component `RatingWidget` con optimistic UI, nuevos módulos `ratingsApi.ts` y `userId.ts`, actualización de tipos TypeScript, integración en `Course.tsx` y `CourseDetail.tsx`.
- **Estado**: `RatingWidget` maneja `averageRating`, `totalRatings`, `userRating` y `isSubmitting` localmente con `useState`.
- **Identidad de usuario**: UUID generado y persistido en `localStorage` bajo `platziflix_user_id`, sin sistema de autenticación.
- **Server/Client boundary**: `CourseDetail.tsx` y `Course.tsx` permanecen como Server Components; `StarRating` y `RatingWidget` son Client Components.

## Propuesta de Solución

Usar el patrón de Server Component padre que pasa datos iniciales a Client Components hijos. `CourseDetail.tsx` pasa `initialAverageRating` e `initialTotalRatings` a `RatingWidget`, evitando convertir el Server Component en cliente. El optimistic UI actualiza el estado local de inmediato y luego sincroniza con la respuesta real del backend. Las medias estrellas se implementan con CSS `clip-path` sin dependencias externas.

## Plan de Implementación

### Fase F1 — Tipos TypeScript *(paralela con B1 del backend)*

**Archivos:**
- `Frontend/src/types/index.ts` — modificar

**Cambios:**
Agregar `average_rating?: number` y `total_ratings?: number` a las interfaces `Course` y `CourseDetail`. Usar `?` (opcional) para mantener retrocompatibilidad con los componentes existentes antes de que el backend exponga estos campos.

**Validación:** `yarn type-check` sin errores; componentes existentes `Course.tsx` y `CourseDetail.tsx` siguen compilando sin cambios.

**Dependencias:** Ninguna.

---

### Fase F2 — Utilidad de identidad de usuario *(requiere F1)*

**Archivos:**
- `Frontend/src/utils/userId.ts` — crear

**Cambios:**
Crear función exportada `getOrCreateUserId(): string`. Verifica si `window` está definido; si no, retorna string vacío (SSR guard). Si `window` existe, lee `platziflix_user_id` de `localStorage`; si no existe, genera UUID con `crypto.randomUUID()`, lo persiste y lo retorna; si existe, lo retorna directamente.

**Validación:** Primera llamada en navegador genera y persiste UUID; segunda llamada retorna el mismo valor; en contexto SSR retorna string vacío sin lanzar error.

**Dependencias:** F1.

---

### Fase F3 — Servicio ratingsApi *(requiere F1, paralela con F2)*

**Archivos:**
- `Frontend/src/services/ratingsApi.ts` — crear

**Cambios:**
Crear función `submitRating(slug: string, userId: string, rating: number): Promise<{ average_rating: number; total_ratings: number }>`: POST a `http://localhost:8000/courses/{slug}/ratings` con body `{ user_id, rating }`, retorna las stats actualizadas; lanza error si la respuesta no es ok. Crear función `getUserRating(slug: string, userId: string): Promise<number | null>`: GET a `http://localhost:8000/courses/{slug}/ratings/me?user_id={userId}` sin caché; retorna `null` si status 404, retorna `data.rating` si ok, lanza error en cualquier otro caso. Sin dependencias de `window` ni `localStorage`.

**Validación:** POST genera request visible en DevTools hacia la URL correcta; `getUserRating` retorna `null` en 404; `yarn type-check` sin errores.

**Dependencias:** F1.

---

### Fase F4 — Componente StarRating *(requiere F1)*

**Archivos:**
- `Frontend/src/components/StarRating/StarRating.tsx` — crear
- `Frontend/src/components/StarRating/StarRating.module.scss` — crear

**Cambios:**
Crear Client Component (`"use client"`) con props: `averageRating: number`, `totalRatings: number`, `courseId: string`, `userRating?: number`, `onRate?: (rating: number) => void`.

Modo readonly (sin `onRate`): cada estrella calcula su fill desde `averageRating`; las medias estrellas usan clase CSS con `clip-path: inset(0 50% 0 0)` sobre una capa de estrella llena superpuesta a la vacía; sin event handlers.

Modo interactivo (con `onRate`): `useState` para `hoverRating: number | null`; `onMouseEnter` por estrella actualiza `hoverRating`; `onMouseLeave` en el contenedor lo resetea a `null`; el fill usa `hoverRating ?? userRating ?? 0`; `onClick` llama `onRate(value)`. Incluir `aria-label` descriptivo en cada estrella y mostrar total de ratings junto a las estrellas.

**Validación:** `averageRating=3.5` renderiza 3 llenas + 1 media + 1 vacía; hover ilumina correctamente; click dispara `onRate` con el valor correcto; `yarn type-check` sin errores.

**Dependencias:** F1.

---

### Fase F5 — Integración de StarRating en Course.tsx *(requiere F1 + F4)*

**Archivos:**
- `Frontend/src/components/Course/Course.tsx` — modificar

**Cambios:**
Importar `StarRating` desde `@/components/StarRating/StarRating`. Agregar `<StarRating>` en modo readonly dentro del JSX de la card, pasando `averageRating={course.average_rating ?? 0}`, `totalRatings={course.total_ratings ?? 0}`, `courseId={course.slug}`. El operador `??` garantiza que `undefined` no rompe el render mientras el backend no expone los campos.

**Validación:** Home (`/`) carga sin errores; cards muestran estrellas; `undefined` en rating no rompe la UI; `yarn build` sin errores de tipo.

**Dependencias:** F1, F4.

---

### Fase F6 — Componente RatingWidget *(requiere F1 + F2 + F3 + F4)*

**Archivos:**
- `Frontend/src/components/CourseDetail/RatingWidget.tsx` — crear

**Cambios:**
Crear Client Component (`"use client"`) con props: `slug: string`, `initialAverageRating: number`, `initialTotalRatings: number`.

Estado interno con `useState`: `averageRating` (init: `initialAverageRating`), `totalRatings` (init: `initialTotalRatings`), `userRating: number | null` (init: `null`), `isSubmitting: boolean` (init: `false`).

`useEffect` vacío (on mount): llama `getOrCreateUserId()`, luego `getUserRating(slug, userId)`; si retorna número, actualiza `userRating`.

Handler de voto: guarda `prevRating`, actualiza `userRating` de inmediato (optimistic), marca `isSubmitting: true`, llama `submitRating(slug, userId, rating)`, en éxito actualiza `averageRating` y `totalRatings` con los valores del servidor, en error revierte `userRating` a `prevRating`, siempre marca `isSubmitting: false` al finalizar.

Renderiza `<StarRating>` en modo interactivo pasando el estado actual y el handler. Mientras `isSubmitting` es true, deshabilita la interacción visual.

**Validación:** Stars pre-seleccionadas si el usuario ya votó; cambio visual inmediato al votar; stats actualizadas tras respuesta del servidor; reversión en error.

**Dependencias:** F1, F2, F3, F4.

---

### Fase F7 — Integración de RatingWidget en CourseDetail.tsx *(requiere F1 + F5 + F6)*

**Archivos:**
- `Frontend/src/components/CourseDetail/CourseDetail.tsx` — modificar

**Cambios:**
Importar `RatingWidget` desde `@/components/CourseDetail/RatingWidget`. El componente permanece como Server Component. Renderizar `<RatingWidget slug={course.slug} initialAverageRating={course.average_rating ?? 0} initialTotalRatings={course.total_ratings ?? 0} />` en una posición visible del layout (debajo del título, antes de la lista de clases).

**Validación:** `/course/[slug]` carga sin errores; `RatingWidget` visible y funcional; flujo E2E completo (cargar → ver rating promedio → votar → ver nuevo promedio → recargar → voto pre-seleccionado); `yarn build` y `yarn type-check` sin errores.

**Dependencias:** F1, F5, F6.

---

## Dependencias entre fases

```
F1 ─── F2 ──────────────────────── F6 ─── F7
    └── F3 (paralela con F2) ─────┘
    └── F4 ─── F5 ────────────────┘
```

**Nota de integración:** Las fases F5 y F7 (integración en componentes existentes) requieren que el backend (fases B4 y B5) esté completo para verificar el flujo E2E. Las fases F1–F4 pueden desarrollarse en paralelo con el backend.
