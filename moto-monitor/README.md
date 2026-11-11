# 🏍️ Moto Monitor — Curitiba e região

Site local que vigia anúncios de motos **custom, clássicas e estradeiras** na OLX e no
Mercado Livre (Curitiba e região metropolitana), compara com a **Tabela FIPE** e avisa
quando aparece oportunidade.

## Regras de alerta (padrão)

Um anúncio de um modelo monitorado vira alerta quando:

1. **preço ≤ R$ 18.000**, ou
2. **preço ≤ R$ 30.000** e **pelo menos 10% abaixo da FIPE** do mesmo modelo/ano.

Anúncios abaixo de R$ 4.000 são descartados (quase sempre é "entrada", parcela ou golpe).
Se o preço de um anúncio já alertado cair de novo, você recebe outro alerta.
Tudo isso é ajustável em `config.json` → `regras`.

## Como usar (Windows)

1. Instale o **Python 3.10+** em <https://www.python.org/downloads/> marcando *Add python.exe to PATH*.
2. Baixe esta pasta e dê **duplo clique em `iniciar.bat`**.
   Na primeira vez ele cria o ambiente e instala as dependências (1–2 min).
3. O navegador abre em **http://localhost:8765**. Clique em **🔔 Ativar avisos** para
   receber notificação do navegador (com som) quando surgir alerta.

Linux/macOS: `./iniciar.sh`.

Enquanto a janela estiver aberta, ele busca tudo de novo a cada 30 minutos
(`intervalo_minutos`). Também dá para clicar em **↻ Buscar agora**.

### Rodar sozinho quando o PC ligar (opcional)
Crie um atalho para `iniciar.bat` em `shell:startup` (Win+R → `shell:startup`).
Para só coletar sem abrir o site (ex.: Agendador de Tarefas): `iniciar.bat --uma-vez`.

## Onde chegam os avisos

- **No site**: aba *Alertas* (com contador de não lidos).
- **Notificação do navegador + bip**: com a aba aberta e avisos ativados.
- **Notificação do Windows**: automática (via `plyer`); desligue com `"desktop": false`.
- **Telegram (opcional, chega no celular)**: crie um bot com o @BotFather, pegue o token,
  mande uma mensagem para o bot e descubra seu `chat_id` em
  `https://api.telegram.org/bot<TOKEN>/getUpdates`. Depois preencha em `config.json`:
  ```json
  "telegram": { "ativo": true, "token": "123:ABC...", "chat_id": "987654321" }
  ```

## Modelos monitorados

Honda Shadow 600/750, Rebel 500 · Yamaha Virago 250/535, Drag Star 650, Midnight Star 950 ·
Suzuki Intruder 125/250, Boulevard M800/C800/M1500, Marauder 800 · Kawasaki Vulcan
500/800/900/S 650, Eliminator · Harley-Davidson Sportster 883/1200 · Dafra Horizon 150/250 ·
Kasinski Mirage 150/250/650 · Haojue Master Ride · Royal Enfield Classic 350, Meteor 350,
Bullet, Hunter 350, Interceptor 650, Continental GT · Triumph Bonneville ·
**Estradeiras**: Kawasaki Versys 650, Honda NC 700X/750X, Honda CB 500X, Suzuki V-Strom 650.

No `config.json`:
- `estilos_ativos`: tire `"estradeira"` se quiser só custom/clássicas;
- `modelos_desativados`: lista de chaves (ex.: `["rebel500", "bonneville"]`);
- `modelos_extras`: acrescente modelos sem mexer no código, por exemplo
  ```json
  "modelos_extras": [{"chave": "fury", "nome": "Honda Fury 1300", "estilo": "custom",
    "busca": "honda fury", "padrao": "\\bfury\\b", "fipe_marca": "honda", "fipe_tokens": ["FURY"]}]
  ```
- `cidades`: municípios aceitos (anúncios de outras cidades são ignorados).

## Como funciona

```
fontes (OLX, Mercado Livre) ──► identifica o modelo pelo título ──► filtra cidade/preço
      ──► FIPE (API pública parallelum, com cache) ──► regras ──► SQLite ──► site + alertas
```

- `motomonitor/modelos.py` — catálogo e reconhecimento do modelo pelo título;
- `motomonitor/fontes/` — leitura das páginas da OLX e do Mercado Livre;
- `motomonitor/fipe.py` — valor FIPE (mediana das versões do modelo naquele ano);
- `motomonitor/regras.py` — regras de alerta;
- `motomonitor/coletor.py` — rodada de coleta e agendamento;
- `motomonitor/web.py` + `templates/index.html` — o site.
- Banco em `dados/motos.db` (guarda histórico de preço de cada anúncio).

Testes: `python -m pytest tests`.

## Limitações honestas

- OLX e Mercado Livre mudam o HTML de tempos em tempos e às vezes bloqueiam robôs
  (aparece em *Avisos da última coleta* no rodapé do site). Os leitores procuram os dados
  de forma tolerante, mas se uma fonte parar de trazer anúncios, é ali que se ajusta.
- Facebook Marketplace exige login e não é coberto.
- A FIPE gratuita tem limite diário de consultas; o cache evita repetir. Se estourar, dá
  para cadastrar um token grátis em <https://fipe.online> e pôr em `fipe.token`
  (e trocar `url_base` para a v2, se for o caso).
- Use com moderação (o intervalo padrão de 30 min e as pausas entre requisições existem
  para não sobrecarregar os sites).
