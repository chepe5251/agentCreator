# Agent Factory Enterprise

Agent Factory Enterprise es una organización autónoma de agentes de inteligencia artificial coordinados para diseñar, desarrollar, revisar y auditar proyectos. El sistema funciona en un bucle iterativo de hasta 10 iteraciones de auto-corrección, garantizando la calidad y la seguridad del código generado antes de su aprobación final.

## Estructura Organizativa (13 Roles)

El sistema coordina trece especialistas clasificados en cuatro fases de trabajo:
1. **Fase de Planificación e Investigación:**
   - **Project Manager:** Define el alcance y coordina las correcciones en el bucle.
   - **Research Lead:** Investiga tecnologías y bibliotecas de software recomendadas.
   - **AI Architect:** Diseña el flujo de agentes, topología y diagramas arquitectónicos.
   - **Prompt Engineer:** Diseña las directrices de prompts e instrucciones del sistema.
2. **Fase de Desarrollo:**
   - **Backend Engineer:** Implementa la lógica principal de la aplicación y APIs en Python.
   - **RAG Specialist:** Diseña e implementa la recuperación y procesamiento de conocimiento vectorial.
   - **Memory Engineer:** Diseña e implementa la persistencia de conversaciones y base de datos.
3. **Fase de Análisis de Calidad y Entorno:**
   - **QA Engineer:** Crea pruebas unitarias automatizadas y las ejecuta.
   - **Security Engineer:** Analiza el código buscando vulnerabilidades de inyección, credenciales expuestas, etc.
   - **DevOps Engineer:** Genera la configuración de contenedores (Dockerfile, Docker Compose) y despliegue.
   - **Cost Optimization Engineer:** Estima el coste de tokens y sugiere modelos optimizados.
4. **Fase de Auditoría de Conformidad:**
   - **Technical Auditor:** Verifica la viabilidad técnica y que los tests y compilaciones pasen.
   - **Business Auditor:** Asegura la alineación con las intenciones de negocio y previene la sobreingeniería.

## Bucle de Auditoría Autocorrectiva

```
        ┌──────────────────────────┐
        │     Inicio del Prompt    │
        └─────────────┬────────────┘
                      │
                      ▼
        ┌──────────────────────────┐
        │   Fase 1-6: Desarrollo   │◄──────────────────────────┐
        │  (PM, Devs, Analistas)   │                           │
        └─────────────┬────────────┘                           │
                      │                                        │
                      ▼                                        │
        ┌──────────────────────────┐                           │
        │   Auditoría de Control   │                           │
        │ (Técnica & de Negocios)  │                           │
        └─────────────┬────────────┘                           │
                      │                                        │
         [¿Aprobado?]─┴────────────┐                           │
                │                  │                           │
              Sí│                No│                           │
                ▼                  ▼                           │
        ┌───────────────┐  ┌───────────────┐                   │
        │ APROBACIÓN    │  │ Bucle de Fix  │───────────────────┘
        │   (Final)     │  │ (PM a Devs)   │ (Máx 10 iteraciones)
        └───────────────┘  └───────────────┘
```

## Requisitos de Instalación

El proyecto se ejecuta en un entorno virtual aislado:

1. **Crear e iniciar el entorno virtual:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
2. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Configurar el proveedor de IA:**
   Cree un archivo `.env` en la raíz del proyecto. El sistema soporta múltiples proveedores vía [LiteLLM](https://docs.litellm.ai/docs/providers):

   **OpenAI (ChatGPT):**
   ```env
   LLM_FAST_MODEL=gpt-4o-mini
   LLM_REASONING_MODEL=gpt-4o
   OPENAI_API_KEY=sk-...
   ```

   **Anthropic (Claude):**
   ```env
   LLM_FAST_MODEL=anthropic/claude-3-5-haiku-20241022
   LLM_REASONING_MODEL=anthropic/claude-3-5-sonnet-20241022
   ANTHROPIC_API_KEY=sk-ant-...
   ```

   **Ollama (local):**
   ```env
   LLM_FAST_MODEL=ollama/llama3.2
   LLM_REASONING_MODEL=ollama/llama3.2
   OLLAMA_API_BASE=http://localhost:11434
   ```

   **Google Gemini:**
   ```env
   LLM_FAST_MODEL=gemini/gemini-2.0-flash
   LLM_REASONING_MODEL=gemini/gemini-1.5-pro
   GEMINI_API_KEY=...
   ```

## Ejecución del Sistema

Para ejecutar el orquestador y crear un proyecto, use el comando:

```bash
python3 main.py --prompt "Crear un bot de Telegram que recuerde el contexto de los usuarios y use una base de datos SQLite local"
```

Los entregables generados se escribirán en la carpeta `output/`. Los registros e historial de auditoría de cada iteración se guardarán en `logs/`.

## Ejecución de Pruebas Unitarias

Para ejecutar el conjunto de pruebas unitarias y verificar el funcionamiento del orquestador, ejecute:

```bash
python3 -m unittest discover -s tests
```
