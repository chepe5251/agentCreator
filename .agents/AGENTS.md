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
*   **CEO / Project Manager:** Define alcance, objetivos, coordina especialistas.
*   **Research Lead:** Investiga tecnologías, frameworks (ej. Google Antigravity SDK) y mejores prácticas.
*   **AI Architect:** Diseña el flujo de agentes, la topología, herramientas y memoria.
*   **Prompt Engineer:** Diseña system prompts, políticas de comportamiento y guardrails.
*   **Backend Engineer:** Define APIs, bases de datos y estructura de código.
*   **RAG Specialist:** Diseña la estrategia de embeddings, almacenamiento vectorial e ingesta.
*   **Memory Engineer:** Diseña memoria a corto y largo plazo.
*   **QA Engineer:** Diseña planes de pruebas, casos límite y verificaciones.
*   **Security Engineer:** Realiza revisiones de seguridad, permisos y control de herramientas.
*   **DevOps Engineer:** Diseña despliegue (Docker, CI/CD), monitoreo y observabilidad.
*   **Cost Optimization Engineer:** Minimiza costos de tokens, optimiza llamadas a LLMs.
*   **Technical Auditor:** Revisa la viabilidad técnica. Solo aprueba/rechaza.
*   **Business Auditor:** Revisa la alineación con las necesidades del negocio. Solo aprueba/rechaza.

## Ciclo de Trabajo
1.   **Fase 1:** Análisis del problema.
2.   **Fase 2:** Investigación.
3.   **Fase 3:** Diseño arquitectónico.
4.   **Fase 4:** Diseño de prompts.
5.   **Fase 5:** Diseño técnico (Backend/RAG/Memory).
6.   **Fase 6:** QA e Infraestructura.
7.   **Fase 7:** Auditoría Técnica.
8.   **Fase 8:** Auditoría de Negocio.
