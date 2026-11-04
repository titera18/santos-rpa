"""Pessoas citadas no título."""
import re

from santos_rpa.dominio.clubes import CLUBES
from santos_rpa.dominio.texto import norm

NOME = re.compile(
    r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]{2,}(?:\s+(?:de\s+|da\s+|do\s+)?[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]{2,})?"
)
NAO_NOMES = set(norm(x) for x in """
Santos Peixe Análise Atuações Brasileirão Copa Série Veja Saiba Confira Vila Belmiro Como Por Para Com
Sem Após Antes Onde Quando Quem Qual Mais Não Sim Ele Ela Isso Este Esta Esse Essa Uma Dos Das Nos Nas
Ainda Segundo Assim Agora Hoje Ontem Amanhã Melhores Momentos Bastidores Vídeo Vídeos Foto Fotos
Gol Gols Técnico Clube Futebol Time Jogo Jogos Rodada Sul-Americana Libertadores Data Fifa Seleção
Mercado Bola Base Feminino Torcida Diretoria Presidente Lateral Atacante Zagueiro Goleiro Volante
Meia Santista Santistas Alvinegro Ex Ao Vivo Paulistão Campeonato Liga Brasil Sub Sobre Entre Até
Desde Durante Contra Pelo Pela Nova Novo Novos Novas Ídolo Jogador Jogadores Saiba Escalação
Palpite Palpites Prováveis Provável Horário Assistir Transmissão Salário Especialista Entrevista
Brasileiro Brasileira Brasileiros Paulista Foi Jornalista Venda Nota Entenda Mar Gramado Treino Ásia
Sereias Rei Instituto Umbro Bicampeãs Conmebol Maracanã Morumbis Sobre Marca Dia Ano Cidade Governo
Lei Justiça Evento Projeto Programa Festival Semana Domingo Sábado Segunda Terça Quarta Quinta Sexta
Janeiro Fevereiro Março Abril Maio Junho Julho Agosto Setembro Outubro Novembro Dezembro
Cuiabá Bragança Leão Jovem Torcedores Torcedor Regra Assista Embalado Agibank Mundial Falhou
Inacreditável Lamentável Opinião Suspenso Feminina Pampas Topo Núcleo Vini Série Atuação Massa
Empate Reveladas Revelado Comunicado Novidade Crise Absurdo Colunista Federação Museu Estatuto
""".split())
LUGARES = {"sao vicente", "santo andre", "praia grande", "sao paulo"}
APELIDOS = {"Philippe Coutinho": "Coutinho", "Willian Arão": "Arão", "Pelé Rei": "Pelé",
            "João Schmidt": "Schmidt", "Álvaro Barreal": "Barreal", "Lucas Veríssimo": "Veríssimo",
            "Rodrigo Nestor": "Nestor", "Arthur Melo": "Arthur", "Vinicius Lira": "Vinícius Lira"}


def extrair_nomes(titulo: str) -> list[str]:
    """Pessoas citadas no título. Clubes e palavras comuns em maiúscula ficam de fora."""
    nomes = []
    for m in NOME.finditer(titulo or ""):
        nome = m.group(0)
        partes = norm(nome).split()
        if norm(nome) in CLUBES or norm(nome) in LUGARES:
            continue
        if partes[0] in NAO_NOMES or partes[0] in CLUBES:
            if len(partes) == 2 and partes[1] not in NAO_NOMES and partes[1] not in CLUBES:
                nome = nome.split()[-1]  # "Santos Barreal" -> "Barreal"
            else:
                continue
        if partes[-1] in NAO_NOMES or partes[-1] in CLUBES:
            nome = nome.split()[0]  # "Cuca Santos" -> "Cuca"
            if norm(nome) in NAO_NOMES or norm(nome) in CLUBES:
                continue
        nome = APELIDOS.get(nome, nome)
        if nome not in nomes:
            nomes.append(nome)
    return nomes
