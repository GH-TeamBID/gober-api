# Gober API

API para gestión de licitaciones gubernamentales.

## Arquitectura

Este proyecto sigue una arquitectura monolítica modular con FastAPI:

- **Monolítica**: Una sola aplicación que contiene toda la lógica de negocio.
- **Modular**: Organizada en módulos independientes por dominio de negocio.

## Estructura del Proyecto

```
app/
├── core/                  # Componentes centrales
│   ├── config.py          # Configuración centralizada
│   ├── database.py        # Conexión a base de datos
│   └── init_db.py         # Inicialización de la base de datos
├── modules/               # Módulos de la aplicación
│   ├── auth/              # Módulo de autenticación
│   ├── clients/           # Módulo de clientes
│   ├── tenders/           # Módulo de licitaciones
│   └── ai_tools/          # Módulo de herramientas de IA
└── main.py                # Punto de entrada de la aplicación
```

## Configuración Centralizada

La configuración está centralizada en `app/core/config.py` usando Pydantic Settings:

1. Todas las configuraciones se definen en la clase `Settings`
2. Los valores por defecto se pueden sobrescribir con variables de entorno
3. Se usa un archivo `.env` para configuración local

### Cómo usar la configuración

```python
from app.core.config import settings

# Acceder a la configuración
db_name = settings.DB_NAME
secret_key = settings.SECRET_KEY
```

## Instalación

1. Clonar el repositorio
2. Crear un entorno virtual: `python -m venv api-venv`
3. Activar el entorno virtual:
   - Windows: `api-venv\Scripts\activate`
   - Linux/Mac: `source api-venv/bin/activate`
4. Instalar dependencias: `pip install -r requirements.txt`
5. Copiar `.env.example` a `.env` y configurar las variables
6. Inicializar la base de datos: `python -m app.core.init_db`

## Ejecución

```bash
# Desarrollo
python -m app.main

# Producción
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Acceso a la API

- Documentación Swagger: http://localhost:8000/docs
- Documentación ReDoc: http://localhost:8000/redoc
- API Base URL: http://localhost:8000/api 