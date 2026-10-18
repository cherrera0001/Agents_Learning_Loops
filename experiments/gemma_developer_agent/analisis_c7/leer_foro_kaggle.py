#!/usr/bin/env python3
"""Lector del foro de una competencia de Kaggle con la sesión autenticada del CLI (kagglesdk).

Solo lee. No publica, no vota, no envía nada. Sirve para registrar en STATUS §Reglas el estado
VERIFICADO / NO VERIFICADO de cada regla con su fuente (URL del hilo) y fecha.

Uso (desde la raíz del repo, con el venv del CLI de Kaggle):
  python analisis_c7/leer_foro_kaggle.py listar --foro gemma-4-developer-agent --buscar "12 h" --salida DIR
  python analisis_c7/leer_foro_kaggle.py tema --id 123456 --salida DIR

Salida: JSON por consulta en DIR (fuera del repo versionado: data/ está en .gitignore).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def _plano(obj):
    """Convierte un KaggleObject (o lista) en dict JSON-serializable, sin dependencias privadas."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, (list, tuple)):
        return [_plano(x) for x in obj]
    if hasattr(obj, "value") and obj.__class__.__module__.endswith("enums"):
        return obj.name
    salida = {}
    for nombre in dir(obj):
        if nombre.startswith("_") or nombre in {
            "endpoint",
            "endpoint_path",
            "to_dict",
            "to_field_map",
            "from_dict",
        }:
            continue
        try:
            valor = getattr(obj, nombre)
        except Exception:
            continue
        if callable(valor):
            continue
        salida[nombre] = _plano(valor)
    return salida


def _cliente():
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()
    return api


