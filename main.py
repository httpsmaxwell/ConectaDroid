import json
import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

try:
    from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
    TEM_ZEROCONF = True
except ImportError:
    TEM_ZEROCONF = False

# ----------------------------------------------------------------------------
# Configuração
# ----------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
PASTA_SCRCPY_PADRAO = r"C:\scrcpy"
PORTA_PADRAO = 5555
FLAGS_SEM_JANELA = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
REGEX_ALVO = re.compile(r"^(\d{1,3}(?:\.\d{1,3}){3})(?::(\d{1,5}))?$")

CONFIG_PADRAO = {
    "alvo": "",
    "scrcpy_dir": "",
    "always_on_top": True,
    "stay_awake": True,
    "tela_apagada": True,
    "fechar_ao_abrir": True,
}


def carregar_config():
    config = dict(CONFIG_PADRAO)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            dados = json.load(f)
        if isinstance(dados, dict):
            # Compatibilidade com a versão antiga, que guardava só {"ip": "..."}
            if "ip" in dados and "alvo" not in dados:
                dados["alvo"] = dados["ip"]
            config.update({k: v for k, v in dados.items() if k in CONFIG_PADRAO})
    except (OSError, ValueError):
        pass
    return config


def salvar_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def localizar_ferramenta(nome, pasta_extra=""):
    """Procura adb/scrcpy na pasta configurada, em C:\\scrcpy, ao lado do script e no PATH."""
    exe = nome + (".exe" if os.name == "nt" else "")
    pastas = [p for p in (pasta_extra, PASTA_SCRCPY_PADRAO, BASE_DIR) if p]
    for pasta in pastas:
        caminho = os.path.join(pasta, exe)
        if os.path.isfile(caminho):
            return caminho
    return shutil.which(nome)


def rodar_cmd(cmd, timeout=15):
    """Executa um comando e devolve (sucesso, saída). Nunca levanta exceção."""
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=FLAGS_SEM_JANELA,
        )
        saida = (r.stdout + "\n" + r.stderr).strip()
        return r.returncode == 0, saida
    except subprocess.TimeoutExpired:
        return False, "Tempo esgotado ao executar o comando."
    except (OSError, ValueError) as e:
        return False, str(e)


def normalizar_alvo(texto):
    """Aceita 'ip' ou 'ip:porta' e devolve 'ip:porta', ou None se for inválido."""
    m = REGEX_ALVO.match(texto.strip())
    if not m:
        return None
    ip, porta = m.group(1), m.group(2)
    if any(int(p) > 255 for p in ip.split(".")):
        return None
    porta = int(porta) if porta else PORTA_PADRAO
    if not 1 <= porta <= 65535:
        return None
    return f"{ip}:{porta}"


# ----------------------------------------------------------------------------
# Descoberta por mDNS (Depuração sem fio do Android 11+)
# ----------------------------------------------------------------------------
if TEM_ZEROCONF:
    class _OuvinteADB(ServiceListener):
        def __init__(self):
            self.encontrado = None
            self.evento = threading.Event()

        def add_service(self, zc, type_, name):
            info = zc.get_service_info(type_, name, timeout=2000)
            if not info:
                return
            ipv4 = [a for a in info.parsed_addresses() if ":" not in a]
            if ipv4:
                self.encontrado = f"{ipv4[0]}:{info.port}"
                self.evento.set()

        def update_service(self, zc, type_, name):
            self.add_service(zc, type_, name)

        def remove_service(self, zc, type_, name):
            pass


def buscar_alvo_na_rede(timeout=5.0):
    """Devolve 'ip:porta' do celular anunciado na rede, ou None."""
    if not TEM_ZEROCONF:
        return None
    zc = Zeroconf()
    try:
        ouvinte = _OuvinteADB()
        navegador = ServiceBrowser(zc, "_adb-tls-connect._tcp.local.", ouvinte)
        ouvinte.evento.wait(timeout)
        navegador.cancel()
        return ouvinte.encontrado
    finally:
        zc.close()


