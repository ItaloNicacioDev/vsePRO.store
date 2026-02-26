# 🎬 VSE PRO Marketplace — Guia Completo de Hospedagem

## Arquitetura

```
vsepro-marketplace/          ← repositório GitHub
├── site/
│   └── index.html           ← site completo (React inline, zero build)
├── content/
│   ├── content.json         ← catálogo gerado automaticamente
│   ├── fx-zoom-punch.vsepro ← pacotes de conteúdo gratuito
│   └── ...
├── api/
│   └── content.py           ← funções Vercel (conteúdo pago / validação)
└── .github/
    └── workflows/
        └── deploy-site.yml  ← GitHub Actions → GitHub Pages
```

---

## Parte 1 — GitHub Pages (site + conteúdo gratuito)

### Passo 1 — Criar o repositório

```bash
# Crie um repositório público no GitHub chamado "vsepro" (ou "vsepro-marketplace")
# Em seguida:

git clone https://github.com/SEU-USUARIO/vsepro.git
cd vsepro

# Copie os arquivos do site
cp -r vsepro-site/* .
git add .
git commit -m "feat: VSE PRO Marketplace initial commit"
git push
```

### Passo 2 — Habilitar GitHub Pages

1. No repositório → **Settings** → **Pages**
2. Em **Source**, selecione **GitHub Actions**
3. O workflow `.github/workflows/deploy-site.yml` vai rodar automaticamente
4. Em ~2 minutos o site estará em:
   ```
   https://SEU-USUARIO.github.io/vsepro/
   ```

### Passo 3 — Domínio customizado (opcional)

```bash
# Crie o arquivo CNAME na raiz do repositório:
echo "marketplace.vsepro.dev" > site/CNAME

# Configure o DNS no seu provedor:
# Tipo: CNAME
# Host: marketplace
# Valor: seu-usuario.github.io
```

### Passo 4 — Hospedar o conteúdo gratuito nos GitHub Releases

```bash
# Instale a GitHub CLI
brew install gh   # macOS
# ou: https://cli.github.com/

# Faça login
gh auth login

# Crie um release e adicione os pacotes .vsepro
gh release create v1.0.0 \
  content/fx-zoom-punch.vsepro \
  content/lut-cinematic-pack.vsepro \
  content/sfx-transitions.vsepro \
  --title "VSE PRO Content Pack v1.0" \
  --notes "Primeiro pacote de conteúdo gratuito"
```

Os arquivos ficam em:
```
https://github.com/SEU-USUARIO/vsepro/releases/download/v1.0.0/fx-zoom-punch.vsepro
```

> **Vantagem:** GitHub serve esses arquivos via CDN global, sem custo para
> qualquer volume de downloads (limite de 100 GB/mês no GitHub Free).

---

## Parte 2 — Backend para conteúdo pago (Vercel — GRÁTIS)

### Por que Vercel?
GitHub Pages é 100% estático — não pode executar código.
O Vercel serverless roda Python/Node grátis e tem 100k invocações/mês no free tier.

### Passo 1 — Criar conta Vercel

1. Acesse https://vercel.com e crie conta (pode logar com GitHub)

### Passo 2 — Instalar Vercel CLI

```bash
npm install -g vercel
vercel login
```

### Passo 3 — Configurar o projeto

```bash
cd vsepro-site

# Crie vercel.json na raiz:
cat > vercel.json << 'EOF'
{
  "functions": {
    "api/*.py": { "runtime": "python3.9" }
  },
  "routes": [
    { "src": "/api/(.*)", "dest": "/api/$1" }
  ]
}
EOF

# Deploy
vercel deploy --prod
# → https://vsepro-api.vercel.app
```

### Passo 4 — Configurar variáveis de ambiente

No Vercel Dashboard → Settings → Environment Variables:

| Nome | Valor |
|------|-------|
| `GUMROAD_ACCESS_TOKEN` | Token de acesso da API do Gumroad |
| `DOWNLOAD_SECRET` | String aleatória (use: `openssl rand -hex 32`) |
| `GITHUB_TOKEN` | Token GitHub para assets privados (opcional) |