def listar(args) -> int:
    from kagglesdk.discussions.types.discussions_api_service import ApiListTopicsRequest
    from kagglesdk.discussions.types.discussions_enums import TopicListSortBy

    api = _cliente()
    with api.build_kaggle_client() as kc:
        req = ApiListTopicsRequest()
        if args.foro:
            req.forum_slug = args.foro
        if args.buscar:
            req.search_query = args.buscar
        req.sort_by = getattr(TopicListSortBy, f"TOPIC_LIST_SORT_BY_{args.orden.upper()}")
        req.page_size = args.n
        temas = []
        token = None
        while True:
            if token:
                req.page_token = token
            resp = kc.discussions.discussion_api_client.list_topics(req)
            temas.extend(_plano(t) for t in (resp.topics or []))
            token = resp.next_page_token
            if not token or len(temas) >= args.max:
                break
        total = getattr(resp, "total_count", None)
    destino = Path(args.salida)
    destino.mkdir(parents=True, exist_ok=True)
    etiqueta = (args.buscar or "todos").replace(" ", "_")[:40]
    archivo = destino / f"temas_{etiqueta}_{datetime.utcnow():%Y%m%dT%H%M%SZ}.json"
    archivo.write_text(
        json.dumps({"total_count": total, "temas": temas}, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{len(temas)} temas (total_count={total}) -> {archivo}")
    for t in temas:
        print(
            f"  id={t.get('id')} votos={t.get('votes')} com={t.get('comment_count')} "
            f"{str(t.get('post_date'))[:10]} | {t.get('title')} | {t.get('url')}"
        )
    return 0


def competencia(args) -> int:
    """Lista TODOS los temas del foro de una competencia (/competitions/{slug}/topics, paginado)."""
    from kagglesdk.competitions.types.competition_api_service import ApiListCompetitionTopicsRequest
    from kagglesdk.discussions.types.discussions_enums import TopicListSortBy

    api = _cliente()
    temas = []
    total = None
    with api.build_kaggle_client() as kc:
        pagina = 1
        while pagina <= args.max_paginas:
            req = ApiListCompetitionTopicsRequest()
            req.competition_name = args.competencia
            req.sort_by = getattr(TopicListSortBy, f"TOPIC_LIST_SORT_BY_{args.orden.upper()}")
            req.page = pagina
            resp = kc.competitions.competition_api_client.list_competition_topics(req)
            lote = [_plano(t) for t in (resp.topics or [])]
            total = getattr(resp, "total_count", total)
            if not lote:
                break
            temas.extend(lote)
            if total and len(temas) >= total:
                break
            pagina += 1
    destino = Path(args.salida)
    destino.mkdir(parents=True, exist_ok=True)
    archivo = destino / f"temas_competencia_{args.orden}_{datetime.utcnow():%Y%m%dT%H%M%SZ}.json"
    archivo.write_text(
        json.dumps({"total_count": total, "temas": temas}, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{len(temas)} temas (total_count={total}) -> {archivo}")
    filtro = (args.buscar or "").lower()
    for t in temas:
        titulo = str(t.get("title") or t.get("name") or "")
        if filtro and filtro not in titulo.lower():
            continue
        comentarios = t.get("comment_count") or t.get("total_comments")
        print(
            f"  id={t.get('id')} votos={t.get('votes')} com={comentarios} "
            f"{str(t.get('post_date') or t.get('date'))[:10]} | {titulo}"
        )
    return 0


def mensajes(args) -> int:
    """Lee un tema de competencia con sus mensajes (/competitions/{slug}/topics/{id}/messages)."""
    from kagglesdk.competitions.types.competition_api_service import ApiListTopicMessagesRequest
    from kagglesdk.discussions.types.discussions_enums import CommentListSortBy

    api = _cliente()
    with api.build_kaggle_client() as kc:
        req = ApiListTopicMessagesRequest()
        req.competition_name = args.competencia
        req.topic_id = args.id
        req.sort_by = CommentListSortBy.COMMENT_LIST_SORT_BY_OLD
        req.page_size = args.n
        resp = kc.competitions.competition_api_client.list_topic_messages(req)
        msgs = [_plano(m) for m in (resp.messages or [])]
    destino = Path(args.salida)
    destino.mkdir(parents=True, exist_ok=True)
    archivo = destino / f"mensajes_{args.id}_{datetime.utcnow():%Y%m%dT%H%M%SZ}.json"
    archivo.write_text(
        json.dumps({"topic_id": args.id, "mensajes": msgs}, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"tema {args.id}: {len(msgs)} mensajes -> {archivo}")
    if args.imprimir:
        for m in msgs:
            _imprimir_comentario(m, 0)
    return 0


def tema(args) -> int:
    from kagglesdk.discussions.types.discussions_api_service import ApiGetTopicRequest, ApiListCommentsRequest

    api = _cliente()
    with api.build_kaggle_client() as kc:
        req = ApiGetTopicRequest()
        req.id = args.id
        topic = _plano(kc.discussions.discussion_api_client.get_topic(req).topic)
        comentarios = []
        creq = ApiListCommentsRequest()
        creq.topic_id = args.id
        creq.page_size = 100
        token = None
        while True:
            if token:
                creq.page_token = token
            cresp = kc.discussions.discussion_api_client.list_comments(creq)
            comentarios.extend(_plano(c) for c in (cresp.comments or []))
            token = cresp.next_page_token
            if not token:
                break
    destino = Path(args.salida)
    destino.mkdir(parents=True, exist_ok=True)
    archivo = destino / f"tema_{args.id}_{datetime.utcnow():%Y%m%dT%H%M%SZ}.json"
    archivo.write_text(
        json.dumps({"tema": topic, "comentarios": comentarios}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"tema {args.id}: {topic.get('title')} | {topic.get('url')}")
    print(f"  {len(comentarios)} comentarios -> {archivo}")
    if args.imprimir:
        print("=" * 80)
        print(topic.get("content") or "")
        for c in comentarios:
            _imprimir_comentario(c, 0)
    return 0


def _imprimir_comentario(c, nivel):
    sangria = "  " * nivel
    autor = (
        c.get("author_name")
        or (c.get("author") or {}).get("display_name")
        or (c.get("author") or {}).get("user_name")
    )
    fecha = str(c.get("post_date") or c.get("date"))[:16]
    print(f"{sangria}--- [{fecha}] {autor} (votos {c.get('votes')})")
    for linea in (c.get("content") or c.get("raw_markdown") or c.get("message") or "").splitlines():
        print(f"{sangria}{linea}")
    for r in c.get("replies") or []:
        _imprimir_comentario(r, nivel + 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("listar")
    p1.add_argument("--foro", default="gemma-4-developer-agent")
    p1.add_argument("--buscar", default="")
    p1.add_argument("--orden", default="hot", choices=["hot", "top", "new", "recent", "active", "relevance"])
    p1.add_argument("-n", type=int, default=50)
    p1.add_argument("--max", type=int, default=200)
    p1.add_argument("--salida", required=True)
    p1.set_defaults(fn=listar)
    p3 = sub.add_parser("competencia")
    p3.add_argument("--competencia", default="gemma-4-developer-agent")
    p3.add_argument(
        "--orden", default="recent", choices=["hot", "top", "new", "recent", "active", "relevance"]
    )
    p3.add_argument("--max-paginas", type=int, default=30)
    p3.add_argument("--buscar", default="", help="filtra la impresión por título (la descarga es completa)")
    p3.add_argument("--salida", required=True)
    p3.set_defaults(fn=competencia)
    p4 = sub.add_parser("mensajes")
    p4.add_argument("--competencia", default="gemma-4-developer-agent")
    p4.add_argument("--id", type=int, required=True)
    p4.add_argument("-n", type=int, default=200)
    p4.add_argument("--salida", required=True)
    p4.add_argument("--imprimir", action="store_true")
    p4.set_defaults(fn=mensajes)
    p2 = sub.add_parser("tema")
    p2.add_argument("--id", type=int, required=True)
    p2.add_argument("--salida", required=True)
    p2.add_argument("--imprimir", action="store_true")
    p2.set_defaults(fn=tema)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
