# 📧 Gerador de E-mails Institucionais

Aplicação **local** (roda só no seu computador) que lê um arquivo **CSV** com nomes de
servidores/professores e gera automaticamente os possíveis endereços de e-mail
institucionais no formato:

```
primeironome.iniciaisdomeioultimo@professor.educacao.pe.gov.br
```

> **Privacidade:** nada é enviado para a internet. Todo o processamento acontece na
> sua máquina. A única coisa que *pode* sair (e só se você ligar a opção "Verificar
> DNS/MX") é o **nome do domínio** — nunca a lista de nomes.

---

## 1. Como instalar o Python

1. Acesse **https://www.python.org/downloads/**
2. Clique em **Download Python 3.x** (versão 3.10 ou superior).
3. Execute o instalador.
4. **IMPORTANTE:** na primeira tela, marque a caixinha
   **“Add python.exe to PATH”** antes de clicar em *Install Now*.
5. Conclua a instalação.

Para conferir: abra o **Prompt de Comando** e digite `python --version`.
Deve aparecer algo como `Python 3.12.x`.

---

## 2. Como instalar as dependências e iniciar (jeito fácil — Windows)

Dê **dois cliques** no arquivo **`INICIAR.bat`**.

Na primeira vez ele vai:
- criar um ambiente isolado (`.venv`);
- baixar as bibliotecas necessárias;
- abrir a aplicação no seu navegador (http://localhost:8501).

Nas próximas vezes ele apenas abre a aplicação (bem mais rápido).

> Se o Windows mostrar um aviso de segurança, clique em **“Mais informações” →
> “Executar assim mesmo”**. O arquivo é um script de texto que você pode abrir no
> Bloco de Notas para inspecionar.

### Jeito manual (qualquer sistema)

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

---

## 3. Como importar o CSV

1. Com a aplicação aberta no navegador, **arraste o arquivo CSV** para a área
   *“Arraste seu CSV aqui”* (ou clique em *Browse files*).
2. Se você já colocou o CSV na pasta do projeto, a aplicação oferece a opção de
   usá-lo diretamente, sem precisar arrastar.
3. A aplicação detecta **sozinha**:
   - a codificação do arquivo (acentos);
   - o separador (`;`, `,`, tabulação...);
   - a linha onde começa o cabeçalho;
   - **qual coluna tem o nome completo** (normalmente `Nome Completo`).
4. Confira a coluna detectada. Se estiver errada, escolha a correta na lista.

O arquivo original **nunca é alterado** — ele é só lido.

---

## 4. Como gerar os e-mails

1. Clique no botão **🚀 GERAR EMAILS**.
2. Aguarde a barra de progresso (rápido mesmo com dezenas de milhares de linhas).
3. Aparecem os cartões com os números (válidos, duplicados, revisão, conflitos) e a
   tabela com todos os resultados.

### A regra usada

- **Primeiro nome** + `.` + **iniciais dos nomes do meio** + **último sobrenome**,
  tudo minúsculo e sem acento.
- As partículas **da, de, do, das, dos, e** *não* viram inicial.

| Nome | E-mail gerado |
|---|---|
| JOSE ALESSANDRO CAETANO DA SILVA | `jose.acsilva@professor.educacao.pe.gov.br` |
| KATIA JEANNE ALMEIDA TENORIO | `katia.jatenorio@professor.educacao.pe.gov.br` |
| MARIA JOSE DA SILVA LIMA | `maria.jslima@professor.educacao.pe.gov.br` |
| JOAO PAULO DE SOUZA | `joao.psouza@professor.educacao.pe.gov.br` |
| CARLOS EDUARDO ALMEIDA DOS SANTOS | `carlos.easantos@professor.educacao.pe.gov.br` |
| JOSÉ CÉSAR MENDONÇA | `jose.cmendonca@professor.educacao.pe.gov.br` |

### Filtros disponíveis

- buscar por nome;
- buscar por e-mail;
- filtrar por status;
- mostrar somente conflitos;
- mostrar somente registros que precisam de revisão;
- paginação (para arquivos grandes).

---

## 5. Como exportar

Na seção **5. Exportar**:

| Botão | O que sai |
|---|---|
| **TODOS · CSV** | todos os resultados, CSV compatível com Excel BR |
| **TODOS · XLSX** | planilha Excel formatada (cabeçalho em negrito, filtros, 1ª linha congelada, destaques) |
| **SOMENTE OK · CSV** | apenas os registros sem pendência |
| **SOMENTE REVISÃO · CSV** | apenas os que precisam de conferência |
| **CONFLITOS · CSV** | apenas os conflitos de e-mail |

O CSV sai em **UTF-8 com BOM** e separador `;`, então **abre direto no Excel
brasileiro com os acentos corretos**.

O botão **“Salvar cópias em exports/”** grava os arquivos na pasta `exports/` do
projeto, com data e hora no nome.

---

## 6. O que significam OK, REVISAR e CONFLITO

| Marca | Significado | O que fazer |
|---|---|---|
| **OK** | Passou em todas as checagens automáticas. | Nada. |
| **REVISAR** | O e-mail foi gerado, mas há algo que um humano precisa conferir. O motivo aparece na coluna **Motivo** (ex.: *"Nome contém sufixo FILHO"*, *"Apenas dois nomes"*, *"Cargo não é PROFESSOR"*, *"Nome contém hífen"*). | Ler o motivo e validar/ajustar manualmente. |
| **DUPLICADO** | A mesma pessoa aparece em mais de uma linha do arquivo (matrículas diferentes). As linhas foram **agrupadas** numa só (coluna *Qtd Registros*). | Geralmente é normal; confira se são mesmo a mesma pessoa. |
| **CONFLITO** | **Dois nomes diferentes** geraram **o mesmo e-mail**. Nada é apagado. | Decidir manualmente qual pessoa fica com o e-mail e como diferenciar a outra. A coluna *Conflito Com* mostra o(s) outro(s) nome(s). |
| **INVÁLIDO** | Linha sem nome aproveitável. | Verificar o arquivo de origem. |

Os sufixos **JUNIOR / JÚNIOR / FILHO / NETO / SOBRINHO** **não** têm regra especial de
montagem — o e-mail é gerado normalmente e o registro é apenas **marcado para revisão**.

---

## 7. Configurações

Na barra lateral (**⚙️ Configurações**) você pode ajustar:

- **Domínio** — padrão `professor.educacao.pe.gov.br` (editável para uso futuro).
- **Partículas ignoradas** — padrão `da, de, do, das, dos, e`.
- **Sufixos que pedem revisão** — padrão `junior, filho, neto, sobrinho`.
- **Uma linha por pessoa** — agrupar matrículas do mesmo servidor (ligado por padrão).
- **Verificar DNS/MX do domínio** — consulta opcional (desligado por padrão).

Clique em **💾 Salvar** para guardar as preferências (arquivo `config.json`).

---

## 8. Limitações da validação de e-mail

A ferramenta informa **quatro níveis distintos**, e é honesta sobre cada um:

| Nível | O que garante |
|---|---|
| **E-mail gerado** | A regra conseguiu montar um endereço. |
| **Formato válido** | A sintaxe do endereço é válida (regex + limites de tamanho). |
| **Domínio válido** | O domínio é um nome bem formado; opcionalmente, que ele tem registro **MX** (aceita e-mail). |
| **Caixa postal confirmada** | Só é marcada se você fornecer uma **lista oficial** de e-mails reais (veja abaixo). Sem essa lista, fica sempre *"Não verificável"*. |

**A aplicação não faz** enumeração SMTP, não tenta "adivinhar" contas no servidor e
não envia mensagens. Não existe forma técnica de a ferramenta, sozinha, saber se
`fulano@professor.educacao.pe.gov.br` existe.

### Como habilitar "CONFIRMADA"

Abra o painel **"✅ Lista oficial de e-mails reais (opcional)"** (logo acima do botão
GERAR EMAILS) e cole — ou envie um `.txt`/`.csv` com — os e-mails que você **sabe que
existem**. Fontes válidas:

- pedido pela **Lei de Acesso à Informação** (e-SIC de Pernambuco) — e-mail
  institucional de servidor é informação pública;
- **export do diretório da rede** (LDAP / Active Directory) fornecido pela TI;
- endereços que você já usou e que funcionaram.

O que estiver na lista vira **CONFIRMADA (lista oficial)**. O que não estiver vira
*"Não consta na lista"* — o que **não** quer dizer que não exista, só que a sua lista
não cobre aquele registro. Use o filtro **"Mostrar somente CONFIRMADOS"** e o botão
**SOMENTE CONFIRMADOS · CSV** para trabalhar apenas com o que está comprovado.

Se um dia houver uma API/diretório consultável ao vivo, o ponto de extensão está em
`src/verificador_autorizado.py` (crie uma subclasse de `VerificadorContas`).

---

## Estrutura do projeto

```
verificar email/
├── app.py                     # interface (Streamlit)
├── INICIAR.bat                # inicialização em 2 cliques (Windows)
├── requirements.txt
├── README.md
├── config.json                # criado ao salvar configurações
├── src/
│   ├── config.py              # parâmetros ajustáveis
│   ├── csv_reader.py          # detecção de encoding/separador/cabeçalho/coluna
│   ├── name_parser.py         # normalização + classificação (OK/REVISAR)
│   ├── email_generator.py     # regra do e-mail + pipeline e estatísticas
│   ├── validator.py           # sintaxe, domínio, MX opcional
│   ├── verificador_autorizado.py  # ponto de extensão para verificação autorizada
│   ├── exporter.py            # CSV (Excel BR) e XLSX formatado
│   └── utils.py               # utilidades (remover acentos, cronômetro)
├── tests/                     # testes automatizados (pytest)
├── data/                      # coloque aqui seus CSV (não versionado)
└── exports/                   # saídas geradas
```

## Rodar os testes

```bash
.venv\Scripts\activate
pytest -q
```
