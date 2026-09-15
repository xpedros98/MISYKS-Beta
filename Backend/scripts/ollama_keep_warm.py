#!/usr/bin/env python3
"""Mantiene el modelo de resumen de MISYKS-Beta cargado en RAM en Ollama.

Sin esto, Ollama descarga el modelo tras ~5 minutos sin uso y la siguiente
peticion real paga el coste de cargarlo de disco (varios segundos extra,
medido: ~3.4s en llama3.2:3b). Este script manda una peticion minima (genera
1 solo token) cada 4 minutos para resetear ese temporizador de inactividad,
asi que toda peticion real de resumen cae siempre sobre un modelo ya
caliente.

Ejecutar via cron cada 4 minutos:
    */4 * * * * /usr/bin/python3 /root/misyks-beta/Backend/scripts/ollama_keep_warm.py >> /var/log/misyks-keep-warm.log 2>&1

Independiente del keep-warm del ecosistema antiguo (~/maat/scripts/), que
apunta a otro modelo (gemma3:12b) para otro proposito.

Modelo elegido tras comparar con datos reales en maat (12 nucleos, 62GB RAM,
sin GPU): llama3.2:3b resume rapido (~1.9s en caliente) pero pierde matices
en correos con mas de un tema; qwen2.5:7b es ~2.2x mas lento por token pero
capturo correctamente los dos asuntos de un correo de prueba con dos temas.
Con 10 peticiones simultaneas de verdad, ninguno de los dos modelos fallo;
qwen2.5:7b tardo entre 4s y 36.6s en el peor caso (vs. 2.1s-21.8s de
llama3.2:3b) -- aceptable porque el resumen se genera en segundo plano, sin
bloquear al usuario.
"""
import json
import sys
import urllib.request

MODELO = "qwen2.5:7b"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"


def main():
    peticion = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(
            {
                "model": MODELO,
                "messages": [{"role": "user", "content": "ok"}],
                "stream": False,
                "options": {"num_predict": 1},
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=30):
            print(f"[keep-warm] OK {MODELO} cargado")
    except Exception as e:
        print(f"[keep-warm] ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
