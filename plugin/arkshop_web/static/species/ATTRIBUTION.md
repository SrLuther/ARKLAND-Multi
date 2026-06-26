# Imagens de espécies — Catálogo e Comércio P2P

Documento de conformidade legal para thumbnails de criaturas em **arkland.com.br** (loja comercial).

## Conclusão legal (resumo)

| Fonte | Usar na loja? | Motivo |
|-------|---------------|--------|
| **ARK Fandom Wiki** (ark.fandom.com) | **Não** hospedar/copiar | Texto wiki: [CC BY-NC-SA 3.0](https://ark.fandom.com/wiki/ARK_Survival_Evolved_Wiki:Copyrights) (não comercial). Imagens de criaturas: **© Studio Wildcard**, fair use na wiki — **não** licenciadas para redistribuição. Hotlink também é frágil (ToS Fandom, links quebrados). |
| **Dododex** | **Não** | Arte © Dan Leveille. Sem API de redistribuição; scrape/hotlink viola direitos autorais. |
| **Ark IDs** (arkids.net) | **Não** copiar | Imagens são assets do jogo © Studio Wildcard (Dantoo Ltd). Sem licença de rehost. |
| **Steam / assets do jogo** | **Não** extrair | IP da Studio Wildcard; extração e hospedagem própria não permitida sem autorização. |
| **Fan Content Guidelines** ([survivetheark.com](https://survivetheark.com/index.php?/fan_content_guidelines/)) | **Limitado** | Voltado a conteúdo de fã **não comercial** por **consumidores individuais**. Entidades corporativas (servidor/loja comercial) devem **contatar Studio Wildcard** antes de usar IP. Dossiês oficiais/press kit **não** substituem licença para thumbnails de loja. |
| **Arte original ARKLAND** (`static/species/icons/*.svg`) | **Sim** | Silhuetas procedurais geradas pelo projeto — sem cópia de assets de terceiros. |
| **Placeholders por tier** (`tier-*.svg`) | **Sim** | Silhuetas genéricas originais ARKLAND (fallback). |
| **Comissão / permissão escrita** | **Sim** | Com `icon_path` ou `image_url` + linha nesta tabela de atribuição. |

**Abordagem adotada:** Opção **E** ampliada — ícones SVG originais ARKLAND para cada espécie do registro, com fallback para silhueta por tier quando não houver ícone dedicado.

## Placeholders por tier

Os arquivos `tier-s-plus.svg`, `tier-s.svg`, `tier-a.svg`, `tier-b.svg` e `tier-c.svg` são **silhuetas genéricas originais ARKLAND**.

## Ícones por espécie (bundle local)

- Diretório: `static/species/icons/{species_key}.svg`
- Manifesto: `data/species_icons_manifest.json`
- Gerador: `python tools/generate_species_icons.py` (lê o registro mesclado em `ark_species_registry.py`)
- Licença: © ARKLAND — arte procedural; **não** são retratos do jogo nem imagens de wiki.

Regenerar após adicionar espécies ao registro:

```bash
python tools/generate_species_icons.py
```

Subset:

```bash
python tools/generate_species_icons.py --species rex giga indominus
```

## Como adicionar imagem licenciada (admin)

1. Obtenha direitos explícitos: arte original, comissão, ou autorização escrita da Studio Wildcard / autor.
2. Coloque o arquivo em `static/species/` (ex.: `rex_commission.png`) **ou** use URL externa com licença clara.
3. No JSON do registro, defina **um** dos campos (sobrescreve o ícone procedural):

```json
{
  "species_key": "rex",
  "icon_path": "rex_commission.png",
  "image_url": "/species/rex_commission.png"
}
```

Arquivos editáveis: `data/market_species_defaults.json`, `data/ark_species_registry.json`.

4. Registre na tabela abaixo e reinicie a Web Store (ou aguarde reload do processo).

Prioridade de resolução: `image_url` → `icon_path` → ícone bundle `/species/icons/{key}.svg` → placeholder de tier.

## Atribuição de imagens de terceiros

| Arquivo | Espécie | Fonte | Licença / crédito |
|---------|---------|-------|-------------------|
| `icons/*.svg` (bundle) | várias | ARKLAND procedural | © ARKLAND — gerado por `tools/generate_species_icons.py` |
| `tier-*.svg` | fallback | ARKLAND | Silhueta genérica original |
| *(adicione linhas ao usar arte licenciada)* | | | |

## Referências consultadas

- [ARK Wiki: Copyrights](https://ark.fandom.com/wiki/ARK_Survival_Evolved_Wiki:Copyrights) — CC BY-NC-SA no texto; IP do jogo da Studio Wildcard
- [Fandom: Copyright](https://community.fandom.com/wiki/Copyright) — mídia não é CC automaticamente
- [Commons: Fandom files](https://commons.wikimedia.org/wiki/Commons:Fandom_files) — imagens Fandom presumidas © salvo licença explícita
- [Studio Wildcard Fan Content Guidelines](https://survivetheark.com/index.php?/fan_content_guidelines/) — não comercial; corporações precisam aprovação
- [Ark IDs Privacy](https://arkids.net/privacy) — operador Dantoo Ltd; assets do jogo não são deles
