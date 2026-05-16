import heapq
import math
import random
import statistics
import collections
import os


# Prioridad de eventos: cambios de capacidad (antes), salidas (después), llegadas (últimas)
PRIORIDAD = {"capacity": 0, "departure": 1, "arrival": 2}


class Servidor:
    """Representa un servidor (empleado)."""

    def __init__(self, sid: int):
        self.id = sid
        self.en_turno = False
        self.ocupado = False
        self.marcado_para_retiro = False
        self.proximo_libre = None


def es_pico(t_min: float) -> bool:
    """Devuelve True si el tiempo (minutos desde apertura) está en periodo pico."""
    return (90.0 <= t_min < 210.0) or (420.0 <= t_min < 540.0)


def personal_necesario(t_min: float, escenario: str) -> int:
    """Devuelve el número de empleados requeridos según el escenario y el tiempo."""
    if escenario == "two_servers":
        return 2
    if escenario == "three_servers_peaks":
        return 3 if es_pico(t_min) else 2
    raise ValueError("Escenario desconocido")


def generar_llegadas(rng: random.Random, params: dict):
    """Genera la lista de llegadas (tiempo, producto, id) para un día.

    Las llegadas se generan por tramos con tasa exponencial constante en cada tramo.
    """
    T = params.get("T", 660.0)
    lam_off = params.get("lambda_off", 0.1)
    lam_peak = params.get("lambda_peak", 0.3)
    p_sandwich = params.get("p_sandwich", 0.6)

    segmentos = [
        (0.0, 90.0, lam_off),
        (90.0, 210.0, lam_peak),
        (210.0, 420.0, lam_off),
        (420.0, 540.0, lam_peak),
        (540.0, T, lam_off),
    ]

    llegadas = []
    cid = 0
    for inicio, fin, lam in segmentos:
        if lam <= 0:
            continue
        t = inicio
        while True:
            ia = rng.expovariate(lam)
            t += ia
            if t >= fin:
                break
            prod = "sandwich" if rng.random() < p_sandwich else "sushi"
            llegadas.append({"time": t, "product": prod, "id": cid})
            cid += 1

    llegadas.sort(key=lambda x: x["time"])
    return llegadas


def simular_dia(seed: int, escenario: str, params: dict):
    """Simula un día y devuelve estadísticas de tiempos de espera."""
    rng = random.Random(seed)
    llegadas = generar_llegadas(rng, params)
    T = params.get("T", 660.0)
    service_ranges = params.get("service_ranges", {"sandwich": (3.0, 5.0), "sushi": (5.0, 8.0)})

    # preparar cola de eventos (heap por tiempo, con prioridad para romper empates)
    cola_eventos = []
    contador = 0

    def poner_evento(tiempo, tipo_ev, datos=None):
        nonlocal contador
        if datos is None:
            datos = {}
        heapq.heappush(cola_eventos, (tiempo, PRIORIDAD[tipo_ev], contador, {"type": tipo_ev, **datos}))
        contador += 1

    # eventos de cambio de dotación en los límites de tramos
    for t in [0.0, 90.0, 210.0, 420.0, 540.0, T]:
        poner_evento(t, "capacity", {})

    # eventos de llegada
    for a in llegadas:
        poner_evento(a["time"], "arrival", {"arrival_time": a["time"], "product": a["product"], "id": a["id"]})

    # inicializar servidores (máx. 3)
    servidores = [Servidor(i) for i in range(3)]

    cola = collections.deque()
    tiempos_espera = []

    while cola_eventos:
        tiempo_actual, _, _, ev = heapq.heappop(cola_eventos)
        tipo_evento = ev["type"]

        if tipo_evento == "capacity":
            deseado = personal_necesario(tiempo_actual, escenario)
            en_turno = sum(1 for s in servidores if s.en_turno)

            if deseado > en_turno:
                por_agregar = deseado - en_turno
                for s in servidores:
                    if por_agregar <= 0:
                        break
                    if not s.en_turno and not s.marcado_para_retiro:
                        s.en_turno = True
                        por_agregar -= 1

                # asignar clientes en cola a servidores recién incorporados
                while cola and any((sv.en_turno and not sv.ocupado) for sv in servidores):
                    servidor_libre = next(sv for sv in servidores if sv.en_turno and not sv.ocupado)
                    cliente = cola.popleft()
                    espera = tiempo_actual - cliente["arrival_time"]
                    tiempos_espera.append(espera)
                    lo, hi = service_ranges[cliente["product"]]
                    st = rng.uniform(lo, hi)
                    servidor_libre.ocupado = True
                    servidor_libre.proximo_libre = tiempo_actual + st
                    poner_evento(tiempo_actual + st, "departure", {"server_id": servidor_libre.id})

            elif deseado < en_turno:
                por_quitar = en_turno - deseado
                # quitar inactivos primero
                for s in reversed(servidores):
                    if por_quitar <= 0:
                        break
                    if s.en_turno and not s.ocupado:
                        s.en_turno = False
                        por_quitar -= 1

                # si aún hay que reducir, marcar algunos ocupados para retiro al finalizar
                for s in reversed(servidores):
                    if por_quitar <= 0:
                        break
                    if s.en_turno and s.ocupado and not s.marcado_para_retiro:
                        s.marcado_para_retiro = True
                        s.en_turno = False
                        por_quitar -= 1

                # tras cambios, asignar clientes si hay servidores libres
                while cola and any((sv.en_turno and not sv.ocupado) for sv in servidores):
                    servidor_libre = next(sv for sv in servidores if sv.en_turno and not sv.ocupado)
                    cliente = cola.popleft()
                    espera = tiempo_actual - cliente["arrival_time"]
                    tiempos_espera.append(espera)
                    lo, hi = service_ranges[cliente["product"]]
                    st = rng.uniform(lo, hi)
                    servidor_libre.ocupado = True
                    servidor_libre.proximo_libre = tiempo_actual + st
                    poner_evento(tiempo_actual + st, "departure", {"server_id": servidor_libre.id})

        elif tipo_evento == "arrival":
            prod = ev["product"]
            hora_llegada = ev["arrival_time"]
            # buscar servidor libre y en turno
            idle = next((s for s in servidores if s.en_turno and not s.ocupado), None)
            if idle is not None:
                # atender inmediatamente
                lo, hi = service_ranges[prod]
                st = rng.uniform(lo, hi)
                idle.ocupado = True
                idle.proximo_libre = tiempo_actual + st
                poner_evento(tiempo_actual + st, "departure", {"server_id": idle.id})
                tiempos_espera.append(0.0)
            else:
                cola.append({"arrival_time": hora_llegada, "product": prod})

        elif tipo_evento == "departure":
            sid = ev["server_id"]
            srv = servidores[sid]
            srv.ocupado = False
            srv.proximo_libre = None
            if srv.marcado_para_retiro:
                srv.marcado_para_retiro = False
                srv.en_turno = False

            # asignar siguientes clientes en cola a servidores libres
            while cola and any((sv.en_turno and not sv.ocupado) for sv in servidores):
                asign = next(sv for sv in servidores if sv.en_turno and not sv.ocupado)
                cliente = cola.popleft()
                espera = tiempo_actual - cliente["arrival_time"]
                tiempos_espera.append(espera)
                lo, hi = service_ranges[cliente["product"]]
                st = rng.uniform(lo, hi)
                asign.ocupado = True
                asign.proximo_libre = tiempo_actual + st
                poner_evento(tiempo_actual + st, "departure", {"server_id": asign.id})

    total = len(tiempos_espera)
    over5 = sum(1 for w in tiempos_espera if w > 5.0)
    pct = (over5 / total * 100.0) if total > 0 else 0.0
    return {"total": total, "over5": over5, "percent": pct, "waits": tiempos_espera}


