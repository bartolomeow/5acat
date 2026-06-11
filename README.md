# 5aCAT - Golf Tournament Analysis

Sistema de análisis y gestión de resultados de torneos de golf para el circuito 5aCAT.

## Descripción

Este proyecto procesa datos de jugadores y torneos, generando reportes HTML con estadísticas y clasificaciones de participantes en el circuito de golf 5aCAT.

## Estructura del Proyecto

```
5acat/
├── src/                      # Código fuente Python
│   └── analyze_golf.py       # Script principal de análisis
├── data/                     # Datos del proyecto
│   ├── raw/                  # Datos crudos (JSON)
│   │   └── data.json         # Base de datos de jugadores y resultados
│   └── tournaments/          # Información de torneos
│       └── torneos.txt       # Listado de torneos del circuito
├── output/                   # Archivos generados
│   └── reports/              # Reportes HTML generados
├── requirements.txt          # Dependencias de Python
└── README.md                 # Este archivo
```

## Instalación

1. Clonar el repositorio
2. Crear un entorno virtual (opcional pero recomendado)
3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

## Uso

```bash
python src/analyze_golf.py [opciones]
```

## Datos

- **data.json**: Contiene la información de jugadores registrados, sus resultados históricos y estadísticas
- **torneos.txt**: Lista de torneos del circuito 5aCAT con fechas de celebración

## Salida

Los reportes generados se guardan en `output/reports/` en formato HTML con el siguiente patrón de nombre:
`resultados_[NOMBRE]_[FECHA]_[HORA].html`

## Licencia

Proyecto privado del circuito de golf 5aCAT

## Archivos no versionados

Los siguientes archivos / rutas están en `.gitignore` y NO se suben al repositorio. Debes mantener copias locales si las necesitas:

- `data/raw/data.json` — Datos crudos de jugadores y resultados.
- `data/tournaments/torneos.txt` — Calendario y lista de torneos.
- `requirements.txt` — Lista local de dependencias (no se comparte por defecto).

Instrucciones prácticas:

1. Coloca tus datos locales en las rutas anteriores para que el script pueda procesarlos.

2. Si necesitas generar o actualizar `requirements.txt` en tu entorno local, ejecuta:

```bash
pip freeze > requirements.txt
```

3. Para asegurarte de no subir accidentalmente estos archivos si ya estaban en el índice de git, ejecuta (una sola vez):

```bash
git rm --cached data/raw/data.json data/tournaments/torneos.txt requirements.txt
git commit -m "Stop tracking local data and requirements"
```

4. Si quieres compartir plantillas de datos sin exponer información sensible, crea archivos de ejemplo como `data/raw/data.example.json` y añádelos al repositorio.

Si quieres que añada ejemplos o plantillas de datos, lo hago a continuación.