# ----------------------------------------------------------------------------
# Interface
# ----------------------------------------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        self.config = carregar_config()
        self.ocupado = False

        root.title("ConectaDroid")
        root.geometry("420x470")
        root.resizable(False, False)

        self.var_alvo = tk.StringVar(value=self.config["alvo"])
        self.var_status = tk.StringVar(value="Pronto.")
        self.var_top = tk.BooleanVar(value=self.config["always_on_top"])
        self.var_awake = tk.BooleanVar(value=self.config["stay_awake"])
        self.var_apagada = tk.BooleanVar(value=self.config["tela_apagada"])
        self.var_fechar = tk.BooleanVar(value=self.config["fechar_ao_abrir"])

        self._montar_interface()
        self.root.protocol("WM_DELETE_WINDOW", self._ao_fechar)

    # -- construção ----------------------------------------------------------
    def _montar_interface(self):
        r = self.root
        tk.Label(r, text="Endereço do celular (IP ou IP:porta):",
                 font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(14, 2))

        self.entry_alvo = tk.Entry(r, textvariable=self.var_alvo, font=("Arial", 10))
        self.entry_alvo.pack(fill="x", padx=20, pady=2)
        self.entry_alvo.bind("<Return>", lambda e: self.acao_conectar())

        self.btn_auto = tk.Button(
            r, text="🔍 Detectar automaticamente (Wi-Fi)", bg="#FF9800", fg="white",
            font=("Arial", 9, "bold"), command=self.acao_detectar)
        self.btn_auto.pack(fill="x", padx=20, pady=(8, 4))

        self.btn_conectar = tk.Button(
            r, text="⚡ CONECTAR E ESPELHAR", bg="#4CAF50", fg="white",
            font=("Arial", 10, "bold"), pady=6, command=self.acao_conectar)
        self.btn_conectar.pack(fill="x", padx=20, pady=4)

        self.btn_desconectar = tk.Button(
            r, text="⏏ Desconectar", font=("Arial", 9), command=self.acao_desconectar)
        self.btn_desconectar.pack(fill="x", padx=20, pady=4)

        opcoes = tk.LabelFrame(r, text="Opções do espelhamento", font=("Arial", 9))
        opcoes.pack(fill="x", padx=20, pady=8)
        for texto, var in (
            ("Manter janela sempre no topo", self.var_top),
            ("Manter o celular acordado", self.var_awake),
            ("Apagar a tela do celular durante o espelhamento", self.var_apagada),
            ("Fechar esta janela ao abrir o espelho", self.var_fechar),
        ):
            tk.Checkbutton(opcoes, text=texto, variable=var, anchor="w").pack(fill="x", padx=8)

        ttk.Separator(r).pack(fill="x", padx=20, pady=6)

        self.btn_usb = tk.Button(
            r, text="🔌 Primeira vez: configurar com cabo USB", bg="#2196F3", fg="white",
            font=("Arial", 9), command=self.acao_configurar_usb)
        self.btn_usb.pack(fill="x", padx=20, pady=3)

        self.btn_parear = tk.Button(
            r, text="🔗 Parear por código (Android 11+, sem cabo)", bg="#607D8B", fg="white",
            font=("Arial", 9), command=self.acao_parear)
        self.btn_parear.pack(fill="x", padx=20, pady=3)

        tk.Label(r, textvariable=self.var_status, anchor="w", fg="#555555",
                 wraplength=380, justify="left").pack(fill="x", padx=20, pady=(8, 0))

        self._botoes = [self.btn_auto, self.btn_conectar, self.btn_desconectar,
                        self.btn_usb, self.btn_parear]

    # -- utilidades de UI / threads -----------------------------------------
    def _status(self, texto):
        self.var_status.set(texto)

    def _bloquear(self, ocupado, texto=None):
        self.ocupado = ocupado
        estado = "disabled" if ocupado else "normal"
        for b in self._botoes:
            b.config(state=estado)
        if texto:
            self._status(texto)

    def _em_segundo_plano(self, tarefa, ao_terminar, texto_ocupado):
        """Roda `tarefa` numa thread e chama `ao_terminar(resultado)` na thread da UI."""
        if self.ocupado:
            return
        self._bloquear(True, texto_ocupado)

        def worker():
            try:
                resultado = tarefa()
            except Exception as e:  # noqa: BLE001 - mostramos o erro ao usuário
                resultado = e
            self.root.after(0, lambda: self._finalizar(ao_terminar, resultado))

        threading.Thread(target=worker, daemon=True).start()

    def _finalizar(self, ao_terminar, resultado):
        self._bloquear(False)
        if isinstance(resultado, Exception):
            self._status("Ocorreu um erro.")
            messagebox.showerror("Erro inesperado", str(resultado))
            return
        ao_terminar(resultado)

    def _salvar(self):
        self.config.update({
            "alvo": self.var_alvo.get().strip(),
            "always_on_top": self.var_top.get(),
            "stay_awake": self.var_awake.get(),
            "tela_apagada": self.var_apagada.get(),
            "fechar_ao_abrir": self.var_fechar.get(),
        })
        salvar_config(self.config)

    def _ao_fechar(self):
        self._salvar()
        self.root.destroy()

    def _ferramentas(self):
        """Devolve (adb, scrcpy) ou mostra erro e devolve None."""
        pasta = self.config.get("scrcpy_dir", "")
        adb = localizar_ferramenta("adb", pasta)
        scrcpy = localizar_ferramenta("scrcpy", pasta)
        faltando = [n for n, c in (("adb", adb), ("scrcpy", scrcpy)) if not c]
        if faltando:
            messagebox.showerror(
                "Ferramentas não encontradas",
                f"Não encontrei: {', '.join(faltando)}.\n\n"
                f"Coloque-os em {PASTA_SCRCPY_PADRAO}, ao lado deste programa, "
                "ou adicione a pasta ao PATH do Windows.")
            return None
        return adb, scrcpy

    # -- ações ---------------------------------------------------------------
    def acao_detectar(self):
        if not TEM_ZEROCONF:
            messagebox.showwarning(
                "Biblioteca ausente",
                "A detecção automática precisa do pacote 'zeroconf'.\n\n"
                "Instale com:  pip install zeroconf")
            return

        def terminou(alvo):
            if alvo:
                self.var_alvo.set(alvo)
                self._salvar()
                self._status(f"Celular encontrado: {alvo}")
            else:
                self._status("Nenhum celular encontrado.")
                messagebox.showwarning(
                    "Não encontrado",
                    "Não foi possível detectar o celular.\n\n"
                    "Confira se a Depuração sem fio está ativa e se o celular "
                    "está na mesma rede Wi-Fi, ou digite o IP manualmente.")

        self._em_segundo_plano(buscar_alvo_na_rede, terminou, "Procurando na rede...")

    def acao_configurar_usb(self):
        ferramentas = self._ferramentas()
        if not ferramentas:
            return
        adb, _ = ferramentas

        def tarefa():
            ok, saida = rodar_cmd([adb, "devices"])
            usb = [
                linha.split("\t")[0]
                for linha in saida.splitlines()
                if linha.endswith("\tdevice") and ":" not in linha.split("\t")[0]
            ]
            if not usb:
                return ("sem_usb", None)
            serial = usb[0]
            # Descobre o IP antes de reiniciar o adbd em modo TCP
            ip = self._ip_via_usb(adb, serial)
            rodar_cmd([adb, "-s", serial, "tcpip", str(PORTA_PADRAO)])
            return ("ok", ip)

        def terminou(res):
            tipo, ip = res
            if tipo == "sem_usb":
                self._status("Nenhum celular via USB.")
                messagebox.showerror(
                    "Celular não detectado via USB",
                    "1. Conecte o cabo USB.\n"
                    "2. Ative a 'Depuração USB' no celular.\n"
                    "3. Aceite a autorização exibida na tela do celular.")
            elif ip:
                self.var_alvo.set(f"{ip}:{PORTA_PADRAO}")
                self._salvar()
                self._status(f"Configurado: {ip}:{PORTA_PADRAO}")
                messagebox.showinfo(
                    "Configurado com sucesso!",
                    f"IP: {ip}\nPorta: {PORTA_PADRAO}\n\n"
                    "Já pode desconectar o cabo e clicar em 'Conectar e espelhar'.")
            else:
                self._status("Porta ativada, mas o IP não foi detectado.")
                messagebox.showwarning(
                    "Porta ativada",
                    "A porta sem fio foi ativada, mas não consegui descobrir o IP.\n"
                    "Use 'Detectar automaticamente' ou digite o IP manualmente.")

        self._em_segundo_plano(tarefa, terminou, "Configurando via USB...")

    @staticmethod
    def _ip_via_usb(adb, serial):
        ok, out = rodar_cmd([adb, "-s", serial, "shell", "ip", "route"])
        m = re.search(r"wlan\d.*?src (\d+\.\d+\.\d+\.\d+)", out) or \
            re.search(r"src (\d+\.\d+\.\d+\.\d+)", out)
        if m:
            return m.group(1)
        ok, out = rodar_cmd([adb, "-s", serial, "shell", "ip", "addr", "show", "wlan0"])
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out)
        return m.group(1) if m else ""

    def acao_conectar(self):
        alvo = normalizar_alvo(self.var_alvo.get())
        if not alvo:
            messagebox.showwarning(
                "Endereço inválido",
                "Digite um IP válido (ex.: 192.168.0.15 ou 192.168.0.15:5555) "
                "ou use a detecção automática.")
            return
        ferramentas = self._ferramentas()
        if not ferramentas:
            return
        adb, scrcpy = ferramentas

        self.var_alvo.set(alvo)
        self._salvar()

        def tarefa():
            ok, saida = rodar_cmd([adb, "connect", alvo], timeout=15)
            baixo = saida.lower()
            conectado = bool(re.search(r"connected to", baixo)) and \
                "cannot" not in baixo and "failed" not in baixo
            return conectado, saida

        def terminou(res):
            conectado, saida = res
            if not conectado:
                self._status("Falha ao conectar.")
                messagebox.showerror(
                    "Erro ao conectar via ADB",
                    f"Resposta do ADB:\n{saida}\n\n"
                    "Verifique se:\n"
                    "1. O celular e o PC estão na mesma rede Wi-Fi.\n"
                    "2. A configuração inicial (USB ou pareamento) já foi feita.\n"
                    "3. Para depuração sem fio do Android 11+, a porta mudou: "
                    "use a detecção automática.")
                return
            self._abrir_scrcpy(adb, scrcpy, alvo)

        self._em_segundo_plano(tarefa, terminou, f"Conectando a {alvo}...")

    def _abrir_scrcpy(self, adb, scrcpy, alvo):
        cmd = [scrcpy, "-s", alvo]  # -s mira exatamente este aparelho
        if self.var_top.get():
            cmd.append("--always-on-top")
        if self.var_awake.get():
            cmd.append("--stay-awake")
        if self.var_apagada.get():
            cmd.append("--turn-screen-off")
        env = dict(os.environ, ADB=adb)  # usa o mesmo servidor ADB
        try:
            subprocess.Popen(cmd, env=env, creationflags=FLAGS_SEM_JANELA)
        except OSError as e:
            self._status("Falha ao abrir o scrcpy.")
            messagebox.showerror("Erro ao iniciar o scrcpy", f"Falha ao abrir:\n{e}")
            return
        self._status(f"Espelhando {alvo}.")
        if self.var_fechar.get():
            self._salvar()
            self.root.destroy()

    def acao_desconectar(self):
        ferramentas = self._ferramentas()
        if not ferramentas:
            return
        adb, _ = ferramentas
        alvo = normalizar_alvo(self.var_alvo.get())
        cmd = [adb, "disconnect"] + ([alvo] if alvo else [])

        def terminou(res):
            self._status(res[1] or "Desconectado.")

        self._em_segundo_plano(lambda: rodar_cmd(cmd), terminou, "Desconectando...")

    def acao_parear(self):
        ferramentas = self._ferramentas()
        if not ferramentas:
            return
        adb, _ = ferramentas

        janela = tk.Toplevel(self.root)
        janela.title("Parear por código")
        janela.resizable(False, False)
        janela.transient(self.root)
        janela.grab_set()

        tk.Label(
            janela, justify="left",
            text="No celular: Opções do desenvolvedor > Depuração sem fio >\n"
                 "'Parear dispositivo com código de pareamento'."
        ).pack(padx=16, pady=(14, 8))

        tk.Label(janela, text="IP:porta de pareamento:").pack(anchor="w", padx=16)
        e_host = tk.Entry(janela, width=30)
        e_host.pack(padx=16, pady=(0, 6))
        tk.Label(janela, text="Código de 6 dígitos:").pack(anchor="w", padx=16)
        e_codigo = tk.Entry(janela, width=30)
        e_codigo.pack(padx=16, pady=(0, 10))
        e_host.focus_set()

        def confirmar():
            host = e_host.get().strip()
            codigo = e_codigo.get().strip()
            if not REGEX_ALVO.match(host) or ":" not in host or not codigo.isdigit():
                messagebox.showwarning(
                    "Dados inválidos",
                    "Informe o IP:porta exibido no celular e o código numérico.",
                    parent=janela)
                return
            janela.destroy()

            def terminou(res):
                ok, saida = res
                if ok and "successfully" in saida.lower():
                    self._status("Pareado com sucesso! Agora use 'Detectar automaticamente'.")
                    messagebox.showinfo(
                        "Pareado",
                        "Pareamento concluído.\n\nClique em 'Detectar automaticamente' "
                        "para obter o endereço de conexão.")
                else:
                    self._status("Falha no pareamento.")
                    messagebox.showerror("Falha no pareamento", saida)

            self._em_segundo_plano(
                lambda: rodar_cmd([adb, "pair", host, codigo], timeout=20),
                terminou, "Pareando...")

        tk.Button(janela, text="Parear", bg="#4CAF50", fg="white",
                  command=confirmar).pack(fill="x", padx=16, pady=(0, 14))
        janela.bind("<Return>", lambda e: confirmar())


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
