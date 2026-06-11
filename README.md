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
