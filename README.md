# Simulacion

Repositorio del proyecto "La Cocina de Kojo" (simulación de eventos discretos).

## Requisitos
- Python 3.8+ Python 3.12 

## Instrucciones

1. Clonar el repositorio:

```bash
git clone https://github.com/DJSixHub/Simulacion.git
```

2. Ejecutar el simulador (desde la raíz del repositorio):

```bash
python -u Simulacion/src/simulator.py
# o usando el ejecutable del venv en Windows:
.venv\Scripts\python.exe -u Simulacion/src/simulator.py
```

El script imprimirá en la terminal un resumen con el porcentaje medio de clientes que esperan más de 5 minutos para los dos escenarios analizados, junto con IC95 y desviación estándar.

## Archivos relevantes
- `Simulacion/src/simulator.py` — script ejecutable de la simulación
- `Simulacion/report/report.tex` — informe LaTeX 

