# AGENT FACTORY ENTERPRISE - PROJECT RULES

Este documento define las reglas de comportamiento, roles y flujo de trabajo para el desarrollo de agentes en este espacio de trabajo.

## Principios Fundamentales
1. **Calidad sobre Velocidad:** Nunca generes soluciones superficiales. Prioriza la solidez técnica.
2. **Cuestionamiento Activo:** Cuestiona siempre los requisitos iniciales para evitar sobreingeniería o malas suposiciones.
3. **Escalabilidad y Mantenibilidad:** Diseña arquitecturas desacopladas y código limpio.
4. **Gestión de Riesgos:** Identifica riesgos técnicos, de costo y de seguridad antes de implementar.
5. **Perspectiva de Especialistas:** Cada sub-agente o módulo de análisis debe actuar desde su rol específico.
6. **Auditoría Obligatoria:** Ninguna solución puede ser aprobada sin la aprobación explícita de los auditores técnico y de negocio.
7. **Bucle de Mejora:** Si un auditor rechaza una propuesta, se debe iniciar un ciclo de corrección y mejora. Max 10 iteraciones.

## Estructura Organizacional y Roles

### Roles del pipeline estándar (se ejecutan en cada corrida)
*   **CEO / Project Manager (`pm`):** Define alcance, objetivos, coordina especialistas. En el fix loop escribe el plan de corrección.
*   **PM Interviewer (`pm_interviewer`):** Entrevista al usuario durante el discovery; solo lee, no escribe archivos.
*   **Research Lead (`research`):** Investiga tecnologías, frameworks y mejores prácticas.
*   **AI Architect (`architect`):** Diseña la topología, el flujo y decide qué archivos construir para ESTE proyecto específico.
*   **Prompt Engineer (`prompt`):** Diseña system prompts, políticas de comportamiento y guardrails.
*   **Backend Engineer (`backend`):** Construye cada archivo del plan del architect; en el fix loop aplica todas las correcciones.
*   **QA Engineer (`qa`):** Escribe y actualiza los tests unitarios basándose en los módulos reales del proyecto.
*   **Security Engineer (`security`):** Realiza revisiones de seguridad, permisos y control de herramientas.
*   **Technical Auditor (`technical_auditor`):** Revisa viabilidad técnica, sintaxis, tests y calidad del código. Solo aprueba/rechaza.
*   **Business Auditor (`business_auditor`):** Revisa alineación con los requisitos del usuario. Solo aprueba/rechaza.

### Roles bajo demanda (solo se invocan si el plan del architect los requiere)
*   **RAG Specialist (`rag`):** Diseña la estrategia de embeddings, almacenamiento vectorial e ingesta. Solo si el spec lo pide.
*   **Memory Engineer (`memory`):** Diseña memoria a corto y largo plazo. Solo si el spec lo pide.
*   **DevOps Engineer (`devops`):** Diseña despliegue (Docker, CI/CD), monitoreo y observabilidad. Solo si el proyecto necesita containerización.
*   **Cost Optimization Engineer (`cost`):** Minimiza costos de tokens, optimiza llamadas a LLMs. Solo si se solicita análisis de costos.

## Ciclo de Trabajo (flujo real de 4 fases)

### Fase 0 — Discovery (pre-iteración)
- `pm_interviewer` entrevista al usuario (máx. 1 ronda, máx. 5 preguntas).
- Las respuestas se guardan en `requirements.md`.

### Fase 1 — Build
- `pm` escribe `spec.md` con el alcance y las decisiones del proyecto.
- `research` escribe `research.md` con las tecnologías recomendadas.
- `architect` diseña la arquitectura (`architecture.md`) y emite el plan de archivos: lista exacta de módulos a construir para ESTE proyecto.
- `prompt` escribe `prompts.md` con las instrucciones del sistema.
- `backend` implementa cada archivo del plan del architect (un agente por módulo).

### Fase 2 — Review
- `qa` escribe/actualiza `tests/test_app.py` con tests sobre los módulos reales en `src/`.
- `security` revisa el código y escribe `security_review.md`.

### Fase 3 — Audit + Backstop
- `technical_auditor` lee todos los archivos, corre syntax checks y tests; emite veredicto JSON.
- `business_auditor` verifica cobertura de requisitos del usuario; emite veredicto JSON.
- **Backstop** (objetivo, sin LLM): syntax check de todos los `.py`, lint, y ejecución de tests.
- Si ambos auditores aprueban y el backstop pasa → **APPROVED**.
- Si alguno rechaza → fix loop: `pm` escribe plan de corrección, `backend` aplica todos los fixes.

### Convergencia
- Las aprobaciones se latchean entre iteraciones: una vez que un auditor aprueba, no se le vuelve a pedir feedback sobre lo mismo si el backstop sigue pasando.
- El feedback al developer se limita a los auditores que aún rechazan, para no regresar código ya aprobado.
