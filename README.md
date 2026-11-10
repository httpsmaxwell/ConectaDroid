# ConectaDroid

O **ConectaDroid** é um aplicativo para Windows, feito em Python (Tkinter), que espelha e controla um celular Android pelo Wi-Fi usando o [scrcpy](https://github.com/Genymobile/scrcpy) e o ADB. Ele cuida da parte chata: descobrir o IP, parear, conectar e abrir o espelho com um clique.

## Recursos

- Detecção automática do celular na rede (mDNS/Zeroconf), incluindo a porta da Depuração sem fio do Android 11+
- Configuração inicial por cabo USB (fixa a porta 5555 e descobre o IP sozinho)
- Pareamento por código, sem cabo (Android 11+)
- Conectar e espelhar com um clique, além de botão para desconectar
- Opções do espelhamento salvas: janela sempre no topo, manter o celular acordado, apagar a tela do celular e fechar o app ao abrir o espelho
- Interface que não trava durante as operações
- Localiza `adb` e `scrcpy` automaticamente

## Requisitos

- Windows
- Python 3.8 ou superior (o Tkinter já vem com o instalador oficial)
- [scrcpy para Windows](https://github.com/Genymobile/scrcpy/releases), que já inclui o `adb.exe`
- Pacote Python `zeroconf` (necessário só para a detecção automática)
- Celular Android com **Opções do desenvolvedor** ativadas
- Celular e computador na **mesma rede Wi-Fi**

## Instalação

1. Baixe o scrcpy e extraia em `C:\scrcpy` (o `scrcpy.exe` e o `adb.exe` devem ficar nessa pasta).
2. Clone o repositório e instale a dependência:

```bash
git clone https://github.com/httpsmaxwell/controle-remoto-do-celular.git
cd controle-remoto-do-celular
pip install -r requirements.txt
```

3. Execute:

```bash
python main.py
```

> **Onde o programa procura o scrcpy e o adb:** na pasta definida em `scrcpy_dir` no `config.json`, depois em `C:\scrcpy`, depois ao lado do programa e por fim no `PATH` do Windows.

## Como usar

Escolha **um** dos dois caminhos para a primeira configuração. Depois disso, o uso do dia a dia é sempre o mesmo.

### Opção A: primeira vez com cabo USB

1. No celular, ative **Depuração USB** (Opções do desenvolvedor).
2. Conecte o cabo e aceite a autorização exibida na tela do celular.
3. No app, clique em **Primeira vez: configurar com cabo USB**.
4. O IP é preenchido automaticamente. Pode tirar o cabo.

### Opção B: pareamento por código (Android 11+, sem cabo)

1. No celular, vá em **Opções do desenvolvedor > Depuração sem fio** e ative.
2. Toque em **Parear dispositivo com código de pareamento**.
3. No app, clique em **Parear por código** e informe o IP:porta e o código de 6 dígitos mostrados no celular.
4. Clique em **Detectar automaticamente** para preencher o endereço de conexão.

### Uso diário

1. Clique em **Detectar automaticamente** (ou digite o IP, por exemplo `192.168.0.15` ou `192.168.0.15:5555`).
2. Clique em **Conectar e espelhar**.

## Configuração (`config.json`)

O arquivo é criado automaticamente ao lado do programa.

| Chave | Descrição | Padrão |
|---|---|---|
| `alvo` | Último endereço usado (`ip:porta`) | `""` |
| `scrcpy_dir` | Pasta do `scrcpy.exe` e `adb.exe`, se for diferente do padrão | `""` |
| `always_on_top` | Janela do espelho sempre no topo | `true` |
| `stay_awake` | Mantém o celular acordado | `true` |
| `tela_apagada` | Apaga a tela do celular durante o espelhamento | `true` |
| `fechar_ao_abrir` | Fecha o app ao abrir o espelho | `true` |

Como o arquivo guarda o IP do seu celular, vale ignorá-lo no Git. Crie um `.gitignore` com:

```
config.json
__pycache__/
```

## Problemas comuns

**"Ferramentas não encontradas"**
Confira se `scrcpy.exe` e `adb.exe` estão em `C:\scrcpy` ou defina a pasta em `scrcpy_dir`.

**"Erro ao conectar via ADB"**
- Verifique se o celular e o PC estão na mesma rede Wi-Fi.
- Refaça a configuração inicial (USB ou pareamento).
- No Android 11+, a porta da Depuração sem fio muda com frequência. Use **Detectar automaticamente** para pegar a porta atual.

**A detecção automática não encontra o celular**
- Confirme que o pacote `zeroconf` está instalado (`pip install zeroconf`).
- Confirme que a **Depuração sem fio** está ativa no celular.
- Algumas redes (Wi-Fi de empresa ou de convidados) bloqueiam o mDNS. Nesse caso, digite o IP manualmente.

**Celular não detectado via USB**
Ative a Depuração USB, troque o cabo (alguns só carregam) e aceite a autorização na tela do celular.

## Gerar um executável (.exe)

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --name ConectaDroid main.py
```

O executável fica em `dist/ConectaDroid.exe`. O `config.json` é salvo ao lado dele.

## 📄 Licença
Este projeto é livre para uso e modificações pessoais.