Para obter o token do Gumroad:
1. https://gumroad.com/settings/advanced
2. **Access Tokens** → Generate

---

## Parte 3 — Integração com Gumroad

### Configurar produtos

Para cada item pago, crie um produto no Gumroad:
1. https://app.gumroad.com/products/new
2. **Nome do produto:** "VSE PRO — Glitch Pack"
3. **Preço:** R$ 49
4. **Custom permalink:** `vsepro-glitch`

Anote o permalink — ele é o `gumroadProductId` no catálogo.

### Webhooks (opcional — para liberação automática)

Em Gumroad → Settings → **Ping (webhook)**:
```
URL: https://vsepro-api.vercel.app/api/webhook
Events: Sale
```

Assim, quando alguém compra, o sistema pode:
- Enviar a licença por e-mail automaticamente
- Registrar no banco de dados de licenças válidas

---

## Parte 4 — Criar pacotes .vsepro

```bash
# Estrutura de um pacote de efeito:
mkdir fx-zoom-punch
cd fx-zoom-punch

# Crie o manifest:
cat > manifest.json << 'EOF'
{
  "id": "fx-zoom-punch",
  "title": "Zoom Punch Pack",
  "type": "effect",
  "version": "1.0.0",
  "files": ["zoom_punch_x1.json", "zoom_punch_slow.json"]
}
EOF

# Crie os presets:
cat > zoom_punch_x1.json << 'EOF'
{
  "preset_id": "zoom_punch_x1",
  "preset_name": "Zoom Punch 1×",
  "target": "transform",
  "keyframes": [
    { "frame_offset": 0,  "scale_x": 1.0,  "scale_y": 1.0  },
    { "frame_offset": 4,  "scale_x": 1.15, "scale_y": 1.15 },
    { "frame_offset": 18, "scale_x": 1.0,  "scale_y": 1.0  }
  ]
}
EOF

# Empacota como .vsepro
cd ..
zip -r fx-zoom-punch.vsepro fx-zoom-punch/
```

---

## Parte 5 — Fluxo de atualização

Sempre que adicionar novo conteúdo:

```bash
# 1. Adicione o .vsepro em content/
cp novo-pack.vsepro content/

# 2. Crie um novo release no GitHub
gh release create v1.1.0 \
  content/novo-pack.vsepro \
  --title "Content Pack v1.1" \
  --notes "Novo pacote adicionado!"

# 3. Atualize o catálogo no site
# (o GitHub Actions faz isso automaticamente via build_content_index.py)

# 4. Commit e push → site atualiza automaticamente
git add content/ site/
git commit -m "feat: novo pacote de conteúdo"
git push
```

---

## Parte 6 — Atualizar a URL no addon

Em `vsepro/modules/marketplace.py`, altere as constantes:

```python
MARKETPLACE_API  = "https://vsepro-api.vercel.app/api"          # sua URL Vercel
MARKETPLACE_SITE = "https://SEU-USUARIO.github.io/vsepro"        # GitHub Pages
```

---

## Custos estimados

| Serviço | Custo |
|---------|-------|
| GitHub Pages | **Grátis** (100 GB bandwidth/mês) |
| GitHub Releases | **Grátis** (100 GB storage + bandwidth) |
| Vercel Functions | **Grátis** (100k req/mês) |
| Gumroad | **Grátis** + 10% fee nas vendas (ou 3% no plano Pro $10/mês) |
| **Total inicial** | **R$ 0** |

> O único custo são as taxas do Gumroad sobre as vendas (10% free tier).
> No plano Gumroad Pro ($10/mês), a taxa cai para 3%.

---

## Checklist de lançamento

- [ ] Repositório GitHub criado e público
- [ ] GitHub Pages habilitado via Actions
- [ ] Primeiro release com conteúdo gratuito publicado
- [ ] Vercel deployado com variáveis de ambiente
- [ ] Produtos Gumroad criados para conteúdo pago
- [ ] `MARKETPLACE_API` e `MARKETPLACE_SITE` atualizados no addon
- [ ] Addon v1.2.0 publicado no Gumroad com marketplace integrado
- [ ] README do repositório com link para o Marketplace
