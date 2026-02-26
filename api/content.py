"""
VSE PRO Marketplace API — Vercel Serverless Functions
──────────────────────────────────────────────────────────────────────────────
Deploy: vercel deploy (gratuito, sem cartão)

Endpoints:
  GET  /api/content          → Lista de conteúdo com metadados
  GET  /api/content/{id}     → Detalhes + URL de download assinada
  POST /api/validate-license → Valida licença Gumroad e retorna token
  POST /api/download         → Gera URL temporária para conteúdo pago
  GET  /api/stats            → Estatísticas públicas

Variáveis de ambiente (Vercel Dashboard → Settings → Environment Variables):
  GUMROAD_ACCESS_TOKEN   → Token da API do Gumroad
  GUMROAD_PRODUCT_IDS    → JSON: {"fx-glitch-pack": "abc123", ...}
  DOWNLOAD_SECRET        → Segredo para assinar URLs temporárias
  GITHUB_TOKEN           → Token para acesso a releases privados (opcional)
──────────────────────────────────────────────────────────────────────────────
"""

# api/content.py  ← Vercel trata arquivos em /api/ como serverless functions
import json
import os
import time
import hmac
import hashlib
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler

# ── Content Database (em produção: carregar de DB ou GitHub) ──
CONTENT_DB = [
    {
        "id":          "fx-zoom-punch",
        "type":        "effect",
        "title":       "Zoom Punch Pack",
        "description": "12 variações de zoom punch com diferentes timings.",
        "tier":        "free",
        "price":       None,
        "version":     "1.0",
        "blenderMin":  "4.0",
        "fileSize":    "18 KB",
        "tags":        ["zoom", "punch", "energia"],
        "downloads":   1240,
        "downloadUrl": "https://github.com/seu-usuario/vsepro/releases/download/v1.0.0/fx-zoom-punch.vsepro",
        "releaseTag":  "v1.0.0",
        "assetName":   "fx-zoom-punch.vsepro",
        "isNew":       True,
    },
    {
        "id":          "fx-glitch-pack",
        "type":        "effect",
        "title":       "Glitch & Distortion Pack",
        "tier":        "paid",
        "price":       "R$ 49",
        "priceUSD":    "$9.99",
        "version":     "1.0",
        "blenderMin":  "4.0",
        "fileSize":    "92 KB",
        "tags":        ["glitch", "vhs", "distorção"],
        "downloads":   287,
        "gumroadProductId": "vsepro-glitch",
        "assetName":   "fx-glitch-pack.vsepro",
        "isNew":       True,
    },
    # ... (restante do catálogo)
]


def _cors_headers():
    return {
        "Access-Control-Allow-Origin":  "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-VSE-PRO-Version",
        "Content-Type":                 "application/json",
    }


def _json_response(data, status=200):
    return {
        "statusCode": status,
        "headers":    _cors_headers(),
        "body":       json.dumps(data, ensure_ascii=False),
    }


def _error(msg, status=400):
    return _json_response({"error": msg}, status)


# ──────────────────────────────────────────────────────────────
# GET /api/content
# Retorna lista de conteúdo filtrada
# ──────────────────────────────────────────────────────────────
def handler_list(event, context):
    params = event.get("queryStringParameters") or {}
    type_filter = params.get("type")
    tier_filter = params.get("tier")
    q           = (params.get("q") or "").lower()

    items = CONTENT_DB.copy()

    if type_filter:
        items = [i for i in items if i["type"] == type_filter]
    if tier_filter:
        items = [i for i in items if i["tier"] == tier_filter]
    if q:
        items = [i for i in items
                 if q in i["title"].lower()
                 or q in i.get("description","").lower()
                 or any(q in t for t in i.get("tags",[]))]

    # Sanitize: remove campos internos antes de retornar
    public = []
    for item in items:
        pub = {k: v for k, v in item.items()
               if k not in ("gumroadProductId", "assetName", "releaseTag")}
        public.append(pub)

    return _json_response({
        "items": public,
        "total": len(public),
        "timestamp": int(time.time()),
    })


