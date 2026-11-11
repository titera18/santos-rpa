"""Site local: http://localhost:8765"""
from flask import Flask, jsonify, redirect, render_template, request, url_for

from .modelos import catalogo
from .textos import moeda

ESTILOS = {"custom": "Custom", "classica": "Clássica", "estradeira": "Estradeira clássica"}
FONTES = {"olx": "OLX", "mercadolivre": "Mercado Livre"}


def criar_app(config, banco, coletor) -> Flask:
    app = Flask(__name__)
    app.jinja_env.filters["moeda"] = moeda
    app.jinja_env.globals.update(ESTILOS=ESTILOS, FONTES=FONTES)

    def km(v):
        return "—" if v is None else f"{v:,} km".replace(",", ".")
    app.jinja_env.filters["km"] = km

    @app.route("/")
    def inicio():
        aba = request.args.get("aba", "alertas")
        filtros = {
            "estilo": request.args.get("estilo") or None,
            "fonte": request.args.get("fonte") or None,
            "preco_max": request.args.get("preco_max") or None,
            "ordem": request.args.get("ordem", "desconto"),
            "dias": request.args.get("dias") or None,
        }
        if aba == "alertas":
            itens = banco.alertas(limite=200)
            banco.marcar_alertas_lidos()
        else:
            itens = banco.anuncios(apenas_alertas=False, **filtros)
        return render_template(
            "index.html", aba=aba, itens=itens, filtros=filtros, regras=config["regras"],
            stats=banco.estatisticas(), coleta=banco.ultima_coleta(), status=coletor.status,
            intervalo=config["intervalo_minutos"], modelos=catalogo(config),
            ultimo_alerta=(banco.alertas(limite=1) or [{"alerta_id": 0}])[0]["alerta_id"])

    @app.route("/anuncio/<path:anuncio_id>")
    def detalhe(anuncio_id):
        a = banco.anuncio(anuncio_id)
        if not a:
            return redirect(url_for("inicio"))
        return jsonify({**a, "historico": banco.historico(anuncio_id)})

    @app.post("/ocultar/<path:anuncio_id>")
    def ocultar(anuncio_id):
        banco.ocultar(anuncio_id, True)
        return redirect(request.referrer or url_for("inicio"))

    @app.post("/coletar")
    def coletar():
        coletor.em_segundo_plano()
        return redirect(request.referrer or url_for("inicio"))

    @app.get("/api/status")
    def api_status():
        return jsonify({"status": coletor.status, "stats": banco.estatisticas(),
                        "coleta": banco.ultima_coleta()})

    @app.get("/api/alertas")
    def api_alertas():
        desde = int(request.args.get("desde", 0))
        return jsonify(banco.alertas(desde_id=desde, limite=50))

    @app.get("/api/anuncios")
    def api_anuncios():
        return jsonify(banco.anuncios(apenas_alertas=request.args.get("alertas") == "1"))

    return app
