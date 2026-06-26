# Imagens de espécies — Comércio P2P

## Placeholders incluídos (tier)

Os arquivos `tier-s-plus.svg`, `tier-s.svg`, `tier-a.svg`, `tier-b.svg` e `tier-c.svg` são **silhuetas genéricas originais ARKLAND** (sem dependência externa). Use como fallback até haver arte licenciada por espécie.

## Por que não usar Dododex

- Arte e ícones do [Dododex](https://www.dododex.com/dinosaurs) são obra de **Dan Leveille / Dododex** (© Dan Leveille).
- Não há API pública de redistribuição de imagens; hotlink ou scrape viola direitos autorais e os Termos de Uso do site.
- Mesmo com permissão da Studio Wildcard para o app Dododex, **essa licença não se estende** a terceiros (ex.: ARKLAND).

## Wiki Fandom (ARK)

- Texto da wiki: [CC BY-NC-SA 3.0](https://ark.fandom.com/wiki/ARK_Survival_Evolved_Wiki:Copyrights).
- **Imagens de criaturas** costumam ser capturas/modelos **© Studio Wildcard** em fair use — **não** são CC genérico. Copiar para hospedar na loja exige verificar cada arquivo e, em geral, **não** é seguro sem autorização explícita.

## Como adicionar imagem por espécie (admin)

1. Obtenha direitos: arte original, comissão, assets oficiais permitidos pelas [Fan Content Guidelines](https://survivetheark.com/index.php?/fan_content_guidelines/) da Studio Wildcard, ou upload admin com permissão do autor.
2. Coloque o arquivo em `plugin/arkshop_web/static/species/` (ex.: `rex.png`).
3. No JSON do registro, adicione **um** dos campos:

```json
{
  "species_key": "rex",
  "icon_path": "rex.png",
  "image_url": "/species/rex.png"
}
```

- `icon_path`: nome relativo a `static/species/` (recomendado para bundles locais).
- `image_url`: URL absoluta (`https://…`) ou caminho servido pela Web Store (`/species/…`).

Arquivos editáveis: `data/market_species_defaults.json`, `data/ark_species_registry.json`.

4. Reinicie a Web Store ou aguarde cache do registro (processo único recarrega ao subir).

## Atribuição de imagens de terceiros

Se usar imagens licenciadas, registre aqui:

| Arquivo | Espécie | Fonte | Licença / crédito |
|---------|---------|-------|-------------------|
| *(vazio — adicionar linhas conforme incluir arte)* | | | |