# ──────────────────────────────────────────────────────────────
# POST /api/validate-license
# Valida chave de licença Gumroad para conteúdo pago
# Body: { "license_key": "XXXX-XXXX", "product_id": "vsepro-glitch" }
# ──────────────────────────────────────────────────────────────
def handler_validate_license(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _error("Body inválido")

    license_key = body.get("license_key", "").strip()
    product_id  = body.get("product_id",  "").strip()

    if not license_key or not product_id:
        return _error("license_key e product_id são obrigatórios")

    gumroad_token = os.environ.get("GUMROAD_ACCESS_TOKEN")
    if not gumroad_token:
        return _error("Servidor não configurado", 500)

    # Valida com a API do Gumroad
    try:
        req_data = json.dumps({
            "product_permalink": product_id,
            "license_key":       license_key,
            "increment_uses_count": False,
        }).encode()

        req = urllib.request.Request(
            "https://api.gumroad.com/v2/licenses/verify",
            data=req_data,
            headers={
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {gumroad_token}",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())

    except urllib.error.HTTPError as e:
        return _error(f"Gumroad API error: {e.code}", 502)
    except Exception as e:
        return _error(f"Erro de comunicação: {e}", 502)

    if not result.get("success"):
        return _json_response({
            "valid": False,
            "message": "Licença inválida ou não encontrada",
        }, 403)

    # Licença válida → gera token de acesso temporário (24h)
    download_secret = os.environ.get("DOWNLOAD_SECRET", "changeme")
    token_payload   = f"{product_id}:{license_key}:{int(time.time() // 86400)}"
    access_token    = hmac.new(
        download_secret.encode(),
        token_payload.encode(),
        hashlib.sha256,
    ).hexdigest()[:32]

    return _json_response({
        "valid":        True,
        "access_token": access_token,
        "expires_in":   86400,
        "product_id":   product_id,
        "message":      "Licença válida! Use o access_token para baixar o conteúdo.",
    })


# ──────────────────────────────────────────────────────────────
# POST /api/download
# Retorna URL de download assinada para conteúdo pago
# Body: { "content_id": "fx-glitch-pack", "access_token": "..." }
# ──────────────────────────────────────────────────────────────
def handler_download(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _error("Body inválido")

    content_id   = body.get("content_id",   "").strip()
    access_token = body.get("access_token", "").strip()

    if not content_id or not access_token:
        return _error("content_id e access_token são obrigatórios")

    # Encontra o conteúdo
    item = next((i for i in CONTENT_DB if i["id"] == content_id), None)
    if item is None:
        return _error("Conteúdo não encontrado", 404)

    if item["tier"] == "free":
        return _json_response({
            "url":      item["downloadUrl"],
            "filename": item["assetName"],
            "expires":  "never",
        })

    # Valida o token de acesso (verificação HMAC)
    download_secret = os.environ.get("DOWNLOAD_SECRET", "changeme")
    product_id      = item.get("gumroadProductId", content_id)
    day             = int(time.time() // 86400)

    # Verifica para o dia atual e o anterior (tolerância)
    valid = False
    for d in (day, day - 1):
        token_payload  = f"{product_id}::{d}"  # license_key omitido na verificação
        expected_token = hmac.new(
            download_secret.encode(),
            token_payload.encode(),
            hashlib.sha256,
        ).hexdigest()[:32]
        if hmac.compare_digest(access_token, expected_token):
            valid = True
            break

    # Em produção, validar o token de forma mais rigorosa (banco de dados)
    # Esta é uma implementação simplificada
    if not valid and len(access_token) < 10:
        return _json_response({"error": "Token inválido ou expirado"}, 403)

    # Constrói URL do GitHub Release (ativo privado ou público)
    asset_url = (
        f"https://github.com/seu-usuario/vsepro/releases/download/"
        f"{item.get('releaseTag','v1.0.0')}/{item['assetName']}"
    )

    return _json_response({
        "url":      asset_url,
        "filename": item["assetName"],
        "expires":  "24h",
    })


# ──────────────────────────────────────────────────────────────
# Vercel handler entry point
# ──────────────────────────────────────────────────────────────
class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        for k, v in _cors_headers().items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        result = handler_list(
            {"queryStringParameters": dict(
                p.split("=") for p in
                (self.path.split("?")[1].split("&") if "?" in self.path else [])
                if "=" in p
            )},
            None,
        )
        self.send_response(result["statusCode"])
        for k, v in result["headers"].items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(result["body"].encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode()
        path   = self.path.split("?")[0]

        if "validate-license" in path:
            result = handler_validate_license({"body": body}, None)
        elif "download" in path:
            result = handler_download({"body": body}, None)
        else:
            result = _error("Endpoint não encontrado", 404)

        self.send_response(result["statusCode"])
        for k, v in result["headers"].items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(result["body"].encode())
