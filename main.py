import os
import socket
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "modulos"))

from app import create_app

app = create_app()

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))


def _ips_locales():
    ips = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ":" not in ip:
                ips.add(ip)
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return sorted(ips)


if __name__ == "__main__":
    print("=" * 60)
    print("PLANIFICADOR ACADEMICO - Economia UMSS")
    print("Servidor escuchando en %s:%d" % (HOST, PORT))
    print("-" * 60)
    print("Desde esta computadora:")
    print("  http://127.0.0.1:%d" % PORT)
    for ip in _ips_locales():
        print("Desde tu celular (misma red Wi-Fi):")
        print("  http://%s:%d" % (ip, PORT))
    print("-" * 60)
    print("Para conectarte desde tu celular:")
    print("  1. El celular y la PC deben estar en la MISMA red Wi-Fi.")
    print("  2. Abre el navegador del celular y entra a http://IP:5000")
    print("  3. Si no funciona, permite el puerto 5000 en el Firewall de Windows:")
    print("     netsh advfirewall firewall add rule name=Flask5000 "
          "dir=in action=allow protocol=TCP localport=5000")
    print("  4. Para conocer tu IP local:  ipconfig  (busca 'Direccion IPv4')")
    print("  Nota: NO es acceso a internet; solo tu red local.")
    print("=" * 60)
    app.run(debug=True, host=HOST, port=PORT)