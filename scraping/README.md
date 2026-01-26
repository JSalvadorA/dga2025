# Web Scraping - Consulta Amigable MEF

Scripts para extraer datos presupuestales del portal de Transparencia Económica del MEF.

## Descripción

El portal [Consulta Amigable](https://apps5.mineco.gob.pe/transparencia/) permite consultar la ejecución presupuestal del sector público peruano. Estos scripts automatizan la extracción de datos a nivel de Unidad Ejecutora.

## Requisitos

- Python 3.10+
- Google Chrome
- ChromeDriver (compatible con tu versión de Chrome)
- Selenium

```bash
pip install selenium pandas tqdm
```

## Archivos

| Archivo | Descripción |
|---------|-------------|
| `run_scrape.py` | Ejecución secuencial (más estable) |
| `run_parallel.py` | Ejecución paralela (más rápido) |
| `scraper.py` | Lógica principal de Selenium |
| `routes.py` | Configuración de rutas y niveles de gobierno |
| `padron.py` | Filtrado por padrón SIGA |
| `config.py` | Configuración general |
| `db.py` | Conexión a base de datos |
| `utils.py` | Funciones auxiliares |

## Uso

### Ejecución Secuencial

```bash
python run_scrape.py --years 2022 2023 2024 2025
```

### Ejecución Paralela

```bash
python run_parallel.py --years 2022 2023 2024 2025 --workers 4
```

### Opciones

- `--years`: Años a procesar
- `--workers`: Número de workers paralelos (solo `run_parallel.py`)
- `--nivel`: Nivel de gobierno (E=Nacional, M=Regional, L=Local)

## Datos Extraídos

Para cada Unidad Ejecutora se extrae:

- **SEC_EJEC**: Código de sector-pliego-ejecutora
- **PIA**: Presupuesto Institucional de Apertura
- **PIM**: Presupuesto Institucional Modificado
- **DEVENGADO**: Monto devengado
- **AVANCE**: Porcentaje de ejecución

## Salida

Los datos se guardan en formato Parquet:

```
output/
├── 2022/
│   ├── nivel_E.parquet
│   ├── nivel_M.parquet
│   └── nivel_L.parquet
├── 2023/
│   └── ...
└── ...
```

## Consideraciones

- El portal tiene rate limiting; usar delays entre requests
- Ejecutar en horarios de baja demanda
- Los datos son públicos y de acceso libre