def ejecutar_replicas(n_rep: int, escenario: str, params: dict, seed0: int = 12345):
    """Ejecuta réplicas y devuelve estadísticos del porcentaje pedido."""
    resultados = []
    for i in range(n_rep):
        seed = seed0 + i
        r = simular_dia(seed, escenario, params)
        resultados.append(r["percent"])
    mean = statistics.mean(resultados) if resultados else 0.0
    stdev = statistics.stdev(resultados) if len(resultados) > 1 else 0.0
    ci95 = 1.96 * stdev / math.sqrt(len(resultados)) if len(resultados) > 1 else 0.0
    return {"n": n_rep, "mean_percent": mean, "stdev": stdev, "ci95": ci95, "samples": resultados}


def imprimir_resumen(res_two: dict, res_three: dict, params: dict, n_rep: int):
    avg_customers = params.get("lambda_off", 0.1) * 420 + params.get("lambda_peak", 0.3) * 240
    print("Simulación: La Cocina de Kojo")
    print(f"Réplicas por experimento: {n_rep}")
    print(f"Clientes promedio por día (esperanza): {avg_customers:.1f}")
    print("")
    print("Escenario: Dos empleados")
    print(f"  Porcentaje medio de clientes que esperan > 5 min: {res_two['mean_percent']:.3f}%")
    print(f"  Desvío estándar (samples): {res_two['stdev']:.3f}")
    print(f"  IC95: ±{res_two['ci95']:.3f}")
    print("")
    print("Escenario: Tres empleados (picos)")
    print(f"  Porcentaje medio de clientes que esperan > 5 min: {res_three['mean_percent']:.3f}%")
    print(f"  Desvío estándar (samples): {res_three['stdev']:.3f}")
    print(f"  IC95: ±{res_three['ci95']:.3f}")


def principal():
    params = {
        "T": 660.0,
        "lambda_off": 0.1,
        "lambda_peak": 0.3,
        "p_sandwich": 0.6,
        "service_ranges": {"sandwich": (3.0, 5.0), "sushi": (5.0, 8.0)},
    }

    n_rep = 1000
    print("Ejecutando...")
    res_two = ejecutar_replicas(n_rep, "two_servers", params, seed0=12345)
    res_three = ejecutar_replicas(n_rep, "three_servers_peaks", params, seed0=98765)
    imprimir_resumen(res_two, res_three, params, n_rep)


if __name__ == "__main__":
    principal()
    
